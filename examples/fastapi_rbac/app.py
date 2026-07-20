"""FastAPI RBAC example using ShotGrid Casbin Adapter.

This example demonstrates how to integrate the ShotGrid Casbin Adapter
with FastAPI to implement Role-Based Access Control (RBAC), with
authentication backed by the ShotGrid API.

Setup:
    1. Install dependencies: ``pip install fastapi uvicorn shotgrid-casbin-adapter``
    2. Set environment variables (or use a .env file):
       - SHOTGRID_URL
       - SHOTGRID_SCRIPT_NAME
       - SHOTGRID_API_KEY
       - SHOTGRID_PROJECT_ID (optional, for project-scoped policies)
    3. Run: ``uvicorn app:app --reload``

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

import base64
import os

import casbin
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
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
SHOTGRID_SCRIPT_NAME = os.environ.get("SHOTGRID_SCRIPT_NAME", "")
SHOTGRID_API_KEY = os.environ.get("SHOTGRID_API_KEY", "")


def _authenticate_sg_user(login: str, password: str) -> dict | None:
    """Authenticate a user against ShotGrid using human user credentials.

    Uses the ShotGrid API to validate the login/password combination.
    On success, returns the user entity dict; on failure, returns None.

    Args:
        login: ShotGrid human user login name.
        password: ShotGrid human user password.

    Returns:
        The user entity dict if authentication succeeds, otherwise None.
    """
    try:
        sg = Shotgun(SHOTGRID_URL, login=login, password=password)
        user: dict = sg.find_one(
            "HumanUser",
            [["login", "is", login]],
            ["id", "login", "name"],
        )
        return user
    except Exception:
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> str:
    """Extract and validate the user from the Authorization header.

    Supports two authentication modes:
    - **Bearer token**: The token value is used directly as the username
      (for development / testing).
    - **Basic auth**: Decodes ``login:password`` and validates against
      the ShotGrid API.

    Args:
        credentials: The HTTP Authorization credentials.

    Returns:
        The authenticated username (login).

    Raises:
        HTTPException: 401 if authentication fails.
    """
    token = credentials.credentials

    # Try Basic Auth (base64-encoded login:password)
    try:
        decoded = base64.b64decode(token).decode("utf-8")
        if ":" in decoded:
            login, password = decoded.split(":", 1)
            user = _authenticate_sg_user(login, password)
            if user:
                return user.get("login", login)
            raise HTTPException(status_code=401, detail="Invalid ShotGrid credentials")
    except (UnicodeDecodeError, ValueError):
        pass

    # Fallback: treat token as username (dev/testing mode)
    return token


def authorize(sub: str, obj: str, act: str) -> None:
    """Check if the subject is authorized to perform the action on the object.

    Args:
        sub: The subject (username).
        obj: The object (resource).
        act: The action (e.g. "read", "write").

    Raises:
        HTTPException: If the subject is not authorized.
    """
    if not enforcer.enforce(sub, obj, act):
        raise HTTPException(status_code=403, detail=f"Forbidden: {sub} cannot {act} on {obj}")


# --- FastAPI app ---

app = FastAPI(title="ShotGrid Casbin RBAC Example")


@app.get("/dataset1/{item}")
def read_dataset(item: str, user: str = Depends(get_current_user)):
    """Read access to dataset1 items — requires 'read' permission."""
    authorize(user, "dataset1", "read")
    return {"message": f"Read access granted to dataset1/{item}", "user": user}


@app.post("/dataset1/{item}")
def write_dataset(item: str, user: str = Depends(get_current_user)):
    """Write access to dataset1 items — requires 'write' permission."""
    authorize(user, "dataset1", "write")
    return {"message": f"Write access granted to dataset1/{item}", "user": user}


@app.get("/admin/settings")
def admin_settings(user: str = Depends(get_current_user)):
    """Admin settings — requires 'admin' role with 'read' on 'settings'."""
    authorize(user, "settings", "read")
    return {"message": "Admin settings accessed", "user": user}
