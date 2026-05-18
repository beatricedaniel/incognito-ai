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

# --- GLiNER model preparation (bundle for offline first-launch) ---
GLINER_MODEL="knowledgator/gliner-pii-large-v1.0"
HF_MODEL_CACHE="$HOME/.cache/huggingface/hub/models--knowledgator--gliner-pii-large-v1.0"
BUNDLE_HF="$PACKAGING_DIR/hf-cache/hub/models--knowledgator--gliner-pii-large-v1.0"

echo "==> Preparing GLiNER model for bundling..."
if find "$BUNDLE_HF/snapshots" -name "pytorch_model.bin" -print -quit 2>/dev/null | grep -q .; then
    echo "  Model already staged, skipping."
else
    if [ ! -d "$HF_MODEL_CACHE/snapshots" ]; then
        echo "ERROR: GLiNER model not found in HuggingFace cache."
        echo "  Run first:  uv run python -c \"from gliner import GLiNER; GLiNER.from_pretrained('$GLINER_MODEL')\""
        exit 1
    fi
    SNAP_SHA=$(cat "$HF_MODEL_CACHE/refs/main")
    SNAP_SRC="$HF_MODEL_CACHE/snapshots/$SNAP_SHA"
    SNAP_DST="$BUNDLE_HF/snapshots/$SNAP_SHA"
    mkdir -p "$BUNDLE_HF/refs" "$SNAP_DST"
    cp "$HF_MODEL_CACHE/refs/main" "$BUNDLE_HF/refs/"
    for f in gliner_config.json pytorch_model.bin tokenizer.json tokenizer_config.json special_tokens_map.json; do
        cp -L "$SNAP_SRC/$f" "$SNAP_DST/"
    done
    echo "  Staged $(du -sh "$PACKAGING_DIR/hf-cache" | cut -f1) at $PACKAGING_DIR/hf-cache/"
fi

echo "==> Running PyInstaller..."
cd "$PACKAGING_DIR"
uv run pyinstaller incognito.spec \
    --noconfirm --clean \
    --distpath "$DIST_DIR" \
    --workpath "$PROJECT_ROOT/build"

APP_DIR="$DIST_DIR/${APP_NAME}.app"

echo "==> Ad-hoc code signing..."
codesign --deep --force --sign - "$APP_DIR"

echo "==> Verifying signature..."
codesign --verify --deep "$APP_DIR"
echo "  Signature OK"

APP_SIZE=$(du -sh "$APP_DIR" | cut -f1)
echo "==> App bundle complete: $APP_DIR ($APP_SIZE)"

# --- DMG packaging ---
VERSION=$(grep '^version' "$PROJECT_ROOT/pyproject.toml" | head -1 | sed 's/.*"\(.*\)"/\1/')
DMG_NAME="${APP_NAME}-${VERSION}-arm64.dmg"
DMG_STAGING="$DIST_DIR/dmg-staging"

cleanup_staging() { rm -rf "$DMG_STAGING"; }
trap cleanup_staging EXIT

echo "==> Staging DMG contents..."
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -Rp "$APP_DIR" "$DMG_STAGING/"

echo "==> Verifying staged app signature..."
codesign --verify --deep "$DMG_STAGING/${APP_NAME}.app"

# --- Generate DMG background image (Retina 2x of 600x400) ---
BG_IMG="$DIST_DIR/dmg-background.png"
BG_FLAG=""
if uv run python -c "from PIL import Image" 2>/dev/null; then
    echo "==> Generating DMG background image..."
    uv run python - "$BG_IMG" <<'PYEOF'
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 800  # 2x Retina of 600x400
img = Image.new("RGBA", (W, H))
draw = ImageDraw.Draw(img)

# Dark gradient background
for y in range(H):
    t = y / H
    r = int(26 + (22 - 26) * t)
    g = int(26 + (33 - 26) * t)
    b = int(46 + (62 - 46) * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

# Arrow shaft: between icon positions (scaled 2x: 160*2=320, 440*2=880, y=170*2=340)
ax1, ax2, ay = 400, 820, 340
draw.line([(ax1, ay), (ax2, ay)], fill=(200, 200, 200, 160), width=5)
# Arrowhead
for dy in range(-18, 19):
    draw.line([(ax2, ay + dy), (ax2 + 28, ay)], fill=(200, 200, 200, 160), width=2)

# Labels below icon positions
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
except OSError:
    font = ImageFont.load_default()
draw.text((320, 500), "Incognito", fill=(255, 255, 255, 180), font=font, anchor="mm")
draw.text((880, 500), "Applications", fill=(255, 255, 255, 180), font=font, anchor="mm")

img.save(sys.argv[1])
PYEOF
    BG_FLAG="--background $BG_IMG"
    echo "  Background image: $BG_IMG"
else
    echo "  Warning: Pillow not available, DMG will have no background image."
fi

echo "==> Creating DMG..."
if command -v create-dmg &>/dev/null; then
    # create-dmg returns exit code 2 when AppleScript window-styling
    # fails (common in SSH/headless). The DMG is still valid.
    set +e
    create-dmg \
        --volname "$APP_NAME" \
        ${BG_FLAG} \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 80 \
        --icon "$APP_NAME.app" 160 170 \
        --app-drop-link 440 170 \
        --no-internet-enable \
        --format UDZO \
        "$DIST_DIR/$DMG_NAME" \
        "$DMG_STAGING/"
    CREATE_DMG_EXIT=$?
    set -e

    if [ "$CREATE_DMG_EXIT" -gt 2 ]; then
        echo "ERROR: create-dmg failed (exit $CREATE_DMG_EXIT)"
        exit 1
    fi
    if [ "$CREATE_DMG_EXIT" -eq 2 ]; then
        echo "  Warning: create-dmg couldn't apply window styling (exit 2). DMG is still valid."
    fi
else
    echo "  create-dmg not found, falling back to hdiutil."
    ln -s /Applications "$DMG_STAGING/Applications"
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$DMG_STAGING" \
        -ov \
        -format UDZO \
        -nospotlight \
        -o "$DIST_DIR/$DMG_NAME"
fi

DMG_PATH="$DIST_DIR/$DMG_NAME"
DMG_BYTES=$(stat -f%z "$DMG_PATH")
DMG_MB=$((DMG_BYTES / 1048576))
MAX_MB=2048

if [ "$DMG_MB" -gt "$MAX_MB" ]; then
    echo "ERROR: DMG is ${DMG_MB}MB, exceeds ${MAX_MB}MB limit."
    exit 1
fi

DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
echo "==> Build complete: $DMG_PATH ($DMG_SIZE)"
