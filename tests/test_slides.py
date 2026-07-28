import sys
from pathlib import Path

import pytest

import slides


@pytest.fixture(autouse=True)
def reset_ehsf_root():
    """slides.EHSF_ROOT is process-global; keep tests from leaking into each other."""
    original = slides.EHSF_ROOT
    yield
    slides.set_ehsf_root(original)


class TestLoadJsonSafe:
    def test_loads_utf8_json(self, tmp_path):
        f = tmp_path / "song.json"
        f.write_text('{"title": "Amazing Grace"}', encoding="utf-8")
        assert slides.load_json_safe(str(f)) == {"title": "Amazing Grace"}

    def test_falls_back_to_latin1_for_legacy_credit_lines(self, tmp_path):
        # Regression: a Windows packaged build crashed with
        # UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa9 (the
        # latin-1 copyright sign) when a page read a generated song JSON
        # with a hardcoded `open(path, encoding="utf-8")` instead of this
        # fallback-aware loader. 0xa9 is invalid UTF-8 but valid latin-1.
        f = tmp_path / "song.json"
        f.write_bytes('{"credits": "\xa9 1985 Word Music"}'.encode("latin-1"))
        assert slides.load_json_safe(str(f)) == {"credits": "\xa9 1985 Word Music"}

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            slides.load_json_safe(str(tmp_path / "missing.json"))


class TestIsPftlCopyright:
    def test_true_when_paperless_present(self):
        assert slides.is_pftl_copyright("Copyright Paperless Hymnal") is True

    def test_false_when_absent(self):
        assert slides.is_pftl_copyright("Public Domain") is False

    def test_false_for_empty_string(self):
        assert slides.is_pftl_copyright("") is False


class TestIsPftlNumber:
    @pytest.mark.parametrize("text", ["1", "12", "123"])
    def test_true_for_short_numeric(self, text):
        assert slides.is_pftl_number(text) is True

    def test_false_for_long_numeric(self):
        assert slides.is_pftl_number("1234") is False

    def test_false_for_non_numeric(self):
        assert slides.is_pftl_number("abc") is False

    def test_false_for_empty_string(self):
        assert slides.is_pftl_number("") is False


class TestIsPftlTitle:
    def test_true_for_leading_digit_single_line(self):
        assert slides.is_pftl_title("1 - Amazing Grace") is True

    def test_true_for_leading_c(self):
        assert slides.is_pftl_title("chorus - Amazing Grace") is True

    def test_true_for_amen(self):
        assert slides.is_pftl_title("Amen") is True

    def test_true_for_leading_s(self):
        assert slides.is_pftl_title("Song title") is True

    def test_false_for_multiline(self):
        assert slides.is_pftl_title("1 - Amazing Grace\nverse continues") is False

    def test_false_for_empty_string(self):
        assert slides.is_pftl_title("") is False


class TestIsPftlLyric:
    def test_true_for_leading_digit_multiline(self):
        assert slides.is_pftl_lyric("1\nAmazing grace how sweet the sound") is True

    def test_false_for_single_line(self):
        assert slides.is_pftl_lyric("1 Amazing grace") is False

    def test_false_for_non_digit_start(self):
        assert slides.is_pftl_lyric("Amazing\ngrace") is False

    def test_false_for_empty_string(self):
        assert slides.is_pftl_lyric("") is False


class TestEhsfJoin:
    def test_joins_under_configured_root(self):
        slides.set_ehsf_root("ehsf")
        assert slides.ehsf_join("pftl", "012") == "ehsf/pftl/012"

    def test_reflects_overridden_root(self):
        slides.set_ehsf_root("/tmp/custom-root")
        assert slides.ehsf_join("pftl", "012") == "/tmp/custom-root/pftl/012"


