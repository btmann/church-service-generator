import json

import pytest

from tools.build_song_lookup import (
    build_lookup,
    infer_book_and_number,
    load_json_with_fallback,
    normalize_title,
    source_book_folder,
)


class TestNormalizeTitle:
    def test_collapses_whitespace_and_lowercases(self):
        assert normalize_title("  Amazing   Grace \n") == "amazing grace"

    def test_empty_string(self):
        assert normalize_title("") == ""


class TestInferBookAndNumber:
    def test_filename_prefix_wins(self):
        book, number = infer_book_and_number({}, ("pftl", "012"), "pftl-012")
        assert (book, number) == ("pftl", "012")

    def test_falls_back_to_song_json_number(self):
        book, number = infer_book_and_number({"number": 42}, ("pftl", "042"), "song")
        assert (book, number) == ("pftl", "42")

    def test_falls_back_to_rel_parts_when_no_number(self):
        # rel_parts mirrors what build_lookup passes: the full relative path
        # parts *including* the filename, e.g. esp/pftl/012/pftl-012.json.
        book, number = infer_book_and_number({}, ("esp", "pftl", "012", "pftl-012.json"), "song")
        assert (book, number) == ("pftl", "012")

    def test_unknown_book_when_no_path_info(self):
        book, number = infer_book_and_number({}, (), "song")
        assert (book, number) == ("unknown", "0")


class TestSourceBookFolder:
    def test_three_or_more_parts_drops_last_two(self):
        assert source_book_folder(("esp", "pftl", "012", "pftl-012.json")) == "esp/pftl"

    def test_single_part(self):
        assert source_book_folder(("pftl",)) == "pftl"

    def test_empty(self):
        assert source_book_folder(()) == "unknown"


class TestLoadJsonWithFallback:
    def test_loads_utf8(self, tmp_path):
        f = tmp_path / "song.json"
        f.write_text(json.dumps({"title": "Grace"}), encoding="utf-8")
        assert load_json_with_fallback(f) == {"title": "Grace"}

    def test_falls_back_to_latin1(self, tmp_path):
        f = tmp_path / "song.json"
        f.write_bytes('{"title": "45\xb0"}'.encode("latin-1"))
        assert load_json_with_fallback(f) == {"title": "45\xb0"}

    def test_missing_file_returns_none(self, tmp_path):
        assert load_json_with_fallback(tmp_path / "missing.json") is None

    def test_malformed_json_returns_none(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not json", encoding="utf-8")
        assert load_json_with_fallback(f) is None


class TestBuildLookup:
    def test_builds_entries_from_tree(self, tmp_path):
        song_dir = tmp_path / "pftl" / "012"
        song_dir.mkdir(parents=True)
        (song_dir / "pftl-012.json").write_text(json.dumps({"title": "Amazing Grace"}))

        song_dir2 = tmp_path / "phss" / "074"
        song_dir2.mkdir(parents=True)
        (song_dir2 / "phss-074.json").write_text(json.dumps({"title": "Holy, Holy, Holy"}))

        result = build_lookup(tmp_path)
        assert result["song_count"] == 2
        titles = {s["title"] for s in result["songs"]}
        assert titles == {"Amazing Grace", "Holy, Holy, Holy"}

    def test_skips_entries_without_title(self, tmp_path):
        song_dir = tmp_path / "pftl" / "012"
        song_dir.mkdir(parents=True)
        (song_dir / "pftl-012.json").write_text(json.dumps({"number": "012"}))

        result = build_lookup(tmp_path)
        assert result["song_count"] == 0

    def test_skips_the_generated_index_file_itself(self, tmp_path):
        (tmp_path / "song-search-index.json").write_text(json.dumps({"songs": []}))
        result = build_lookup(tmp_path)
        assert result["song_count"] == 0

    def test_dedupes_identical_title_book_number_folder(self, tmp_path):
        song_dir = tmp_path / "pftl" / "012"
        song_dir.mkdir(parents=True)
        (song_dir / "pftl-012.json").write_text(json.dumps({"title": "Amazing Grace"}))
        (song_dir / "pftl-012-dup.json").write_text(json.dumps({"title": "Amazing Grace"}))

        result = build_lookup(tmp_path)
        # Both files live in the same folder and resolve to the same
        # (title_key, book, number, source_folder) key.
        assert result["song_count"] == 1

    def test_empty_tree_returns_zero_songs(self, tmp_path):
        result = build_lookup(tmp_path)
        assert result["song_count"] == 0
        assert result["songs"] == []
