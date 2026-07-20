"""FastAPI RBAC example using ShotGrid Casbin Adapter.

This example demonstrates how to integrate the ShotGrid Casbin Adapter
with FastAPI to implement Role-Based Access Control (RBAC), with
authentication backed by the ShotGrid API.

Two authentication backends are provided:

- **REST API** (``SGCA_AUTH_MODE=rest``): Uses the ShotGrid REST API's
  OAuth 2.0 ``password`` grant type to exchange ``login:password`` for
  an access token. This is the recommended approach for production —
  token-based, stateless, and supports refresh tokens.

- **Python SDK** (``SGCA_AUTH_MODE=sdk``): Uses the Python SDK's
  built-in user-based auth: ``Shotgun(url, login=..., password=...)``.
  Simpler setup but creates a new connection per auth attempt.

- **Bearer** (``SGCA_AUTH_MODE=bearer``): Dev/testing mode — the token
  value is used directly as the username, no ShotGrid auth performed.

Setup:
    1. Install dependencies: ``pip install fastapi uvicorn shotgrid-casbin-adapter httpx``
    2. Set environment variables (or use a .env file):
       - SHOTGRID_URL
       - SHOTGRID_SCRIPT_NAME
       - SHOTGRID_API_KEY
       - SHOTGRID_PROJECT_ID (optional, for project-scoped policies)
       - SGCA_AUTH_MODE (optional, ``rest`` | ``sdk`` | ``bearer``, default: ``rest``)
    3. Run: ``just example-fastapi``

Policy model (rbac_model.conf):
    - Users can have roles (g policy)
    - Roles have permissions on objects with actions (p policy)
    - A request is allowed if the user's role grants the requested action on the object

Example policies stored in ShotGrid:
    p, admin, dataset1, read
    p, admin, dataset1, write
    p, developer, dataset1, read
    g, alice, admin
    g, bob, developer
"""

import os

import casbin
import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBasic
from fastapi.security import HTTPBasicCredentials
from fastapi.security import HTTPBearer
from shotgun_api3.shotgun import Shotgun

from shotgrid_casbin_adapter import Adapter


# --- Casbin enforcer setup ---

adapter = Adapter()
enforcer = casbin.Enforcer(
    os.path.join(os.path.dirname(__file__), "rbac_model.conf"),
    adapter,
)

# --- ShotGrid authentication ---

SHOTGRID_URL = os.environ.get("SHOTGRID_URL", "")



