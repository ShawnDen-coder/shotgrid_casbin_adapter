# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Casbin policy adapter that enables loading and saving access control policies from/to Autodesk ShotGrid (formerly Shotgun). The adapter implements `casbin.persist.Adapter` and `casbin.persist.adapters.UpdateAdapter` interfaces, mapping ShotGrid entities to Casbin policy rules. Supports soft-delete patterns via custom DB classes.

## Commands

### Development Setup
```bash
just init          # Sync deps + install pre-commit hooks
```

### Linting & Formatting
```bash
just lint                # ruff check --fix + ruff format + ruff check
just lint-add-noqa       # Add # noqa for current violations, then lint
just lint-pre-commit     # Run all pre-commit hooks against whole tree
just lint-watch          # Watch and re-run ruff on changes
```

### Testing
```bash
just test                # Run tests with Python 3.10 (dev version)
just test-version 3.12   # Run tests with a specific Python version
just test-all            # Run tests across Python 3.10–3.14
```

### Single Test
```bash
uv run --extra dev pytest tests/test_import.py -v
uv run --extra dev pytest tests/test_import.py::test_imports -v
```

### Docs
```bash
just docs            # Serve docs locally (mkdocs serve)
just docs-build      # Build static docs
just deploy-gh-pages # Deploy docs to GitHub Pages
```

### Build & Publish
```bash
just build              # Build sdist + wheel
just deploy-pypi        # Build + publish to PyPI
just deploy-pypi-server # Build + publish to private PyPI (needs env vars)
```

## Architecture

### Package Structure
- `shotgrid_casbin_adapter/core.py` — Primary business logic: the `Adapter` class implementing Casbin's `persist.Adapter` and `persist.adapters.UpdateAdapter`. Handles policy CRUD, filtered policy loading, soft-delete, and SQLAlchemy session management.
- `shotgrid_casbin_adapter/constants.py` — Application-wide constants and configuration values.
- `shotgrid_casbin_adapter/cli.py` — Click-based CLI entry point. Registered as console script `shotgrid_casbin_adapter` in pyproject.toml.
- `shotgrid_casbin_adapter/__init__.py` — Package metadata (author, email).

### Key Design Patterns
- **SQLAlchemy dual-version compatibility**: The code handles SQLAlchemy 1.x and 2.x declarative base differently (1.x uses `declarative_base()`, 2.x uses `DeclarativeBase`).
- **Soft-delete support**: When `db_class_softdelete_attribute` is provided, all queries apply `_softdelete_query()` which filters out soft-deleted rows. Remove operations set the flag instead of deleting rows.
- **Context-managed sessions**: All DB operations use `_session_scope()` context manager for transactional safety (commit on success, rollback on exception).
- **Custom DB class support**: Users can provide their own SQLAlchemy model class (must have `id`, `ptype`, `v0`–`v5` columns). When provided, the custom class's metadata replaces the default `Base.metadata`.

### Dependencies
- **Runtime**: `click` (CLI), `casbin` (adapter interfaces), `sqlalchemy` (ORM/DB layer), `shotgun-api3` (ShotGrid API client)
- **Dev**: `pytest`, `pytest-mock`, `pytest-cov`
- **Docs**: `mkdocs-material`, `mkdocstrings-python`, `mkdocs-gen-files`, `mkdocs-literate-nav`

### Toolchain
- **uv** for dependency management and virtual environments
- **just** (rust-just) as task runner — all commands go through the justfile
- **ruff** for linting and formatting (config in `.ruff.toml`)
- **cocogitto** for version bumping and changelog generation (config in `cog.toml`)
- **pre-commit** hooks: uv-lock, yamlfmt, check-github-workflows, actionlint

### CI/CD (GitHub Actions)
- **ci-tests.yaml** — Lint + test across Python 3.10–3.14 on push/PR to main/master
- **version-bump.yaml** — Auto version bump with cocogitto on push to main/master
- **package-release.yaml** — Build + publish to PyPI and private PyPI on version tags
- **docs-deploy.yaml** — Deploy docs to GitHub Pages on version tags

### Environment Variables
The project uses `dotenv-load := true` in the justfile. Expected `.env` variables:
- `PYPI_SERVER_USERNAME` / `PYPI_SERVER_PASSWORD` — Private PyPI credentials
- ShotGrid credentials (to be implemented): `SHOTGRID_URL`, `SHOTGRID_SCRIPT_NAME`, `SHOTGRID_API_KEY`

### Code Style
- Line length: 120
- Target Python: 3.10+
- Docstring convention: Google style
- Import sorting: isort with `force-single-line = true`
- Ruff rule set: E, W, F, I, B, C4, D, UP, RUF, SIM (with D100/D104/D401 relaxed)
