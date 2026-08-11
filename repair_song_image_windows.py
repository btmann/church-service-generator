#!/usr/bin/env python3
"""One-time repair for a bug in slides.py's set_crop_window(): the exported
per-slide image window size (meta['window']/meta['window_orientation'],
cached in each song's own JSON) used to be computed from whichever page
happened to be last in the crop dict's own cropped-content aspect ratio,
instead of the song's constant raw canvas aspect ratio. Songs whose last
page has a noticeably different content density than the rest (e.g. a
short final verse) ended up with a badly wrong -- usually far too short --
exported image window, wasting most of the slide as empty space.

The per-page cropped PNG files on disk are NOT affected by this bug and do
not need to be regenerated; only the cached window/window_orientation
fields in each song's JSON need correcting. This script re-derives them
from the raw/ PNGs already on disk (no need to reprocess from the original
PPTX/PPT source) and rewrites them in place.

Usage:
    python repair_song_image_windows.py [ehsf_root]

Defaults to "ehsf" in the current directory. Prints every song whose
window actually changed; leaves everything else untouched.
"""
import json
import os
import re
import sys

import slides

JSON_NAME_RE = re.compile(r"^([A-Za-z]+)-(\d+)\.json$")


def _find_raw_pages(raw_dir, book, number):
    """Return (ndx, path) pairs for <book>-<number>-NN.png in raw_dir, sorted by page number."""
    if not os.path.isdir(raw_dir):
        return []
    pattern = re.compile(rf"^{re.escape(book)}-{re.escape(number)}-(\d+)\.png$", re.IGNORECASE)
    pages = []
    for name in os.listdir(raw_dir):
        m = pattern.match(name)
        if m:
            pages.append((int(m.group(1)), os.path.join(raw_dir, name)))
    pages.sort(key=lambda p: p[0])
    return pages


def repair_song_json(json_path, book, number):
    """Recompute and rewrite one song's cached window, if it has one.

    Returns a result dict, or None if this JSON wasn't something to repair
    (no raw pages found, no existing 'window' field, or an error occurred).
    """
    raw_dir = os.path.join(os.path.dirname(json_path), "raw")
    pages = _find_raw_pages(raw_dir, book, number)
    if not pages:
        return None

    crop = {}
    for ndx, path in pages:
        try:
            crop[ndx] = slides.analyze_image(path)
        except Exception as e:
            print(f"  ! could not analyze {path}: {e}")
            return None

    meta = slides.load_json_safe(json_path)
    if not isinstance(meta, dict) or "window" not in meta:
        return None

    old_window = meta.get("window")
    old_orientation = meta.get("window_orientation")

    try:
        slides.set_crop_window(crop, meta)
    except Exception as e:
        print(f"  ! could not recompute window for {json_path}: {e}")
        return None

    new_window = meta.get("window")
    new_orientation = meta.get("window_orientation")
    changed = (old_window != new_window) or (old_orientation != new_orientation)

    if changed:
        with open(json_path, "w") as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)

    return dict(
        changed=changed,
        old_window=old_window, new_window=new_window,
        old_orientation=old_orientation, new_orientation=new_orientation,
    )


def main():
    ehsf_root = sys.argv[1] if len(sys.argv) > 1 else "ehsf"
    if not os.path.isdir(ehsf_root):
        print(f"ehsf root not found: {ehsf_root}")
        sys.exit(1)

    total = 0
    changed_count = 0

    for dirpath, _dirnames, filenames in os.walk(ehsf_root):
        for name in sorted(filenames):
            m = JSON_NAME_RE.match(name)
            if not m:
                continue
            book, number = m.group(1), m.group(2)
            json_path = os.path.join(dirpath, name)
            total += 1
            result = repair_song_json(json_path, book, number)
            if result is None:
                continue
            if result["changed"]:
                changed_count += 1
                print(f"FIXED {json_path}")
                print(f"  orientation: {result['old_orientation']} -> {result['new_orientation']}")
                print(f"  window:      {result['old_window']}")
                print(f"          ->   {result['new_window']}")

    print(f"\nScanned {total} song JSON file(s) under {ehsf_root}, corrected {changed_count}.")


if __name__ == "__main__":
    main()
