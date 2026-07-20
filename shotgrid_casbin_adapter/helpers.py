"""Helper functions for the ShotGrid Casbin Adapter.

This module provides utility functions for converting between Casbin policy
rules and ShotGrid entity data, building ShotGrid API filter expressions,
performing batch operations, and establishing ShotGrid connections.

These functions are used internally by :class:`~shotgrid_casbin_adapter.core.Adapter`
and are not intended for direct external use.

Functions:
    _rule_to_dict: Convert a Casbin policy rule to a ShotGrid entity dict.
    _entity_to_str: Convert a ShotGrid entity dict to a Casbin policy line.
    _build_rule_filters: Build ShotGrid filters for a specific policy rule.
    _batch_delete: Batch-delete ShotGrid entities.
    _build_create_request: Build a batch create request for a single rule.
    _connect_sg: Create a ShotGrid connection from parameters or env vars.
    _project_filter: Build ShotGrid project scope filter.
    _project_data: Build ShotGrid project scope entity data.
"""

import os
from typing import Any

from shotgun_api3.shotgun import Shotgun

from shotgrid_casbin_adapter.constants import CASBIN_FIELDS
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL


_FIELDS_WITH_ID: list[str] = ["id", *CASBIN_FIELDS]


def _project_filter(project_id: int | None) -> list[list[Any]]:
    """Build ShotGrid filter for project scoping.

    Args:
        project_id: ShotGrid project ID. When ``None``, returns an empty
            list (no project filter applied).

    Returns:
        A list containing a single project filter expression, or an empty
        list if ``project_id`` is ``None``.
    """
    if project_id is None:
        return []
    return [["project", "is", {"type": "Project", "id": project_id}]]


def _project_data(project_id: int | None) -> dict[str, Any]:
    """Build ShotGrid entity data for project association.

    Args:
        project_id: ShotGrid project ID. When ``None``, returns an empty
            dict (no project association).

    Returns:
        A dict with a ``"project"`` key for entity creation, or an empty
        dict if ``project_id`` is ``None``.
    """
    if project_id is None:
        return {}
    return {"project": {"type": "Project", "id": project_id}}


def _rule_to_dict(ptype: str, rule: list[str], project_id: int | None = None) -> dict[str, Any]:
    """Convert a Casbin policy rule to a ShotGrid entity data dict.

    Maps the policy type and rule values to the corresponding ShotGrid
    fields (``ptype``, ``v0``-``v5``). Rule values that exceed the 6-value
    limit are silently truncated.

    Args:
        ptype: The Casbin policy type (e.g. ``"p"`` or ``"g"``).
        rule: The policy rule values (e.g. ``["alice", "data1", "read"]``).
        project_id: Optional ShotGrid project ID to associate the entity with.

    Returns:
        A dict mapping ShotGrid field names to their values, e.g.
        ``{"ptype": "p", "v0": "alice", "v1": "data1", "v2": "read"}``.
        Includes ``"project"`` key when ``project_id`` is provided.
    """
    return {"ptype": ptype} | {f"v{i}": v for i, v in enumerate(rule)} | _project_data(project_id)


def _entity_to_str(entity: Any) -> str:
    """Convert a ShotGrid entity dict to a Casbin policy line string.

    Builds a comma-separated string from the entity's ``ptype`` and
    non-None ``v0``-``v5`` values. Trailing ``None`` values are omitted.

    Args:
        entity: A ShotGrid entity (``BaseEntity`` or dict) with keys
            ``"ptype"``, ``"v0"``, ..., ``"v5"``. ``None`` values indicate
            unused slots.

    Returns:
        A Casbin policy line string, e.g. ``"p, alice, data1, read"``.
    """
    arr: list[str] = [entity.get("ptype", "")]
    for field in CASBIN_FIELDS[1:]:
        v = entity.get(field)
        if v is None:
            break
        arr.append(v)
    return ", ".join(arr)


def _build_rule_filters(ptype: str, rule: list[str], project_id: int | None = None) -> list[list[Any]]:
    """Build ShotGrid filters to locate a specific policy rule.

    Creates filter expressions that match on ``ptype`` and all provided
    rule values using ShotGrid's ``"is"`` operator. When ``project_id``
    is provided, a project scope filter is prepended.

    Args:
        ptype: The Casbin policy type to match.
        rule: The policy rule values to match.
        project_id: Optional ShotGrid project ID to scope the query.

    Returns:
        A list of ShotGrid filter expressions, e.g.
        ``[["project", "is", {...}], ["ptype", "is", "p"], ["v0", "is", "alice"]]``.
    """
    return _project_filter(project_id) + [["ptype", "is", ptype]] + [[f"v{i}", "is", v] for i, v in enumerate(rule)]


def _batch_delete(sg: Shotgun, entity_type: str, entities: list[Any]) -> None:
    """Batch-delete entities in ShotGrid.

    Uses ShotGrid's ``batch()`` API to retire multiple entities in a single
    request. If the entity list is empty, this is a no-op.

    Args:
        sg: A ``shotgun_api3.Shotgun`` connection instance.
        entity_type: The ShotGrid entity type (e.g. ``"CustomEntity01"``).
        entities: List of ShotGrid entities (``BaseEntity`` or dict), each
            containing an ``"id"`` key.
    """
    if not entities:
        return
    sg.batch([{"request_type": "delete", "entity_type": entity_type, "entity_id": e["id"]} for e in entities])


def _build_create_request(
    entity_type: str,
    ptype: str,
    rule: list[str],
    project_id: int | None = None,
) -> dict[str, Any]:
    """Build a ShotGrid batch create request for a single rule.

    Args:
        entity_type: The ShotGrid entity type (e.g. ``"CustomEntity01"``).
        ptype: The Casbin policy type.
        rule: The policy rule values.
        project_id: Optional ShotGrid project ID to associate the entity with.

    Returns:
        A ShotGrid batch request dict with ``"request_type"``,
        ``"entity_type"``, and ``"data"`` keys.
    """
    return {"request_type": "create", "entity_type": entity_type, "data": _rule_to_dict(ptype, rule, project_id)}


def _connect_sg(
    base_url: str | None = None,
    script_name: str | None = None,
    api_key: str | None = None,
) -> Shotgun:
    """Create a ShotGrid connection from parameters or environment variables.

    Each parameter falls back to its corresponding environment variable
    (``SHOTGRID_URL``, ``SHOTGRID_SCRIPT_NAME``, ``SHOTGRID_API_KEY``) if
    not provided directly.

    Args:
        base_url: ShotGrid server URL. Falls back to ``SHOTGRID_URL`` env var.
        script_name: Script name. Falls back to ``SHOTGRID_SCRIPT_NAME`` env var.
        api_key: API key. Falls back to ``SHOTGRID_API_KEY`` env var.

    Returns:
        A connected ``shotgun_api3.Shotgun`` instance.

    Raises:
        ValueError: If any required connection parameter is missing both
            as an argument and as an environment variable.
    """
    url = base_url or os.environ.get(SHOTGRID_URL)
    name = script_name or os.environ.get(SHOTGRID_SCRIPT_NAME)
    key = api_key or os.environ.get(SHOTGRID_API_KEY)

    missing = {
        SHOTGRID_URL: url,
        SHOTGRID_SCRIPT_NAME: name,
        SHOTGRID_API_KEY: key,
    }
    for env_key, value in missing.items():
        if not value:
            msg = f"ShotGrid connection parameter missing. Set {env_key} env var or pass it directly."
            raise ValueError(msg)

    return Shotgun(url, script_name=name, api_key=key)
