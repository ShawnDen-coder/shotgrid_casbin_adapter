# FastAPI RBAC Example

This example demonstrates Role-Based Access Control (RBAC) using the ShotGrid Casbin Adapter with FastAPI, including ShotGrid-backed authentication.

## Setup

```bash
pip install fastapi uvicorn shotgrid-casbin-adapter httpx
```

## Configure

Set environment variables (or use a `.env` file):

```bash
export SHOTGRID_URL="https://your-studio.shotgridstudio.com"
export SHOTGRID_SCRIPT_NAME="casbin_script"
export SHOTGRID_API_KEY="your_api_key"
# Optional: scope policies to a specific project
export SHOTGRID_PROJECT_ID="42"
# Optional: auth mode (default: rest)
export SGCA_AUTH_MODE="rest"
```

## Run

```bash
just example-fastapi
```

## Authentication Modes

Controlled by the `SGCA_AUTH_MODE` environment variable:

### REST API (default: `SGCA_AUTH_MODE=rest`)

Uses the ShotGrid REST API's OAuth 2.0 `password` grant type. The client sends `login:password` via HTTP Basic Auth, and the server exchanges them for an access token via `POST /api/v1.1/auth/access_token`. This is the **recommended approach for production** — token-based, stateless, and supports refresh tokens.

```bash
curl -u alice:her_password http://localhost:8000/dataset1/item1
```

### Python SDK (`SGCA_AUTH_MODE=sdk`)

Uses the ShotGrid Python SDK's built-in user-based authentication: `Shotgun(url, login=..., password=...)`. Simpler setup but creates a new connection per auth attempt (cached via `lru_cache`).

```bash
export SGCA_AUTH_MODE="sdk"
curl -u alice:her_password http://localhost:8000/dataset1/item1
```

### Bearer Token (`SGCA_AUTH_MODE=bearer`)

For development/testing only. The Bearer token is used directly as the username — no ShotGrid authentication is performed.

```bash
export SGCA_AUTH_MODE="bearer"
curl -H "Authorization: Bearer alice" http://localhost:8000/dataset1/item1
```

## Policy Model

The RBAC model (`rbac_model.conf`) defines:

- **`p`** — permission policies: `(subject, object, action)`
- **`g`** — role assignments: `(user, role)`
- A request is allowed if the user's role grants the requested action on the object

## Example Policies

Add these policies in ShotGrid (or programmatically via `enforcer.add_policy`):

| Type | Values                | Meaning                          |
|------|-----------------------|----------------------------------|
| `p`  | admin, dataset1, read | Admins can read dataset1         |
| `p`  | admin, dataset1, write| Admins can write dataset1        |
| `p`  | admin, settings, read | Admins can read settings         |
| `p`  | developer, dataset1, read | Developers can read dataset1 |
| `g`  | alice, admin          | Alice has the admin role         |
| `g`  | bob, developer        | Bob has the developer role       |

## Test

```bash
# Alice (admin) can read dataset1
curl -u alice:password http://localhost:8000/dataset1/item1

# Alice (admin) can write dataset1
curl -X POST -u alice:password http://localhost:8000/dataset1/item1

# Bob (developer) can read dataset1
curl -u bob:password http://localhost:8000/dataset1/item1

# Bob (developer) cannot write dataset1 → 403
curl -X POST -u bob:password http://localhost:8000/dataset1/item1

# Bob (developer) cannot access admin settings → 403
curl -u bob:password http://localhost:8000/admin/settings
```