class TestGetSongPaths:
    def test_regular_book_passthrough(self):
        song, pathname, basename, rawname = slides.get_song_paths("pftl", 12)
        assert song == "012"
        assert pathname.endswith("pftl/012")
        assert basename.endswith("pftl/012/pftl-012")
        assert rawname.endswith("pftl/012/raw/pftl-012")

    def test_shs_34_maps_to_eh_109(self):
        song, pathname, basename, rawname = slides.get_song_paths("shs", 34)
        assert song == "109"
        assert pathname.endswith("eh/109")

    def test_shs_mapped_via_lookup_table(self):
        # shs2phss["1"] == 74
        song, pathname, basename, rawname = slides.get_song_paths("shs", 1)
        assert song == "074"
        assert pathname.endswith("phss/074")

    def test_shs_number_not_in_table_passes_through(self):
        song, pathname, basename, rawname = slides.get_song_paths("shs", 9999)
        assert song == "9999"
        assert pathname.endswith("shs/9999")


class TestGetSongPathsNew:
    def test_builds_eng_and_esp_paths(self):
        song, paths = slides.get_song_paths_new("pftl", 12)
        assert song == "012"
        assert paths["engpath"].endswith("pftl/012")
        assert paths["engbase"].endswith("pftl/012/pftl-012")
        assert paths["esppath"].endswith("esp/pftl/012")
        assert paths["espbase"].endswith("esp/pftl/012/pftl-012")

    def test_shs_34_maps_to_eh_109(self):
        song, paths = slides.get_song_paths_new("shs", 34)
        assert song == "109"
        assert paths["engpath"].endswith("eh/109")


class TestGetItem:
    def test_returns_value_when_present(self):
        assert slides.get_item({"verses": [1, 2]}, "verses") == [1, 2]

    def test_returns_none_when_absent(self):
        assert slides.get_item({}, "verses") is None


class TestVerseIter:
    def test_explicit_verse_list(self):
        meta = {"verses": {"1": [1, 2], "2": [3, 4], "3": [5, 6]}}
        result = list(slides.verse_iter(meta, [1, 3]))
        assert result == [
            ("1", [1, 2], False),
            ("3", [5, 6], True),
        ]

    def test_none_verses_iterates_all_meta_verses_in_order(self):
        meta = {"verses": {"1": [1, 2], "2": [3, 4]}}
        result = list(slides.verse_iter(meta, None))
        assert result == [
            ("1", [1, 2], False),
            ("2", [3, 4], False),
        ]

    def test_none_verses_flags_skip_on_gap(self):
        meta = {"verses": {"1": [1, 2], "3": [5, 6]}}
        result = list(slides.verse_iter(meta, None))
        assert result == [
            ("1", [1, 2], False),
            ("3", [5, 6], True),
        ]


class TestSetEsp:
    def test_no_esp_file_returns_none_and_eng_basename(self, tmp_path):
        paths = {
            "engbase": str(tmp_path / "pftl-012"),
            "espbase": str(tmp_path / "esp" / "pftl-012"),
        }
        esp, basename = slides.set_esp(paths, "eng")
        assert esp is None
        assert basename == paths["engbase"]

    def test_esp_file_present_but_language_eng_still_uses_eng_basename(self, tmp_path):
        espjson = tmp_path / "esp-pftl-012.json"
        espjson.write_text('{"title": "Titulo"}', encoding="utf-8")
        paths = {"engbase": str(tmp_path / "pftl-012"), "espbase": str(espjson).removesuffix(".json")}
        esp, basename = slides.set_esp(paths, "eng")
        assert esp is None
        assert basename == paths["engbase"]

    def test_esp_file_present_and_language_esp_loads_it(self, tmp_path):
        espjson = tmp_path / "esp-pftl-012.json"
        espjson.write_text('{"title": "Titulo"}', encoding="utf-8")
        paths = {"engbase": str(tmp_path / "pftl-012"), "espbase": str(espjson).removesuffix(".json")}
        esp, basename = slides.set_esp(paths, "esp")
        assert esp == {"title": "Titulo"}
        assert basename == paths["espbase"]

    def test_esp_file_present_and_language_bil_loads_it(self, tmp_path):
        espjson = tmp_path / "esp-pftl-012.json"
        espjson.write_text('{"title": "Titulo"}', encoding="utf-8")
        paths = {"engbase": str(tmp_path / "pftl-012"), "espbase": str(espjson).removesuffix(".json")}
        esp, basename = slides.set_esp(paths, "bil")
        assert esp == {"title": "Titulo"}


