#!/bin/bash
# Build standalone Markerz.app and package into a signed .pkg installer.
# Usage: ./build_pkg.sh [--sign]
set -e

VERSION="0.2.1"
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
# Runs as root. On macOS 15+ TCC may restrict ~/Library access.
set -e

APP_EXEC="/Applications/Markerz.app/Contents/MacOS/markerz"

LAUNCHER='"""Launch Markerz marker manager."""
import subprocess, os
subprocess.Popen(
    ["/Applications/Markerz.app/Contents/MacOS/markerz", "ui"],
    start_new_session=True,
    stdout=open(os.devnull, "w"),
    stderr=open(os.devnull, "w"),
)
'

INSTALLED=0

# Install to ALL script folders (Utility, Edit, Color, Comp, Deliver)
# so Markerz appears on every Resolve page
SCRIPT_FOLDERS="Utility Edit Color Comp Deliver"

# --- System-level (all users) ---
for FOLDER in $SCRIPT_FOLDERS; do
    SYS_SCRIPTS="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/$FOLDER"
    if mkdir -p "$SYS_SCRIPTS" 2>/dev/null; then
        echo "$LAUNCHER" > "$SYS_SCRIPTS/Markerz.py" 2>/dev/null && INSTALLED=1
    fi
done

# --- Per-user: try every real user's home ---
for USER_HOME in /Users/*; do
    [ ! -d "$USER_HOME/Library" ] && continue
    UNAME=$(basename "$USER_HOME")
    [ "$UNAME" = "Shared" ] && continue

    for FOLDER in $SCRIPT_FOLDERS; do
        USER_SCRIPTS="$USER_HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/$FOLDER"

        # Try mkdir + write directly
        if mkdir -p "$USER_SCRIPTS" 2>/dev/null; then
            echo "$LAUNCHER" > "$USER_SCRIPTS/Markerz.py" 2>/dev/null && INSTALLED=1
        else
            # TCC blocked us — run as the target user instead
            su "$UNAME" -c "mkdir -p \"$USER_SCRIPTS\" 2>/dev/null && echo '$LAUNCHER' > \"$USER_SCRIPTS/Markerz.py\"" 2>/dev/null && INSTALLED=1 || true
        fi
    done
    chown -R "$UNAME" "$USER_HOME/Library/Application Support/Blackmagic Design" 2>/dev/null || true
done

# Symlink CLI into /usr/local/bin
mkdir -p /usr/local/bin 2>/dev/null || true
ln -sf "$APP_EXEC" /usr/local/bin/markerz 2>/dev/null || true

[ "$INSTALLED" = "1" ] && echo "Markerz installed successfully." || echo "Markerz installed. Run 'markerz ui' once to complete Resolve integration."
exit 0
POSTINSTALL
chmod +x "$PKG_DIR/scripts/postinstall"
chmod +x "$PKG_DIR/scripts/postinstall"

# --- Step 4: Build .pkg ---
echo ""
echo "[4/4] Building installer package..."

# Update welcome.html to remove Python requirement
mkdir -p "$PKG_DIR/resources"
cat > "$PKG_DIR/resources/welcome.html" << WELCOME
<html>
<body style="font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 13px; color: #333; margin: 0; padding: 0;">
<h2 style="margin-top: 0;">Markerz v${VERSION}</h2>
<p style="margin: 2px 0;"><strong>DaVinci Resolve Marker Manager</strong></p>
<p style="margin: 6px 0 8px;">A floating marker panel with bidirectional sync, live playhead tracking, and full marker editing.</p>
<p style="margin: 2px 0; font-size: 12px;"><strong>Features:</strong> Live sync, edit markers (color, TC, name, notes, duration), import EDL/CSV, search, sort, multi-select, undo, customizable display, settings presets.</p>
<p style="margin: 8px 0 2px; font-size: 12px;"><strong>Requires:</strong> DaVinci Resolve 18+ (scripting set to Local), macOS 12+</p>
<p style="margin: 8px 0 0; font-size: 12px;">Installs to Applications and adds to Resolve's Workspace &gt; Scripts menu.</p>
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
<p style="color: #999; font-size: 11px;"><em>If Markerz does not appear in Scripts, restart DaVinci Resolve.</em></p>
<h3>Settings</h3>
<p>All settings (window position, column sizes, fonts, colors) are saved to <code>~/.markerz/settings.json</code> and persist across sessions.</p>
<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0 12px;">
<p style="text-align: center; color: #666; font-size: 12px;">
<strong>Created by Chad Littlepage</strong><br>
chad.littlepage@gmail.com &nbsp;&bull;&nbsp; 323.974.0444<br>
<span style="font-size: 11px; color: #999;">&copy; 2026 Chad Littlepage</span>
</p>
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
