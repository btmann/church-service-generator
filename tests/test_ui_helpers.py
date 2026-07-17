"""Unit tests for ui.py's pure/near-pure helper functions.

ui.py is a Streamlit script: it calls st.set_page_config(), st.markdown(),
etc. at module scope, so `import ui` executes the whole page and fails
outside of a live `streamlit run` session (see conftest.extract_functions
docstring). These tests extract just the target functions' source and exec
them standalone with a fake `streamlit` module and real os/json/Path.
"""
import json
import os
from pathlib import Path

import pytest

from conftest import ROOT, extract_functions, make_fake_streamlit

UI_PY = ROOT / "ui.py"


def load(names, extra_globals=None):
    base_globals = {"os": os, "json": json, "Path": Path}
    if extra_globals:
        base_globals.update(extra_globals)
    return extract_functions(UI_PY, names, base_globals)


class TestShouldKeepExisting:
    def test_keep_manual_false_always_false(self):
        fake_st = make_fake_streamlit(session_state={"leader": "Bob"})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("leader", "Alice", keep_manual=False) is False

    def test_non_empty_string_is_kept(self):
        fake_st = make_fake_streamlit(session_state={"leader": "Bob"})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("leader", "Alice", keep_manual=True) is True

    def test_blank_string_is_not_kept(self):
        fake_st = make_fake_streamlit(session_state={"leader": "   "})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("leader", "Alice", keep_manual=True) is False

    def test_missing_key_is_not_kept(self):
        fake_st = make_fake_streamlit(session_state={})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("leader", "Alice", keep_manual=True) is False

    def test_nonzero_number_differing_from_incoming_is_kept(self):
        fake_st = make_fake_streamlit(session_state={"reading": 3})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("reading", 5, keep_manual=True) is True

    def test_number_equal_to_incoming_is_not_kept(self):
        fake_st = make_fake_streamlit(session_state={"reading": 5})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("reading", 5, keep_manual=True) is False

    def test_zero_number_is_not_kept(self):
        fake_st = make_fake_streamlit(session_state={"reading": 0})
        fn = load(["should_keep_existing"], {"st": fake_st})["should_keep_existing"]
        assert fn("reading", 5, keep_manual=True) is False


