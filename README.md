# Markerz

A standalone marker management tool for DaVinci Resolve. Floating panel with bidirectional sync, live playhead tracking, full marker editing, and EDL/CSV import.

No Python or dependencies required on the target machine. Just install and go.

## Features

- **Bidirectional sync** with Resolve timeline markers (100ms polling)
- **Live playhead tracking** with instant arrow key navigation
- **Edit markers** inline: color, timecode, name, notes, duration
- **Add/delete markers** from the panel or via keyboard shortcuts
- **Multi-select** with Cmd+Click, Shift+Click, and Select All
- **Import markers** from Frame.io EDL, standard CMX3600 EDL, and CSV with timecode offset
- **Search and filter** markers by name, note, color, or timecode
- **Sortable columns** including sort by marker color
- **Resizable columns** with drag handles and show/hide via right-click header menu
- **Settings presets** to save, load, import, and export display configurations
- **Per-column font sizing and colors** with live preview
- **Row height padding** and selection highlight color controls
- **Undo** (Cmd+Z) restores previous marker state, up to 100 levels
- **Copy** selected markers as tab-separated text (Cmd+C)
- **Context menu** with right-click for quick access to all actions
- **Always on top** floating window
- **Dark theme** matching Resolve's native UI
- **Timeline switch detection** automatically refreshes when you change timelines
- **Persistent settings** for window position, column widths, fonts, colors, and presets

## Install

### macOS Installer (recommended)

Download `Markerz-v0.2.0.pkg` from [Releases](../../releases). Double-click to install.

The installer:
- Places `Markerz.app` in `/Applications`
- Adds a launcher to Resolve's **Workspace > Scripts > Markerz** menu
- Creates a `markerz` CLI symlink in `/usr/local/bin`

No Python, pip, or any other dependencies needed on the target machine.

### Development Install

```bash
pip install -e ".[dev]"
```

## Usage

### From DaVinci Resolve

1. Open Resolve with a project and timeline
2. Enable scripting: **Preferences > System > General > External scripting using: Local**
3. Go to **Workspace > Scripts > Markerz**

### From Terminal

```bash
markerz ui
```

### CLI Commands

```bash
markerz status                          # Check Resolve connection
markerz list                            # List all markers
markerz list --color Red                # Filter by color
markerz list --search "vfx"             # Search by name/note
markerz add 1000 --color Green --name "Review" --note "Check framing"
markerz delete 1000                     # Delete marker at frame
markerz purge --color Blue              # Delete all markers of a color
markerz export --output markers.csv     # Export to CSV
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Arrow Up/Down | Navigate markers and move Resolve playhead |
| Delete/Backspace | Delete selected markers |
| Cmd+Z | Undo last marker change |
| Cmd+A | Select all visible markers |
| Cmd+C | Copy selected markers to clipboard |
| Double-click | Edit marker |
| Right-click | Context menu |

## Settings and Presets

Right-click the table or click the gear icon to open Settings:

- **Per-column font size** (8-36pt) with sliders and live preview
- **Per-column font color** with color pickers
- **Row height padding** control
- **Selection highlight color**
- **Column visibility** via right-click on column headers

Presets save all display settings (fonts, colors, padding, column widths, hidden columns) and can be imported/exported as JSON files for sharing between machines.

## Import Formats

| Format | Extension | Source |
|--------|-----------|--------|
| Frame.io EDL | `.edl` | Frame.io marker exports (detected by `\|C:` and `\|M:` markers) |
| Standard EDL | `.edl` | CMX3600 edit decision lists |
| CSV | `.csv` | Comma-separated marker data |

Import includes a preview dialog showing marker count, timecode range, colors, and an adjustable start timecode offset.

## Build from Source

### Prerequisites

- Python 3.10+
- PyInstaller (`pip install pyinstaller`)

### Build standalone .pkg

```bash
./build_pkg.sh          # Unsigned
./build_pkg.sh --sign   # Signed with Developer ID Installer
```

Output: `build/Markerz-v0.2.0.pkg` (~21MB)

### Run tests

```bash
pip install -e ".[dev]"
ruff check src/ tests/
mypy src/markerz
pytest -v
```

## Architecture

- **UI**: pywebview (system WebKit) with HTML/CSS/JS frontend
- **Backend**: Python API class exposed via pywebview JS bridge
- **Resolve API**: DaVinciResolveScript (external process connection)
- **Build**: Hatchling (package) + PyInstaller (standalone app) + pkgbuild/productbuild (.pkg installer)

```
src/markerz/
  __init__.py              # Version
  __main__.py              # python -m markerz entry point
  cli.py                   # Click CLI (list, add, delete, purge, export, status, ui)
  launch.py                # pywebview backend + Resolve polling
  markers.py               # Marker CRUD operations
  resolve_connection.py    # Resolve API connection wrapper
  timecode.py              # Frame/timecode conversion
  importers/               # EDL and CSV parsers
    csv_edl.py
    frameio_edl.py
    standard_edl.py
  web/                     # Frontend assets
    index.html
    style.css
    app.js
```

## Requirements

- DaVinci Resolve 18+ with scripting set to **Local**
- macOS 12+ (standalone installer)
- A timeline must be open in Resolve

## CI/CD

GitHub Actions pipeline:
- **Lint**: ruff check + format
- **Typecheck**: mypy strict mode
- **Test**: pytest across Python 3.10, 3.11, 3.12
- **Dependabot**: weekly dependency updates

## License

MIT
