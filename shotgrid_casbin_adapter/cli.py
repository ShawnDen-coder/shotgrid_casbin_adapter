"""Command Line Interface (CLI) module for defining application commands.

This module contains all CLI command definitions and entry points using Click.
The primary command is ``init``, which creates the Casbin fields (ptype, v0-v5)
on a ShotGrid custom entity type and optionally seeds a default admin policy.
The entity type itself must already be enabled in ShotGrid
(via Site Preferences > Entities) before running ``init``.

Typical usage example:

    from shotgrid_casbin_adapter.cli import cli

    if __name__ == '__main__':
        cli()

Attributes:
    cli: The main Click command group that serves as the entry point.
"""

import os
from typing import Any

import click
from shotgun_api3.shotgun import Fault
from shotgun_api3.shotgun import Shotgun

from shotgrid_casbin_adapter.constants import CASBIN_CREATE_FIELDS
from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_PROJECT_ID
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL
from shotgrid_casbin_adapter.helpers import _rule_to_dict


def _get_sg(
    base_url: str | None,
    script_name: str | None,
    api_key: str | None,
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
        A ``shotgun_api3.Shotgun`` instance.

    Raises:
        click.BadParameter: If required connection parameters are missing.
    """
    url = base_url or os.environ.get(SHOTGRID_URL)
    name = script_name or os.environ.get(SHOTGRID_SCRIPT_NAME)
    key = api_key or os.environ.get(SHOTGRID_API_KEY)

    if not url:
        msg = f"ShotGrid base URL is required. Use --base-url or set {SHOTGRID_URL} env var."
        raise click.BadParameter(msg)
    if not name:
        msg = f"ShotGrid script name is required. Use --script-name or set {SHOTGRID_SCRIPT_NAME} env var."
        raise click.BadParameter(msg)
    if not key:
        msg = f"ShotGrid API key is required. Use --api-key or set {SHOTGRID_API_KEY} env var."
        raise click.BadParameter(msg)

    return Shotgun(url, script_name=name, api_key=key)


@click.group()
def cli() -> None:
    """ShotGrid Casbin Adapter CLI."""


@cli.command()
@click.option(
    "--base-url",
    default=None,
    help=f"ShotGrid server URL (env: {SHOTGRID_URL}).",
)
@click.option(
    "--script-name",
    default=None,
    help=f"ShotGrid script name (env: {SHOTGRID_SCRIPT_NAME}).",
)
@click.option(
    "--api-key",
    default=None,
    help=f"ShotGrid API key (env: {SHOTGRID_API_KEY}).",
)
@click.option(
    "--entity-type",
    default=None,
    help=f"Custom entity type name (env: {SHOTGRID_ENTITY_TYPE}, default: {DEFAULT_ENTITY_TYPE}).",
)
@click.option(
    "--project-id",
    default=None,
    type=int,
    help=f"ShotGrid project ID for seeding the admin policy (env: {SHOTGRID_PROJECT_ID}).",
)
def init(
    base_url: str | None,
    script_name: str | None,
    api_key: str | None,
    entity_type: str | None,
    project_id: int | None,
) -> None:
    """Create Casbin fields on a ShotGrid custom entity type.

    Creates the required fields (ptype, v0-v5) on the specified ShotGrid
    custom entity type, then seeds a default admin policy rule
    (``p, admin, *, *``) so the adapter is ready to use immediately.

    The entity type must already be enabled in ShotGrid
    (Site Preferences > Entities); this command only creates the fields
    and the seed policy.

    Connection parameters can be provided via CLI options or environment
    variables.

    Args:
        base_url: ShotGrid server URL. Falls back to ``SHOTGRID_URL`` env var.
        script_name: ShotGrid script name. Falls back to ``SHOTGRID_SCRIPT_NAME`` env var.
        api_key: ShotGrid API key. Falls back to ``SHOTGRID_API_KEY`` env var.
        entity_type: Custom entity type name. Falls back to ``SHOTGRID_ENTITY_TYPE``
            env var, then ``DEFAULT_ENTITY_TYPE``.
        project_id: ShotGrid project ID for scoping the seed admin policy.
            Falls back to ``SHOTGRID_PROJECT_ID`` env var.
    """
    entity_type = entity_type or os.environ.get(SHOTGRID_ENTITY_TYPE) or DEFAULT_ENTITY_TYPE
    project_id = project_id or (int(v) if (v := os.environ.get(SHOTGRID_PROJECT_ID)) else None)
    sg = _get_sg(base_url, script_name, api_key)

    # Validate that the entity type exists in ShotGrid
    try:
        existing_fields: dict[str, Any] = sg.schema_field_read(entity_type)
    except Fault as exc:
        msg = (
            f"Entity type '{entity_type}' does not exist in ShotGrid.\n"
            f"Use --entity-type to specify a valid custom entity type (e.g. CustomEntity01).\n"
            f"Entity types must be enabled in Site Preferences > Entities first."
        )
        raise click.UsageError(msg) from exc

    click.echo(f"Initializing entity type '{entity_type}' in ShotGrid...")

    existing_field_names: set[str] = set(existing_fields.keys())

    # Create missing Casbin fields.
    # schema_field_read returns names with sg_ prefix (e.g. sg_ptype).
    # schema_field_create takes the base name without prefix (e.g. ptype).
    # "code" is a built-in field on custom entities — no need to create it.
    # It is used for v0 (subject) and is renamed to "Subject" for clarity.
    display_names: dict[str, str] = {
        "ptype": "Policy Type",
        "v1": "V1",
        "v2": "V2",
        "v3": "V3",
        "v4": "V4",
        "v5": "V5",
    }
    # Map base name → API field name (with sg_ prefix) for existence check
    sg_field_map: dict[str, str] = {
        "ptype": "sg_ptype",
        "v1": "sg_v1",
        "v2": "sg_v2",
        "v3": "sg_v3",
        "v4": "sg_v4",
        "v5": "sg_v5",
    }

    created: list[str] = []
    skipped: list[str] = []
    for base_name in CASBIN_CREATE_FIELDS:
        sg_field = sg_field_map[base_name]
        if sg_field in existing_field_names:
            skipped.append(base_name)
            click.echo(f"  Field '{base_name}' already exists, skipping.")
        else:
            sg.schema_field_create(entity_type, "text", display_names[base_name], properties={"name": base_name})
            created.append(base_name)
            click.echo(f"  Created field '{base_name}' (text).")

    # Rename the built-in "code" field to "Subject" for clarity
    if "code" in existing_fields:
        code_props = existing_fields["code"]
        current_name = code_props.get("name", {}).get("value", "") if isinstance(code_props, dict) else ""
        if current_name != "Subject":
            try:
                sg.schema_field_update(entity_type, "code", {"name": "Subject"})
                click.echo("  Renamed 'code' field to 'Subject'.")
            except Exception:
                click.echo("  Could not rename 'code' field (may lack permission).")
    else:
        click.echo("  Built-in 'code' field not found (expected on custom entities).")

    click.echo(f"\nCreated {len(created)} field(s), skipped {len(skipped)} existing field(s).")

    # Seed default admin policy: p, admin, *, * (skip if already exists)
    from shotgrid_casbin_adapter.helpers import _build_rule_filters

    existing_admin = sg.find_one(entity_type, _build_rule_filters("p", ["admin", "*", "*"], project_id), ["id"])
    if existing_admin:
        click.echo("Default admin policy already exists, skipping.")
    else:
        admin_data = _rule_to_dict("p", ["admin", "*", "*"], project_id)
        sg.create(entity_type, admin_data)
        click.echo("Seeded default admin policy: p, admin, *, *")
        if project_id is not None:
            click.echo(f"  (scoped to project {project_id})")

    click.echo("\nDone!")
