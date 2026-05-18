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
