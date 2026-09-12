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
        # width/height (6x4, aspect 1.5) is deliberately different from
        # raw_width/raw_height (8x5, aspect 1.6) here: set_crop_window must
        # use the raw canvas aspect ratio for meta['window'], not the
        # cropped-content one, so this catches a regression back to the old
        # cr["width"]/cr["height"] behavior (see TestSetCropWindowUsesRawAspectRatio).
        crop = {1: {"top": 0.1, "bot": 0.9, "left": 0.2, "right": 0.8, "width": 6, "height": 4, "raw_width": 8, "raw_height": 5}}
        meta = {}
        window, padding = slides.set_crop_window(crop, meta)
        assert window == [0.1, 0.2, pytest.approx(0.6), pytest.approx(0.8)]
        assert padding == 0.95
        assert meta["window_orientation"] == "tall"
        assert meta["window"] == pytest.approx([0.125, 0.95, 7.2, 6.0])


class TestSetCropWindowUsesRawAspectRatio:
    """Regression: the final image window size/orientation used to be
    computed from cr["width"]/cr["height"] -- the CROPPED CONTENT box of
    whichever page happened to be last in the crop dict -- instead of the
    constant raw canvas aspect ratio. A song whose last page has notably
    less content than the rest (e.g. a short final verse) produced a wildly
    wrong aspect ratio, shrinking the exported image window (PFTL-557's
    real bug: a normal-sized hymn rendered at ~1.8" tall instead of ~4.7").
    """

    def test_last_page_having_less_content_does_not_skew_the_window(self):
        # Page 1: full-height content. Page 2: same raw canvas, but only
        # half the vertical content (its own cropped-content aspect ratio
        # is very different from page 1's) -- as would happen with a short
        # final verse/refrain on an otherwise normal hymn.
        full_page = {"top": 0.1, "bot": 0.9, "left": 0.0, "right": 1.0, "width": 1000, "height": 800, "raw_width": 1000, "raw_height": 1000}
        short_page = {"top": 0.1, "bot": 0.5, "left": 0.0, "right": 1.0, "width": 1000, "height": 400, "raw_width": 1000, "raw_height": 1000}

        meta_last_is_short = {}
        slides.set_crop_window({1: full_page, 2: short_page}, meta_last_is_short)

        meta_last_is_full = {}
        slides.set_crop_window({1: short_page, 2: full_page}, meta_last_is_full)

        # Regardless of which page happens to be last in the dict, the
        # window must come out the same -- both use the raw canvas ratio.
        assert meta_last_is_short["window"] == pytest.approx(meta_last_is_full["window"])
        assert meta_last_is_short["window_orientation"] == meta_last_is_full["window_orientation"]


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


class TestNoMojibakeInSource:
    """Canary: slides.py/worship.py declare `# encoding: iso-8859-15`, so
    Spanish accented characters must be written as single ISO-8859-15 bytes
    (or \\uXXXX escapes), never as raw UTF-8 multi-byte sequences -- those
    get double-decoded into garbage (e.g. "Oraciï¿œn" instead of "Oración")
    the moment the file is re-saved by a UTF-8-default editor. This has
    regressed silently more than once; catch it before it ships again.
    """

    REPLACEMENT_CHAR_UTF8 = b"\xef\xbf\xbd"
    # The one legitimate use: sanitize_display_text's own cleanup pattern,
    # which intentionally contains this byte sequence to strip it out.
    ALLOWED_CONTEXT = b'cleaned.replace("\xc3\xaf\xc2\xbf\xc2\xbd", "")'

    def _unexpected_occurrences(self, path):
        with open(path, "rb") as f:
            data = f.read()
        count = data.count(self.REPLACEMENT_CHAR_UTF8)
        if self.ALLOWED_CONTEXT in data:
            count -= 1
        return count

    def test_slides_py_has_no_stray_mojibake(self):
        assert self._unexpected_occurrences("slides.py") == 0

    def test_worship_py_has_no_stray_mojibake(self):
        assert self._unexpected_occurrences("worship.py") == 0


