#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -r packaging/requirements-build.txt

# PyInstaller's own onedir build step unconditionally deletes and recreates
# its ENTIRE named output directory (dist/church-service-ui) once it decides
# the COLLECT step needs to rerun -- confirmed directly in a PyInstaller
# build log ("Removing dir .../dist/church-service-ui"). Anything the app
# stores next to the EXE (ehsf/, the generated-output worship/ folder, the
# log file, etc.) would otherwise be silently destroyed on every rebuild.
# Move everything PyInstaller does NOT manage out of the way first, and
# restore it afterward (even if the build fails) so that data survives.
APP_DIR="$ROOT_DIR/dist/church-service-ui"
PRESERVE_DIR="$ROOT_DIR/dist/_preserve_temp"
rm -rf "$PRESERVE_DIR"
if [ -d "$APP_DIR" ]; then
  mkdir -p "$PRESERVE_DIR"
  find "$APP_DIR" -mindepth 1 -maxdepth 1 \
    ! -name "_internal" ! -name "church-service-ui" \
    -exec mv {} "$PRESERVE_DIR/" \;
fi

restore_preserved() {
  if [ -d "$PRESERVE_DIR" ]; then
    mkdir -p "$APP_DIR"
    find "$PRESERVE_DIR" -mindepth 1 -maxdepth 1 -exec mv {} "$APP_DIR/" \;
    rm -rf "$PRESERVE_DIR"
  fi
}
trap restore_preserved EXIT

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name church-service-ui \
  --paths "$ROOT_DIR/python-pptx-mods" \
  --hidden-import slides \
  --hidden-import worship \
  --hidden-import shs2phss \
  --hidden-import ui_theme \
  --add-data "$ROOT_DIR/ui.py:." \
  --add-data "$ROOT_DIR/pages:pages" \
  --add-data "$ROOT_DIR/assets:assets" \
  --add-data "$ROOT_DIR/backgrounds:backgrounds" \
  --add-data "$ROOT_DIR/worship:worship" \
  --collect-all streamlit \
  --collect-all altair \
  --collect-all pydeck \
  launch-ui.py

echo "Build complete: $ROOT_DIR/dist/church-service-ui/"
