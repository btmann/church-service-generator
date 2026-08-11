"""Tests for repair_song_image_windows.py, the one-time migration that
fixes already-processed songs' cached window/window_orientation (see
TestSetCropWindowUsesRawAspectRatio in test_slides.py for the underlying
bug: set_crop_window used to compute the exported image size from
whichever page happened to be last in the crop dict instead of the song's
constant raw canvas aspect ratio).
"""
import json

from PIL import Image, ImageDraw

import repair_song_image_windows as repair


def _make_page(path, content_box):
    img = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(img).rectangle(content_box, fill="black")
    img.save(path)


def _make_song(tmp_path, book="pftl", number="532", pages=(
    (100, 100, 900, 900),  # full page
    (100, 100, 900, 500),  # short final page
)):
    song_dir = tmp_path / number
    raw_dir = song_dir / "raw"
    raw_dir.mkdir(parents=True)
    for i, box in enumerate(pages, start=1):
        _make_page(raw_dir / f"{book}-{number}-{i:02d}.png", box)

    json_path = song_dir / f"{book}-{number}.json"
    json_path.write_text(json.dumps({
        "title": "Test Song",
        "window": [1.9, 0.8, 9.0, 1.8],  # deliberately wrong/stale cached value
        "window_orientation": "wide",
    }))
    return json_path


class TestRepairSongJson:
    def test_recomputes_and_rewrites_stale_window(self, tmp_path):
        json_path = _make_song(tmp_path)
        before = json.loads(json_path.read_text())

        result = repair.repair_song_json(str(json_path), "pftl", "532")

        assert result["changed"] is True
        after = json.loads(json_path.read_text())
        assert after["window"] != before["window"]
        # Unrelated fields must survive untouched.
        assert after["title"] == "Test Song"

    def test_no_change_when_already_correct(self, tmp_path):
        json_path = _make_song(tmp_path)
        # Run once to correct it...
        repair.repair_song_json(str(json_path), "pftl", "532")
        # ...then again: should be a no-op the second time.
        result = repair.repair_song_json(str(json_path), "pftl", "532")
        assert result["changed"] is False

    def test_returns_none_when_no_raw_pages_found(self, tmp_path):
        song_dir = tmp_path / "532"
        song_dir.mkdir()
        json_path = song_dir / "pftl-532.json"
        json_path.write_text(json.dumps({"title": "No raw pages", "window": [0, 0, 1, 1]}))

        result = repair.repair_song_json(str(json_path), "pftl", "532")
        assert result is None

    def test_returns_none_when_json_has_no_window_field(self, tmp_path):
        json_path = _make_song(tmp_path)
        json_path.write_text(json.dumps({"title": "No window field here"}))

        result = repair.repair_song_json(str(json_path), "pftl", "532")
        assert result is None


class TestMain:
    def test_walks_ehsf_root_and_reports_count(self, tmp_path, capsys):
        _make_song(tmp_path / "pftl", number="532")
        _make_song(tmp_path / "pftl", number="557", pages=(
            (100, 100, 900, 900),
            (100, 100, 900, 300),
        ))

        import sys
        old_argv = sys.argv
        sys.argv = ["repair_song_image_windows.py", str(tmp_path)]
        try:
            repair.main()
        finally:
            sys.argv = old_argv

        out = capsys.readouterr().out
        assert "corrected 2" in out
