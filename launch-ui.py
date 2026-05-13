#!/usr/bin/env python3
"""
Launcher for Church Service Generator UI
Starts Streamlit app on local server
"""

import subprocess
import sys
import os

# Change to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Run Streamlit
subprocess.run([
    sys.executable, "-m", "streamlit", "run",
    "ui.py",
    "--server.address=127.0.0.1",
    "--server.port=8501",
    "--server.headless=true",
    "--server.fileWatcherType=none",
    "--logger.level=info",
    "--client.showErrorDetails=true",
    "--browser.gatherUsageStats=false"
])