class TestGetDisplayNumber:
    @pytest.mark.parametrize("book,song,expected", [
        ("shs", "5", "S-5"),
        ("phss", "74", "PHSS-74"),
        ("eh", "109", "EH-109"),
        ("pftl", "12", "12"),
    ])
    def test_book_prefix(self, book, song, expected):
        assert slides.getDisplayNumber({"book": book, "song": song}) == expected


class TestGetValidReadingIndex:
    def test_missing_reading_key_returns_none(self):
        assert slides.get_valid_reading_index({}) is None

    def test_none_value_returns_none(self):
        assert slides.get_valid_reading_index({"reading": None}) is None

    def test_blank_string_returns_none(self):
        assert slides.get_valid_reading_index({"reading": "   "}) is None

    def test_numeric_string_returns_int(self):
        assert slides.get_valid_reading_index({"reading": "2"}) == 2

    def test_int_value_returns_int(self):
        assert slides.get_valid_reading_index({"reading": 3}) == 3

    def test_non_numeric_string_returns_none(self):
        assert slides.get_valid_reading_index({"reading": "abc"}) is None


class TestGetIsodate:
    def test_uses_explicit_time(self):
        service = {"isodate": "2021-06-09", "time": "19:30:00"}
        assert slides.get_isodate(service, "isodate") == "2021-06-09T19:30:00"

    def test_defaults_sunday_morning(self):
        service = {"isodate": "2021-06-13", "service": "Sunday Morning"}
        assert slides.get_isodate(service, "isodate") == "2021-06-13T10:00:00"

    def test_defaults_sunday_evening(self):
        service = {"isodate": "2021-06-13", "service": "Sunday Evening"}
        assert slides.get_isodate(service, "isodate") == "2021-06-13T18:00:00"

    def test_defaults_other_service_to_evening_meeting_time(self):
        service = {"isodate": "2021-06-16", "service": "Wednesday"}
        assert slides.get_isodate(service, "isodate") == "2021-06-16T19:30:00"

    def test_missing_time_and_service_raises_keyerror(self):
        with pytest.raises(KeyError):
            slides.get_isodate({"isodate": "2021-06-16"}, "isodate")


class TestParseIsodate:
    def test_short_isodate_delegates_to_get_isodate(self):
        service = {"isodate": "2021-06-13", "time": "19:30:00"}
        assert slides.parse_isodate(service) == "2021-06-13T19:30:00"

    def test_long_isodate_used_verbatim(self):
        service = {"isodate": "2021-06-13T19:30:00"}
        assert slides.parse_isodate(service) == "2021-06-13T19:30:00"

    def test_date_key_delegates_to_get_isodate(self):
        service = {"date": "2021-06-13", "time": "19:30:00"}
        assert slides.parse_isodate(service) == "2021-06-13T19:30:00"

    def test_neither_key_present_raises_nameerror(self):
        # Known bug: the fallback branch reads an undefined name `file`
        # (leftover from a Python 2 `file` builtin) instead of returning a
        # sentinel like "0000-00-00" as the comment suggests.
        with pytest.raises(NameError):
            slides.parse_isodate({})


class TestSetCropWindow:
    def test_raises_clear_error_on_empty_crop(self):
        # Regression: an empty `crop` dict (e.g. no PNGs were found for a
        # song) used to blow up with an opaque
        # `UnboundLocalError: cannot access local variable 'iar'` deep in
        # set_window(), instead of a message pointing at the actual cause.
        with pytest.raises(ValueError, match="No slide images found"):
            slides.set_crop_window({}, {})

    def test_computes_window_from_single_crop(self):
        crop = {1: {"top": 0.1, "bot": 0.9, "left": 0.2, "right": 0.8, "width": 6, "height": 4}}
        meta = {}
        window, padding = slides.set_crop_window(crop, meta)
        assert window == [0.1, 0.2, pytest.approx(0.6), pytest.approx(0.8)]
        assert padding == 0.95
        assert "window" in meta


class TestFindSoffice:
    def test_prefers_which_result(self, monkeypatch):
        monkeypatch.setattr(slides.shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)
        assert slides.find_soffice() == "/usr/bin/soffice"

    def test_falls_back_to_windows_path(self, monkeypatch):
        monkeypatch.setattr(slides.shutil, "which", lambda cmd: None)
        windows_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
        monkeypatch.setattr(slides.os.path, "exists", lambda p: p == windows_path)
        assert slides.find_soffice() == windows_path

    def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr(slides.shutil, "which", lambda cmd: None)
        monkeypatch.setattr(slides.os.path, "exists", lambda p: False)
        assert slides.find_soffice() is None


