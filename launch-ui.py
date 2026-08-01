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


def _runtime_dir() -> str:
    """Directory where diagnostics should be written."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


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
    log_dir = _runtime_dir() if getattr(sys, "frozen", False) else script_dir
    log_path = os.path.join(log_dir, "church-service-ui.log")
    try:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except Exception:
        # Avoid masking the real startup failure if logging itself fails.
        pass


def _show_error_dialog(message: str) -> None:
    """Show a visible error dialog on Windows windowed builds."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "Church Service UI Error", 0x10)
    except Exception:
        pass


def main() -> None:
    runtime_dir = _runtime_dir()
    _write_log(runtime_dir, "Launcher starting")

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

    # Some Windows environments carry a global Streamlit dev-mode setting,
    # which conflicts with an explicit server.port. Force production behavior.
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        "--global.developmentMode=false",
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
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        _write_log(_runtime_dir(), "Fatal launcher exception:")
        _write_log(_runtime_dir(), error_text)
        _show_error_dialog(
            "Church Service UI failed to start.\n\n"
            "See church-service-ui.log in the same folder as the EXE for details."
        )
        raise
