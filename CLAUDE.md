# Markerz

DaVinci Resolve marker management tool. Python CLI + Fusion UI panel.

## Stack
- Python 3.10+, Click, Rich
- DaVinci Resolve Scripting API (DaVinciResolveScript)
- Hatchling build system
- ruff + mypy + pytest

## Structure
- `src/markerz/` - main package
  - `resolve_connection.py` - Resolve API connection
  - `markers.py` - marker CRUD operations
  - `cli.py` - Click CLI interface
- `tests/` - pytest tests (mock Resolve API)

## Commands
- `ruff check src/ tests/` - lint
- `ruff format src/ tests/` - format
- `mypy src/markerz` - typecheck
- `pytest -v` - run tests
- `pip install -e ".[dev]"` - install for development

## Conventions
- Type annotations on all public functions
- Mock DaVinci Resolve objects in tests (API not available in CI)
- Primary color: #4a556c
