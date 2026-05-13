$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install -r packaging/requirements-build.txt

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name church-service-ui `
  --paths "$Root/python-pptx-mods" `
  --add-data "$Root/assets;assets" `
  --add-data "$Root/backgrounds;backgrounds" `
  --add-data "$Root/worship;worship" `
  --collect-all streamlit `
  --collect-all altair `
  --collect-all pydeck `
  launch-ui.py

Write-Host "Build complete: $Root/dist/church-service-ui/"
