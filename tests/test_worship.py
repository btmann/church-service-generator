import json

import pytest

import worship


class TestLoadJsonSafe:
    def test_loads_utf8_json(self, tmp_path):
        f = tmp_path / "spec.json"
        f.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
        assert worship.load_json_safe(str(f)) == {"hello": "world"}

    def test_falls_back_to_latin1(self, tmp_path):
        f = tmp_path / "spec.json"
        # A degree sign encodes differently in latin-1 vs utf-8; write raw
        # latin-1 bytes so the utf-8 decode attempt fails and the fallback
        # kicks in.
        f.write_bytes('{"desc": "45\xb0"}'.encode("latin-1"))
        assert worship.load_json_safe(str(f)) == {"desc": "45\xb0"}

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            worship.load_json_safe(str(tmp_path / "does-not-exist.json"))

    def test_malformed_json_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            worship.load_json_safe(str(f))


class TestGetSpecBase:
    def test_builds_expected_paths(self):
        specpath, specbase, jsonbase = worship.get_spec_base("2021-06-09", "19:30:00")
        assert specpath == "worship/specs/2021/06/09/1930"
        assert specbase == "worship/specs/2021/06/09/1930/20210609-1930"
        assert jsonbase == "worship/2021/20210609-1930"

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            worship.get_spec_base("not-a-date", "19:30:00")


class TestGenerateWorshipSpec:
    def test_builds_spec_dict(self):
        spec = worship.generate_worship_spec("2021-06-09", "19:30:00", "sunday-am", "bil", "Sun - AM")
        assert spec == {
            "isodate": "2021-06-09T19:30:00",
            "template": "sunday-am",
            "language": "bil",
            "type": "Sun - AM",
        }


class TestGenerateSongs:
    def test_picks_up_song_and_song_music_items(self):
        items = [
            {"type": "song", "id": "song-1"},
            {"type": "song-music", "id": "song-2"},
            {"type": "welcome", "id": "welcome-1"},
        ]
        result = worship.generate_songs(items)
        assert set(result["songs"].keys()) == {"song-1", "song-2"}
        assert result["songs"]["song-1"] == {
            "book": "pftl", "song": "", "verses": [], "chorus": [], "coda": 0,
        }

    def test_empty_items_returns_empty_songs(self):
        assert worship.generate_songs([]) == {"songs": {}}


class TestGenerateLeaders:
    def test_picks_up_items_with_position(self):
        items = [
            {"type": "song", "id": "song-1", "position": "Song Leader"},
            {"type": "welcome", "id": "welcome-1"},
        ]
        result = worship.generate_leaders(items)
        assert result == {"leaders": {"Song Leader": ""}}

    def test_no_positions_returns_empty(self):
        assert worship.generate_leaders([{"type": "welcome"}]) == {"leaders": {}}


class TestGenerateReadings:
    def test_reading_type(self):
        items = [{"type": "reading", "id": "reading-1"}]
        result = worship.generate_readings(items)
        assert result == {
            "readings": {"reading-1": {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}}
        }

    def test_ls_am_type(self):
        items = [{"type": "ls-am", "id": "ls-1"}]
        result = worship.generate_readings(items)
        assert result == {"readings": {"ls-1": {"reading": ""}}}

    def test_sermon_type(self):
        items = [{"type": "sermon", "id": "sermon-1"}]
        result = worship.generate_readings(items)
        assert result["readings"]["sermon-1"]["title"] == ""

    def test_unhandled_type_ignored(self):
        items = [{"type": "prayer", "id": "prayer-1"}]
        assert worship.generate_readings(items) == {"readings": {}}


class TestParseReading:
    def test_builds_lang_list(self):
        data = {
            "english": {"book": "Matthew", "reference": "26:27-29"},
            "spanish": {"book": "Mateo", "reference": "26:27-29"},
        }
        result = worship.parse_reading(data)
        assert result == {
            "lang": [
                {"passage": "Matthew 26:27-29"},
                {"passage": "Mateo 26:27-29"},
            ]
        }

    def test_missing_language_key_raises(self):
        with pytest.raises(KeyError):
            worship.parse_reading({"english": {"book": "Matthew", "reference": "1:1"}})


class TestSampleFixture:
    def test_sample_json_matches_generate_songs_shape(self, sample_service_spec):
        song_items = [i for i in sample_service_spec["items"] if i["type"] == "song"]
        assert len(song_items) == 2
        assert sample_service_spec["language"] == "bil"
