"""Unit tests for pages/2_Song_Processing.py's path-building and conversion
helpers, extracted the same way as test_ui_helpers.py (see that file's
docstring): this page also calls st.* at module scope.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import ROOT, extract_functions

PAGE_PY = ROOT / "pages" / "2_Song_Processing.py"
EHSF_ROOT_PATH = Path("/fake/ehsf")


def _module_level_dict(name):
    """Exec only the named top-level dict assignment(s) -- SONG_BOOK_LABELS
    and TRANSLATION_BOOK_LABELS -- from the page in an isolated namespace,
    without running the whole script (which calls st.* at module scope --
    see extract_functions' docstring), and return `name`'s resulting
    value. Execs rather than ast.literal_eval since TRANSLATION_BOOK_LABELS
    references SONG_BOOK_LABELS via dict-unpacking, not a plain literal;
    limited to these two by name so unrelated top-level assignments
    earlier in the file (which depend on things not in this namespace,
    e.g. a not-yet-defined helper function) are never exec'd."""
    wanted = {"SONG_BOOK_LABELS", "TRANSLATION_BOOK_LABELS"}
    tree = ast.parse(PAGE_PY.read_text(encoding="utf-8"))
    namespace = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted for t in node.targets
        ):
            module = ast.Module(body=[node], type_ignores=[])
            exec(compile(module, filename=str(PAGE_PY), mode="exec"), namespace)
    if name not in namespace:
        raise ValueError(f"No top-level assignment to {name!r} in {PAGE_PY}")
    return namespace[name]


def load(names, extra_globals=None):
    base_globals = {
        "os": os,
        "shutil": shutil,
        "subprocess": subprocess,
        "sys": sys,
        "tempfile": tempfile,
        "Path": Path,
        "EHSF_ROOT_PATH": EHSF_ROOT_PATH,
    }
    if extra_globals:
        base_globals.update(extra_globals)
    return extract_functions(PAGE_PY, names, base_globals)


class TestResolveResourceDir:
    """Same regression as TestResolveResourceDir in test_ui_helpers.py: this
    page recomputes its own EHSF_ROOT_PATH and calls _slides.set_ehsf_root
    with it, so this copy is the one that actually matters for where a
    processed song's files end up in the packaged EXE.
    """

    def test_falls_back_to_exe_folder_when_frozen_and_nothing_found(self, tmp_path, monkeypatch):
        fake_root = tmp_path / "internal"
        fns = load(["_resolve_resource_dir"], {"_ROOT": fake_root})
        monkeypatch.setattr(Path, "cwd", lambda: fake_root)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "church-service-ui.exe"))
        result = fns["_resolve_resource_dir"]("ehsf")
        assert result == tmp_path / "dist" / "ehsf"

    def test_falls_back_to_root_when_not_frozen_and_nothing_found(self, tmp_path, monkeypatch):
        fake_root = tmp_path / "src"
        fns = load(["_resolve_resource_dir"], {"_ROOT": fake_root})
        monkeypatch.setattr(Path, "cwd", lambda: fake_root)
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        result = fns["_resolve_resource_dir"]("ehsf")
        assert result == fake_root / "ehsf"

    def test_returns_existing_candidate_over_fallback(self, tmp_path, monkeypatch):
        (tmp_path / "dist" / "ehsf").mkdir(parents=True)
        fake_root = tmp_path / "internal"
        fns = load(["_resolve_resource_dir"], {"_ROOT": fake_root})
        monkeypatch.setattr(Path, "cwd", lambda: fake_root)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "church-service-ui.exe"))
        result = fns["_resolve_resource_dir"]("ehsf")
        assert result == tmp_path / "dist" / "ehsf"

    def test_frozen_never_reads_from_cwd_even_if_it_has_a_match(self, tmp_path, monkeypatch):
        # Regression: launching the packaged EXE from different working
        # directories used to resolve ehsf/ to a different folder each time,
        # because cwd/_ROOT were checked before the exe's own folder. Once
        # frozen, only the exe's folder should ever be consulted.
        (tmp_path / "cwd" / "ehsf").mkdir(parents=True)
        (tmp_path / "dist" / "ehsf").mkdir(parents=True)
        fake_root = tmp_path / "cwd"
        fns = load(["_resolve_resource_dir"], {"_ROOT": fake_root})
        monkeypatch.setattr(Path, "cwd", lambda: fake_root)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "church-service-ui.exe"))
        result = fns["_resolve_resource_dir"]("ehsf")
        assert result == tmp_path / "dist" / "ehsf"


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

    def test_falls_back_to_windows_install_path_when_not_on_path(self, monkeypatch):
        # winget-installed LibreOffice/Tesseract aren't always added to PATH;
        # this covers the fallback to the default Windows install location.
        fn = load(["_find_ppt_converter"])["_find_ppt_converter"]
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        windows_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
        monkeypatch.setattr(os.path, "exists", lambda p: p == windows_path)
        assert fn() == windows_path


class TestConvertLegacyPptToPptx:
    def test_no_converter_available_returns_helpful_error(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"])
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", tmp_path / "out.pptx")
        assert ok is False
        assert "LibreOffice" in message

    def test_no_converter_error_suggests_winget_on_windows(self, monkeypatch, tmp_path):
        fns = load(["_find_ppt_converter", "_convert_legacy_ppt_to_pptx"], {"sys": sys})
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        monkeypatch.setattr(sys, "platform", "win32")
        ok, message = fns["_convert_legacy_ppt_to_pptx"](tmp_path / "in.ppt", tmp_path / "out.pptx")
        assert ok is False
        assert "winget" in message

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


class TestTranslationBookLabels:
    """Regression: the "Add Spanish Translation" tab's book dropdowns
    (s1_book, s2_book) only offered pftl/phss, even though the pipeline
    functions they drive (make_esp_blank/export_bil_pngs/make_esp_trans in
    slides.py) are fully book-agnostic -- eh just had nowhere to be
    selected from. "Process New English Song" genuinely doesn't support eh
    (it has no branch for it, see its else clause), so that tab's own
    SONG_BOOK_LABELS deliberately stays pftl/phss-only.
    """

    def test_translation_tab_includes_eh(self):
        labels = _module_level_dict("TRANSLATION_BOOK_LABELS")
        assert "eh" in labels

    def test_new_english_song_tab_still_excludes_eh(self):
        labels = _module_level_dict("SONG_BOOK_LABELS")
        assert "eh" not in labels

    def test_translation_tab_still_includes_the_original_books(self):
        labels = _module_level_dict("TRANSLATION_BOOK_LABELS")
        assert "pftl" in labels
        assert "phss" in labels
