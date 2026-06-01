#!/usr/bin/env python3
"""Build a song lookup index from song metadata JSON files.

The generated index is used by ui.py to power song title search at scale.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json_with_fallback(path: Path) -> dict[str, Any] | None:
    """Load JSON using UTF-8 first, then latin-1 for legacy metadata."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        try:
            return json.loads(path.read_text(encoding="latin-1"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
    except (OSError, json.JSONDecodeError):
        return None


def normalize_title(title: str) -> str:
    return " ".join(title.strip().lower().split())


def infer_book_and_number(song_json: dict[str, Any], rel_parts: tuple[str, ...], filename: str) -> tuple[str, str]:
    """Infer book code and song number from filename/path/data."""
    match = re.match(r"^([A-Za-z0-9]+)-(\d+)", filename)
    if match:
        return match.group(1).lower(), match.group(2)

    number = song_json.get("number")
    song_number = str(number).strip() if number is not None else ""
    if not song_number and len(rel_parts) >= 2:
        song_number = rel_parts[-2]

    if len(rel_parts) >= 3:
        # e.g. pftl/208/pftl-208.json -> pftl
        # e.g. esp/pftl/017/pftl-017.json -> pftl
        song_book = rel_parts[-3].lower()
    elif len(rel_parts) >= 2:
        song_book = rel_parts[0].lower()
    else:
        song_book = "unknown"

    return song_book, song_number or "0"


def source_book_folder(rel_parts: tuple[str, ...]) -> str:
    """Return top-level source folder label, preserving nested source paths."""
    if len(rel_parts) >= 3:
        return "/".join(rel_parts[:-2])
    if rel_parts:
        return rel_parts[0]
    return "unknown"


def build_lookup(root: Path) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    folder_counts: Counter[str] = Counter()

    for json_path in sorted(root.rglob("*.json")):
        if json_path.name == "song-search-index.json":
            continue

        rel_parts = json_path.relative_to(root).parts
        song_data = load_json_with_fallback(json_path)
        if not song_data or not isinstance(song_data, dict):
            continue

        title = song_data.get("title")
        if not isinstance(title, str) or not title.strip():
            continue

        book, number = infer_book_and_number(song_data, rel_parts, json_path.stem)
        title_value = title.strip()
        title_key = normalize_title(title_value)
        src_folder = "/".join(rel_parts[:-1])
        src_book_folder = source_book_folder(rel_parts)

        dedupe_key = (title_key, book, number, src_folder)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        folder_counts[src_book_folder] += 1

        entries.append(
            {
                "title": title_value,
                "title_key": title_key,
                "book": book,
                "number": str(number),
                "source_book_folder": src_book_folder,
                "source_folder": src_folder,
                "json_path": str(json_path.relative_to(root.parent)).replace("\\", "/"),
            }
        )

    entries.sort(key=lambda s: (s["title_key"], s["book"], s["number"], s["source_folder"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root).replace("\\", "/"),
        "song_count": len(entries),
        "folder_counts": dict(sorted(folder_counts.items())),
        "songs": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build song title lookup index.")
    parser.add_argument("--root", default="ehsf", help="Root folder containing song metadata.")
    parser.add_argument(
        "--output",
        default="",
        help="Output file path. Defaults to <root>/song-search-index.json.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: root folder not found: {root}")
        return 1

    output = Path(args.output).resolve() if args.output else root / "song-search-index.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    lookup = build_lookup(root)
    output.write_text(json.dumps(lookup, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {lookup['song_count']} songs to {output}")
    if lookup["folder_counts"]:
        print("Source folders:")
        for folder, count in lookup["folder_counts"].items():
            print(f"  - {folder}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