class TestGetAvailableTemplates:
    def test_lists_json_files_sorted_without_extension(self, tmp_path):
        (tmp_path / "sunday-am.json").write_text("{}")
        (tmp_path / "wednesday.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("ignore me")
        fn = load(["get_available_templates"], {"TEMPLATES_ROOT": str(tmp_path) + "/"})["get_available_templates"]
        assert fn() == ["sunday-am", "wednesday"]

    def test_missing_directory_returns_empty_list(self, tmp_path):
        fn = load(["get_available_templates"], {"TEMPLATES_ROOT": str(tmp_path / "nope") + "/"})["get_available_templates"]
        assert fn() == []


class TestLoadTemplate:
    def test_loads_order_list(self, tmp_path):
        (tmp_path / "sunday-am.json").write_text(json.dumps({"order": [{"type": "welcome"}]}))
        fn = load(["load_template"], {"TEMPLATES_ROOT": str(tmp_path) + "/"})["load_template"]
        assert fn("sunday-am") == [{"type": "welcome"}]

    def test_non_list_order_raises_valueerror(self, tmp_path):
        (tmp_path / "bad.json").write_text(json.dumps({"order": {"not": "a list"}}))
        fn = load(["load_template"], {"TEMPLATES_ROOT": str(tmp_path) + "/"})["load_template"]
        with pytest.raises(ValueError):
            fn("bad")

    def test_missing_order_key_defaults_to_empty_list(self, tmp_path):
        (tmp_path / "empty.json").write_text(json.dumps({}))
        fn = load(["load_template"], {"TEMPLATES_ROOT": str(tmp_path) + "/"})["load_template"]
        assert fn("empty") == []


class TestMakeCustomTemplateItem:
    def test_welcome(self):
        fn = load(["make_custom_template_item"])["make_custom_template_item"]
        item = fn("welcome", 1)
        assert item["id"] == "welcome-1"
        assert item["position"] == "Announcements"

    def test_song(self):
        fn = load(["make_custom_template_item"])["make_custom_template_item"]
        item = fn("song", 2)
        assert item == {"type": "song", "id": "song-2", "position": "Song Leader"}

    def test_ls_am_includes_reading_default(self):
        fn = load(["make_custom_template_item"])["make_custom_template_item"]
        item = fn("ls-am", 3)
        assert item["reading"] == 0
        assert item["id"] == "ls-3"

    @pytest.mark.parametrize("item_type", ["sermon", "lesson", "report"])
    def test_preach_types_share_position(self, item_type):
        fn = load(["make_custom_template_item"])["make_custom_template_item"]
        item = fn(item_type, 4)
        assert item["position"] == "Preach"
        assert item["id"] == f"{item_type}-4"

    def test_unknown_type_falls_back_to_minimal_item(self):
        fn = load(["make_custom_template_item"])["make_custom_template_item"]
        assert fn("mystery", 9) == {"type": "mystery", "id": "mystery-9"}


class TestGetSongPositions:
    def test_extracts_song_items_by_id(self):
        fn = load(["get_song_positions"])["get_song_positions"]
        items = [
            {"type": "song", "id": "song-1"},
            {"type": "song-music", "id": "song-2"},
            {"type": "welcome", "id": "welcome-1"},
            "not-a-dict",
        ]
        result = fn(items)
        assert set(result.keys()) == {"song-1", "song-2"}

    def test_empty_list(self):
        fn = load(["get_song_positions"])["get_song_positions"]
        assert fn([]) == {}


class TestGetLeaderPositions:
    def test_extracts_by_position_name(self):
        fn = load(["get_leader_positions"])["get_leader_positions"]
        items = [
            {"type": "song", "position": "Song Leader"},
            {"type": "welcome"},
            {"not": "a position field"},
        ]
        result = fn(items)
        assert list(result.keys()) == ["Song Leader"]

    def test_non_dict_items_are_skipped(self):
        fn = load(["get_leader_positions"])["get_leader_positions"]
        assert fn([None, 42, "x"]) == {}


class TestBuildDefaultReadings:
    def test_reading_type(self):
        fn = load(["build_default_readings"])["build_default_readings"]
        result = fn([{"type": "reading", "id": "reading-1"}])
        assert result == {"reading-1": {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}}

    @pytest.mark.parametrize("item_type", ["ls-am", "collection"])
    def test_ls_and_collection_types(self, item_type):
        fn = load(["build_default_readings"])["build_default_readings"]
        result = fn([{"type": item_type, "id": "x-1"}])
        assert result == {"x-1": {"reading": ""}}

    @pytest.mark.parametrize("item_type", ["sermon", "lesson", "report"])
    def test_title_types(self, item_type):
        fn = load(["build_default_readings"])["build_default_readings"]
        result = fn([{"type": item_type, "id": "x-1"}])
        assert result["x-1"]["title"] == ""

    def test_items_without_id_are_skipped(self):
        fn = load(["build_default_readings"])["build_default_readings"]
        assert fn([{"type": "reading"}]) == {}

    def test_unhandled_type_ignored(self):
        fn = load(["build_default_readings"])["build_default_readings"]
        assert fn([{"type": "prayer", "id": "prayer-1"}]) == {}


class TestSongSourceGroup:
    def test_blank_source_folder_defaults_to_ehsf(self):
        fn = load(["song_source_group"])["song_source_group"]
        assert fn({"source_folder": ""}) == "ehsf"

    def test_esp_prefixed_folder_keeps_two_levels(self):
        fn = load(["song_source_group"])["song_source_group"]
        assert fn({"source_folder": "esp/pftl/012"}) == "ehsf/esp/pftl"

    def test_plain_book_folder_keeps_one_level(self):
        fn = load(["song_source_group"])["song_source_group"]
        assert fn({"source_folder": "pftl/012"}) == "ehsf/pftl"
