# Church Service Generator

Tools for preparing church service slides, including:

- Song parsing and song deck generation.
- Worship spec generation from templates/schedules.
- Full worship deck generation (English, Spanish, bilingual).

The primary entry scripts are at the repository root:

- `worship.py` — service spec JSON workflows.
- `slides.py` — song processing and PowerPoint generation.
- `ui.py` + `launch-ui.py` — Streamlit web interface for non-technical users.

## New: Streamlit Web UI (Recommended for Non-Technical Users)

For non-technical users, a simple web interface is available:

- **`ui.py`** - Browser-based interface (Streamlit)
- **`launch-ui.py`** - Single-click launcher for OneDrive distribution
- **See `UI-README.md`** for setup and packaging instructions

The UI allows users to:
1. Select a service date/time and template
2. Enter songs (book + number)
3. Assign leader names
4. Click "Generate" to create PowerPoint decks
5. Download or share the generated files

**Quick Start:**
```bash
pip3 install -r requirements-ui.txt
python3 -m streamlit run ui.py
```

For OneDrive distribution, see packaging instructions in `UI-README.md`.

---

## Advanced: Command-Line Scripts

For technical users and automation:

Main workflow:

1. Generate service spec files from a template or schedule.
2. Fill/update songs, leaders, and readings JSON.
3. Compile a final worship JSON file.
4. Render a final `.pptx` deck.

Song workflow (when adding/updating songs):

1. Parse source song files into EHSF-style JSON + PNG assets.
2. Optionally generate bilingual (Spanish) variants.
3. Build standalone song decks or include songs in a worship deck.

## Repository Layout (Key Paths)

- `worship/`
  - `schedules/`, `templates/`, `styles/`, and generated `specs/`.
- `assets/`
  - Slide templates, logos, backgrounds, fonts.
- `ehsf/` (created/used by scripts)
  - Parsed song JSON and slide images by songbook.
- `python-pptx-mods/`
  - Local patched `pptx` package used by build tooling.
- `packaging/`
  - Cross-platform executable build scripts.

## Prerequisites

- Python 3.7+ (project notes originally used 3.7).
- PowerPoint files and assets in expected repository locations.
- Tesseract OCR installed and available in PATH for OCR-dependent commands.
- **Song data folder** (`ehsf/`): Large folder containing song JSON and slide images. A sample song (PFTL 738) is included for testing. Full song library should be kept in OneDrive alongside the app distribution.

Notes from project history:

- Windows workflows may require extra native build tools for some optional packages.
- If you run into OCR/path issues, verify your Tesseract installation and executable path.

## Setup

### 1. Create and activate a virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```bash
pip install --upgrade pip
pip install python-pptx lxml pillow pytesseract python-dateutil requests
```

Optional for building executable artifacts:

```bash
pip install -r packaging/requirements-build.txt
```

## Quick Start

### A) Generate worship specs from a schedule

```bash
python worship.py -d 2026-05-10 -s sunday
```

This creates spec files under `worship/specs/YYYY/MM/DD/HHMM/`.

### B) Update leaders/readings for one service

```bash
python worship.py -d 2026-05-10 -t 10:00:00 -l
python worship.py -d 2026-05-10 -t 10:00:00 -r
```

### C) Build the final worship JSON

```bash
python worship.py -d 2026-05-10 -t 10:00:00 -j -style jan-1
```

Output example:

- `worship/2026/20260510-1000.json`

### D) Render PowerPoint deck from worship JSON

```bash
python slides.py -w worship/2026/20260510-1000.json
```

Output example:

- `worship/2026/20260510-1000.pptx`

## Main Commands

### `worship.py`

Common flags:

- `-d YYYY-MM-DD` service date.
- `-t HH:MM:SS` service time.
- `-s <schedule>` generate all services from schedule.
- `-template <template>` create initial service files.
- `-lang eng|esp|bil` language.
- `-type "Sun - AM"` service type.
- `-l` fetch leaders.
- `-r` fetch readings.
- `-j` generate merged worship JSON.
- `-style <style>` apply style while generating JSON.

Examples:

```bash
python worship.py -d 2026-05-10 -t 18:00:00 -template sunday-am -lang bil -type "Sun - PM"
python worship.py -d 2026-05-10 -t 18:00:00 -j -style mar-pm
```

### `slides.py`

Common flags:

- `-w <worship-json>` build full worship deck.
- `-b <book>` songbook (`pftl`, `shs`, `phss`, `eh`, `phss-eh`).
- `-s <song-number>` song number.
- `--ppt` build a single song deck.
- `-lang eng|esp|bil` output language.
- `-output <file>` output `.pptx` name.

Song-focused examples:

```bash
python slides.py -b pftl -s 123
python slides.py -b phss -s 88
python slides.py -b pftl -s 123 --ppt -lang bil -output pftl-123-bil.pptx
```

Bilingual conversion helpers:

```bash
python slides.py -b pftl -s 123 --esp-eng
python slides.py -b pftl -s 123 --esp-bil
```

Utility examples:

```bash
python slides.py --lyrics -b pftl -s 123
python slides.py --export
python slides.py --db
python slides.py --hist -b pftl -s 123
```

## Building a Standalone Executable

Use scripts in `packaging/`.

**UI app (Streamlit — for end users):**

macOS:
```bash
./packaging/build-ui-macos.sh
```
Windows (PowerShell):
```powershell
.\packaging\build-ui-windows.ps1
```
Output: `dist/church-service-ui/` — copy entire folder to OneDrive for distribution.

**CLI tool (slides.py — for technical users):**

macOS:
```bash
./packaging/build-macos.sh --entry slides.py --name church-service-generator
```
Windows:
```powershell
.\packaging\build-windows.ps1 --entry slides.py --name church-service-generator
```

Notes:

- Build output is created in `dist/`.
- Builder automatically includes `python-pptx-mods` in module paths.
- If present, `assets`, `backgrounds`, and `worship` are bundled by default.

## Troubleshooting

- `ModuleNotFoundError` for `pptx` or OCR libs:
  - Re-activate your virtual environment and reinstall dependencies.
- Tesseract OCR errors:
  - Install Tesseract and verify executable/path configuration.
- Missing song assets or JSON:
  - Verify expected folder structure under `ehsf/` and songbook paths.
- Locale errors for Spanish date formatting:
  - Install/support the required locale on your OS.

## Historical Notes

Project notes and legacy setup details are in:

- `old_root_files/drw-songtool-notes.txt`

These notes include environment history, song processing conventions, and bilingual workflow details that informed this README.
Other legacy experiment files (test PPTXs, scratch scripts, old JSON drafts) have been archived to `old_root_files/`.