class TestAnalyzeImage:
    """Regression: analyze_image() used to be a no-op that always reported
    the full raw image as "content" (top=0, bot=1), which fed a skewed
    aspect ratio into set_window() whenever the source export had uneven
    margins -- causing slides to render "tall" instead of "wide", with no
    margin above the topmost content and excess margin below it.
    """

    def _make_image(self, tmp_path, img_width=1000, img_height=800, content_box=(100, 200, 900, 500)):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (img_width, img_height), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle(content_box, fill="black")
        path = tmp_path / "test.png"
        img.save(path)
        return path

    def test_detects_content_bounds_not_full_image(self, tmp_path):
        path = self._make_image(tmp_path, 1000, 800, content_box=(100, 200, 900, 500))
        result = slides.analyze_image(str(path))

        # Content spans y=200..500 of an 800-tall image, so top/bot should
        # reflect that (with a small safety margin), not 0/1 (full image).
        assert 0 < result["top"] < 0.3
        assert 0.55 < result["bot"] < 0.75
        assert result["width"] < 1000
        assert result["height"] < 800

    def test_blank_image_falls_back_to_full_bounds(self, tmp_path):
        from PIL import Image
        path = tmp_path / "blank.png"
        Image.new("RGB", (400, 300), "white").save(path)

        result = slides.analyze_image(str(path))
        assert result == dict(width=400, height=300, raw_width=400, raw_height=300, top=0, bot=1, staff=-1, left=0, right=1)

    def test_wide_content_yields_wide_aspect_ratio(self, tmp_path):
        # A short, wide content band (like a line of sheet music) should
        # produce a wide (width > height) content aspect ratio, even though
        # the raw image itself might be closer to square/tall due to margins.
        path = self._make_image(tmp_path, 1000, 1000, content_box=(50, 400, 950, 600))
        result = slides.analyze_image(str(path))
        assert result["width"] > result["height"]


class TestSizeImageToWindow:
    def test_crops_to_song_wide_window(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (1000, 800), "white")
        src = tmp_path / "src.png"
        img.save(src)

        basename = str(tmp_path / "pftl-012")
        # window fractions: top=0.1, left=0.05, width=0.9, height=0.6
        slides.size_image_to_window(str(src), None, [0.1, 0.05, 0.9, 0.6], 0.95, basename, None, 1)

        out = Image.open(basename + "-01.png")
        assert out.size == (900, 480)  # 1000*0.9, 800*0.6

    def test_also_saves_raw_copy_when_rawname_given(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (400, 300), "white")
        src = tmp_path / "src.png"
        img.save(src)

        basename = str(tmp_path / "pftl-012")
        rawname = str(tmp_path / "raw" / "pftl-012")
        (tmp_path / "raw").mkdir()
        slides.size_image_to_window(str(src), None, [0, 0, 1, 1], 0.95, basename, rawname, 1)

        assert (tmp_path / "raw" / "pftl-012-01.png").exists()
        assert Image.open(basename + "-01.png").size == (400, 300)


class TestIsBlankCreditLine:
    # Regression: PHSS-277's credits ended with three trailing lines that
    # were each just "_" -- placeholder credit-line shapes left blank in
    # the Sumphonia export template, swept up by process_phss_song_ppt's
    # "every text frame on the title slide" credits extraction.
    @pytest.mark.parametrize("text", ["_", "___", "", "   ", " _ "])
    def test_blank_or_underscore_only(self, text):
        assert slides.is_blank_credit_line(text) is True

    @pytest.mark.parametrize("text", [
        "© 2005 Thankyou Music (admin. by EMI Christian Music Group)",
        "Tune: SPEAK O LORD",
        "_not blank_",
    ])
    def test_real_credit_text(self, text):
        assert slides.is_blank_credit_line(text) is False


