#!/usr/bin/env python3
"""
Streamlit UI for Church Service Generator - FIXED VERSION
Allows non-technical users to generate worship presentations easily
"""

import streamlit as st
import streamlit.components.v1 as components
import json
import os
import base64
from pathlib import Path
from datetime import datetime
import sys
import traceback

# Add current directory to path to import worship and slides modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worship
import slides


def _runtime_base_candidates():
    """Return likely base directories for app resources in dev and packaged runs."""
    candidates = []

    def add(path_obj):
        if not path_obj:
            return
        try:
            resolved = path_obj.resolve()
        except Exception:
            return
        if resolved not in candidates:
            candidates.append(resolved)

    add(Path.cwd())
    add(Path(__file__).resolve().parent)
    try:
        add(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    expanded = []
    for base in candidates:
        if base not in expanded:
            expanded.append(base)
        parent = base.parent
        if parent and parent not in expanded:
            expanded.append(parent)
    return expanded


def _resolve_resource_dir(folder_name):
    """Find a resource directory across common runtime locations."""
    for base in _runtime_base_candidates():
        candidate = base / folder_name
        if candidate.exists() and candidate.is_dir():
            return candidate
    # Nothing found yet (e.g. first run before any songs are processed).
    # Default to next to the actual EXE (packaged) or next to ui.py (source)
    # rather than a bare relative path, which would resolve against the
    # process's cwd -- the PyInstaller onedir _internal folder, not the
    # folder a user is actually looking in next to the .exe.
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent / folder_name
        except Exception:
            pass
    return Path(__file__).resolve().parent / folder_name

# Configuration
EHSF_ROOT_PATH = _resolve_resource_dir("ehsf")
WORSHIP_RESOURCE_PATH = _resolve_resource_dir("worship")

# Keep templates/styles discovery independent from where generated files are written.
OUTPUT_WORSHIP_ROOT_PATH = Path(os.environ.get("CHURCH_SERVICE_OUTPUT_ROOT", "")).expanduser() if os.environ.get("CHURCH_SERVICE_OUTPUT_ROOT") else (EHSF_ROOT_PATH.parent / "worship")

WORSHIP_ROOT = str(OUTPUT_WORSHIP_ROOT_PATH).rstrip("/") + "/"
TEMPLATES_ROOT = str(WORSHIP_RESOURCE_PATH / "templates").rstrip("/") + "/"
SPECS_ROOT = str(OUTPUT_WORSHIP_ROOT_PATH / "specs").rstrip("/") + "/"
os.environ["CHURCH_SERVICE_EHSF_ROOT"] = str(EHSF_ROOT_PATH)
if hasattr(slides, "set_ehsf_root"):
    slides.set_ehsf_root(str(EHSF_ROOT_PATH))
SERVICE_TYPE_OPTIONS = ['Sun - AM', 'Sun - PM', 'Wed', 'Gospel Meeting']
SERVICE_TYPE_TIME_MAP = {
    "Sun - AM": "10:00",
    "Sun - PM": "17:00",
    "Wed": "19:00",
    "Gospel Meeting": "19:00",
}
SONG_BOOK_OPTIONS = {
    "pftl": "Praise for the Lord",
    "phss": "Psalms, Hymns, and Spiritual Songs",
    "eh": "Embry Hills",
    "shs": "Sumphonia Hymn Supplement",
}
CUSTOM_TEMPLATE_KEY = "__custom__"
CUSTOM_TEMPLATE_LABEL = "Custom Template (Build Order)"
CUSTOM_ITEM_TYPE_OPTIONS = [
    "welcome",
    "song",
    "reading",
    "prayer",
    "ls-am",
    "collection",
    "sermon",
    "lesson",
    "report",
    "invitation",
]

# Streamlit page config
st.set_page_config(
    page_title="Church Service Generator",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

HARBOR_BLUE_THEME = {
    "bg": "#dcebf5",
    "surface": "#f7fbff",
    "text": "#102f42",
    "muted": "#35576a",
    "accent": "#1c6f96",
    "hero_start": "#0f4461",
    "hero_end": "#1b6387",
    "hero_text": "#ffffff",
    "field_bg": "#ffffff",
}


def build_ui_style():
    theme = HARBOR_BLUE_THEME

    return f"""
    <style>
    :root {{
        --ui-bg: {theme['bg']};
        --ui-surface: {theme['surface']};
        --ui-text: {theme['text']};
        --ui-muted: {theme['muted']};
        --ui-accent: {theme['accent']};
        --ui-hero-start: {theme['hero_start']};
        --ui-hero-end: {theme['hero_end']};
        --ui-hero-text: {theme['hero_text']};
        --ui-field-bg: {theme['field_bg']};
        --ui-border: var(--ui-accent);
    }}

    .stApp {{
        font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
        background: var(--ui-bg);
        color: var(--ui-text);
    }}

    .stApp p,
    .stApp li,
    .stMarkdown,
    .stMarkdown p,
    .stMarkdown li,
    .stText,
    .stCaption,
    div[data-testid="stMarkdownContainer"] p {{
        color: var(--ui-text);
    }}

    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6,
    div[data-testid="stWidgetLabel"] > label,
    div[data-testid="stExpander"] summary,
    div[data-testid="stFileUploaderDropzoneInstructions"] {{
        color: var(--ui-text) !important;
    }}

    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] *,
    div[data-testid="stForm"] small,
    div[data-testid="stForm"] [data-testid="stMarkdownContainer"] small,
    div[data-testid="stWidgetLabel"] [data-testid="stMarkdownContainer"] p {{
        color: var(--ui-muted) !important;
    }}

    .block-container {{
        max-width: 1420px;
        padding-top: 1.1rem;
        padding-bottom: 1.6rem;
        padding-left: 1.1rem;
        padding-right: 1.1rem;
    }}

    .hero-wrap {{
        width: 100%;
        margin: 0;
        padding: 0.2rem 0 0.7rem 0;
    }}

    .hero {{
        width: 100%;
        margin: 0;
        padding: 1.3rem 1.25rem;
        border-radius: 14px;
        background: linear-gradient(135deg, var(--ui-hero-start) 0%, var(--ui-hero-end) 100%);
        color: var(--ui-hero-text) !important;
        border: 1px solid var(--ui-border);
        box-shadow: 0 10px 22px rgba(15, 68, 97, 0.18);
        margin-bottom: 0.25rem;
        overflow: visible;
    }}

    .hero h1,
    .hero p {{
        color: var(--ui-hero-text) !important;
    }}

    .hero h1 {{
        font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
        margin: 0 0 0.15rem 0;
        font-size: 1.6rem;
        line-height: 1.35;
        letter-spacing: 0;
        font-weight: 700;
    }}

    .hero p {{
        margin: 0;
        font-size: 0.98rem;
        line-height: 1.45;
        opacity: 0.96;
    }}

    .section-heading {{
        margin: 0.6rem 0 0.45rem 0;
        color: var(--ui-text);
        font-size: 0.92rem;
        font-weight: 700;
        letter-spacing: 0.55px;
        text-transform: uppercase;
    }}

    .flow-item {{
        margin: 0.65rem 0 0.45rem 0;
        padding: 0.5rem 0.6rem;
        border-left: 4px solid var(--ui-accent);
        background: linear-gradient(90deg, var(--ui-hero-start) 0%, var(--ui-hero-end) 100%);
        color: var(--ui-hero-text) !important;
        border-radius: 8px;
        font-weight: 700;
        line-height: 1.45;
        overflow-wrap: anywhere;
        letter-spacing: 0;
        box-shadow: inset 0 0 0 1px var(--ui-border), 0 3px 10px rgba(15, 68, 97, 0.12);
    }}

    div[data-testid="stVerticalBlock"] div:has(> div > .section-heading) {{
        border: 1px solid var(--ui-border);
        border-radius: 12px;
        padding: 0.65rem 0.8rem 0.75rem 0.8rem;
        background: var(--ui-surface);
        box-shadow: 0 4px 14px rgba(16, 47, 66, 0.08);
    }}

    div[data-testid="stVerticalBlock"] {{
        gap: 0.6rem;
    }}

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {{
        border-radius: 8px;
        border: 1px solid var(--ui-border);
        background: var(--ui-field-bg);
        box-shadow: none;
        min-height: 2.5rem;
    }}

    div[data-baseweb="select"] > div:hover,
    div[data-baseweb="input"] > div:hover {{
        border-color: var(--ui-accent);
    }}

    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="input"] > div:focus-within {{
        border-color: var(--ui-accent);
        box-shadow: 0 0 0 1px var(--ui-accent);
    }}

    div[data-baseweb="input"] input,
    div[data-baseweb="input"] input[type="number"],
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] span,
    div[data-baseweb="tag"] span,
    div[data-baseweb="select"] [role="combobox"],
    div[data-baseweb="popover"] [role="option"] {{
        color: var(--ui-text) !important;
        -webkit-text-fill-color: var(--ui-text) !important;
    }}

    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="select"] input::placeholder {{
        color: var(--ui-muted) !important;
        -webkit-text-fill-color: var(--ui-muted) !important;
        opacity: 1;
    }}

    div[data-testid="stWidgetLabel"] > label {{
        color: var(--ui-text) !important;
        font-weight: 600;
        line-height: 1.45;
        overflow-wrap: anywhere;
    }}

    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p,
    .stCaption {{
        line-height: 1.45;
    }}

    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        background: var(--ui-surface);
        border: 1px solid var(--ui-border);
        border-radius: 6px;
        padding: 0.12rem;
    }}

    div[data-testid="stTabs"] [data-baseweb="tab"] {{
        border-radius: 4px;
        color: var(--ui-text) !important;
        font-weight: 600;
    }}

    div[data-testid="stTabs"] [aria-selected="true"] {{
        background: var(--ui-accent);
        color: var(--ui-hero-text) !important;
    }}

    .stButton > button {{
        border-radius: 8px;
        border: 1px solid var(--ui-accent);
        background: var(--ui-accent);
        color: var(--ui-hero-text);
        font-weight: 700;
        letter-spacing: 0;
        min-height: 2.6rem;
        box-shadow: 0 5px 14px rgba(28, 111, 150, 0.24);
    }}

    .stButton > button:hover {{
        filter: brightness(0.9);
        border-color: var(--ui-accent);
        background: var(--ui-accent);
    }}

    div[data-testid="stAlert"] {{
        border-radius: 6px;
        border: 1px solid var(--ui-border);
        background: var(--ui-surface);
    }}

    @media (max-width: 900px) {{
        .hero h1 {{
            font-size: 1.3rem;
        }}

        .block-container {{
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }}
    }}
    </style>
    <div class="hero-wrap">
      <div class="hero">
          <h1>Church Service Generator</h1>
          <p>Prepare each service in a clear, simple bulletin-style workflow.</p>
      </div>
    </div>
    """


st.markdown(build_ui_style(), unsafe_allow_html=True)

# Initialize session state
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = None


def should_keep_existing(key, incoming_value, keep_manual):
    """Return True when manual values should not be overwritten by pulled data."""
    if not keep_manual:
        return False

    current_value = st.session_state.get(key)
    if isinstance(current_value, str):
        return current_value.strip() != ""

    if isinstance(current_value, (int, float)):
        if isinstance(incoming_value, (int, float)):
            return current_value != 0 and current_value != incoming_value
        return current_value != 0

    return current_value is not None


def get_available_templates():
    """Load list of available templates"""
    templates = []
    if os.path.exists(TEMPLATES_ROOT):
        for file in os.listdir(TEMPLATES_ROOT):
            if file.endswith('.json'):
                templates.append(file.replace('.json', ''))
    return sorted(templates)


def load_template(template_name):
    """Load template and return the order items with encoding handling"""
    template_path = TEMPLATES_ROOT + template_name + ".json"
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except UnicodeDecodeError:
        with open(template_path, 'r', encoding='latin-1') as f:
            data = json.load(f)
    
    items = data.get('order', [])
    if not isinstance(items, list):
        raise ValueError(f"Template 'order' must be a list, got {type(items).__name__}")
    
    return items


def make_custom_template_item(item_type, seq):
    """Create one custom order item with sensible defaults."""
    if item_type == "welcome":
        return {
            "type": "welcome",
            "id": f"welcome-{seq}",
            "desc": "Announcements",
            "esp": "Bienvenida",
            "position": "Announcements",
        }
    if item_type == "song":
        return {
            "type": "song",
            "id": f"song-{seq}",
            "position": "Song Leader",
        }
    if item_type == "reading":
        return {
            "type": "reading",
            "id": f"reading-{seq}",
            "position": "Scripture Reading",
        }
    if item_type == "prayer":
        return {
            "type": "prayer",
            "id": f"prayer-{seq}",
            "position": "Prayer",
        }
    if item_type == "ls-am":
        return {
            "type": "ls-am",
            "id": f"ls-{seq}",
            "position": "Lord's Supper",
            "reading": 0,
        }
    if item_type == "collection":
        return {
            "type": "collection",
            "id": f"coll-{seq}",
            "style": "zelle",
            "reading": 0,
        }
    if item_type in ["sermon", "lesson", "report"]:
        return {
            "type": item_type,
            "id": f"{item_type}-{seq}",
            "position": "Preach",
        }
    if item_type == "invitation":
        return {
            "type": "invitation",
            "id": f"invitation-{seq}",
        }
    return {"type": item_type, "id": f"{item_type}-{seq}"}


def get_song_positions(template_items):
    """Extract song positions from template"""
    songs = {}
    for item in template_items:
        if not isinstance(item, dict):
            continue
        if 'song' in item.get('type', ''):
            if 'id' in item:
                songs[item['id']] = item
    return songs


def get_leader_positions(template_items):
    """Extract leader positions from template"""
    leaders = {}
    for item in template_items:
        if not isinstance(item, dict):
            continue
        if 'position' in item:
            position_name = item['position']
            leaders[position_name] = item
    return leaders


def build_default_readings(template_items):
    """Build default readings structure expected by worship.fetch_readings."""
    readings = {}
    for item in template_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get('id')
        item_type = item.get('type')
        if not item_id:
            continue
        if item_type == 'reading':
            readings[item_id] = {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}
        elif item_type in ['ls-am', 'collection']:
            readings[item_id] = {"reading": ""}
        elif item_type in ['sermon', 'lesson', 'report']:
            readings[item_id] = {"title": "", "título": ""}
    return readings


def build_song_search_index():
    """Build searchable song index.

    Preferred source is ehsf/song-search-index.json generated by
    tools/build_song_lookup.py. Falls back to live scanning when the file
    is missing.
    """
    ehsf_root = EHSF_ROOT_PATH
    lookup_file = ehsf_root / "song-search-index.json"

    if lookup_file.exists():
        try:
            loaded = load_json_safe(str(lookup_file))
            songs = loaded.get("songs", []) if isinstance(loaded, dict) else []
            if isinstance(songs, list):
                normalized = []
                for song in songs:
                    if not isinstance(song, dict):
                        continue
                    title = str(song.get("title", "")).strip()
                    if not title:
                        continue
                    normalized.append({
                        "title": title,
                        "title_key": str(song.get("title_key", title.lower())).strip(),
                        "book": str(song.get("book", "")).strip().lower(),
                        "number": str(song.get("number", "")).strip(),
                        "source_book_folder": str(song.get("source_book_folder", "")).strip(),
                        "source_folder": str(song.get("source_folder", "")).strip(),
                    })
                if normalized:
                    return normalized
        except Exception:
            # Non-blocking fallback to live scan.
            pass

    # Fallback scan for environments where lookup file has not been generated yet.
    results = []
    for json_file in ehsf_root.rglob("*.json"):
        if json_file.name == "song-search-index.json":
            continue
        try:
            song_data = load_json_safe(str(json_file))
            if not isinstance(song_data, dict):
                continue
            title = str(song_data.get("title", "")).strip()
            if not title:
                continue

            rel_parts = json_file.relative_to(ehsf_root).parts
            source_folder = "/".join(rel_parts[:-1])
            source_book_folder = "/".join(rel_parts[:-2]) if len(rel_parts) >= 3 else (rel_parts[0] if rel_parts else "")

            if len(rel_parts) >= 3:
                book_code = rel_parts[-3].lower()
                song_num = rel_parts[-2]
            elif len(rel_parts) >= 2:
                book_code = rel_parts[0].lower()
                song_num = rel_parts[-2]
            else:
                book_code = str(song_data.get("book", "")).strip().lower()
                song_num = str(song_data.get("number", "")).strip()

            if not book_code:
                book_code = "pftl"
            if not song_num:
                song_num = str(song_data.get("number", "1")).strip() or "1"

            results.append({
                "title": title,
                "title_key": title.lower(),
                "book": book_code,
                "number": song_num,
                "source_book_folder": source_book_folder,
                "source_folder": source_folder,
            })
        except Exception:
            continue

    return results


def song_source_group(entry):
    """Normalize an indexed entry into a user-facing source group label."""
    source_folder = str(entry.get("source_folder", "")).strip("/")
    if not source_folder:
        return "ehsf"

    parts = source_folder.split("/")
    if len(parts) >= 2 and parts[0] == "esp":
        return f"ehsf/{parts[0]}/{parts[1]}"
    return f"ehsf/{parts[0]}"


def create_worship_files(date, time, template, songs_data, leaders_data, readings_data=None, service_type='Sun - AM', template_items_override=None):
    """Create initial worship files (spec, songs, leaders, readings)"""
    # Parse date/time
    wdate = date.strftime("%Y-%m-%d")
    wtime = time.strftime("%H:%M:%S")
    
    # Get base paths
    isodate = wdate + "T" + wtime
    wdiso = datetime.fromisoformat(isodate)
    specpath = SPECS_ROOT + wdiso.strftime("%Y/%m/%d/%H%M")
    specbase = SPECS_ROOT + wdiso.strftime("%Y/%m/%d/%H%M/%Y%m%d-%H%M")
    jsonbase = WORSHIP_ROOT + wdiso.strftime("%Y/%Y%m%d-%H%M")
    
    # Create directories
    Path(specpath).mkdir(parents=True, exist_ok=True)
    Path(WORSHIP_ROOT + wdiso.strftime("%Y")).mkdir(parents=True, exist_ok=True)
    
    # Ensure songs_data is a dict
    if not isinstance(songs_data, dict):
        songs_data = {}
    if not isinstance(leaders_data, dict):
        leaders_data = {}
    if not isinstance(readings_data, dict):
        readings_data = {}
    
    # Create spec.json
    spec = {
        'isodate': isodate,
        'template': 'custom' if template == CUSTOM_TEMPLATE_KEY else template,
        'language': 'bil',
        'type': service_type
    }
    with open(specbase + "-spec.json", 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=4)
    
    # Create songs.json
    with open(specbase + "-songs.json", 'w', encoding='utf-8') as f:
        json.dump({'songs': songs_data}, f, ensure_ascii=False, indent=4)
    
    # Create leaders.json
    with open(specbase + "-leaders.json", 'w', encoding='utf-8') as f:
        json.dump({'leaders': leaders_data}, f, ensure_ascii=False, indent=4)
    
    # Create readings.json
    readings = {}
    source_template_items = template_items_override if template_items_override is not None else load_template(template)
    for item in source_template_items:
        if not isinstance(item, dict):
            continue
        if item.get('type') == 'reading' and 'id' in item:
            readings[item['id']] = {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}
        elif item.get('type') == 'ls-am' and 'id' in item:
            readings[item['id']] = {"reading": ""}
        elif item.get('type') in ['sermon', 'lesson', 'report'] and 'id' in item:
            readings[item['id']] = {"title": "", "título": ""}

    for item_id, item_data in readings_data.items():
        if isinstance(item_data, dict):
            readings[item_id] = item_data
    
    with open(specbase + "-readings.json", 'w', encoding='utf-8') as f:
        json.dump({'readings': readings}, f, ensure_ascii=False, indent=4)
    
    return specbase, jsonbase


def load_json_safe(path):
    """Load JSON file with encoding fallback"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1') as f:
            return json.load(f)


def read_binary_file(path):
    """Read a binary file and return bytes, or None if missing/unreadable."""
    if not path or not isinstance(path, str):
        return None
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


def render_generated_downloads():
    """Trigger PowerPoint auto-download for the most recently generated file."""
    generated = st.session_state.get('generated_files')
    if not isinstance(generated, dict):
        return

    pptx_name = generated.get('pptx_name')
    pptx_bytes = generated.get('pptx_bytes')

    if pptx_bytes is None:
        pptx_path = generated.get('pptx_path')
        if isinstance(pptx_path, str):
            pptx_bytes = read_binary_file(pptx_path)
            if not pptx_name:
                pptx_name = os.path.basename(pptx_path)

    if not pptx_name:
        pptx_name = "service.pptx"

    if not pptx_bytes:
        st.warning("Generated file is no longer available on this server.")
        return

    if st.session_state.get("auto_download_pptx") and pptx_bytes:
        pptx_b64 = base64.b64encode(pptx_bytes).decode("ascii")
        safe_filename = json.dumps(pptx_name)
        components.html(
            f"""
            <script>
            const a = document.createElement('a');
            a.href = 'data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,{pptx_b64}';
            a.download = {safe_filename};
            document.body.appendChild(a);
            a.click();
            a.remove();
            </script>
            """,
            height=0,
        )
        st.session_state["auto_download_pptx"] = False
        st.toast("PowerPoint download started.", icon="⬇️")

    # Keep a manual backup button for browsers that block auto-download.
    st.download_button(
        label="Download PowerPoint",
        data=pptx_bytes,
        file_name=pptx_name,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
        key="download_pptx_manual",
    )


def get_song_structure(book, song_num, source_folder=""):
    """Return available verses and chorus slots for a song.
    Uses the same metadata resolver as slide generation, including fallback
    layout inference from song PNG images.
    """
    try:
        song_value = int(song_num)
        _, paths = slides.get_song_paths_new(book, song_value)
        meta = slides.load_song_meta_with_fallback(book, song_value, paths, source_folder)

        verses = []
        chorus = []

        verses = sorted([
            int(v)
            for v in meta.get('verses', {}).keys()
            if str(v).isdigit()
        ])
        chorus = sorted([
            int(v)
            for v in meta.get('chorus', {}).keys()
            if str(v).isdigit()
        ])

        return verses, chorus, None
    except Exception as e:
        return [], [], str(e)


def generate_presentation(date, time, template, songs_data, leaders_data, readings_data=None, service_type='Sun - AM', template_items_override=None):
    """Generate the complete presentation"""
    try:
        # Step 1: Create worship files
        specbase, jsonbase = create_worship_files(
            date,
            time,
            template,
            songs_data,
            leaders_data,
            readings_data,
            service_type,
            template_items_override=template_items_override,
        )
        
        # Step 2: Generate JSON (mimics worship.py generate_json)
        spec = load_json_safe(specbase + "-spec.json")
        if not isinstance(spec, dict):
            raise ValueError(f"spec.json root should be dict, got {type(spec).__name__}")
        
        # Load songs data with type checking
        songs_file_data = load_json_safe(specbase + "-songs.json")
        if not isinstance(songs_file_data, dict):
            raise ValueError(f"songs.json root should be dict, got {type(songs_file_data).__name__}")
        songs = songs_file_data.get('songs', {})
        if not isinstance(songs, dict):
            raise ValueError(f"songs.json['songs'] should be dict, got {type(songs).__name__}")
        
        # Load leaders data with type checking
        leaders_file_data = load_json_safe(specbase + "-leaders.json")
        if not isinstance(leaders_file_data, dict):
            raise ValueError(f"leaders.json root should be dict, got {type(leaders_file_data).__name__}")
        leaders = leaders_file_data.get('leaders', {})
        if not isinstance(leaders, dict):
            raise ValueError(f"leaders.json['leaders'] should be dict, got {type(leaders).__name__}")
        
        # Load readings data with type checking
        readings_file_data = load_json_safe(specbase + "-readings.json")
        if not isinstance(readings_file_data, dict):
            raise ValueError(f"readings.json root should be dict, got {type(readings_file_data).__name__}")
        readings = readings_file_data.get('readings', {})
        if not isinstance(readings, dict):
            raise ValueError(f"readings.json['readings'] should be dict, got {type(readings).__name__}")
        
        # Load template and merge data
        if template_items_override is not None:
            template_items = json.loads(json.dumps(template_items_override))
        else:
            template_items = load_template(template)
        
        # Ensure template_items is a list
        if not isinstance(template_items, list):
            raise ValueError(f"Template items should be a list, got {type(template_items).__name__}")
        
        for idx, item in enumerate(template_items):
            if not isinstance(item, dict):
                raise ValueError(f"Template item {idx} should be a dict, got {type(item).__name__}")
            
            # Merge position/leader data
            if 'position' in item:
                pos_name = item['position']
                if pos_name in leaders:
                    leader_data = leaders[pos_name]
                    item['leader'] = leader_data
            
            # Merge song/reading data
            if 'id' in item:
                item_id = item['id']
                
                if item_id in songs:
                    song_data = songs[item_id]
                    if isinstance(song_data, dict):
                        item.update(song_data)
                    else:
                        raise ValueError(f"Song data for '{item_id}' should be dict, got {type(song_data).__name__}: {song_data}")
                
                if item_id in readings:
                    reading_data = readings[item_id]
                    if isinstance(reading_data, dict):
                        item.update(reading_data)
                    else:
                        raise ValueError(f"Reading data for '{item_id}' should be dict, got {type(reading_data).__name__}")
        
        spec['items'] = template_items
        
        # Write final JSON with proper encoding
        with open(jsonbase + ".json", 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False, indent=4)
        
        # Step 3: Generate PPTX
        outfile = jsonbase + ".pptx"
        slides.make_worship_deck(jsonbase + ".json")
        
        return True, jsonbase + ".json", outfile
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
        return False, str(e), error_detail


# Main UI layout

templates = get_available_templates()
selected_template = None
template_items = []
songs_input = {}
leaders_input = {}
readings_input = {}

st.markdown('<div class="section-heading">Service Setup</div>', unsafe_allow_html=True)
service_date = st.date_input("Service Date", value=datetime.now())
service_type = st.selectbox("Service Type", SERVICE_TYPE_OPTIONS, index=0)
service_time = datetime.strptime(SERVICE_TYPE_TIME_MAP[service_type], "%H:%M").time()

if templates:
    template_choices = ["-- Select Template --", CUSTOM_TEMPLATE_LABEL] + templates
    if "template_select" in st.session_state and st.session_state["template_select"] not in template_choices:
        st.session_state["template_select"] = "-- Select Template --"
    selected_template_choice = st.selectbox("Template", template_choices, index=0, key="template_select")
    if selected_template_choice in templates:
        selected_template = selected_template_choice
    elif selected_template_choice == CUSTOM_TEMPLATE_LABEL:
        selected_template = CUSTOM_TEMPLATE_KEY
else:
    st.error("No templates found in worship/templates")

if not selected_template:
    st.info("Select template and date first. The rest of the form will appear after template selection.")
    st.stop()

if selected_template == CUSTOM_TEMPLATE_KEY:
    if "custom_template_items" not in st.session_state:
        st.session_state.custom_template_items = []

    st.markdown('<div class="section-heading">Custom Template Builder</div>', unsafe_allow_html=True)
    builder_col1, builder_col2 = st.columns([2.2, 1])
    with builder_col1:
        custom_item_type = st.selectbox(
            "Add service item",
            CUSTOM_ITEM_TYPE_OPTIONS,
            key="custom_item_type_select",
            format_func=lambda t: t.replace("-", " ").title(),
        )
    with builder_col2:
        st.write("")
        if st.button("Add Item", key="custom_add_item", use_container_width=True):
            current_items = list(st.session_state.custom_template_items)
            seq = 1 + sum(1 for item in current_items if isinstance(item, dict) and item.get("type") == custom_item_type)
            current_items.append(make_custom_template_item(custom_item_type, seq))
            st.session_state.custom_template_items = current_items
            st.rerun()

    custom_items = list(st.session_state.custom_template_items)
    if custom_items:
        st.caption("Arrange the order using Up/Down, then fill details below in Service Flow.")
        for ndx, citem in enumerate(custom_items):
            ccols = st.columns([7, 1, 1, 1])
            item_desc = f"{ndx + 1}. {citem.get('type', 'item')} ({citem.get('id', 'no-id')})"
            ccols[0].markdown(item_desc)
            if ccols[1].button("↑", key=f"custom_up_{ndx}", disabled=(ndx == 0)):
                custom_items[ndx - 1], custom_items[ndx] = custom_items[ndx], custom_items[ndx - 1]
                st.session_state.custom_template_items = custom_items
                st.rerun()
            if ccols[2].button("↓", key=f"custom_down_{ndx}", disabled=(ndx == len(custom_items) - 1)):
                custom_items[ndx + 1], custom_items[ndx] = custom_items[ndx], custom_items[ndx + 1]
                st.session_state.custom_template_items = custom_items
                st.rerun()
            if ccols[3].button("✕", key=f"custom_remove_{ndx}"):
                del custom_items[ndx]
                st.session_state.custom_template_items = custom_items
                st.rerun()
    else:
        st.info("Add at least one item to start building a custom service flow.")

    template_items = st.session_state.custom_template_items
else:
    template_items = load_template(selected_template)

leader_positions = get_leader_positions(template_items)

counts = {}
for item in template_items:
    if isinstance(item, dict):
        item_type = item.get('type', 'unknown')
        counts[item_type] = counts.get(item_type, 0) + 1

if counts:
    summary = ", ".join([f"{k}: {v}" for k, v in sorted(counts.items())])
    st.caption(f"Template items: {summary}")

keep_manual_overrides = True
wdate = service_date.strftime("%Y-%m-%d")
wtime = service_time.strftime("%H:%M:%S")
autofill_signature = f"{selected_template}|{wdate}|{wtime}|{service_type}|{int(keep_manual_overrides)}"
autofill_ran_for = st.session_state.get("autofill_ran_for")

if selected_template != CUSTOM_TEMPLATE_KEY and autofill_ran_for != autofill_signature:
    try:
        fetched_leaders_data = worship.fetch_leaders(wdate, wtime, service_type)
        fetched_leaders = fetched_leaders_data.get('leaders', {}) if isinstance(fetched_leaders_data, dict) else {}
        if not isinstance(fetched_leaders, dict):
            fetched_leaders = {}

        fetched_readings_seed = build_default_readings(template_items)
        fetched_readings_data = worship.fetch_readings(wdate, fetched_readings_seed, service_type)
        fetched_readings = fetched_readings_data.get('readings', {}) if isinstance(fetched_readings_data, dict) else {}
        if not isinstance(fetched_readings, dict):
            fetched_readings = {}

        for pos_name in sorted(leader_positions.keys()):
            if pos_name in fetched_leaders and isinstance(fetched_leaders[pos_name], str):
                for idx, item in enumerate(template_items):
                    if isinstance(item, dict) and item.get('position') == pos_name:
                        leader_key = f"leader_{pos_name}_{idx}"
                        if not should_keep_existing(leader_key, fetched_leaders[pos_name], keep_manual_overrides):
                            st.session_state[leader_key] = fetched_leaders[pos_name]

        for item in template_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get('id')
            item_type = item.get('type')
            if not item_id or item_id not in fetched_readings:
                continue

            entry = fetched_readings[item_id]
            if not isinstance(entry, dict):
                continue

            if item_type == 'reading':
                lang = entry.get('lang')
                if isinstance(lang, list):
                    if len(lang) > 0 and isinstance(lang[0], dict):
                        eng_passage = lang[0].get('passage', '')
                        eng_passage_key = f"reading_eng_passage_{item_id}"
                        if not should_keep_existing(eng_passage_key, eng_passage, keep_manual_overrides):
                            st.session_state[eng_passage_key] = eng_passage
                    if len(lang) > 1 and isinstance(lang[1], dict):
                        esp_passage_key = f"reading_esp_passage_{item_id}"
                        esp_passage = lang[1].get('passage', '')
                        if not should_keep_existing(esp_passage_key, esp_passage, keep_manual_overrides):
                            st.session_state[esp_passage_key] = esp_passage
            elif item_type in ['ls-am', 'collection']:
                reading_index = entry.get('reading')
                try:
                    parsed_index = int(reading_index)
                    index_key = f"reading_index_{item_id}"
                    if not should_keep_existing(index_key, parsed_index, keep_manual_overrides):
                        st.session_state[index_key] = parsed_index
                except (TypeError, ValueError):
                    pass
            elif item_type in ['sermon', 'lesson', 'report']:
                title_en_key = f"title_en_{item_id}"
                title_es_key = f"title_es_{item_id}"
                title_en = entry.get('title', '')
                title_es = entry.get('título', '')
                if not should_keep_existing(title_en_key, title_en, keep_manual_overrides):
                    st.session_state[title_en_key] = title_en
                if not should_keep_existing(title_es_key, title_es, keep_manual_overrides):
                    st.session_state[title_es_key] = title_es

        st.session_state["autofill_ran_for"] = autofill_signature
    except Exception:
        # Non-breaking behavior: keep form usable even if pull API fails.
        st.session_state["autofill_ran_for"] = autofill_signature

st.markdown('<div class="section-heading">Service Flow Inputs (PowerPoint Order)</div>', unsafe_allow_html=True)

song_search_index = build_song_search_index()
song_slots = []
for idx, item in enumerate(template_items):
    if not isinstance(item, dict):
        continue
    if 'song' in item.get('type', '') and item.get('id'):
        slot_label = f"{idx + 1}. {item.get('type', 'song')} ({item.get('id')})"
        song_slots.append({
            "label": slot_label,
            "item_id": item.get('id'),
            "idx": idx,
        })

flow_tab, search_tab = st.tabs(["Service Flow", "Song Search"])

with search_tab:
    if song_search_index:
        st.caption(f"Search by title, then apply to a song slot. Indexed songs: {len(song_search_index)}")

        source_groups = sorted({song_source_group(entry) for entry in song_search_index})
        source_options = ["All sources"] + source_groups
        default_source_index = source_options.index("ehsf/esp/pftl") if "ehsf/esp/pftl" in source_options else 0
        selected_source_group = st.selectbox(
            "Song Source",
            options=source_options,
            index=default_source_index,
            key="song_search_source_group"
        )

        filtered_index = song_search_index
        if selected_source_group != "All sources":
            filtered_index = [
                entry for entry in song_search_index
                if song_source_group(entry) == selected_source_group
            ]

        search_titles = sorted({entry["title"] for entry in filtered_index})
        searched_song = st.selectbox(
            "Find song by title",
            ["-- Search by title --"] + search_titles,
            index=0,
            key="song_search_lookup"
        )

        if searched_song != "-- Search by title --":
            matches = [
                entry
                for entry in filtered_index
                if entry.get("title", "").lower() == searched_song.lower()
            ]
            if matches:
                def format_match(entry):
                    source_label = entry.get("source_book_folder") or entry.get("source_folder") or "unknown"
                    return f"{entry.get('book', '').upper()}-{entry.get('number', '')} | {source_label}"

                selected_match_label = st.selectbox(
                    "Choose source",
                    options=[format_match(match) for match in matches],
                    key="song_search_match_choice"
                )
                selected_match = next(
                    (match for match in matches if format_match(match) == selected_match_label),
                    matches[0]
                )
                book_code = selected_match.get("book", "")
                song_num = selected_match.get("number", "")
                source_folder = selected_match.get("source_folder", "")
                st.success(
                    f"Found: **{searched_song}** ({book_code.upper()}-{song_num}) from {source_folder or 'unknown source'}"
                )

                if song_slots:
                    target_label = st.selectbox(
                        "Apply to song slot",
                        options=[slot["label"] for slot in song_slots],
                        key="song_search_target_slot"
                    )

                    if st.button("Use This Song", key="song_search_apply_button"):
                        target = next((slot for slot in song_slots if slot["label"] == target_label), None)
                        if target:
                            st.session_state[f"book_{target['item_id']}_{target['idx']}"] = book_code
                            try:
                                applied_song_num = int(song_num)
                            except (TypeError, ValueError):
                                applied_song_num = 1
                            st.session_state[f"song_{target['item_id']}_{target['idx']}"] = applied_song_num
                            st.session_state[f"song_source_{target['item_id']}_{target['idx']}"] = source_folder
                            st.session_state["song_search_applied_message"] = (
                                f"Applied {book_code.upper()}-{song_num} ({source_folder or 'unknown source'}) to {target_label}."
                            )
                            st.rerun()
                else:
                    st.info("No song slots are available in this template.")
            else:
                st.warning("Song not found in the metadata index.")
    else:
        st.info("Song search metadata is not available.")

with flow_tab:
    if "song_search_applied_message" in st.session_state:
        st.info(st.session_state["song_search_applied_message"])

    missing_song_slots = []
    last_song_payload = None
    last_song_label = None

    for idx, item in enumerate(template_items):
        if not isinstance(item, dict):
            continue

        item_type = item.get('type', 'unknown')
        item_id = item.get('id')
        position_name = item.get('position')
        item_label = f"{idx + 1}. {item_type}"
        if item_id:
            item_label += f" ({item_id})"

        st.markdown(f'<div class="flow-item">{item_label}</div>', unsafe_allow_html=True)

        if position_name and "prayer for" not in position_name.lower() and "reading" not in position_name.lower() and item_type not in ['prayer', 'reading', 'welcome']:
            leaders_input[position_name] = st.text_input(
                f"Leader: {position_name}",
                key=f"leader_{position_name}_{idx}"
            )

        if 'song' in item_type and item_id:
            default_book = item.get("book", "pftl") if isinstance(item, dict) else "pftl"
            default_song = item.get("song", "") if isinstance(item, dict) else ""
            try:
                default_song_num = int(default_song)
            except (TypeError, ValueError):
                default_song_num = 0

            # Song title slides should mirror the most recent selected song.
            if item_type == 'song-title':
                auto_payload = None
                if isinstance(last_song_payload, dict):
                    auto_payload = {
                        k: (list(v) if isinstance(v, list) else v)
                        for k, v in last_song_payload.items()
                    }
                elif default_song_num > 0:
                    auto_payload = {
                        "book": default_book,
                        "song": str(default_song_num),
                        "coda": 0,
                    }
                    existing_source_folder = str(item.get("source_folder", "")).strip()
                    if existing_source_folder:
                        auto_payload["source_folder"] = existing_source_folder

                if auto_payload is not None:
                    songs_input[item_id] = auto_payload
                    copied_from = last_song_label if last_song_label else f"{default_book.upper()}-{default_song_num:03d}"
                    st.caption(f"Auto-filled {item_id} from previous song: {copied_from}")
                else:
                    missing_song_slots.append(item_label)
                    st.caption("Auto-fill waits for a previous song selection.")
                continue

            song_col1, song_col2, song_col3, song_col4, song_col5 = st.columns([0.9, 1.1, 1.2, 2.0, 2.0])
            with song_col1:
                st.caption("Song Book")
                book_options = list(SONG_BOOK_OPTIONS.keys())
                default_book_index = book_options.index(default_book) if default_book in book_options else 0
                
                book = st.selectbox(
                    f"Book ({item_id})",
                    book_options,
                    index=default_book_index,
                    key=f"book_{item_id}_{idx}",
                    label_visibility="collapsed",
                    format_func=lambda code: SONG_BOOK_OPTIONS.get(code, code)
                )
            with song_col2:
                st.caption("Song Number")
                
                song_num = st.number_input(
                    f"Song # ({item_id})",
                    min_value=0,
                    max_value=1000,
                    key=f"song_{item_id}_{idx}",
                    value=default_song_num,
                    label_visibility="collapsed"
                )

            with song_col3:
                st.caption("Song Source")
                existing_source_folder = str(
                    st.session_state.get(
                        f"song_source_{item_id}_{idx}",
                        item.get("source_folder", "") if isinstance(item, dict) else ""
                    )
                ).strip().lower()
                default_source_key = "esp" if existing_source_folder.startswith("esp") else "eng"
                source_choice = st.selectbox(
                    f"Source ({item_id})",
                    ["eng", "esp"],
                    index=1 if default_source_key == "esp" else 0,
                    key=f"song_source_choice_{item_id}_{idx}",
                    label_visibility="collapsed",
                    format_func=lambda code: "English (ehsf)" if code == "eng" else "Spanish (ehsf/esp)"
                )

                if source_choice == "esp":
                    source_folder = f"esp/{book}"
                else:
                    source_folder = book
                st.session_state[f"song_source_{item_id}_{idx}"] = source_folder

            available_verses = []
            available_chorus = []
            song_error = None
            has_song_selected = int(song_num) > 0
            if has_song_selected:
                available_verses, available_chorus, song_error = get_song_structure(book, int(song_num), source_folder)
            else:
                missing_song_slots.append(item_label)

            selected_verses = None
            selected_chorus = None
            with song_col4:
                st.caption("Verses")
                if available_verses:
                    selected_verses = st.multiselect(
                        f"Verses ({item_id})",
                        options=available_verses,
                        default=available_verses,
                        key=f"verses_{item_id}_{idx}",
                        label_visibility="collapsed"
                    )
                else:
                    st.caption("Select song number to load verses")
            with song_col5:
                st.caption("Chorus")
                if available_chorus:
                    selected_chorus = st.multiselect(
                        f"Chorus After Verse ({item_id})",
                        options=available_chorus,
                        default=available_chorus,
                        key=f"chorus_{item_id}_{idx}",
                        label_visibility="collapsed"
                    )
                else:
                    st.caption("Select song number to load chorus")

            if song_error and has_song_selected:
                st.caption(f"Can\'t find song {book.upper()}-{int(song_num):03d}.")
            elif has_song_selected and not available_verses and not available_chorus:
                st.caption(f"Song {book.upper()}-{int(song_num):03d} was found, but it has no verse/chorus layout data.")

            if has_song_selected:
                song_payload = {
                    "book": book,
                    "song": str(song_num),
                    "coda": 0
                }

                selected_source_folder = source_folder or st.session_state.get(f"song_source_{item_id}_{idx}", "")
                if selected_source_folder:
                    song_payload["source_folder"] = str(selected_source_folder)

                if available_verses and selected_verses is not None:
                    if len(selected_verses) == 0:
                        st.warning(f"{item_id}: No verses selected. Using all verses.")
                    elif selected_verses != available_verses:
                        song_payload["verses"] = selected_verses

                if available_chorus and selected_chorus is not None:
                    if len(selected_chorus) == 0:
                        song_payload["chorus"] = [0]
                    elif selected_chorus != available_chorus:
                        song_payload["chorus"] = selected_chorus

                songs_input[item_id] = song_payload
                last_song_payload = {
                    k: (list(v) if isinstance(v, list) else v)
                    for k, v in song_payload.items()
                }
                last_song_label = f"{book.upper()}-{int(song_num):03d}"

        if item_type == 'reading' and item_id:
            reading_number_str = st.text_input(
                "Scripture reading number (optional)",
                key=f"reading_number_{item_id}_{idx}",
                help="Optional manual override if you need to track or force a specific reading number."
            )
            eng_passage = st.text_input("English passage", key=f"reading_eng_passage_{item_id}")
            esp_passage = st.text_input("Spanish passage (optional)", key=f"reading_esp_passage_{item_id}")
            reading_payload = {
                "lang": [
                    {"passage": eng_passage},
                    {"passage": esp_passage}
                ]
            }
            if reading_number_str.strip().isdigit():
                reading_payload["reading"] = int(reading_number_str.strip())
            readings_input[item_id] = reading_payload
        elif item_type in ['ls-am', 'collection'] and item_id:
            reading_index = st.number_input(
                "Reading slide index (0-based)",
                min_value=0,
                max_value=50,
                value=0,
                key=f"reading_index_{item_id}"
            )
            readings_input[item_id] = {"reading": int(reading_index)}
        elif item_type == 'sermon' and item_id:
            st.info("Sermon details will be added later by another person.")
            readings_input[item_id] = {"title": "", "título": ""}
        elif item_type in ['lesson', 'report'] and item_id:
            title_en = st.text_input("Title (English)", key=f"title_en_{item_id}")
            title_es = st.text_input("Title (Spanish)", key=f"title_es_{item_id}")
            readings_input[item_id] = {"title": title_en, "título": title_es}
        elif item_type in ['welcome', 'invitation'] and item_id:
            desc = st.text_input("Display text (optional)", key=f"desc_{item_id}_{idx}")
            if desc:
                readings_input[item_id] = {"desc": desc}

# Generate Button
st.divider()
missing_song_slots = [slot for slot in locals().get("missing_song_slots", []) if slot]
if missing_song_slots:
    st.warning("Select a song number for each song item before generating the presentation.")

col_left, col_generate, col_right = st.columns([1, 1.2, 1])

with col_generate:
    if st.button("🚀 Generate & Download PowerPoint", type="primary", use_container_width=True, disabled=len(missing_song_slots) > 0):
        with st.spinner("🔄 Generating presentation..."):
            success, result, debug_info = generate_presentation(
                service_date,
                service_time,
                selected_template,
                songs_input if 'songs_input' in locals() else {},
                leaders_input if 'leaders_input' in locals() else {},
                readings_input if 'readings_input' in locals() else {},
                service_type,
                template_items_override=template_items if selected_template == CUSTOM_TEMPLATE_KEY else None,
            )
        
        if success:
            pptx_bytes = read_binary_file(debug_info)
            st.session_state.generated_files = {
                'pptx_path': debug_info,
                'pptx_name': os.path.basename(debug_info),
                'pptx_bytes': pptx_bytes,
            }
            st.session_state["auto_download_pptx"] = True
            st.toast("Presentation generated. Starting download...", icon="✅")
            st.success("Presentation generated successfully. Your browser should start the download automatically.")
        else:
            st.error(f"❌ Error generating presentation: {result}")
            if isinstance(debug_info, str) and debug_info:
                st.write("**Debug Information:**")
                st.code(debug_info, language="python")

render_generated_downloads()
