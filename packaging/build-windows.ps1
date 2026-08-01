Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

py -m pip install -r packaging/requirements-build.txt
py tools/build_executable.py @args
