#!/usr/bin/env bash
# Build Incognito.app for macOS arm64 via PyInstaller.
# Usage: bash scripts/build_macos.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGING_DIR="$PROJECT_ROOT/packaging"
DIST_DIR="$PROJECT_ROOT/dist"
APP_NAME="Incognito"

echo "==> Cleaning previous build artifacts..."
rm -rf "$PROJECT_ROOT/build" "$DIST_DIR"

echo "==> Running PyInstaller..."
cd "$PACKAGING_DIR"
uv run pyinstaller incognito.spec \
    --noconfirm --clean \
    --distpath "$DIST_DIR" \
    --workpath "$PROJECT_ROOT/build"

APP_DIR="$DIST_DIR/${APP_NAME}.app"

# Copy icon if available
if [ -f "$PROJECT_ROOT/assets/AppIcon.icns" ]; then
    cp "$PROJECT_ROOT/assets/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
else
    echo "  (No AppIcon.icns found in assets/, skipping icon)"
fi

echo "==> Ad-hoc code signing..."
codesign --force --sign - "$APP_DIR"

echo "==> Verifying signature..."
codesign --verify "$APP_DIR"
echo "  Signature OK"

APP_SIZE=$(du -sh "$APP_DIR" | cut -f1)
echo "==> Build complete: $APP_DIR ($APP_SIZE)"