@pytest.mark.skipif(slides.find_soffice() is None, reason="requires LibreOffice (soffice) to be installed")
class TestExportBilPngs:
    def _make_bil_pptx(self, tmp_path, book, number, notes):
        from pptx import Presentation
        from pptx.util import Inches

        song = f"{number:03d}"
        prs = Presentation()
        blank = prs.slide_layouts[6]
        prs.slides.add_slide(blank)  # slide 1: metadata slide, must be skipped
        song_slide = prs.slides.add_slide(blank)
        song_slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "Hola"
        song_slide.notes_slide.notes_text_frame.text = notes

        bildir = tmp_path / "esp" / book / "bil"
        bildir.mkdir(parents=True)
        pptx_path = bildir / f"{book}-{song}-bil.pptx"
        prs.save(str(pptx_path))
        return pptx_path

    def test_exports_png_at_notes_specified_size_and_skips_metadata_slide(self, tmp_path):
        self._make_bil_pptx(tmp_path, "test", 999, "400x300xtest/test-999-001.png")
        slides.set_ehsf_root(str(tmp_path))

        exported = slides.export_bil_pngs("test", 999)

        assert exported == 1
        out_path = tmp_path / "esp" / "test" / "bil" / "test" / "test-999-001.png"
        assert out_path.exists()
        from PIL import Image
        assert Image.open(out_path).size == (400, 300)

    def test_missing_pptx_raises(self, tmp_path):
        slides.set_ehsf_root(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            slides.export_bil_pngs("test", 999)


@pytest.mark.skipif(sys.platform == "win32", reason="covers the darwin/linux home-dir install path")
class TestInstallBundledFonts:
    def test_installs_bundled_fonts_into_user_fonts_dir(self, tmp_path, monkeypatch):
        # Regression: LibreOffice silently substitutes a fallback font when
        # Alegreya Sans isn't installed on the machine, which wraps subtitle
        # text differently and (combined with "auto-fit shape to text")
        # overlaps it with the slide content below. Installing the bundled
        # font files fixes this; this test checks the install mechanics
        # without touching the real user font directory.
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "AlegreyaSans-Medium.otf").write_bytes(b"fake-font-data")
        monkeypatch.setattr(slides, "assetRoot", str(assets_dir) + "/")

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

        results = slides.install_bundled_fonts()

        assert len(results) == 1
        installed_path = Path(results[0][0])
        expected_dir = (
            home_dir / "Library" / "Fonts" if sys.platform == "darwin" else home_dir / ".local" / "share" / "fonts"
        )
        assert installed_path.parent == expected_dir
        assert installed_path.read_bytes() == b"fake-font-data"

    def test_no_bundled_fonts_returns_empty_list(self, tmp_path, monkeypatch):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        monkeypatch.setattr(slides, "assetRoot", str(assets_dir) + "/")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        assert slides.install_bundled_fonts() == []


class TestRepairPptxZipSeparators:
    def _make_zip(self, path, names):
        import zipfile
        with zipfile.ZipFile(path, "w") as zf:
            for name in names:
                zf.writestr(name, b"<xml/>")

    def test_repairs_backslash_separators(self, tmp_path):
        # Regression: some Windows export/re-packaging tools zip .pptx
        # internals with "\" instead of the ZIP/OPC-required "/", so
        # python-pptx can't find _rels/.rels and fails with a cryptic
        # KeyError instead of opening the file.
        import zipfile
        path = tmp_path / "broken.pptx"
        self._make_zip(path, [r"_rels\.rels", r"ppt\presentation.xml"])

        assert slides.repair_pptx_zip_separators(str(path)) is True

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert "_rels/.rels" in names
        assert "ppt/presentation.xml" in names
        assert not any("\\" in n for n in names)

    def test_noop_when_already_compliant(self, tmp_path):
        path = tmp_path / "fine.pptx"
        self._make_zip(path, ["_rels/.rels", "ppt/presentation.xml"])

        assert slides.repair_pptx_zip_separators(str(path)) is False
