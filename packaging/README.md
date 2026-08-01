Cross-platform executable build

This folder lets you build a standalone executable on macOS or Windows with PyInstaller.

What was added
- packaging/build-macos.sh
- packaging/build-windows.ps1
- packaging/requirements-build.txt
- tools/build_executable.py

Quick start
1. Put your main Python script in the project root (example: shs2phss.py).
2. On macOS, run:
   ./packaging/build-macos.sh --entry shs2phss.py --name church-service-generator
3. On Windows (PowerShell), run:
   .\packaging\build-windows.ps1 --entry shs2phss.py --name church-service-generator

Notes
- The builder automatically adds python-pptx-mods to module paths.
- If present, these folders are bundled into the executable: assets, backgrounds, worship.
- Build output is written to the dist folder.

Useful options
- --windowed
  Build as GUI app (no terminal window).
- --icon assets/app.ico
  Use a custom icon.
- --add-data src:dest
  Add extra files/folders. Repeat the flag for multiple paths.

Example
./packaging/build-macos.sh --entry shs2phss.py --name service-gen --windowed --add-data assets:assets --add-data worship:worship
