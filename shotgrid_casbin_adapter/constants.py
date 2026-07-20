"""Constants module for application-wide configuration values.

This module centralizes all constant definitions used throughout the application.
All configuration values, magic numbers, and fixed strings should be defined here
to maintain a single source of truth.

ShotGrid automatically prepends ``sg_`` to custom entity field names. The
``CASBIN_FIELDS`` constant uses the API-facing names for queries and mutations.
The ``code`` field (built-in on custom entities) is used for the first policy
value (``v0``), so it does not need to be created via ``schema_field_create``.

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
    CASBIN_CREATE_FIELDS: Base field names (without ``sg_`` prefix) for schema creation.
    CASBIN_FIELDS: API-facing field names for queries and mutations.
"""

from typing import Final


SHOTGRID_URL: Final[str] = "SHOTGRID_URL"
SHOTGRID_SCRIPT_NAME: Final[str] = "SHOTGRID_SCRIPT_NAME"
SHOTGRID_API_KEY: Final[str] = "SHOTGRID_API_KEY"
SHOTGRID_ENTITY_TYPE: Final[str] = "SHOTGRID_ENTITY_TYPE"
SHOTGRID_PROJECT_ID: Final[str] = "SHOTGRID_PROJECT_ID"

DEFAULT_ENTITY_TYPE: Final[str] = "CustomEntity01"

# Fields to create via schema_field_create (base names, ShotGrid adds sg_ prefix).
# "code" is a built-in field on custom entities and does not need to be created.
CASBIN_CREATE_FIELDS: Final[list[str]] = ["ptype", "v1", "v2", "v3", "v4", "v5"]

# API-facing field names for queries and mutations.
# code is used for v0 (subject) — it is a built-in field, not prefixed with sg_.
CASBIN_FIELDS: Final[list[str]] = ["sg_ptype", "code", "sg_v1", "sg_v2", "sg_v3", "sg_v4", "sg_v5"]
