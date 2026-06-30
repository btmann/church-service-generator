#!/usr/bin/env python3
"""Launcher for Church Service Generator UI.

Works both from source and from a PyInstaller frozen executable.
"""

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser


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


def _find_open_port(start_port: int = 8501, max_tries: int = 20) -> int:
    """Return the first available localhost TCP port starting at start_port."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def _write_log(script_dir: str, message: str) -> None:
    """Append launcher diagnostics to a local log file for windowed builds."""
    if getattr(sys, "frozen", False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = script_dir
    log_path = os.path.join(log_dir, "church-service-ui.log")
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def main() -> None:
    ui_script = _resolve_ui_script()
    script_dir = os.path.dirname(ui_script)
    os.chdir(script_dir)

    port = _find_open_port(8501)
    url = f"http://127.0.0.1:{port}"

    # In windowed executables, open browser automatically so launch is visible.
    def _open_browser_later() -> None:
        time.sleep(1.5)
        webbrowser.open(url, new=1)

    threading.Thread(target=_open_browser_later, daemon=True).start()

    # Run Streamlit in-process so frozen builds do not rely on spawning python -m.
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--logger.level=info",
        "--client.showErrorDetails=true",
        "--browser.gatherUsageStats=false",
    ]
    _write_log(script_dir, f"Starting Church Service UI on {url}")
    try:
        raise SystemExit(stcli.main())
    except Exception:
        _write_log(script_dir, "Launcher failed with exception:")
        _write_log(script_dir, traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
