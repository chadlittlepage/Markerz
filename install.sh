#!/bin/bash
# Markerz Installer
# Installs the Markerz marker manager for DaVinci Resolve
set -e

echo "================================"
echo "  Markerz Installer v0.1.0"
echo "  DaVinci Resolve Marker Manager"
echo "================================"
echo ""

# Check for Python 3.10+
PYTHON=""
for p in python3 python3.12 python3.11 python3.10; do
    if command -v "$p" &>/dev/null; then
        ver=$("$p" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$p" -c "import sys; print(sys.version_info.major)")
        minor=$("$p" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$p"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ is required but not found."
    echo "Install Python from https://python.org or via Homebrew: brew install python"
    exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"
PYTHON_PATH=$(which "$PYTHON")

# Check for DaVinci Resolve
RESOLVE_SCRIPTS="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
if [ ! -d "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve" ]; then
    echo "WARNING: DaVinci Resolve does not appear to be installed."
    echo "The Markerz CLI will still work, but the Resolve integration won't."
fi

# Install Markerz package
echo ""
echo "Installing Markerz..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
$PYTHON -m pip install --break-system-packages "$SCRIPT_DIR" PySide6 2>&1 | tail -5 || \
$PYTHON -m pip install "$SCRIPT_DIR" PySide6 2>&1 | tail -5

# Find the installed markerz command
MARKERZ_PATH=$($PYTHON -c "import shutil; print(shutil.which('markerz') or '')")
if [ -z "$MARKERZ_PATH" ]; then
    for bp in "$HOME/.local/bin/markerz" "$HOME/Library/Python/3.12/bin/markerz" "$HOME/Library/Python/3.11/bin/markerz" "$HOME/Library/Python/3.10/bin/markerz"; do
        if [ -f "$bp" ]; then
            MARKERZ_PATH="$bp"
            break
        fi
    done
fi

if [ -n "$MARKERZ_PATH" ]; then
    echo "Markerz command: $MARKERZ_PATH"
else
    echo "Markerz installed (use: $PYTHON -m markerz)"
fi

# Install Resolve launcher script (self-contained, finds Python at runtime)
echo ""
echo "Installing DaVinci Resolve launcher script..."
mkdir -p "$RESOLVE_SCRIPTS"

cat > "$RESOLVE_SCRIPTS/Markerz.py" << 'LAUNCHER'
"""Launch Markerz marker manager."""
import subprocess
import shutil
import os

def _find_python():
    """Find a Python 3.10+ interpreter at runtime."""
    candidates = [
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        shutil.which("python3") or "",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                out = subprocess.check_output(
                    [p, "-c", "import sys; print(sys.version_info.minor)"],
                    text=True, timeout=5,
                )
                if int(out.strip()) >= 10:
                    return p
            except Exception:
                continue
    return None

python = _find_python()
if python:
    markerz_cmd = shutil.which("markerz")
    if markerz_cmd:
        subprocess.Popen([markerz_cmd, "ui"], start_new_session=True)
    else:
        subprocess.Popen([python, "-m", "markerz", "ui"], start_new_session=True)
LAUNCHER

echo "Installed to: $RESOLVE_SCRIPTS/Markerz.py"

# Verify
echo ""
echo "================================"
echo "  Installation Complete!"
echo "================================"
echo ""
echo "To launch Markerz:"
echo "  1. From Resolve: Workspace > Scripts > Markerz"
echo "  2. From Terminal: markerz ui"
echo ""
echo "Requirements:"
echo "  - DaVinci Resolve must be running"
echo "  - Preferences > System > General > External scripting: Local"
echo "  - A timeline must be open"
echo ""
echo "Settings saved to: ~/.markerz/settings.json"
echo ""