class TestProcessPhssSongPptReadsBundledXml:
    """Regression: phss.xml (Sumphonia's hymnal reference database that
    process_phss_song_ppt parses for lyrics/title) used to be read via
    ehsf_join("phss", "phss.xml") -- a location under the user-generated
    ehsf/ data folder it was never actually shipped to. Every fresh
    install/rebuild hit "no such file or dir .../ehsf/phss/phss.xml" until
    someone manually copied it in. It's bundled, read-only reference data
    like fonts/backgrounds/templates, so it must be read via assetRoot
    instead, where it ships automatically with the rest of assets/.
    """

    def test_source_reads_from_assetroot_not_ehsf(self):
        import inspect
        source = inspect.getsource(slides.process_phss_song_ppt)
        assert 'assetRoot + "phss.xml"' in source
        assert "ehsf_join(\"phss\", \"phss.xml\")" not in source

    def test_bundled_phss_xml_parses_and_has_hymn_entries(self):
        from lxml import etree
        with open(slides.assetRoot + "phss.xml", "rb") as xml:
            tree = etree.parse(xml)
        hymn = tree.xpath('/Hymnal/HymnEntry[@HymnNumber="1"]')
        assert len(hymn) == 1


class TestSupperReading1Cor11_27to29Nasb95:
    """Regression for the added Lord's Supper reading at index 103: 1
    Corinthians 11:27-29 in the NASB95 wording specifically (distinct from
    the existing 1 Corinthians 11:27-32 entry at index 51, which uses
    NKJV/RVR1960) -- both should keep working independently.
    """

    def test_index_103_is_nasb95_1_corinthians_11_27_29(self):
        eng_ref, eng_passage = slides.get_supper_reading(103, 0)
        assert eng_ref.text == "1 Corinthians 11:27-29"
        assert eng_passage.text == (
            "Therefore whoever eats the bread or drinks the cup of the Lord in an "
            "unworthy manner, shall be guilty of the body and the blood of the Lord. "
            "But a man must examine himself, and in so doing he is to eat of the "
            "bread and drink of the cup. For he who eats and drinks, eats and "
            "drinks judgment to himself if he does not judge the body rightly."
        )

    def test_index_103_spanish_is_rvr1960(self):
        esp_ref, esp_passage = slides.get_supper_reading(103, 1)
        assert esp_ref.text == "1 Corintios 11:27-29"
        assert esp_passage.text == (
            "De manera que cualquiera que comiere este pan o bebiere esta copa del "
            "Señor indignamente, será culpado del cuerpo y de la sangre del Señor. "
            "Por tanto, pruébese cada uno a sí mismo, y coma así del pan, y beba de "
            "la copa. Porque el que come y bebe indignamente, sin discernir el "
            "cuerpo del Señor, juicio come y bebe para sí."
        )

    def test_existing_index_51_still_intact(self):
        # The pre-existing, differently-worded 1 Cor 11:27-32 (NKJV) entry
        # must survive untouched -- this addition only appends a new slide.
        eng_ref, _ = slides.get_supper_reading(51, 0)
        assert eng_ref.text == "1 Corinthians 11:27-32"

    def test_index_105_still_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            slides.get_supper_reading(105, 0)


