# FastAPI RBAC Example

This example demonstrates Role-Based Access Control (RBAC) using the ShotGrid Casbin Adapter with FastAPI, including ShotGrid-backed authentication.

## Setup

```bash
pip install fastapi uvicorn shotgrid-casbin-adapter
```

## Configure

Set environment variables (or use a `.env` file):

```bash
export SHOTGRID_URL="https://your-studio.shotgridstudio.com"
export SHOTGRID_SCRIPT_NAME="casbin_script"
export SHOTGRID_API_KEY="your_api_key"
# Optional: scope policies to a specific project
export SHOTGRID_PROJECT_ID="42"
```

## Run

```bash
uvicorn app:app --reload
```

## Authentication

The example supports two authentication modes:

### 1. ShotGrid Basic Auth (Production)

Send the user's ShotGrid `login:password` as a base64-encoded Bearer token:

```bash
# Encode credentials
TOKEN=$(echo -n "alice:her_password" | base64)

# Authenticate and access
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/dataset1/item1
```

The server validates credentials against the ShotGrid API using `shotgun_api3.Shotgun(login=..., password=...)`.

### 2. Direct Username (Development / Testing)

Pass the username directly as the Bearer token:

```bash
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
curl -H "Authorization: Bearer alice" http://localhost:8000/dataset1/item1

# Alice (admin) can write dataset1
curl -X POST -H "Authorization: Bearer alice" http://localhost:8000/dataset1/item1

# Bob (developer) can read dataset1
curl -H "Authorization: Bearer bob" http://localhost:8000/dataset1/item1

# Bob (developer) cannot write dataset1 → 403
curl -X POST -H "Authorization: Bearer bob" http://localhost:8000/dataset1/item1

# Bob (developer) cannot access admin settings → 403
curl -H "Authorization: Bearer bob" http://localhost:8000/admin/settings
```
