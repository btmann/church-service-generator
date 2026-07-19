#!/usr/bin/env python3
"""Song Processing page — add new songs to the EHSF library."""

import base64
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import streamlit as st

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Ensure OCR binary is discoverable before slides.py imports pytesseract.
if not os.environ.get("TESSERACT_CMD"):
    for _cmd in (
        shutil.which("tesseract"),
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if _cmd and os.path.exists(_cmd):
            os.environ["TESSERACT_CMD"] = _cmd
            break

import slides as _slides

# Mirror the resource-resolution logic from ui.py so the same EHSF root is used.
def _resolve_resource_dir(folder_name):
    candidates = [_ROOT, Path.cwd()]
    try:
        # In a packaged EXE, resources (like ehsf/) ship next to the actual
        # executable, not next to the bundled source under _MEIPASS.
        candidates.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    for base in candidates:
        candidate = base / folder_name
        if candidate.exists() and candidate.is_dir():
            return candidate
    # Nothing found yet (first run): default to next to the actual EXE
    # (packaged) rather than _ROOT, which under PyInstaller onedir is the
    # _internal bundle folder -- invisible next to the .exe a user checks.
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent / folder_name
        except Exception:
            pass
    return _ROOT / folder_name

EHSF_ROOT_PATH = _resolve_resource_dir("ehsf")
os.environ["CHURCH_SERVICE_EHSF_ROOT"] = str(EHSF_ROOT_PATH)
if hasattr(_slides, "set_ehsf_root"):
    _slides.set_ehsf_root(str(EHSF_ROOT_PATH))

# Change CWD to project root so the hardcoded relative paths in slides.py resolve.
os.chdir(str(_ROOT))

SONG_BOOK_LABELS = {
    "pftl": "Praise for the Lord (PFTL)",
    "phss": "Psalms, Hymns, and Spiritual Songs (PHSS)",
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Song Processing — Church Service Generator",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 Song Library Processing")

st.caption(
    "Use these tools to add new songs or Spanish translations to the song library. "
    "Each processed song produces slide images and a JSON structure file that the "
    "Service Builder uses when generating presentations."
)

# ── Helper utilities ──────────────────────────────────────────────────────────

def _capture(fn, *args, **kwargs):
    """Call *fn* and return (return_value, captured_stdout, error_or_None)."""
    buf = io.StringIO()
    err = None
    result = None
    try:
        with contextlib.redirect_stdout(buf):
            result = fn(*args, **kwargs)
    except Exception:
        err = traceback.format_exc()
    return result, buf.getvalue(), err


def _song_str(number: int) -> str:
    return f"{number:03d}"


def _pptx_input_path(book: str, number: int) -> Path:
    """Where process_pftl/phss_song_ppt expects the source PPTX."""
    return EHSF_ROOT_PATH / book / "pptx" / (_song_str(number) + ".pptx")


def _ppt_input_path(book: str, number: int) -> Path:
    """Where the raw legacy PPT upload is stored before conversion."""
    return EHSF_ROOT_PATH / book / "pptx" / (_song_str(number) + ".ppt")


def _find_ppt_converter() -> str | None:
    """Return an available CLI converter for legacy .ppt files."""
    for cmd in ("soffice", "libreoffice", "unoconv"):
        path = shutil.which(cmd)
        if path:
            return path
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _convert_legacy_ppt_to_pptx(ppt_path: Path, pptx_path: Path) -> tuple[bool, str]:
    """Convert a binary .ppt to .pptx via LibreOffice-compatible CLI."""
    converter = _find_ppt_converter()
    if not converter:
        install_hint = (
            "winget install -e --id TheDocumentFoundation.LibreOffice"
            if sys.platform == "win32"
            else "brew install --cask libreoffice"
        )
        return False, f"Legacy .ppt conversion requires LibreOffice. Install it and retry: {install_hint}"

    with tempfile.TemporaryDirectory(prefix="ppt-convert-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        if Path(converter).name == "unoconv":
            cmd = [converter, "-f", "pptx", "-o", str(tmpdir_path), str(ppt_path)]
        else:
            cmd = [converter, "--headless", "--convert-to", "pptx", "--outdir", str(tmpdir_path), str(ppt_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            details = (proc.stderr or proc.stdout or "unknown error").strip()
            return False, f"Conversion failed ({Path(converter).name}): {details}"

        converted_files = list(tmpdir_path.glob("*.pptx"))
        if not converted_files:
            return False, "Conversion did not produce a .pptx file."

        pptx_path.write_bytes(converted_files[0].read_bytes())
        return True, ""


def _esp_blank_output(book: str, number: int) -> Path:
    """Where make_esp_blank saves the generated English/blank deck."""
    song = _song_str(number)
    return EHSF_ROOT_PATH / "esp" / book / "eng" / f"{book}-{song}-eng.pptx"


def _esp_bil_pptx_path(book: str, number: int) -> Path:
    """Where make_esp_trans expects the completed bilingual PPTX."""
    song = _song_str(number)
    return EHSF_ROOT_PATH / "esp" / book / "bil" / f"{book}-{song}-bil.pptx"


def _esp_bil_png_dir(book: str, number: int) -> Path:
    """Where make_esp_trans expects exported PNG slides."""
    song = _song_str(number)
    return EHSF_ROOT_PATH / "esp" / book / "bil" / song


def _eng_song_exists(book: str, number: int) -> bool:
    song = _song_str(number)
    return (EHSF_ROOT_PATH / book / song / f"{book}-{song}.json").exists()


def _download_button(label: str, file_path: Path, mime: str, key: str):
    if file_path.exists():
        data = file_path.read_bytes()
        st.download_button(label=label, data=data, file_name=file_path.name, mime=mime, key=key)
    else:
        st.warning(f"Output file not found: {file_path}")


# ── Tabs for workflow ──────────────────────────────────────────────────────────
eng_tab, esp_tab = st.tabs(["Process New English Song", "Add Spanish Translation"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1 — Process new English song
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with eng_tab:
    st.markdown("### Add a New Song")
    st.markdown(
        "Upload the source PowerPoint file for a song and click **Process** to extract "
        "slide images and build the verse/chorus JSON used by the presentation generator."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        eng_book = st.selectbox(
            "Song Book",
            options=list(SONG_BOOK_LABELS.keys()),
            format_func=lambda c: SONG_BOOK_LABELS[c],
            key="eng_book",
        )
    with col2:
        eng_num = st.number_input(
            "Song Number", min_value=1, max_value=9999, value=1, step=1, key="eng_num"
        )

    eng_upload = st.file_uploader(
        "Upload source PowerPoint file (.ppt or .pptx)",
        type=["ppt", "pptx"],
        key="eng_upload",
        help=(
            "Upload one song per file. Legacy .ppt files are auto-converted to .pptx "
            "when LibreOffice is installed."
        ),
    )

    already_exists = _eng_song_exists(eng_book, int(eng_num))
    if already_exists:
        st.info(
            f"{eng_book.upper()}-{_song_str(int(eng_num))} already exists in the library. "
            "Processing again will overwrite the existing images and JSON."
        )

    if st.button("⚙️ Process Song", key="eng_process", type="primary", disabled=eng_upload is None):
        number = int(eng_num)
        song = _song_str(number)

        upload_bytes = eng_upload.read()
        upload_ext = Path(eng_upload.name).suffix.lower()

        # Save uploaded file to expected location and convert if needed.
        pptx_path = _pptx_input_path(eng_book, number)
        pptx_path.parent.mkdir(parents=True, exist_ok=True)

        if upload_ext == ".pptx":
            pptx_path.write_bytes(upload_bytes)
        elif upload_ext == ".ppt":
            # Some sources label OOXML data as .ppt. If so, keep it as .pptx directly.
            if upload_bytes.startswith(b"PK"):
                pptx_path.write_bytes(upload_bytes)
            else:
                ppt_path = _ppt_input_path(eng_book, number)
                ppt_path.write_bytes(upload_bytes)
                ok, msg = _convert_legacy_ppt_to_pptx(ppt_path, pptx_path)
                if not ok:
                    st.error(msg)
                    st.stop()
                st.info("Converted legacy .ppt upload to .pptx.")
        else:
            st.error("Unsupported file type. Please upload a .ppt or .pptx file.")
            st.stop()

        with st.spinner(f"Processing {eng_book.upper()}-{song}…"):
            if eng_book == "pftl":
                _, log, err = _capture(_slides.process_pftl_song, number)
            elif eng_book == "phss":
                _, log, err = _capture(_slides.process_phss_song_ppt, number)
            else:
                err = f"Processing for book '{eng_book}' is not yet supported in the UI."
                log = ""

        if err:
            st.error("Processing failed.")
            st.code(err, language="python")
        else:
            song_dir = EHSF_ROOT_PATH / eng_book / song
            json_path = song_dir / f"{eng_book}-{song}.json"
            pngs = list(song_dir.glob("*.png"))

            st.success(
                f"✅ Processed {eng_book.upper()}-{song}: "
                f"{len(pngs)} slide image(s) created."
            )

            if json_path.exists():
                meta = _slides.load_json_safe(str(json_path))
                with st.expander("View generated JSON metadata"):
                    st.json(meta)

        if log:
            with st.expander("Processing log"):
                st.code(log)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2 — Spanish translation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with esp_tab:
    st.markdown("### Spanish Translation Workflow")
    st.markdown(
        "Follow the two steps below to add a Spanish version of an existing English song. "
        "The Spanish slides will appear on the right-hand column of bilingual services."
    )

    with st.expander("🔤 One-time setup: install subtitle fonts", expanded=False):
        st.caption(
            "The Spanish subtitle text boxes use a specific font (Alegreya Sans). If it isn't "
            "installed on this PC, PowerPoint/LibreOffice silently substitute a different font, "
            "which can wrap the text differently and make it overlap the slide below it — the "
            "text itself is still correct, but the layout looks broken. Run this once per PC "
            "before using either export method below."
        )
        if st.button("🔤 Install Fonts", key="install_fonts_go"):
            results = _slides.install_bundled_fonts()
            if results:
                for path, msg in results:
                    st.write(f"- {msg}: `{path}`")
                st.success(
                    "✅ Fonts installed. If you already have PowerPoint or LibreOffice open, "
                    "close and reopen it so it picks up the new font."
                )
            else:
                st.error("No bundled font files found in assets/.")

    # ── Step 1: Generate blank template ──────────────────────────────────────
    with st.expander("📋 **Step 1** — Generate Translation Template", expanded=True):
        st.markdown(
            """
**What this does:**  
Generates a PowerPoint file that shows each song slide with extra space at the bottom for
Spanish subtitle text. Open the file in PowerPoint, type the Spanish lyrics into the text
boxes, then come back to **Step 2** to process your completed translation.
"""
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            s1_book = st.selectbox(
                "Song Book",
                options=list(SONG_BOOK_LABELS.keys()),
                format_func=lambda c: SONG_BOOK_LABELS[c],
                key="s1_book",
            )
        with col2:
            s1_num = st.number_input(
                "Song Number", min_value=1, max_value=9999, value=1, step=1, key="s1_num"
            )

        s1_song = _song_str(int(s1_num))
        s1_eng_exists = _eng_song_exists(s1_book, int(s1_num))

        if not s1_eng_exists:
            st.warning(
                f"{s1_book.upper()}-{s1_song} has not been processed yet. "
                "Process the English song first before generating a translation template."
            )

        if st.button(
            "📄 Generate Template",
            key="s1_go",
            type="primary",
            disabled=not s1_eng_exists,
        ):
            with st.spinner(f"Generating translation template for {s1_book.upper()}-{s1_song}…"):
                _, log, err = _capture(_slides.make_esp_blank, s1_book, int(s1_num), None)

            if err:
                st.error("Template generation failed.")
                st.code(err, language="python")
            else:
                out_path = _esp_blank_output(s1_book, int(s1_num))
                st.success("✅ Template generated.")
                _download_button(
                    f"⬇️ Download {out_path.name}",
                    out_path,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="s1_download",
                )
                st.info(
                    "**Next steps:**\n"
                    "1. Get Spanish lyrics typed into each text box of the downloaded file "
                    "(either do it yourself or send it to a translator) — do **not** touch the "
                    "hidden text in each slide's Notes pane, it's needed for exporting slide "
                    "images later.\n"
                    "2. Save the completed file anywhere convenient (e.g. Desktop, or wherever "
                    "your translator sends it back).\n"
                    "3. Go to **Step 2**, paste that file's path, and click **Process Translation** "
                    "— it handles placing the file, exporting slide images, and building the final "
                    "Spanish version automatically (requires LibreOffice; see the setup section "
                    "above if it's not installed yet).\n\n"
                    "*No PowerPoint or macro needed for this path — see Step 2's \"Advanced\" option "
                    "only if you specifically want to use the manual PowerPoint macro process instead.*"
                )

            if log:
                with st.expander("Processing log"):
                    st.code(log)

    # ── Step 2: Process translated file ──────────────────────────────────────
    with st.expander("✅ **Step 2** — Process Translated File", expanded=False):
        st.markdown(
            """
**What this does:**
Takes the completed bilingual PPTX (with Spanish text added) — wherever it currently is — and
in one step: places it in the song library, exports each slide to PNG, and builds the final
Spanish version of the song. Requires LibreOffice to be installed (see the setup section above).
"""
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            s2_book = st.selectbox(
                "Song Book",
                options=list(SONG_BOOK_LABELS.keys()),
                format_func=lambda c: SONG_BOOK_LABELS[c],
                key="s2_book",
            )
        with col2:
            s2_num = st.number_input(
                "Song Number", min_value=1, max_value=9999, value=1, step=1, key="s2_num"
            )

        s2_pptx_path_input = st.text_input(
            "Path to completed bil.pptx",
            key="s2_pptx_path",
            help="Full path to the finished bilingual PPTX with Spanish text added, wherever it "
            "currently is (e.g. downloaded from a translator).",
        )
        s2_pptx_file = Path(s2_pptx_path_input).expanduser() if s2_pptx_path_input else None
        s2_pptx_valid = s2_pptx_file is not None and s2_pptx_file.is_file()
        if s2_pptx_path_input and not s2_pptx_valid:
            st.warning(f"PPTX file not found: {s2_pptx_file}")

        if st.button("🚀 Process Translation", key="s2_go", type="primary", disabled=not s2_pptx_valid):
            number = int(s2_num)
            song = _song_str(number)

            # Place the PPTX where the rest of the pipeline expects it. If
            # it's already there (e.g. you're re-running this), this is a
            # safe no-op self-copy.
            bil_pptx_path = _esp_bil_pptx_path(s2_book, number)
            bil_pptx_path.parent.mkdir(parents=True, exist_ok=True)
            bil_pptx_path.write_bytes(s2_pptx_file.read_bytes())
            png_dir = _esp_bil_png_dir(s2_book, number)
            png_dir.mkdir(parents=True, exist_ok=True)

            with st.spinner(f"Exporting slide images for {s2_book.upper()}-{song}…"):
                count, export_log, export_err = _capture(_slides.export_bil_pngs, s2_book, number)

            if export_err:
                st.error(
                    "PNG export failed. If you don't have LibreOffice installed, use the "
                    "'Advanced' option below instead (for the manual PowerPoint macro route)."
                )
                st.code(export_err, language="python")
                if export_log:
                    with st.expander("Export log"):
                        st.code(export_log)
                st.stop()

            st.info(f"Exported {count} slide image(s) to {png_dir}.")

            with st.spinner(f"Processing Spanish translation for {s2_book.upper()}-{song}…"):
                _, process_log, process_err = _capture(_slides.make_esp_trans, s2_book, number)

            if process_err:
                st.error("Processing failed.")
                st.code(process_err, language="python")
            else:
                esp_json = EHSF_ROOT_PATH / "esp" / s2_book / song / f"{s2_book}-{song}.json"
                esp_pngs = list((EHSF_ROOT_PATH / "esp" / s2_book / song).glob("*.png"))
                st.success(
                    f"✅ Spanish translation processed for {s2_book.upper()}-{song}: "
                    f"{len(esp_pngs)} slide image(s) created."
                )
                if esp_json.exists():
                    meta = _slides.load_json_safe(str(esp_json))
                    with st.expander("View generated Spanish JSON metadata"):
                        st.json(meta)

            if export_log or process_log:
                with st.expander("Processing log"):
                    if export_log:
                        st.code(export_log)
                    if process_log:
                        st.code(process_log)

        with st.expander(
            "🛠️ Advanced: I already ran the PowerPoint macro myself (no LibreOffice)",
            expanded=False,
        ):
            st.caption(
                "Use this only if you followed Step 1's manual PowerPoint + ExtractImagesFromPres "
                "macro walkthrough yourself and the PNGs are already sitting in "
                "`ehsf/esp/<book>/bil/<song>/`. This skips the PPTX placement and auto-export above "
                "and goes straight to building the final Spanish version from those existing PNGs."
            )
            if st.button("Finish Processing (skip auto-export)", key="s2_manual_finish"):
                number = int(s2_num)
                song = _song_str(number)
                with st.spinner(f"Processing Spanish translation for {s2_book.upper()}-{song}…"):
                    _, log, err = _capture(_slides.make_esp_trans, s2_book, number)

                if err:
                    st.error("Processing failed.")
                    st.code(err, language="python")
                else:
                    esp_json = EHSF_ROOT_PATH / "esp" / s2_book / song / f"{s2_book}-{song}.json"
                    esp_pngs = list((EHSF_ROOT_PATH / "esp" / s2_book / song).glob("*.png"))
                    st.success(
                        f"✅ Spanish translation processed for {s2_book.upper()}-{song}: "
                        f"{len(esp_pngs)} slide image(s) created."
                    )
                    if esp_json.exists():
                        meta = _slides.load_json_safe(str(esp_json))
                        with st.expander("View generated Spanish JSON metadata"):
                            st.json(meta)

                if log:
                    with st.expander("Processing log"):
                        st.code(log)
