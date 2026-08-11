$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Remove-PathWithRetry {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [int]$Attempts = 5,
    [int]$DelaySeconds = 2
  )

  if (-not (Test-Path $Path)) { return }

  for ($i = 1; $i -le $Attempts; $i++) {
    try {
      Remove-Item $Path -Recurse -Force
      return
    }
    catch {
      if ($i -eq $Attempts) {
        throw "Failed to remove '$Path' after $Attempts attempts. Close church-service-ui.exe and retry. Last error: $($_.Exception.Message)"
      }
      Start-Sleep -Seconds $DelaySeconds
    }
  }
}

# Ensure prior UI app process is not locking dist files.
Get-Process -Name "church-service-ui" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

# Remove stale one-file artifact from older builds to avoid launching the wrong EXE.
$StaleExe = Join-Path $Root "dist/church-service-ui.exe"
if (Test-Path $StaleExe) {
  Remove-Item $StaleExe -Force
}

# Remove only the PyInstaller-managed pieces of the previous onedir output
# (the _internal bundle and the .exe itself), NOT the whole
# dist/church-service-ui folder -- that folder is also where the app stores
# ehsf/ (the song library) next to the EXE.
$AppDir = Join-Path $Root "dist/church-service-ui"
$StaleInternal = Join-Path $AppDir "_internal"
Remove-PathWithRetry -Path $StaleInternal
$StaleAppExe = Join-Path $AppDir "church-service-ui.exe"
if (Test-Path $StaleAppExe) {
  Remove-Item $StaleAppExe -Force
}

# PyInstaller's own onedir build step unconditionally deletes and recreates
# its ENTIRE named output directory (dist/church-service-ui) once it decides
# the COLLECT step needs to rerun -- confirmed directly in a PyInstaller
# build log ("Removing dir .../dist/church-service-ui"). This happens
# regardless of the cleanup above, so anything the app stores next to the
# EXE (ehsf/, the generated-output worship/ folder, the log file, etc.)
# would otherwise be silently destroyed on every single rebuild. Move
# everything PyInstaller does NOT manage out of the way first, and restore
# it afterward (even if the build fails) so that data survives.
$PreserveDir = Join-Path $Root "dist/_preserve_temp"
Remove-PathWithRetry -Path $PreserveDir
if (Test-Path $AppDir) {
  New-Item -ItemType Directory -Path $PreserveDir | Out-Null
  Get-ChildItem -Path $AppDir -Force | Where-Object {
    $_.Name -ne "_internal" -and $_.Name -ne "church-service-ui.exe"
  } | ForEach-Object {
    Move-Item -Path $_.FullName -Destination $PreserveDir
  }
}

try {
  python -m pip install -r packaging/requirements-build.txt
  if ($LASTEXITCODE -ne 0) {
    throw "pip install failed with exit code $LASTEXITCODE"
  }

  python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name church-service-ui `
    --paths "$Root/python-pptx-mods" `
    --hidden-import slides `
    --hidden-import worship `
    --hidden-import shs2phss `
    --hidden-import ui_theme `
    --add-data "$Root/ui.py;." `
    --add-data "$Root/pages;pages" `
    --add-data "$Root/assets;assets" `
    --add-data "$Root/backgrounds;backgrounds" `
    --add-data "$Root/worship;worship" `
    --collect-all streamlit `
    --collect-all altair `
    --collect-all pydeck `
    launch-ui.py
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
  }

  $ExpectedExe = Join-Path $Root "dist/church-service-ui/church-service-ui.exe"
  if (-not (Test-Path $ExpectedExe)) {
    throw "Build finished but expected EXE was not found: $ExpectedExe"
  }
}
finally {
  # Restore preserved data regardless of whether the build succeeded, so a
  # failed build never stays behind holding the user's ehsf/worship data.
  if (Test-Path $PreserveDir) {
    if (-not (Test-Path $AppDir)) {
      New-Item -ItemType Directory -Path $AppDir | Out-Null
    }
    Get-ChildItem -Path $PreserveDir -Force | ForEach-Object {
      Move-Item -Path $_.FullName -Destination $AppDir -Force
    }
    Remove-Item $PreserveDir -Force -Recurse
  }
}

Write-Host "Build complete: $Root/dist/church-service-ui/"
Write-Host "Run this EXE (inside the folder, not dist root): $ExpectedExe"
