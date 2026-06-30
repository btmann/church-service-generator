$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Remove stale one-file artifact from older builds to avoid launching the wrong EXE.
$StaleExe = Join-Path $Root "dist/church-service-ui.exe"
if (Test-Path $StaleExe) {
  Remove-Item $StaleExe -Force
}

python -m pip install -r packaging/requirements-build.txt

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name church-service-ui `
  --paths "$Root/python-pptx-mods" `
  --add-data "$Root/ui.py;." `
  --add-data "$Root/assets;assets" `
  --add-data "$Root/backgrounds;backgrounds" `
  --add-data "$Root/worship;worship" `
  --collect-all streamlit `
  --collect-all altair `
  --collect-all pydeck `
  launch-ui.py

$ExpectedExe = Join-Path $Root "dist/church-service-ui/church-service-ui.exe"
if (-not (Test-Path $ExpectedExe)) {
  throw "Build finished but expected EXE was not found: $ExpectedExe"
}

Write-Host "Build complete: $Root/dist/church-service-ui/"
Write-Host "Run this EXE (inside the folder, not dist root): $ExpectedExe"
