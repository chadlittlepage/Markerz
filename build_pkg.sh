#!/bin/bash
# Build standalone Markerz.app and package into a signed .pkg installer.
# Usage: ./build_pkg.sh [--sign]
set -e

VERSION="0.2.0"
APP_NAME="Markerz"
BUNDLE_ID="com.chadlittlepage.markerz"
BUILD_DIR="build"
PKG_DIR="$BUILD_DIR/pkg"
PKG_ROOT="$PKG_DIR/root"
DIST_DIR="dist"

SIGN=false
if [ "$1" = "--sign" ]; then
    SIGN=true
fi

echo "========================================"
echo "  Building $APP_NAME v$VERSION"
echo "========================================"

# --- Step 1: PyInstaller build ---
echo ""
echo "[1/4] Building standalone app with PyInstaller..."
pyinstaller markerz.spec --noconfirm --clean 2>&1 | tail -10

if [ ! -d "$DIST_DIR/$APP_NAME.app" ]; then
    echo "ERROR: PyInstaller did not produce $APP_NAME.app"
    exit 1
fi

echo "  App size: $(du -sh "$DIST_DIR/$APP_NAME.app" | cut -f1)"

# --- Step 1b: Codesign the app for notarization ---
if [ "$SIGN" = true ]; then
    echo ""
    echo "[1b] Codesigning app with Developer ID Application..."
    APP_SIGN_ID="Developer ID Application: Chad Littlepage (72J767FV46)"

    # Sign all binaries, dylibs, and frameworks inside the app with hardened runtime
    find "$DIST_DIR/$APP_NAME.app" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) -exec \
        codesign --force --options runtime --timestamp --sign "$APP_SIGN_ID" {} \; 2>&1 | tail -5

    # Sign all .so files (Python extensions)
    find "$DIST_DIR/$APP_NAME.app" -type f -name "*.so" -exec \
        codesign --force --options runtime --timestamp --sign "$APP_SIGN_ID" {} \; 2>&1 | tail -5

    # Sign frameworks
    find "$DIST_DIR/$APP_NAME.app/Contents/Frameworks" -maxdepth 2 -name "*.framework" -type d | while read fw; do
        codesign --force --deep --options runtime --timestamp --sign "$APP_SIGN_ID" "$fw" 2>&1
    done

    # Sign the main executable
    codesign --force --options runtime --timestamp --sign "$APP_SIGN_ID" \
        "$DIST_DIR/$APP_NAME.app/Contents/MacOS/markerz" 2>&1

    # Sign the entire app bundle
    codesign --force --deep --options runtime --timestamp --sign "$APP_SIGN_ID" \
        "$DIST_DIR/$APP_NAME.app" 2>&1

    # Verify
    codesign --verify --deep --strict "$DIST_DIR/$APP_NAME.app" 2>&1 && echo "  Codesign OK" || echo "  WARNING: Codesign verification failed"
fi

# --- Step 2: Prepare pkg root ---
echo ""
echo "[2/4] Preparing installer payload..."

# Clean previous pkg root (may be root-owned from prior install test)
chmod -R u+rwX "$PKG_ROOT" 2>/dev/null || true
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/Applications"
cp -R "$DIST_DIR/$APP_NAME.app" "$PKG_ROOT/Applications/"

# --- Step 3: Write postinstall ---
echo ""
echo "[3/4] Writing installer scripts..."

mkdir -p "$PKG_DIR/scripts"
cat > "$PKG_DIR/scripts/postinstall" << 'POSTINSTALL'
#!/bin/bash
# Markerz postinstall — install Resolve launcher script
set -e

APP_EXEC="/Applications/Markerz.app/Contents/MacOS/markerz"