def _authenticate_sg_rest(login: str, password: str) -> str | None:
    """Authenticate a user via the ShotGrid REST API (OAuth 2.0).

    Uses the ``password`` grant type to exchange credentials for an
    access token. On success, returns the login name; on failure,
    returns None.

    The REST API endpoint is ``POST /api/v1.1/auth/access_token`` with
    ``grant_type=password``. This is the recommended auth method for
    production — token-based, stateless, and supports refresh tokens.

    Results are cached to avoid repeated auth calls.

    Args:
        login: ShotGrid human user login name.
        password: ShotGrid human user password.

    Returns:
        The login name if authentication succeeds, otherwise None.
    """
    try:
        resp = httpx.post(
            f"{SHOTGRID_URL}/api/v1.1/auth/access_token",
            data={"grant_type": "password", "username": login, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return login
        return None
    except Exception:
        return None



def _authenticate_sg_sdk(login: str, password: str) -> str | None:
    """Authenticate a user via the ShotGrid Python SDK.

    Uses the SDK's built-in user-based authentication:
    ``Shotgun(url, login=..., password=...)``. If credentials are
    invalid, the constructor raises ``AuthenticationFault``; if valid,
    the connection succeeds and the user's login is returned.

    Results are cached to avoid repeated authentication calls.

    Args:
        login: ShotGrid human user login name.
        password: ShotGrid human user password.

    Returns:
        The login name if authentication succeeds, otherwise None.
    """
    from shotgun_api3.shotgun import AuthenticationFault

    try:
        sg = Shotgun(SHOTGRID_URL, login=login, password=password)
        # The constructor validates credentials — if we reach here,
        # authentication succeeded.  Avoid calling sg.find_one() because
        # ShotGrid instances that require a Personal Access Token (PAT)
        # for API reads will reject the query even though user-based
        # login succeeded.
        sg.close()
        return login
    except AuthenticationFault:
        return None


def _get_user_rest(credentials: HTTPBasicCredentials = Depends(HTTPBasic())) -> str:
    """Authenticate user via HTTP Basic Auth using the ShotGrid REST API.

    Args:
        credentials: The HTTP Basic Auth credentials.

    Returns:
        The authenticated username (login).

    Raises:
        HTTPException: 401 if ShotGrid authentication fails.
    """
    login = _authenticate_sg_rest(credentials.username, credentials.password)
    if login is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid ShotGrid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return login


def _get_user_sdk(credentials: HTTPBasicCredentials = Depends(HTTPBasic())) -> str:
    """Authenticate user via HTTP Basic Auth using the ShotGrid Python SDK.

    Args:
        credentials: The HTTP Basic Auth credentials.

    Returns:
        The authenticated username (login).

    Raises:
        HTTPException: 401 if ShotGrid authentication fails.
    """
    login = _authenticate_sg_sdk(credentials.username, credentials.password)
    if login is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid ShotGrid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return login


def _get_user_bearer(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> str:
    """Authenticate user via Bearer token (dev/testing mode).

    Treats the token value directly as the username. No ShotGrid
    authentication is performed — use this only for development.

    Args:
        credentials: The HTTP Bearer credentials.

    Returns:
        The token value as the username.
    """
    return credentials.credentials


# Choose auth dependency based on environment variable
_AUTH_MODE = os.environ.get("SGCA_AUTH_MODE", "rest").lower()
print(_AUTH_MODE)
_AUTH_BACKENDS = {
    "rest": _get_user_rest,
    "sdk": _get_user_sdk,
    "bearer": _get_user_bearer,
}
_current_user = _AUTH_BACKENDS.get(_AUTH_MODE, _get_user_rest)
print(_current_user)


def authorize(sub: str, obj: str, act: str) -> None:
    """Check if the subject is authorized to perform the action on the object.

    Args:
        sub: The subject (username).
        obj: The object (resource).
        act: The action (e.g. "read", "write").

    Raises:
        HTTPException: 403 if the subject is not authorized.
    """
    if not enforcer.enforce(sub, obj, act):
        raise HTTPException(status_code=403, detail=f"Forbidden: {sub} cannot {act} on {obj}")


# --- FastAPI app ---

app = FastAPI(title="ShotGrid Casbin RBAC Example")


@app.get("/dataset1/{item}")
def read_dataset(item: str, user: str = Depends(_current_user)):
    """Read access to dataset1 items — requires 'read' permission."""
    authorize(user, "dataset1", "read")
    return {"message": f"Read access granted to dataset1/{item}", "user": user}


@app.post("/dataset1/{item}")
def write_dataset(item: str, user: str = Depends(_current_user)):
    """Write access to dataset1 items — requires 'write' permission."""
    authorize(user, "dataset1", "write")
    return {"message": f"Write access granted to dataset1/{item}", "user": user}


@app.get("/admin/settings")
def admin_settings(user: str = Depends(_current_user)):
    """Admin settings — requires 'admin' role with 'read' on 'settings'."""
    authorize(user, "settings", "read")
    return {"message": "Admin settings accessed", "user": user}


@app.get("/debug/policies")
def debug_policies():
    """Debug endpoint — list all loaded policies and groupings."""
    # Also try to re-load from ShotGrid to see raw data
    try:
        raw = adapter.sg.find(adapter.entity_type, [], _FIELDS_WITH_ID)
    except Exception as e:
        raw = f"Error: {e}"
    return {
        "policies": enforcer.get_policy(),
        "grouping": enforcer.get_grouping_policy(),
        "entity_type": adapter.entity_type,
        "project_id": adapter.project_id,
        "raw_shotgrid_entities": raw,
    }
