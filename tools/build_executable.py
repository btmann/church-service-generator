#!/usr/bin/env python3
"""Build a standalone executable for this project on macOS or Windows."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


DEFAULT_DATA_DIRS = ("assets", "backgrounds", "worship")


def _default_entrypoint(root: Path) -> Path:
    """Return a likely entrypoint path if one exists."""
    candidates = (
        root / "shs2phss.py",
        root / "main.py",
        root / "app.py",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return root / "shs2phss.py"


def _add_data_args(root: Path, pairs: Iterable[str]) -> list[str]:
    sep = ";" if os.name == "nt" else ":"
    args: list[str] = []

    for pair in pairs:
        if ":" not in pair:
            raise ValueError(f"Invalid --add-data value '{pair}'. Use src:dest format.")

        src, dest = pair.split(":", 1)
        src_path = (root / src).resolve()
        if not src_path.exists():
            continue

        args.extend(["--add-data", f"{src_path}{sep}{dest}"])

    return args


def _default_data_pairs(root: Path) -> list[str]:
    pairs: list[str] = []
    for folder in DEFAULT_DATA_DIRS:
        if (root / folder).exists():
            pairs.append(f"{folder}:{folder}")
    return pairs


def _entrypoint_help(root: Path) -> str:
    py_files = sorted(root.glob("*.py"))
    suggestions = [p.name for p in py_files]
    cache_hint = root / "__pycache__" / "shs2phss.cpython-313.pyc"
    if cache_hint.exists():
        suggestions.append(str(cache_hint.relative_to(root)))
    if not suggestions:
        return "No top-level .py files were found. Pass --entry <path-to-script.py>."
    return "Try one of these: " + ", ".join(suggestions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build standalone executable with PyInstaller.")
    parser.add_argument("--entry", default=None, help="Path to the Python entry script.")
    parser.add_argument("--name", default="church-service-generator", help="Output executable name.")
    parser.add_argument("--windowed", action="store_true", help="Build a GUI app with no terminal window.")
    parser.add_argument("--icon", default=None, help="Optional icon path.")
    parser.add_argument(
        "--add-data",
        action="append",
        default=None,
        help="Extra data in src:dest format. Can be repeated.",
    )

    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    entry = Path(args.entry) if args.entry else _default_entrypoint(root)
    if not entry.is_absolute():
        entry = (root / entry).resolve()

    if not entry.exists():
        print(f"Entry script not found: {entry}", file=sys.stderr)
        print(_entrypoint_help(root), file=sys.stderr)
        return 2

    add_data_pairs = args.add_data if args.add_data else _default_data_pairs(root)

    try:
        add_data_args = _add_data_args(root, add_data_pairs)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        args.name,
        "--paths",
        str((root / "python-pptx-mods").resolve()),
        *add_data_args,
    ]

    if args.windowed:
        command.append("--windowed")

    if args.icon:
        icon_path = (root / args.icon).resolve() if not Path(args.icon).is_absolute() else Path(args.icon)
        if icon_path.exists():
            command.extend(["--icon", str(icon_path)])

    command.append(str(entry))

    print("Running:", " ".join(command))
    subprocess.run(command, check=True, cwd=root)

    dist_dir = root / "dist"
    if dist_dir.exists():
        print(f"Build complete. See: {dist_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
