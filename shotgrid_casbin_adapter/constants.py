"""Constants module for application-wide configuration values.

This module centralizes all constant definitions used throughout the application.
All configuration values, magic numbers, and fixed strings should be defined here
to maintain a single source of truth.

ShotGrid automatically prepends ``sg_`` to custom entity field names. The
``CASBIN_FIELDS`` constant uses the API-facing names (with ``sg_`` prefix),
while ``CASBIN_FIELD_NAMES`` stores the base names used in
``schema_field_create`` (without prefix).

Typical usage example:

    from shotgrid_casbin_adapter.constants import SHOTGRID_URL, DEFAULT_ENTITY_TYPE

    url = os.environ.get(SHOTGRID_URL)
    entity_type = DEFAULT_ENTITY_TYPE

Attributes:
    SHOTGRID_URL: Environment variable key for ShotGrid server URL.
    SHOTGRID_SCRIPT_NAME: Environment variable key for ShotGrid script name.
    SHOTGRID_API_KEY: Environment variable key for ShotGrid API key.
    SHOTGRID_ENTITY_TYPE: Environment variable key for custom entity type name.
    SHOTGRID_PROJECT_ID: Environment variable key for ShotGrid project ID.
    DEFAULT_ENTITY_TYPE: Default ShotGrid entity type for Casbin rules (``CustomEntity01``).
    CASBIN_FIELD_NAMES: Base field names (without ``sg_`` prefix) for schema creation.
    CASBIN_FIELDS: API-facing field names (with ``sg_`` prefix) for queries and mutations.
"""

from typing import Final


SHOTGRID_URL: Final[str] = "SHOTGRID_URL"
SHOTGRID_SCRIPT_NAME: Final[str] = "SHOTGRID_SCRIPT_NAME"
SHOTGRID_API_KEY: Final[str] = "SHOTGRID_API_KEY"
SHOTGRID_ENTITY_TYPE: Final[str] = "SHOTGRID_ENTITY_TYPE"
SHOTGRID_PROJECT_ID: Final[str] = "SHOTGRID_PROJECT_ID"

DEFAULT_ENTITY_TYPE: Final[str] = "CustomEntity01"

CASBIN_FIELD_NAMES: Final[list[str]] = ["ptype", "v0", "v1", "v2", "v3", "v4", "v5"]
CASBIN_FIELDS: Final[list[str]] = [f"sg_{name}" for name in CASBIN_FIELD_NAMES]