# Resolve launcher script — calls the bundled app directly, no Python needed
LAUNCHER="\"\"\"Launch Markerz marker manager.\"\"\"
import subprocess
subprocess.Popen(
    [\"$APP_EXEC\", \"ui\"],
    start_new_session=True,
)
"

# Try system-level Resolve Scripts (may fail on macOS 15 due to SIP)
RESOLVE_SCRIPTS="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
mkdir -p "$RESOLVE_SCRIPTS" 2>/dev/null && echo "$LAUNCHER" > "$RESOLVE_SCRIPTS/Markerz.py" 2>/dev/null || true

# Per-user install for EVERY real user — create the full path even if
# Blackmagic Design dir doesn't exist yet (Resolve will find it on next launch)
for USER_HOME in /Users/*; do
    [ ! -d "$USER_HOME/Library" ] && continue
    [ "$(basename "$USER_HOME")" = "Shared" ] && continue
    USER_SCRIPTS="$USER_HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    mkdir -p "$USER_SCRIPTS" 2>/dev/null || continue
    echo "$LAUNCHER" > "$USER_SCRIPTS/Markerz.py" 2>/dev/null || continue
    OWNER=$(stat -f '%Su' "$USER_HOME")
    chown -R "$OWNER" "$USER_HOME/Library/Application Support/Blackmagic Design" 2>/dev/null || true
done

# Symlink CLI into /usr/local/bin
mkdir -p /usr/local/bin 2>/dev/null || true
ln -sf "$APP_EXEC" /usr/local/bin/markerz 2>/dev/null || true

echo "Markerz installed successfully."
exit 0
POSTINSTALL
chmod +x "$PKG_DIR/scripts/postinstall"

# --- Step 4: Build .pkg ---
echo ""
echo "[4/4] Building installer package..."

# Update welcome.html to remove Python requirement
mkdir -p "$PKG_DIR/resources"
cat > "$PKG_DIR/resources/welcome.html" << WELCOME
<html>
<body style="font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 14px; color: #333;">
<h2>Markerz v${VERSION}</h2>
<p><strong>DaVinci Resolve Marker Manager</strong></p>
<p>Markerz is a floating marker management panel for DaVinci Resolve with bidirectional sync, live playhead tracking, and full marker editing.</p>
<h3>Features</h3>
<ul>
<li>Live bidirectional sync with Resolve timeline markers</li>
<li>Edit color, timecode, name, notes, and duration</li>
<li>Import markers from Frame.io EDL, standard EDL, and CSV</li>
<li>Search, sort, multi-select, undo</li>
<li>Customizable fonts, colors, and highlight</li>
<li>Persistent settings across sessions</li>
</ul>
<h3>Requirements</h3>
<ul>
<li>DaVinci Resolve 18+ with scripting set to Local</li>
<li>macOS 12+</li>
</ul>
<p>This installer will place Markerz in your Applications folder and add it to Resolve's Workspace &gt; Scripts menu.</p>
</body>
</html>
WELCOME

cat > "$PKG_DIR/resources/conclusion.html" << 'CONCLUSION'
<html>
<body style="font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 14px; color: #333;">
<h2>Installation Complete</h2>
<p><strong>Markerz is ready to use.</strong></p>
<h3>How to launch</h3>
<ol>
<li>Open DaVinci Resolve</li>
<li>Make sure scripting is enabled: <em>Preferences &gt; System &gt; General &gt; External scripting using: Local</em></li>
<li>Open a project with a timeline</li>
<li>Go to <strong>Workspace &gt; Scripts &gt; Markerz</strong></li>
</ol>
<p>You can also launch from Terminal: <code>markerz ui</code></p>
<h3>Settings</h3>
<p>All settings (window position, column sizes, fonts, colors) are saved to <code>~/.markerz/settings.json</code> and persist across sessions.</p>
</body>
</html>
CONCLUSION

# Generate component plist and disable bundle relocation.
# Without this, macOS Installer silently skips ad-hoc signed .app bundles.
pkgbuild --analyze --root "$PKG_ROOT" "$PKG_DIR/component.plist"
# Disable relocation and version-checking so the .app always installs
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$PKG_DIR/component.plist"
/usr/libexec/PlistBuddy -c "Set :0:BundleIsVersionChecked false" "$PKG_DIR/component.plist"
/usr/libexec/PlistBuddy -c "Set :0:BundleHasStrictIdentifier false" "$PKG_DIR/component.plist"

# Build component pkg
pkgbuild \
    --root "$PKG_ROOT" \
    --component-plist "$PKG_DIR/component.plist" \
    --identifier "$BUNDLE_ID" \
    --version "$VERSION" \
    --scripts "$PKG_DIR/scripts" \
    --install-location "/" \
    "$PKG_DIR/$APP_NAME-component.pkg"

# Write distribution.xml
cat > "$PKG_DIR/distribution.xml" << DISTXML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>$APP_NAME v$VERSION</title>
    <organization>com.chadlittlepage</organization>
    <domains enable_localSystem="true" enable_currentUserHome="false"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true"/>
    <welcome file="welcome.html" mime-type="text/html"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>
    <choices-outline>
        <line choice="default">
            <line choice="$BUNDLE_ID"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="$BUNDLE_ID" visible="false">
        <pkg-ref id="$BUNDLE_ID"/>
    </choice>
    <pkg-ref id="$BUNDLE_ID" version="$VERSION" onConclusion="none">$APP_NAME-component.pkg</pkg-ref>
</installer-gui-script>
DISTXML

# Build product archive
productbuild \
    --distribution "$PKG_DIR/distribution.xml" \
    --resources "$PKG_DIR/resources" \
    --package-path "$PKG_DIR" \
    "$PKG_DIR/$APP_NAME-unsigned.pkg"

if [ "$SIGN" = true ]; then
    echo ""
    echo "Signing installer..."
    productsign \
        --sign "Developer ID Installer: Chad Littlepage" \
        "$PKG_DIR/$APP_NAME-unsigned.pkg" \
        "$BUILD_DIR/$APP_NAME-v$VERSION.pkg"
    echo "Signed: $BUILD_DIR/$APP_NAME-v$VERSION.pkg"
else
    cp "$PKG_DIR/$APP_NAME-unsigned.pkg" "$BUILD_DIR/$APP_NAME-v$VERSION.pkg"
    echo "Unsigned: $BUILD_DIR/$APP_NAME-v$VERSION.pkg"
fi

PKG_SIZE=$(du -sh "$BUILD_DIR/$APP_NAME-v$VERSION.pkg" | cut -f1)
echo ""
echo "========================================"
echo "  Done! $APP_NAME-v$VERSION.pkg ($PKG_SIZE)"
echo "========================================"
