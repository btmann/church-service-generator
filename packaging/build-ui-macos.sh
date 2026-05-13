#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -r packaging/requirements-build.txt

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name church-service-ui \
  --paths "$ROOT_DIR/python-pptx-mods" \
  --add-data "$ROOT_DIR/assets:assets" \
  --add-data "$ROOT_DIR/backgrounds:backgrounds" \
  --add-data "$ROOT_DIR/worship:worship" \
  --collect-all streamlit \
  --collect-all altair \
  --collect-all pydeck \
  launch-ui.py

echo "Build complete: $ROOT_DIR/dist/church-service-ui/"
