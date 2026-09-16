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


class TestTranslateReferenceToSpanish:
    """The getScriptureReading API (which provided both languages) is being
    retired in favor of a local CSV schedule that only has English
    references -- this fills in the Spanish side by translating just the
    book name."""

    def test_translates_known_book(self):
        assert worship.translate_reference_to_spanish("Romans 3:21-28") == "Romanos 3:21-28"

    def test_translates_numbered_book(self):
        assert worship.translate_reference_to_spanish("1 Corinthians 10:1-11") == "1 Corintios 10:1-11"

    def test_tolerates_source_spreadsheet_typos(self):
        # "Ezekial"/"Zehariah" are literal misspellings present in the
        # source spreadsheet -- translation must not choke on them.
        assert worship.translate_reference_to_spanish("Ezekial 34:11-16") == "Ezequiel 34:11-16"
        assert worship.translate_reference_to_spanish("Zehariah 13:7-9") == "Zacarías 13:7-9"

    def test_unknown_book_falls_back_to_english(self):
        # Better to show the English book name than to fail the whole
        # autofill over one book missing from SPANISH_BOOK_NAMES.
        assert worship.translate_reference_to_spanish("Obadiah 1:1-4") == "Obadiah 1:1-4"


class TestLoadLocalScriptureSchedule:
    """Reads Bug_folder/*.csv -- the replacement for the retired
    getScriptureReading API. See load_local_scripture_schedule's docstring
    for the {date: {"am", "pm"}} shape and multi-file/collision handling.
    """

    def _write_csv(self, tmp_path, filename, rows):
        path = tmp_path / filename
        lines = ["Date,Morning Readings (Apostles),Evening Readings (Prophets),"]
        for date, am, pm in rows:
            lines.append(f"{date},{am},{pm},")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_parses_dates_and_both_columns(self, tmp_path):
        self._write_csv(tmp_path, "Scripture Reading 2026.csv", [("2026-09-13", "Romans 3:21-28", "Genesis 22:9-18")])
        schedule = worship.load_local_scripture_schedule(str(tmp_path))
        assert schedule["2026-09-13"] == {"am": "Romans 3:21-28", "pm": "Genesis 22:9-18"}

    def test_ignores_unrelated_csv_files(self, tmp_path):
        # The schedule only matches "Scripture Reading*.csv" -- assets/ can
        # hold other, unrelated CSVs without them being misread as a
        # reading schedule.
        self._write_csv(tmp_path, "other-data.csv", [("2026-09-13", "Should Not Load", "Should Not Load")])
        assert worship.load_local_scripture_schedule(str(tmp_path)) == {}

    def test_later_file_wins_on_date_collision(self, tmp_path):
        self._write_csv(tmp_path, "Scripture Reading 2026-a.csv", [("2026-09-13", "Old AM", "Old PM")])
        self._write_csv(tmp_path, "Scripture Reading 2026-b.csv", [("2026-09-13", "New AM", "New PM")])
        schedule = worship.load_local_scripture_schedule(str(tmp_path))
        assert schedule["2026-09-13"] == {"am": "New AM", "pm": "New PM"}

    def test_empty_folder_gives_empty_schedule(self, tmp_path):
        assert worship.load_local_scripture_schedule(str(tmp_path)) == {}


class TestFetchReadings:
    """fetch_readings() now reads the local schedule instead of calling the
    (retired) getScriptureReading API."""

    def _patch_schedule(self, monkeypatch, schedule):
        monkeypatch.setattr(worship, "load_local_scripture_schedule", lambda: schedule)

    def test_sun_am_uses_morning_reading(self, monkeypatch):
        self._patch_schedule(monkeypatch, {"2026-09-13": {"am": "Romans 3:21-28", "pm": "Genesis 22:9-18"}})
        result = worship.fetch_readings("2026-09-13", {}, "Sun - AM")
        assert result == {
            "readings": {
                "reading-1": {
                    "lang": [
                        {"passage": "Romans 3:21-28"},
                        {"passage": "Romanos 3:21-28"},
                    ]
                }
            }
        }

    def test_sun_pm_uses_evening_reading(self, monkeypatch):
        self._patch_schedule(monkeypatch, {"2026-09-13": {"am": "Romans 3:21-28", "pm": "Genesis 22:9-18"}})
        result = worship.fetch_readings("2026-09-13", {}, "Sun - PM")
        assert result["readings"]["reading-1"]["lang"][0]["passage"] == "Genesis 22:9-18"
        assert result["readings"]["reading-1"]["lang"][1]["passage"] == "Génesis 22:9-18"

    def test_date_not_in_schedule_gives_no_reading_not_an_error(self, monkeypatch):
        self._patch_schedule(monkeypatch, {})
        result = worship.fetch_readings("2026-09-13", {}, "Sun - AM")
        assert result == {"readings": {}}
        assert "_error" not in result

    def test_service_type_not_covered_by_schedule_gives_no_reading(self, monkeypatch):
        self._patch_schedule(monkeypatch, {"2026-09-13": {"am": "Romans 3:21-28", "pm": "Genesis 22:9-18"}})
        assert worship.fetch_readings("2026-09-13", {}, "Wed") == {"readings": {}}
        assert worship.fetch_readings("2026-09-13", {}, "Gospel Meeting") == {"readings": {}}


class TestSampleFixture:
    def test_sample_json_matches_generate_songs_shape(self, sample_service_spec):
        song_items = [i for i in sample_service_spec["items"] if i["type"] == "song"]
        assert len(song_items) == 2
        assert sample_service_spec["language"] == "bil"
