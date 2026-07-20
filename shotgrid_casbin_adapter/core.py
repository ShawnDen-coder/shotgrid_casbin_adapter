"""Core module for the ShotGrid Casbin Adapter.

This module implements the Casbin policy adapter that enables loading and saving
access control policies from/to Autodesk ShotGrid (formerly Shotgun). The adapter
implements ``casbin.persist.Adapter`` and ``casbin.persist.adapters.UpdateAdapter``
interfaces, mapping ShotGrid custom entities to Casbin policy rules.

Typical usage example:

    from shotgrid_casbin_adapter.core import Adapter

    adapter = Adapter(
        base_url="https://example.shotgridstudio.com",
        script_name="my_script",
        api_key="abc123",
        project_id=42,
    )
    e = casbin.Enforcer("model.conf", adapter)

Attributes:
    Adapter: The main adapter class for Casbin policy storage via ShotGrid.
"""

import os
from typing import Any

from casbin import persist
from casbin.model import Model
from shotgun_api3.shotgun import Shotgun

from shotgrid_casbin_adapter.constants import CASBIN_FIELDS
from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_PROJECT_ID
from shotgrid_casbin_adapter.filter import Filter
from shotgrid_casbin_adapter.filter import _build_sg_filters
from shotgrid_casbin_adapter.helpers import _FIELDS_WITH_ID
from shotgrid_casbin_adapter.helpers import _batch_delete
from shotgrid_casbin_adapter.helpers import _build_create_request
from shotgrid_casbin_adapter.helpers import _build_rule_filters
from shotgrid_casbin_adapter.helpers import _connect_sg
from shotgrid_casbin_adapter.helpers import _entity_to_str
from shotgrid_casbin_adapter.helpers import _project_filter
from shotgrid_casbin_adapter.helpers import _rule_to_dict


