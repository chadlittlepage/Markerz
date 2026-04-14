# Markerz

DaVinci Resolve marker management tool. List, add, delete, filter, search, and export markers from the CLI or a Fusion UI panel inside Resolve.

## Features

- List all timeline and clip markers with color, name, note, and timecode
- Add, delete, and bulk-purge markers by color
- Search and filter markers by name, note, or color
- Export markers to CSV
- Fusion UIManager panel (coming soon)

## Install

```bash
pip install -e .
```

## Usage

```bash
# Check connection
markerz status

# List all markers
markerz list

# Filter by color
markerz list --color Red

# Search by name/note
markerz list --search "vfx"

# Add a marker
markerz add 1000 --color Green --name "Review" --note "Check framing"

# Delete a marker
markerz delete 1000

# Purge all markers of a color
markerz purge --color Blue

# Export to CSV
markerz export --output markers.csv
```

## Requirements

- DaVinci Resolve with scripting enabled
- Python 3.10+

## Development

```bash
pip install -e ".[dev]"
ruff check src/ tests/
mypy src/markerz
pytest -v
```

## CI/CD

GitHub Actions pipeline:
- **Lint**: ruff check + format
- **Typecheck**: mypy strict mode
- **Test**: pytest across Python 3.10, 3.11, 3.12
- **Dependabot**: weekly dependency updates

## License

MIT
