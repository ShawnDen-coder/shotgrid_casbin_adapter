"""Command Line Interface (CLI) module for defining application commands.

This module contains all CLI command definitions and entry points using Click.
The primary command is ``init``, which creates the ShotGrid custom entity type
and fields required for storing Casbin policy rules.

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
from shotgun_api3.shotgun import Shotgun

from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL


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
def init(base_url: str | None, script_name: str | None, api_key: str | None, entity_type: str | None) -> None:
    """Initialize ShotGrid entity type and fields for Casbin policy storage.

    Creates the required fields (ptype, v0-v5) on the specified ShotGrid
    custom entity type. The entity type must already exist in ShotGrid;
    this command only creates the fields.

    Connection parameters can be provided via CLI options or environment
    variables.

    Args:
        base_url: ShotGrid server URL. Falls back to ``SHOTGRID_URL`` env var.
        script_name: ShotGrid script name. Falls back to ``SHOTGRID_SCRIPT_NAME`` env var.
        api_key: ShotGrid API key. Falls back to ``SHOTGRID_API_KEY`` env var.
        entity_type: Custom entity type name. Falls back to ``SHOTGRID_ENTITY_TYPE``
            env var, then ``DEFAULT_ENTITY_TYPE``.
    """
    entity_type = entity_type or os.environ.get(SHOTGRID_ENTITY_TYPE) or DEFAULT_ENTITY_TYPE
    sg = _get_sg(base_url, script_name, api_key)

    click.echo(f"Initializing entity type '{entity_type}' in ShotGrid...")

    # Read existing fields on the entity type
    existing_fields: dict[str, Any] = sg.schema_field_read(entity_type)
    existing_field_names: set[str] = set(existing_fields.keys())

    # Create missing Casbin fields
    field_definitions: dict[str, tuple[str, str]] = {
        "ptype": ("text", "Policy Type"),
        "v0": ("text", "V0"),
        "v1": ("text", "V1"),
        "v2": ("text", "V2"),
        "v3": ("text", "V3"),
        "v4": ("text", "V4"),
        "v5": ("text", "V5"),
    }

    created: list[str] = []
    skipped: list[str] = []
    for field_name, (data_type, display_name) in field_definitions.items():
        if field_name in existing_field_names:
            skipped.append(field_name)
            click.echo(f"  Field '{field_name}' already exists, skipping.")
        else:
            sg.schema_field_create(entity_type, data_type, display_name, properties={"name": field_name})
            created.append(field_name)
            click.echo(f"  Created field '{field_name}' ({data_type}).")

    click.echo(f"\nDone! Created {len(created)} field(s), skipped {len(skipped)} existing field(s).")
