# shotgrid-casbin-adapter

A Casbin policy adapter that enables loading and saving access control policies from/to Autodesk ShotGrid (formerly Shotgun).

## Installation

```bash
pip install shotgrid-casbin-adapter
```

## Quick Start

### Basic Usage

```python
import casbin
from shotgrid_casbin_adapter import Adapter

# Using environment variables (SHOTGRID_URL, SHOTGRID_SCRIPT_NAME, SHOTGRID_API_KEY)
adapter = Adapter()

# Or pass connection parameters directly
adapter = Adapter(
    base_url="https://your-studio.shotgridstudio.com",
    script_name="casbin_script",
    api_key="your_api_key",
)

# Scope to a specific project (one adapter = one project's policies)
adapter = Adapter(
    base_url="https://your-studio.shotgridstudio.com",
    script_name="casbin_script",
    api_key="your_api_key",
    project_id=42,
)

e = casbin.Enforcer("model.conf", adapter)

sub = "alice"
obj = "data1"
act = "read"

if e.enforce(sub, obj, act):
    # permit alice to read data1
    pass
else:
    # deny the request
    pass
```

### Integration with FastAPI

Use this adapter with [fastapi-authz](https://github.com/pycasbin/fastapi-authz) to add Casbin-based authorization to your FastAPI application:

```python
import casbin
from fastapi import FastAPI
from fastapi_authz import CasbinMiddleware
from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser
from starlette.middleware.authentication import AuthenticationMiddleware

from shotgrid_casbin_adapter import Adapter

app = FastAPI()

# Set up the ShotGrid-backed Casbin enforcer
adapter = Adapter(
    base_url="https://your-studio.shotgridstudio.com",
    script_name="casbin_script",
    api_key="your_api_key",
)
enforcer = casbin.Enforcer("rbac_model.conf", adapter)


# Authentication backend (example with basic auth)
class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, request):
        if "Authorization" not in request.headers:
            return None
        # ... your authentication logic ...
        username = "alice"
        return AuthCredentials(["authenticated"]), SimpleUser(username)


# Add middleware (order matters: auth first, then Casbin)
app.add_middleware(CasbinMiddleware, enforcer=enforcer)
app.add_middleware(AuthenticationMiddleware, backend=BasicAuthBackend())


@app.get("/dataset1/{item}")
async def access_dataset(item: str):
    return {"message": f"Access granted to dataset1/{item}"}
```

Example `rbac_model.conf`:

```ini
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

## CLI Usage

Create Casbin fields on a ShotGrid custom entity type and seed a default admin policy:

> **Prerequisite:** The custom entity type must already be enabled in ShotGrid
> (Site Preferences > Entities). The `init` command only creates fields on an
> existing entity type — it cannot create the entity type itself.

```bash
# Using just (loads .env automatically)
just sgca-init CustomEntity39

# Or using environment variables directly
export SHOTGRID_URL="https://your-studio.shotgridstudio.com"
export SHOTGRID_SCRIPT_NAME="casbin_script"
export SHOTGRID_API_KEY="your_api_key"
sgca init

# Or pass parameters via CLI options
sgca init \
    --base-url "https://your-studio.shotgridstudio.com" \
    --script-name "casbin_script" \
    --api-key "your_api_key"

# Specify a custom entity type (must already exist in ShotGrid)
sgca init --entity-type "CustomEntity01"

# Scope the admin policy to a specific project
sgca init --entity-type "CustomEntity39" --project-id 42
```

The `init` command creates the fields and seeds a default admin policy (`p, admin, *, *`) so the adapter is ready to use immediately. If `--project-id` is provided, the admin policy is scoped to that project.

If the entity type does not exist, the command will report an error and remind you to enable it in Site Preferences first.

The `init` command creates the following fields on the entity type:

| Field   | Type | Description                          |
|---------|------|--------------------------------------|
| `ptype` | text | Policy type (e.g. `p`, `g`)         |
| `v0`    | text | First policy value (subject)         |
| `v1`    | text | Second policy value (object)         |
| `v2`    | text | Third policy value (action)          |
| `v3`    | text | Fourth policy value                  |
| `v4`    | text | Fifth policy value                   |
| `v5`    | text | Sixth policy value                   |

## Environment Variables

| Variable                | Description                                    | Required |
|-------------------------|------------------------------------------------|----------|
| `SHOTGRID_URL`          | ShotGrid server URL                            | Yes*     |
| `SHOTGRID_SCRIPT_NAME`  | Script name for authentication                 | Yes*     |
| `SHOTGRID_API_KEY`      | API key for authentication                     | Yes*     |
| `SHOTGRID_ENTITY_TYPE`  | Custom entity type name (default: `CustomEntity01`)| No       |
| `SHOTGRID_PROJECT_ID`   | ShotGrid project ID for scoping operations     | No       |

\* Required when not passing connection parameters directly to the `Adapter` constructor.

## Adapter API

### `Adapter(sg=None, base_url=None, script_name=None, api_key=None, entity_type=None, project_id=None, filtered=False)`

| Parameter      | Type                    | Description                                                    |
|----------------|-------------------------|----------------------------------------------------------------|
| `sg`           | `shotgun_api3.Shotgun`  | Existing ShotGrid connection. If provided, other params ignored.|
| `base_url`     | `str`                   | ShotGrid server URL. Falls back to `SHOTGRID_URL` env var.     |
| `script_name`  | `str`                   | Script name. Falls back to `SHOTGRID_SCRIPT_NAME` env var.     |
| `api_key`      | `str`                   | API key. Falls back to `SHOTGRID_API_KEY` env var.             |
| `entity_type`  | `str`                   | Entity type name. Falls back to `SHOTGRID_ENTITY_TYPE` env var.|
| `project_id`   | `int`                   | ShotGrid project ID. Falls back to `SHOTGRID_PROJECT_ID` env var. `None` = site-wide. |
| `filtered`     | `bool`                  | Enable filtered policy loading. Default: `False`.              |

### Supported Methods

| Method                       | Description                                        |
|------------------------------|----------------------------------------------------|
| `load_policy(model)`         | Load all policies from ShotGrid                    |
| `save_policy(model)`         | Save all policies to ShotGrid (replaces existing)  |
| `add_policy(sec, ptype, rule)` | Add a single policy rule                          |
| `add_policies(sec, ptype, rules)` | Add multiple policy rules (batch)              |
| `remove_policy(sec, ptype, rule)` | Remove a single policy rule                     |
| `remove_policies(sec, ptype, rules)` | Remove multiple policy rules (batch)         |
| `remove_filtered_policy(sec, ptype, field_index, *field_values)` | Remove by filter |
| `load_filtered_policy(model, filter)` | Load policies matching a filter              |
| `update_policy(sec, ptype, old_rule, new_rule)` | Update a single rule                |
| `update_policies(sec, ptype, old_rules, new_rules)` | Update multiple rules          |
| `update_filtered_policies(sec, ptype, new_rules, field_index, *field_values)` | Update by filter |
| `is_filtered()`              | Check if adapter is in filtered mode               |

### Project Scoping

ShotGrid sites contain multiple projects. By default, the adapter operates at site level — all policy rules across projects are mixed together. To isolate policies per project, bind a `project_id` at the Adapter level:

```python
# One adapter per project — policies are automatically scoped
project_a_adapter = Adapter(sg=sg, project_id=1)
project_b_adapter = Adapter(sg=sg, project_id=2)

# Each enforcer only sees/modify its project's policies
enforcer_a = casbin.Enforcer("model.conf", project_a_adapter)
enforcer_b = casbin.Enforcer("model.conf", project_b_adapter)
```

When `project_id` is set:
- All `find()` queries include a `["project", "is", {"type": "Project", "id": project_id}]` filter
- All `create()` operations link the entity to the project
- When `project_id` is `None` (default), behavior is site-wide (backward compatible)

### Soft Delete

ShotGrid's `delete()` operation retires entities rather than destroying them, and `find()` excludes retired records by default. This provides natural soft-delete behavior — retired policies are invisible to the adapter but can be restored via the ShotGrid UI if needed.

## License

MIT
