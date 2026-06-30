#!/usr/bin/env python3
"""Launcher for Church Service Generator UI.

Works both from source and from a PyInstaller frozen executable.
"""

import os
import sys


def _resolve_ui_script() -> str:
    """Return an absolute path to ui.py in source or frozen bundle."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(script_dir, "ui.py")
    if os.path.exists(candidate):
        return candidate

    bundle_dir = getattr(sys, "_MEIPASS", script_dir)
    candidate = os.path.join(bundle_dir, "ui.py")
    if os.path.exists(candidate):
        return candidate

    raise FileNotFoundError(f"Could not locate ui.py in {script_dir} or {bundle_dir}")


def main() -> None:
    ui_script = _resolve_ui_script()
    os.chdir(os.path.dirname(ui_script))

    # Run Streamlit in-process so frozen builds do not rely on spawning python -m.
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--logger.level=info",
        "--client.showErrorDetails=true",
        "--browser.gatherUsageStats=false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
