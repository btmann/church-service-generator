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
                bil_target = _esp_bil_pptx_path(s1_book, int(s1_num))
                png_target_dir = _esp_bil_png_dir(s1_book, int(s1_num))
                st.info(
                    "**Next steps:**\n"
                    "1. Get Spanish lyrics typed into each text box of the downloaded file "
                    "(either do it yourself or send it to a translator) — do **not** touch the "
                    "hidden text in each slide's Notes pane, the export macro needs it.\n"
                    f"2. Save the completed file directly as:\n   `{bil_target}`\n"
                    "3. In PowerPoint, open `assets/template-spanish.pptm` **first** — then open "
                    f"the `{bil_target.name}` file you just saved in step 2 (opening it from that "
                    "exact location matters — the export macro writes relative to wherever the "
                    "open file is saved).\n"
                    "4. Run the **ExtractImagesFromPres** macro (Developer/View → Macros, set "
                    "\"Macros in\" to template-spanish.pptm, select ExtractImagesFromPres, Run). "
                    f"This exports each slide's PNG directly into:\n   `{png_target_dir}`\n"
                    "5. Come back to **Step 2** and point both fields at those same two paths above."
                )

            if log:
                with st.expander("Processing log"):
                    st.code(log)

    # ── Step 2: Process translated file ──────────────────────────────────────
    with st.expander("✅ **Step 2** — Process Translated File", expanded=False):
        st.markdown(
            """
**What this does:**
Takes the bilingual PPTX (with Spanish text you added) and the slide PNG images exported
from PowerPoint, then builds the Spanish version of the song into the library.

**Before you start** (see **Step 1**'s "Next steps" for the full walkthrough):
- The completed `-bil.pptx` must be saved directly into `ehsf/esp/<book>/bil/`, not some other folder
  (e.g. a translator hand-off folder) — the export macro depends on it being opened from there.
- The PNGs must come from running the **ExtractImagesFromPres** macro in `assets/template-spanish.pptm`
  against that file — not a generic "Export to Image" — since the macro embeds the correct filenames
  and skips the non-song metadata slide automatically. A plain PowerPoint export would misalign every
  verse image by one slide.
- Both fields below will normally point at the *same* `ehsf/esp/<book>/bil/...` location the macro
  already wrote to — that's expected, not a mistake.
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

        with st.expander(
            "📂 Already have a completed bil.pptx from elsewhere? Place it and prepare the folder",
            expanded=False,
        ):
            st.caption(
                "Use this if you already have a finished `<book>-<song>-bil.pptx` (e.g. from a "
                "translator, or copied over from another machine) and just need it saved in the "
                "right spot with the export folder ready, before running the macro in Step 4 of "
                "the walkthrough above."
            )
            s2_prep_path_input = st.text_input(
                "Path to your existing bil.pptx",
                key="s2_prep_path",
                help="Full path to the completed bilingual PPTX file wherever it currently is.",
            )
            if st.button("📂 Place PPTX & Create Folder", key="s2_prep_go"):
                prep_number = int(s2_num)
                prep_src = Path(s2_prep_path_input).expanduser() if s2_prep_path_input else None
                if prep_src is None or not prep_src.is_file():
                    st.error(f"PPTX file not found: {prep_src}")
                else:
                    prep_dest = _esp_bil_pptx_path(s2_book, prep_number)
                    prep_dest.parent.mkdir(parents=True, exist_ok=True)
                    prep_dest.write_bytes(prep_src.read_bytes())
                    prep_png_dir = _esp_bil_png_dir(s2_book, prep_number)
                    prep_png_dir.mkdir(parents=True, exist_ok=True)
                    st.success(
                        f"✅ Placed PPTX at `{prep_dest}` and created the export folder "
                        f"`{prep_png_dir}`.\n\n"
                        "Now open `assets/template-spanish.pptm` first, then open that PPTX from "
                        "its new location, and run the ExtractImagesFromPres macro."
                    )

        with st.expander("🤖 Auto-Export PNGs (no PowerPoint needed)", expanded=False):
            st.caption(
                "Alternative to the manual PowerPoint macro above, for anyone without PowerPoint "
                "or macro access. Requires the completed `bil.pptx` to already be sitting at "
                "`ehsf/esp/<book>/bil/<book>-<song>-bil.pptx` (use the 'Place PPTX & Create Folder' "
                "section above first if it isn't there yet). Requires LibreOffice to be installed."
            )
            if st.button("🤖 Auto-Export PNGs", key="s2_autoexport_go"):
                autoexport_number = int(s2_num)
                autoexport_pptx = _esp_bil_pptx_path(s2_book, autoexport_number)
                if not autoexport_pptx.is_file():
                    st.error(
                        f"No bilingual PPTX found at {autoexport_pptx}. Place it there first "
                        "(see 'Already have a completed bil.pptx' above)."
                    )
                else:
                    with st.spinner(f"Auto-exporting PNGs for {s2_book.upper()}-{_song_str(autoexport_number)}…"):
                        count, log, err = _capture(_slides.export_bil_pngs, s2_book, autoexport_number)
                    if err:
                        st.error("Auto-export failed.")
                        st.code(err, language="python")
                    else:
                        st.success(
                            f"✅ Exported {count} PNG(s) to "
                            f"{_esp_bil_png_dir(s2_book, autoexport_number)}. "
                            "You can now use that same folder in the PNG field below."
                        )
                    if log:
                        with st.expander("Auto-export log"):
                            st.code(log)

        s2_pptx_path_input = st.text_input(
            "Path to completed bilingual PPTX",
            key="s2_pptx_path",
            help="Full path to the PPTX file from Step 1 with Spanish text filled in.",
        )
        s2_png_folder_input = st.text_input(
            "Path to folder with exported PNG images",
            key="s2_png_folder",
            help="Folder containing the PNG images exported from PowerPoint. File names must sort "
            "in slide order (PowerPoint names them Slide1.PNG, Slide2.PNG, etc.).",
        )

        s2_pptx_file = Path(s2_pptx_path_input).expanduser() if s2_pptx_path_input else None
        s2_png_dir_input = Path(s2_png_folder_input).expanduser() if s2_png_folder_input else None

        s2_pptx_valid = s2_pptx_file is not None and s2_pptx_file.is_file()
        s2_png_valid = s2_png_dir_input is not None and s2_png_dir_input.is_dir()

        if s2_pptx_path_input and not s2_pptx_valid:
            st.warning(f"PPTX file not found: {s2_pptx_file}")
        if s2_png_folder_input and not s2_png_valid:
            st.warning(f"Folder not found: {s2_png_dir_input}")

        s2_ready = s2_pptx_valid and s2_png_valid

        if st.button(
            "⚙️ Process Translation",
            key="s2_go",
            type="primary",
            disabled=not s2_ready,
        ):
            number = int(s2_num)
            song = _song_str(number)

            # Copy bilingual PPTX from its local path
            bil_pptx_path = _esp_bil_pptx_path(s2_book, number)
            bil_pptx_path.parent.mkdir(parents=True, exist_ok=True)
            bil_pptx_path.write_bytes(s2_pptx_file.read_bytes())

            # Copy PNGs from the local folder. This is normally the exact same
            # folder the ExtractImagesFromPres macro already exported into
            # (ehsf/esp/<book>/bil/<song>/) -- reading and rewriting the same
            # files in place is a safe no-op, not an error.
            png_dir = _esp_bil_png_dir(s2_book, number)
            png_dir.mkdir(parents=True, exist_ok=True)

            png_files = sorted(
                (p for p in s2_png_dir_input.iterdir() if p.is_file() and p.suffix.lower() == ".png"),
                key=lambda p: p.name,
            )
            if not png_files:
                st.error("No PNG files found in that folder. Make sure you exported slides as PNG.")
                st.stop()

            st.info(
                f"Reading {len(png_files)} PNG(s) from {s2_png_dir_input}:\n\n"
                + "\n".join(f"- {p.name}" for p in png_files)
            )

            # Rename to sequential format (book-song-01.png, etc.)
            for ndx, src in enumerate(png_files, start=1):
                dest = png_dir / f"{s2_book}-{song}-{ndx:03d}.png"
                dest.write_bytes(src.read_bytes())

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