class Adapter(persist.Adapter, persist.adapters.UpdateAdapter):  # type: ignore[override]
    """Casbin policy adapter backed by Autodesk ShotGrid.

    This adapter maps Casbin policy rules to ShotGrid custom entity records.
    Each record contains ``ptype`` and ``v0``-``v5`` fields representing one
    policy line.

    When ``project_id`` is provided, all operations are scoped to that project:
    queries include a project filter, and created entities are linked to the
    project. This enables per-project policy isolation within a single ShotGrid
    site. When ``project_id`` is ``None``, the adapter operates at site level.

    ShotGrid's ``delete()`` operation retires entities rather than destroying
    them, and ``find()`` excludes retired records by default. This provides
    natural soft-delete behavior without additional configuration.

    Args:
        sg: An existing ``shotgun_api3.Shotgun`` instance. If provided,
            ``base_url``, ``script_name``, and ``api_key`` are ignored.
        base_url: ShotGrid server URL. Falls back to ``SHOTGRID_URL`` env var.
        script_name: ShotGrid script name. Falls back to ``SHOTGRID_SCRIPT_NAME`` env var.
        api_key: ShotGrid API key. Falls back to ``SHOTGRID_API_KEY`` env var.
        entity_type: ShotGrid entity type for storing rules.
            Falls back to ``SHOTGRID_ENTITY_TYPE`` env var, then ``DEFAULT_ENTITY_TYPE``.
        project_id: ShotGrid project ID for scoping operations.
            Falls back to ``SHOTGRID_PROJECT_ID`` env var. When ``None``,
            operations are site-wide.
        filtered: Whether this adapter supports filtered policy loading.

    Raises:
        ValueError: If neither ``sg`` nor sufficient connection parameters are provided.
    """

    def __init__(
        self,
        sg: Shotgun | None = None,
        base_url: str | None = None,
        script_name: str | None = None,
        api_key: str | None = None,
        entity_type: str | None = None,
        project_id: int | None = None,
        filtered: bool = False,
    ) -> None:
        """Initialize the ShotGrid Casbin adapter.

        Args:
            sg: An existing ``shotgun_api3.Shotgun`` instance. If provided,
                ``base_url``, ``script_name``, and ``api_key`` are ignored.
            base_url: ShotGrid server URL. Falls back to ``SHOTGRID_URL`` env var.
            script_name: ShotGrid script name. Falls back to ``SHOTGRID_SCRIPT_NAME`` env var.
            api_key: ShotGrid API key. Falls back to ``SHOTGRID_API_KEY`` env var.
            entity_type: ShotGrid entity type for storing rules.
                Falls back to ``SHOTGRID_ENTITY_TYPE`` env var, then ``DEFAULT_ENTITY_TYPE``.
            project_id: ShotGrid project ID for scoping operations.
                Falls back to ``SHOTGRID_PROJECT_ID`` env var. When ``None``,
                operations are site-wide.
            filtered: Whether this adapter supports filtered policy loading.
        """
        self._entity_type: str = entity_type or os.environ.get(SHOTGRID_ENTITY_TYPE) or DEFAULT_ENTITY_TYPE
        self._project_id: int | None = (
            project_id if project_id is not None else (int(v) if (v := os.environ.get(SHOTGRID_PROJECT_ID)) else None)
        )
        self._filtered: bool = filtered
        self._sg: Shotgun = sg or _connect_sg(base_url=base_url, script_name=script_name, api_key=api_key)

    @property
    def sg(self) -> Shotgun:
        """The underlying ``shotgun_api3.Shotgun`` connection instance."""
        return self._sg

    @property
    def entity_type(self) -> str:
        """The ShotGrid entity type used for storing Casbin rules."""
        return self._entity_type

    @property
    def project_id(self) -> int | None:
        """The ShotGrid project ID for scoping operations, or ``None`` for site-wide."""
        return self._project_id

    # --- Adapter interface ---

    def load_policy(self, model: Model) -> None:
        """Load all policy rules from ShotGrid into the Casbin model.

        Queries all non-retired entities of the configured type (optionally
        scoped to the configured project) and feeds each one into
        :func:`casbin.persist.load_policy_line`.

        Args:
            model: The Casbin model to populate with policy rules.
        """
        for entity in self._sg.find(self._entity_type, _project_filter(self._project_id), _FIELDS_WITH_ID):
            persist.load_policy_line(_entity_to_str(entity), model)

    def is_filtered(self) -> bool:
        """Check whether the adapter is in filtered mode.

        Returns:
            ``True`` if a filtered policy has been loaded, ``False`` otherwise.
        """
        return self._filtered

    def load_filtered_policy(self, model: Model, filter: Filter) -> None:
        """Load policy rules matching the filter from ShotGrid.

        After loading, the adapter is marked as filtered (``is_filtered()``
        returns ``True``).

        Args:
            model: The Casbin model to populate with matching policy rules.
            filter: A :class:`Filter` instance specifying field value constraints.
        """
        sg_filters = _project_filter(self._project_id) + _build_sg_filters(filter)
        for entity in self._sg.find(self._entity_type, sg_filters, _FIELDS_WITH_ID):
            persist.load_policy_line(_entity_to_str(entity), model)
        self._filtered = True

    def save_policy(self, model: Model) -> bool:
        """Save all policy rules from the Casbin model to ShotGrid.

        Replaces all existing rules with the current model state. First
        deletes all existing entities (optionally scoped to the configured
        project), then creates new ones for every rule in the model's
        ``"p"`` and ``"g"`` sections.

        Args:
            model: The Casbin model whose rules to persist.

        Returns:
            ``True`` on success.
        """
        existing = self._sg.find(self._entity_type, _project_filter(self._project_id), ["id"])
        _batch_delete(self._sg, self._entity_type, existing)

        create_requests: list[dict[str, Any]] = []
        for sec in ["p", "g"]:
            if sec not in model.model:
                continue
            for ptype, ast in model.model[sec].items():
                for rule in ast.policy:
                    create_requests.append(_build_create_request(self._entity_type, ptype, rule, self._project_id))
        if create_requests:
            self._sg.batch(create_requests)
        return True

    def add_policy(self, sec: str, ptype: str, rule: list[str]) -> None:
        """Add a policy rule to ShotGrid.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            rule: The policy rule values.
        """
        self._sg.create(self._entity_type, _rule_to_dict(ptype, rule, self._project_id))

    def add_policies(self, sec: str, ptype: str, rules: list[list[str]]) -> None:
        """Add multiple policy rules to ShotGrid via batch operation.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            rules: A list of policy rule value lists.
        """
        if not rules:
            return
        self._sg.batch([_build_create_request(self._entity_type, ptype, r, self._project_id) for r in rules])

    def remove_policy(self, sec: str, ptype: str, rule: list[str]) -> bool:
        """Remove a policy rule from ShotGrid.

        ShotGrid's delete retires the entity (soft-delete). ``find()
        excludes retired records by default.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            rule: The policy rule values to remove.

        Returns:
            ``True`` if at least one matching rule was removed, ``False`` otherwise.
        """
        entities = self._sg.find(self._entity_type, _build_rule_filters(ptype, rule, self._project_id), ["id"])
        if not entities:
            return False
        for entity in entities:
            self._sg.delete(self._entity_type, entity["id"])  # type: ignore[typeddict-item]
        return True

    def remove_policies(self, sec: str, ptype: str, rules: list[list[str]]) -> None:
        """Remove multiple policy rules from ShotGrid via batch operation.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            rules: A list of policy rule value lists to remove.
        """
        if not rules:
            return
        all_ids: set[int] = set()
        for rule in rules:
            for e in self._sg.find(self._entity_type, _build_rule_filters(ptype, rule, self._project_id), ["id"]):
                all_ids.add(e["id"])  # type: ignore[typeddict-item]
        if all_ids:
            _batch_delete(self._sg, self._entity_type, [{"id": eid} for eid in all_ids])

    def remove_filtered_policy(self, sec: str, ptype: str, field_index: int, *field_values: str) -> bool:
        """Remove policy rules matching a field filter from ShotGrid.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            field_index: The starting field index (0-5) for filtering.
            *field_values: The field values to match starting at ``field_index``.

        Returns:
            ``True`` if at least one rule was removed, ``False`` otherwise.
        """
        if not (0 <= field_index <= 5) or not (1 <= field_index + len(field_values) <= 6):
            return False

        sg_filters: list[list[Any]] = [*_project_filter(self._project_id), [CASBIN_FIELDS[0], "is", ptype]]
        for i, v in enumerate(field_values):
            if v != "":
                sg_filters.append([CASBIN_FIELDS[field_index + i + 1], "is", v])

        entities = self._sg.find(self._entity_type, sg_filters, ["id"])
        if not entities:
            return False
        _batch_delete(self._sg, self._entity_type, entities)
        return True

    # --- UpdateAdapter interface ---

    def update_policy(self, sec: str, ptype: str, old_rule: list[str], new_policy: list[str]) -> None:
        """Update a policy rule in ShotGrid.

        Finds the first entity matching ``old_rule`` and updates its fields
        to ``new_policy``. If the new policy is shorter than the old rule,
        excess fields are set to ``None``.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            old_rule: The current policy rule values.
            new_policy: The replacement policy rule values.
        """
        entities = self._sg.find(self._entity_type, _build_rule_filters(ptype, old_rule, self._project_id), ["id"])
        if not entities:
            return

        data = _rule_to_dict(ptype, new_policy)
        for i in range(len(new_policy), max(len(old_rule), len(new_policy))):
            data[CASBIN_FIELDS[i + 1]] = None
        self._sg.update(self._entity_type, entities[0]["id"], data)  # type: ignore[typeddict-item]

    def update_policies(self, sec: str, ptype: str, old_rules: list[list[str]], new_rules: list[list[str]]) -> None:
        """Update multiple policy rules in ShotGrid.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            old_rules: The current policy rule value lists.
            new_rules: The replacement policy rule value lists.
        """
        for i in range(len(old_rules)):
            self.update_policy(sec, ptype, old_rules[i], new_rules[i])

    def update_filtered_policies(
        self,
        sec: str,
        ptype: str,
        new_rules: list[list[str]],
        field_index: int,
        *field_values: str,
    ) -> list[list[str]]:
        """Update all policies matching a filter with new rules.

        Deletes all entities matching the filter, then creates new entities
        for each rule in ``new_rules``.

        Args:
            sec: The policy section (``"p"`` or ``"g"``).
            ptype: The policy type identifier.
            new_rules: The replacement policy rule value lists.
            field_index: The starting field index (0-5) for filtering.
            *field_values: The field values to match starting at ``field_index``.

        Returns:
            A list of the old rule value lists that were replaced.
        """
        filter_obj = Filter()
        filter_obj.ptype = [ptype]
        for i in range(len(field_values)):
            if field_index <= i < field_index + len(field_values):
                setattr(filter_obj, f"v{i}", [field_values[i - field_index]])
            else:
                break
        return self._update_filtered_policies(ptype, new_rules, filter_obj)

    def _update_filtered_policies(
        self,
        ptype: str,
        new_rules: list[list[str]],
        filter_obj: Filter,
    ) -> list[list[str]]:
        """Replace filtered policies with new rules.

        Args:
            ptype: The policy type identifier.
            new_rules: The replacement policy rule value lists.
            filter_obj: A :class:`Filter` instance specifying which rules to replace.

        Returns:
            A list of the old rule value lists that were replaced.
        """
        sg_filters = _project_filter(self._project_id) + _build_sg_filters(filter_obj)
        old_entities = self._sg.find(self._entity_type, sg_filters, _FIELDS_WITH_ID)

        old_rules: list[list[str]] = []
        for entity in old_entities:
            rule = [entity[f] for f in CASBIN_FIELDS[1:] if entity.get(f) is not None]
            old_rules.append(rule)

        _batch_delete(self._sg, self._entity_type, old_entities)
        self.add_policies("p", filter_obj.ptype[0] if filter_obj.ptype else ptype, new_rules)
        return old_rules