class TestSupperReadingLuke23_27to31Nasb95:
    """Regression for the added Lord's Supper reading at index 104: Luke
    23:27-31 in the NASB95 wording (the deck otherwise mixes translations
    slide by slide -- NASB95 was an explicit choice here, matching index
    103's, not a house style)."""

    def test_index_104_is_nasb95_luke_23_27_31(self):
        eng_ref, eng_passage = slides.get_supper_reading(104, 0)
        assert eng_ref.text == "Luke 23:27-31"
        assert eng_passage.text == (
            "And there followed Him a great multitude of the people, and of women "
            "who also mourned and lamented Him. But Jesus, turning to them, said, "
            "“Daughters of Jerusalem, do not weep for Me, but weep for yourselves "
            "and for your children. For indeed the days are coming in which they "
            "will say, ‘Blessed are the barren, wombs that never bore, and breasts "
            "which never nursed!’ Then they will begin ‘to say to the mountains, "
            "“Fall on us!” and to the hills, “Cover us!”’ For if they do these "
            "things in the green wood, what will be done in the dry?”"
        )

    def test_index_104_spanish_is_rvr1960(self):
        esp_ref, esp_passage = slides.get_supper_reading(104, 1)
        assert esp_ref.text == "Lucas 23:27-31"
        assert esp_passage.text == (
            "Y le seguía gran multitud del pueblo, y de mujeres que lloraban y "
            "hacían lamentación por él. Pero Jesús, vuelto hacia ellas, les dijo: "
            "Hijas de Jerusalén, no lloréis por mí, sino llorad por vosotras mismas "
            "y por vuestros hijos. Porque he aquí vendrán días en que dirán: "
            "Bienaventuradas las estériles, y los vientres que no concibieron, y "
            "los pechos que no criaron. Entonces comenzarán a decir a los montes: "
            "Caed sobre nosotros; y a los collados: Cubridnos. Porque si en el "
            "árbol verde hacen estas cosas, ¿en el seco, qué no se hará?"
        )

    def test_existing_index_103_still_intact(self):
        eng_ref, _ = slides.get_supper_reading(103, 0)
        assert eng_ref.text == "1 Corinthians 11:27-29"

    def test_index_105_still_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            slides.get_supper_reading(105, 0)


