"""Constants module for application-wide configuration values.

This module centralizes all constant definitions used throughout the application.
All configuration values, magic numbers, and fixed strings should be defined here
to maintain a single source of truth.

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
    CASBIN_FIELDS: Field names that map to Casbin policy rule components.
"""

from typing import Final


SHOTGRID_URL: Final[str] = "SHOTGRID_URL"
SHOTGRID_SCRIPT_NAME: Final[str] = "SHOTGRID_SCRIPT_NAME"
SHOTGRID_API_KEY: Final[str] = "SHOTGRID_API_KEY"
SHOTGRID_ENTITY_TYPE: Final[str] = "SHOTGRID_ENTITY_TYPE"
SHOTGRID_PROJECT_ID: Final[str] = "SHOTGRID_PROJECT_ID"

DEFAULT_ENTITY_TYPE: Final[str] = "CustomEntity01"

CASBIN_FIELDS: Final[list[str]] = ["ptype", "v0", "v1", "v2", "v3", "v4", "v5"]
