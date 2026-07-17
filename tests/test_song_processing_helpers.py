"""Unit tests for pages/2_Song_Processing.py's path-building and conversion
helpers, extracted the same way as test_ui_helpers.py (see that file's
docstring): this page also calls st.* at module scope.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import ROOT, extract_functions

PAGE_PY = ROOT / "pages" / "2_Song_Processing.py"
EHSF_ROOT_PATH = Path("/fake/ehsf")


def load(names, extra_globals=None):
    base_globals = {
        "shutil": shutil,
        "subprocess": subprocess,
        "tempfile": tempfile,
        "Path": Path,
        "EHSF_ROOT_PATH": EHSF_ROOT_PATH,
    }
    if extra_globals:
        base_globals.update(extra_globals)
    return extract_functions(PAGE_PY, names, base_globals)


class TestSongStr:
    @pytest.mark.parametrize("number,expected", [(1, "001"), (12, "012"), (123, "123")])
    def test_zero_pads_to_three_digits(self, number, expected):
        fn = load(["_song_str"])["_song_str"]
        assert fn(number) == expected


class TestPathBuilders:
    def test_pptx_input_path(self):
        fn = load(["_song_str", "_pptx_input_path"])["_pptx_input_path"]
        assert fn("pftl", 12) == EHSF_ROOT_PATH / "pftl" / "pptx" / "012.pptx"

    def test_ppt_input_path(self):
        fn = load(["_song_str", "_ppt_input_path"])["_ppt_input_path"]
        assert fn("pftl", 12) == EHSF_ROOT_PATH / "pftl" / "pptx" / "012.ppt"

    def test_esp_blank_output(self):
        fn = load(["_song_str", "_esp_blank_output"])["_esp_blank_output"]
        assert fn("phss", 5) == EHSF_ROOT_PATH / "esp" / "phss" / "eng" / "phss-005-eng.pptx"

    def test_esp_bil_pptx_path(self):
        fn = load(["_song_str", "_esp_bil_pptx_path"])["_esp_bil_pptx_path"]
        assert fn("phss", 5) == EHSF_ROOT_PATH / "esp" / "phss" / "bil" / "phss-005-bil.pptx"

    def test_esp_bil_png_dir(self):
        fn = load(["_song_str", "_esp_bil_png_dir"])["_esp_bil_png_dir"]
        assert fn("phss", 5) == EHSF_ROOT_PATH / "esp" / "phss" / "bil" / "005"


class TestEngSongExists:
    def test_true_when_json_present(self, tmp_path, monkeypatch):
        song_dir = tmp_path / "pftl" / "012"
        song_dir.mkdir(parents=True)
        (song_dir / "pftl-012.json").write_text("{}")
        fn = load(["_song_str", "_eng_song_exists"], {"EHSF_ROOT_PATH": tmp_path})["_eng_song_exists"]
        assert fn("pftl", 12) is True

    def test_false_when_missing(self, tmp_path):
        fn = load(["_song_str", "_eng_song_exists"], {"EHSF_ROOT_PATH": tmp_path})["_eng_song_exists"]
        assert fn("pftl", 12) is False


class TestFindPptConverter:
    def test_returns_first_available_converter(self, monkeypatch):
        fn = load(["_find_ppt_converter"])["_find_ppt_converter"]
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)
        assert fn() == "/usr/bin/soffice"

    def test_returns_none_when_no_converter_found(self, monkeypatch):
        fn = load(["_find_ppt_converter"])["_find_ppt_converter"]
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        assert fn() is None


class TestConvertLegacyPptToPptx:
    def test_no_converter_available_returns_helpful_error(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"])
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", tmp_path / "out.pptx")
        assert ok is False
        assert "LibreOffice" in message

    def test_nonzero_return_code_reports_stderr(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"])
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)

        class FakeCompletedProcess:
            returncode = 1
            stdout = ""
            stderr = "conversion exploded"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompletedProcess())
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", tmp_path / "out.pptx")
        assert ok is False
        assert "conversion exploded" in message

    def test_success_copies_converted_file_to_target(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"])
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)

        def fake_run(cmd, capture_output, text):
            outdir = Path(cmd[cmd.index("--outdir") + 1])
            (outdir / "in.pptx").write_bytes(b"PPTX-BYTES")

            class FakeCompletedProcess:
                returncode = 0
                stdout = ""
                stderr = ""

            return FakeCompletedProcess()

        monkeypatch.setattr(subprocess, "run", fake_run)
        out_path = tmp_path / "out.pptx"
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", out_path)
        assert ok is True
        assert message == ""
        assert out_path.read_bytes() == b"PPTX-BYTES"

    def test_no_pptx_produced_reports_error(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"])
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)

        class FakeCompletedProcess:
            returncode = 0
            stdout = ""
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompletedProcess())
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", tmp_path / "out.pptx")
        assert ok is False
        assert "did not produce" in message