class TestAnnouncementsTitleItemType:
    """New custom-template item type: a title card reading "ANNOUNCEMENT"
    (English deliberately singular -- see below; Spanish stays "ANUNCIOS")
    (mirroring the existing "Sermon"/"Lesson"/"Report" title cards' fade to
    black afterward and background) rather than the pre-existing
    "announcements" type, which is just an immediate blank slide with no
    title at all -- a different type name was needed to avoid changing that
    existing type's behavior (used by sunday-pm.json). Unlike sermon/lesson,
    it has no quote/reference (a preaching-specific Bible verse doesn't fit
    an announcements slide) and uses its own, smaller/repositioned DETAIL
    box: "ANNOUNCEMENTS" is much longer than "SERMON"/"LESSON" and was
    wrapping onto a second line -- verified empirically against the actual
    LibreOffice-rendered output, not just fit_text's own calculation, which
    doesn't account for install_bundled_fonts() never installing the
    English Avenir Next LT Pro files (only the Spanish AlegreyaSans ones),
    so English text renders with a substituted, measurably wider font. Once
    the sizing was fixed, the requester still preferred the singular
    "ANNOUNCEMENT" as a wording choice (not a technical requirement).
    """

    def test_add_sermon_uses_announcements_title_and_fades_to_black(self):
        from pptx import Presentation
        outp = Presentation(slides.assetRoot + "template-2020.pptx")
        item = {'type': 'announcements-title'}
        slides.add_sermon(outp, "bil", item, None, 0)

        assert len(outp.slides) == 2  # title slide + fade-to-black slide
        title_slide = outp.slides[-2]
        eng_detail = slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ENG_DETAIL)
        esp_detail = slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ESP_DETAIL)
        assert eng_detail.text_frame.text == "ANNOUNCEMENT"
        assert esp_detail.text_frame.text == "ANUNCIOS"

    def test_has_no_quote_or_reference(self):
        # A sermon-specific Bible verse doesn't belong on an announcements
        # slide; add_texts() removes any placeholder not in the texts dict.
        from pptx import Presentation
        outp = Presentation(slides.assetRoot + "template-2020.pptx")
        slides.add_sermon(outp, "bil", {'type': 'announcements-title'}, None, 0)
        title_slide = outp.slides[-2]
        assert slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ENG_QUOTE) is None
        assert slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ESP_QUOTE) is None

    def test_sermon_still_has_its_quote_and_reference(self):
        # Regression: removing the quote/reference for announcements-title
        # must not disturb sermon/lesson, which still need theirs.
        from pptx import Presentation
        outp = Presentation(slides.assetRoot + "template-2020.pptx")
        slides.add_sermon(outp, "bil", {'type': 'sermon'}, None, 0)
        title_slide = outp.slides[-2]
        quote = slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ENG_QUOTE)
        assert quote is not None
        assert "PREACH" in quote.text_frame.text

    def test_detail_font_size_has_safety_margin_against_font_substitution(self):
        # fit_text sizes English text against the real AvenirNextLTPro-Bold.otf
        # file, but LibreOffice/PowerPoint substitute a wider fallback font at
        # render time (that font is never actually installed on the system --
        # see install_bundled_fonts()), so a size fit_text considers safely
        # fitting can still wrap in the real output. 32pt was the empirically
        # confirmed threshold; anything higher risks reintroducing the wrap.
        from pptx import Presentation
        outp = Presentation(slides.assetRoot + "template-2020.pptx")
        slides.add_sermon(outp, "eng", {'type': 'announcements-title'}, None, 0)
        title_slide = outp.slides[-2]
        eng_detail = slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ENG_DETAIL)
        size_pt = eng_detail.text_frame.paragraphs[0].runs[0].font.size.pt
        assert size_pt <= 32

    def test_sermon_and_lesson_still_show_their_own_text(self):
        # Regression: adding the new branch must not disturb the existing
        # sermon/lesson text selection it sits alongside.
        from pptx import Presentation
        for item_type, expected_eng in [("sermon", "SERMON"), ("lesson", "LESSON")]:
            outp = Presentation(slides.assetRoot + "template-2020.pptx")
            slides.add_sermon(outp, "bil", {'type': item_type}, None, 0)
            title_slide = outp.slides[-2]
            eng_detail = slides.get_placeholder(title_slide, slides.LAYOUT_TITLE_BIL_ENG_DETAIL)
            assert eng_detail.text_frame.text == expected_eng

    def test_dispatches_through_add_sermon_in_make_worship_deck(self):
        import inspect
        source = inspect.getsource(slides.make_worship_deck)
        assert "'announcements-title'" in source

    def test_parse_worship_item_uses_announcements_tag(self):
        order = []
        slides.parse_worship_item(order, {'type': 'announcements-title'}, 'eng')
        assert order == [["Announcements", 0, " "]]

        orden = []
        slides.parse_worship_item(orden, {'type': 'announcements-title'}, 'esp')
        assert orden == [["Anuncios", 0, " "]]

    def test_parse_worship_item_honors_custom_title_override(self):
        order = []
        slides.parse_worship_item(order, {'type': 'announcements-title', 'title': 'Special Notice'}, 'eng')
        assert order == [["Special Notice", 0, " "]]

    def test_get_navbar_lists_announcements_title(self):
        # Singular "Announcement" to match the title card's DETAIL text --
        # this sidebar nav label is a separate text element, so changing the
        # DETAIL text's wording didn't touch this one automatically.
        worship = {'items': [{'type': 'announcements-title'}]}
        engitems, espitems = slides.get_navbar(worship, 'bil')
        assert engitems == [[0, "announcements-title", "Announcement"]]
        assert espitems == [[0, "announcements-title", "Anuncios"]]

    def test_existing_plain_announcements_type_is_unaffected(self):
        # The pre-existing "announcements" type (an immediate blank slide,
        # used by sunday-pm.json) must keep its own separate behavior.
        order = []
        slides.parse_worship_item(order, {'type': 'announcements'}, 'eng')
        assert order == [["Announcements", 0, " "]]

        worship = {'items': [{'type': 'announcements'}]}
        engitems, _ = slides.get_navbar(worship, 'bil')
        assert engitems == [[0, "announcements", "Closing", 10]]
