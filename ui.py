#!/usr/bin/env python3
"""
Streamlit UI for Church Service Generator - FIXED VERSION
Allows non-technical users to generate worship presentations easily
"""

import streamlit as st
import streamlit.components.v1 as components
import json
import os
import re
import base64
from pathlib import Path
from datetime import datetime
import sys
import traceback

# Add current directory to path to import worship and slides modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worship
import slides
import ui_theme


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

    if getattr(sys, "frozen", False):
        # Packaged EXE: user-writable/generated data (ehsf/, output worship/)
        # always lives next to the actual executable, checked first here --
        # deliberately not cwd, which depends on how/where the EXE happened
        # to be launched from and would make the same data resolve to a
        # different folder on different runs.
        try:
            add(Path(sys.executable).resolve().parent)
        except Exception:
            pass
        # Bundled read-only resources (e.g. worship/templates) ship inside
        # the PyInstaller onedir bundle folder (_internal, next to the exe),
        # not next to the exe itself. __file__ for a script executed out of
        # that bundle resolves to _internal, and moves correctly along with
        # the app if the whole onedir folder is relocated, so it's safe to
        # check as a fallback after the exe-adjacent folder.
        try:
            add(Path(__file__).resolve().parent)
        except Exception:
            pass
    else:
        add(Path.cwd())
        add(Path(__file__).resolve().parent)

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


def _resolve_bundled_templates_dir():
    """Resolve the shipped worship/ resource folder (the template library).

    This must NOT be found via the same "does a folder named worship exist
    nearby" scan _resolve_resource_dir does for ehsf/: OUTPUT_WORSHIP_ROOT_PATH
    below (where generated services get written) is exe_dir / "worship" --
    the exact same path and name as the bundled template folder would be if
    it were looked up the same way. Once a single service has ever been
    generated, that output folder exists, so a generic scan permanently
    matches it instead of the real template library and "No templates found
    in worship/templates" never goes away, even on a correct fresh build.
    The template library only ever lives in one deterministic place: inside
    the PyInstaller onedir bundle (_internal, alongside ui.py) when frozen,
    or next to ui.py itself in a source checkout.
    """
    if getattr(sys, "frozen", False):
        try:
            return Path(__file__).resolve().parent / "worship"
        except Exception:
            return Path(sys.executable).resolve().parent / "_internal" / "worship"
    return Path(__file__).resolve().parent / "worship"

# Configuration
EHSF_ROOT_PATH = _resolve_resource_dir("ehsf")
WORSHIP_RESOURCE_PATH = _resolve_bundled_templates_dir()

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
    "song-title",
    "song-music",
    "reading",
    "prayer",
    "ls-am",
    "collection",
    "sermon",
    "lesson",
    "report",
    "announcements-title",
    "invitation",
]
CUSTOM_ITEM_TYPE_LABELS = {
    # "song-title"/"song-music" are the same mechanism the AM template uses
    # for the invitation song: a preview slide before the sermon (title
    # only, no music) and a matching background-music slide after it (music
    # only, no title) -- see make_custom_template_item's docstring for how
    # the two get linked. Generic internal names, so give them a label a
    # user planning a service actually recognizes.
    "song-title": "Invitation Song (Preview)",
    "song-music": "Invitation Song (Music)",
    "announcements-title": "Announcements",
}

# Streamlit page config
st.set_page_config(
    page_title="Church Service Generator",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

ui_theme.inject_shared_theme()
st.markdown(
    '''<div class="hero-wrap">
      <div class="hero">
          <h1>Church Service Generator</h1>
          <p>Prepare each service in a clear, simple bulletin-style workflow.</p>
      </div>
    </div>''',
    unsafe_allow_html=True,
)

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


def list_saved_services(limit=200):
    """List past generated services under worship/<year>/<YYYYMMDD>-<HHMM>.json,
    most recent first.

    Every "Generate" click already writes one of these -- it's the full
    merged worship JSON make_worship_deck() consumes to build the pptx, so
    it already carries everything "Load Past Service" needs (item order,
    types, ids, positions, and each item's own song/leader/reading values)
    without any separate reverse-engineering of the .pptx itself.
    """
    root = Path(WORSHIP_ROOT)
    if not root.is_dir():
        return []
    # Matches "20260830-1000.json" but not the alternate export variants
    # ("...-web2.json", "...-command-line.json") sitting in the same folder.
    pattern = re.compile(r"^(\d{8})-(\d{4})\.json$")
    found = []
    for year_dir in root.iterdir():
        if not year_dir.is_dir():
            continue
        for path in year_dir.glob("*.json"):
            m = pattern.match(path.name)
            if not m:
                continue
            found.append((m.group(1) + m.group(2), path))
    found.sort(key=lambda t: t[0], reverse=True)
    results = []
    for _, path in found[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(data.get("items"), list):
            continue
        results.append({
            "path": path,
            "isodate": data.get("isodate", ""),
            "template": data.get("template", ""),
            "service_type": data.get("type", ""),
            "item_count": len(data["items"]),
            "items": data["items"],
        })
    return results


def load_template(template_name):
    """Load template and return the order items with encoding handling"""
    template_path = TEMPLATES_ROOT + template_name + ".json"
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except UnicodeDecodeError:
        with open(template_path, 'r', encoding='cp1252') as f:
            data = json.load(f)
    
    items = data.get('order', [])
    if not isinstance(items, list):
        raise ValueError(f"Template 'order' must be a list, got {type(items).__name__}")
    
    return items


def make_custom_template_item(item_type, seq):
    """Create one custom order item with sensible defaults.

    Position labels include `seq` so that adding several items of the same
    type (e.g. 9 songs) gives each its own distinct leader field instead of
    all of them sharing one position name and silently overwriting each
    other's leader input down to whichever was typed last.
    """
    if item_type == "welcome":
        return {
            "type": "welcome",
            "id": f"welcome-{seq}",
            "desc": "Announcements",
            "esp": "Bienvenida",
            "position": f"Announcements {seq}",
        }
    if item_type == "song":
        return {
            "type": "song",
            "id": f"song-{seq}",
            "position": f"Song Leader {seq}",
        }
    if item_type == "song-title":
        # A title-only preview slide, no music -- see make_worship_deck's
        # dispatch (add_song(..., music=False)). Matches sunday-am.json's
        # invitation-song preview: no "position" field, since the song
        # itself has already been (or will be) led elsewhere -- this slide
        # just previews it, it doesn't need its own leader.
        return {
            "type": "song-title",
            "id": f"song-title-{seq}",
            "bubble": "Invitation Song",
        }
    if item_type == "song-music":
        # Music-only, no title slide (add_song(..., title=False)) -- the AM
        # template plays this after the sermon as the invitation song,
        # faded out at the end. Pairing its "id" with a song-title item's
        # id (done in the Add Item handler, which has the sibling list this
        # function doesn't) makes both slides share one song selection,
        # just like sunday-am.json's matching "song-5" ids.
        return {
            "type": "song-music",
            "id": f"song-music-{seq}",
            "fade": "out",
        }
    if item_type == "reading":
        return {
            "type": "reading",
            "id": f"reading-{seq}",
            "position": f"Scripture Reading {seq}",
        }
    if item_type == "prayer":
        return {
            "type": "prayer",
            "id": f"prayer-{seq}",
            "position": f"Prayer {seq}",
        }
    if item_type == "ls-am":
        return {
            "type": "ls-am",
            "id": f"ls-{seq}",
            "position": f"Lord's Supper {seq}",
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
            "position": f"Preach {seq}",
        }
    if item_type == "announcements-title":
        return {
            "type": item_type,
            "id": f"{item_type}-{seq}",
            # Deliberately NOT "Announcements {seq}" -- the "welcome" item
            # type already uses that exact position name, and two items
            # sharing a position name silently overwrite each other's
            # leader input (see make_custom_template_item's docstring).
            "position": f"Announcer {seq}",
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
        elif item_type in ['sermon', 'lesson', 'report', 'announcements-title']:
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
        with open(path, 'r', encoding='cp1252') as f:
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


def get_readings_index_section(item_type):
    """Return the markdown body of assets/readings-index.md's section for
    this item type (Lord's Supper vs Collection), for the "View Index"
    popover next to the reading-slide-index field -- lets a user look up
    which index number matches which passage without leaving the form.
    """
    path = Path(__file__).resolve().parent / "assets" / "readings-index.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    heading = "## Lord's Supper Readings" if item_type == "ls-am" else "## Collection Readings"
    if heading not in text:
        return None
    section = text.split(heading, 1)[1]
    section = section.split("\n## ", 1)[0]  # stop before the next heading, if any
    return heading + section


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

        # Mirrors worship.py's generate_json: slides.add_welcome() writes this
        # into the welcome slide's speaker notes ("Song Leader: <name>"), but
        # only if the spec dict actually has a top-level 'leader' key -- this
        # UI's own from-scratch spec never set it, so the notes were silently
        # never populated when generating through the app.
        if 'Song Leader' in leaders:
            spec['leader'] = leaders['Song Leader']
        else:
            # Custom templates give every song its own distinct position
            # ("Song Leader 1", "Song Leader 2", ...) instead of sharing one
            # "Song Leader" key (see make_custom_template_item), so there's
            # never a literal "Song Leader" match to fall back on here --
            # collect all of them instead, in the songs' own order.
            song_leader_names = [
                name.strip()
                for pos, name in leaders.items()
                if pos.startswith('Song Leader') and isinstance(name, str) and name.strip()
            ]
            if song_leader_names:
                spec['leader'] = ', '.join(song_leader_names)

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

# Applying a "Load Past Service" selection here, before any widget below
# renders, is what lets it flip the template selector and pre-fill leader/
# song/reading fields in the same click -- a widget's session_state value
# can't be reassigned after that widget has already rendered in the same
# script run (Streamlit raises StreamlitAPIException), so the Load button's
# own handler (further down the page) can only stash the request; this is
# the first point in the script where it's safe to actually apply it.
if "load_past_service_pending" in st.session_state:
    _pending_items = st.session_state.pop("load_past_service_pending")
    st.session_state["custom_template_items"] = _pending_items
    st.session_state["template_select"] = CUSTOM_TEMPLATE_LABEL
    st.toast(f"Loaded {len(_pending_items)} items into the Custom Template Builder.", icon="📋")

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
    builder_col1, builder_col_pos, builder_col2 = st.columns([2.2, 1, 1])
    with builder_col1:
        custom_item_type = st.selectbox(
            "Add service item",
            CUSTOM_ITEM_TYPE_OPTIONS,
            key="custom_item_type_select",
            # A few of these are internal type names, not something a user
            # needs to see (e.g. "announcements-title", distinct from the
            # pre-existing plain "announcements" type, would otherwise show
            # as the redundant-looking "Announcements Title") -- see
            # CUSTOM_ITEM_TYPE_LABELS.
            format_func=lambda t: CUSTOM_ITEM_TYPE_LABELS.get(t, t.replace("-", " ").title()),
        )
    with builder_col_pos:
        st.write("")
        # A checkbox that always means "prepend" needs no notion of "the
        # current bottom" to stay correct as the list grows, unlike a plain
        # position number -- which would need resetting after every Add, and
        # a widget's stored value can't be reassigned after it has already
        # rendered in the same run, so any such reset can only take effect
        # on the *next* rerun and would clobber a legitimate edit the user
        # made to it in the meantime.
        add_to_top = st.checkbox("Add to top", key="custom_add_to_top")
    with builder_col2:
        st.write("")
        if st.button("Add Item", key="custom_add_item", use_container_width=True):
            current_items = list(st.session_state.custom_template_items)
            seq = 1 + sum(1 for item in current_items if isinstance(item, dict) and item.get("type") == custom_item_type)
            new_item = make_custom_template_item(custom_item_type, seq)
            if custom_item_type == "song-music":
                # Reuse the most recent not-yet-paired song-title's id so
                # this background-music slide shares its song selection with
                # that preview slide, the same way sunday-am.json links its
                # invitation song-title and song-music entries by giving
                # them the same "id".
                paired_title_ids = {
                    it.get("id") for it in current_items if isinstance(it, dict) and it.get("type") == "song-music"
                }
                unpaired_titles = [
                    it for it in current_items
                    if isinstance(it, dict) and it.get("type") == "song-title" and it.get("id") not in paired_title_ids
                ]
                if unpaired_titles:
                    new_item["id"] = unpaired_titles[-1]["id"]
            insert_at = 0 if add_to_top else len(current_items)
            current_items.insert(insert_at, new_item)
            st.session_state.custom_template_items = current_items
            # Deliberately no st.rerun() here: Streamlit already reruns this
            # whole script on every button click, and calling st.rerun() would
            # abort *this* pass before it reaches the Service Flow widgets
            # further down -- any widget not instantiated during a pass has
            # its session_state pruned, which wiped out every already-entered
            # field (song numbers, leaders, verses/chorus...) on every add/
            # remove/reorder click. Letting this pass run to completion keeps
            # all of those widgets alive and their values intact.

    custom_items = list(st.session_state.custom_template_items)
    if custom_items:
        st.caption(
            "Type a target position for any item you want to move, then click "
            "“Apply Order.” Fill in details below in Service Flow."
        )
        # Position inputs are keyed by the item's own id (not its row index),
        # so a value typed for a given item stays attached to that item even
        # as Apply Order (or an Add/Remove elsewhere) shifts everyone's row.
        # Up/Down arrows keyed by row index used to require re-locating and
        # re-clicking a *different* button after every single-step move --
        # clicking the same visual row twice in a row just swapped the same
        # two items back and forth, which looked like items randomly
        # changing identity and made far moves (e.g. "send this to the top")
        # painful. Typing a position and applying once avoids that entirely.
        n_items = len(custom_items)

        def _pos_key(citem):
            # id alone isn't unique: a song-title/song-music invitation-song
            # pair is deliberately given the *same* id (see
            # make_custom_template_item) so they share one song selection.
            # Pairing id with type keeps this key unique for them while
            # staying stable across reorders, unlike a row-index-based key.
            return f"custom_pos_{citem.get('id')}_{citem.get('type')}"

        for ndx, citem in enumerate(custom_items):
            ccols = st.columns([1, 6, 1])
            pos_key = _pos_key(citem)
            ccols[0].number_input(
                "Pos",
                min_value=1,
                value=min(st.session_state.get(pos_key, ndx + 1), n_items),
                key=pos_key,
                label_visibility="collapsed",
            )
            item_desc = f"{ndx + 1}. {citem.get('type', 'item')} ({citem.get('id') or 'no-id'})"
            ccols[1].markdown(item_desc)
            if ccols[2].button("✕", key=f"custom_remove_{ndx}"):
                del custom_items[ndx]
                st.session_state.custom_template_items = custom_items

        if st.button("Apply Order", key="custom_apply_order"):
            # Only move items whose typed position actually differs from
            # where they already are. Sorting everyone by their position
            # box's raw value doesn't work: every untouched item's box still
            # shows its own current position, so typing "1" for one item
            # ties with whatever's already sitting in slot 1 -- and a
            # stable sort on that tie keeps the untouched item first,
            # silently ignoring the move the user asked for.
            requested = []
            for ndx, citem in enumerate(custom_items):
                raw_pos = st.session_state.get(_pos_key(citem), ndx + 1)
                try:
                    raw_pos = int(raw_pos)
                except (TypeError, ValueError):
                    raw_pos = ndx + 1
                if raw_pos != ndx + 1:
                    requested.append((citem.get("id"), citem.get("type"), raw_pos))

            for item_id, item_type_, target_pos in requested:
                cur_idx = next(
                    i for i, it in enumerate(custom_items)
                    if it.get("id") == item_id and it.get("type") == item_type_
                )
                moved = custom_items.pop(cur_idx)
                insert_at = max(0, min(target_pos - 1, len(custom_items)))
                custom_items.insert(insert_at, moved)
            st.session_state.custom_template_items = custom_items
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

        # Surface autofill failures instead of leaving fields silently
        # blank with no indication why -- a real API error (auth, network,
        # or the church schedule genuinely having nothing for this date)
        # was previously indistinguishable from "nothing to autofill",
        # so a failure looked identical to a bug with no way to tell them apart.
        autofill_errors = []
        if isinstance(fetched_leaders_data, dict) and fetched_leaders_data.get('_error'):
            autofill_errors.append(f"Leader assignments: {fetched_leaders_data['_error']}")
        if isinstance(fetched_readings_data, dict) and fetched_readings_data.get('_error'):
            autofill_errors.append(f"Scripture reading: {fetched_readings_data['_error']}")
        if autofill_errors:
            st.warning(
                "Could not auto-fill from the church schedule:\n\n"
                + "\n".join(autofill_errors)
                + "\n\nYou can still enter these fields manually."
            )

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
    except Exception as e:
        # Keep the form usable even if the pull API fails entirely, but say
        # why instead of leaving every field silently blank with no clue.
        st.warning(f"Could not auto-fill from the church schedule: {e}\n\nYou can still enter these fields manually.")
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

flow_tab, search_tab, load_past_tab = st.tabs(["Service Flow", "Song Search", "Load Past Service"])

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
                            st.session_state[f"book_{target['item_id']}"] = book_code
                            try:
                                applied_song_num = int(song_num)
                            except (TypeError, ValueError):
                                applied_song_num = 1
                            st.session_state[f"song_{target['item_id']}"] = applied_song_num
                            st.session_state[f"song_source_{target['item_id']}"] = source_folder
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
            leader_key = f"leader_{position_name}"
            # Only takes effect on this key's very first render (Streamlit
            # ignores `value=` once a keyed widget has session_state) --
            # this is what lets "Load Past Service" restore leader names by
            # seeding items with their own "leader" field before this loop.
            if leader_key not in st.session_state:
                st.session_state[leader_key] = item.get("leader", "") if isinstance(item, dict) else ""
            leaders_input[position_name] = st.text_input(
                f"Leader: {position_name}",
                key=leader_key,
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
                    key=f"book_{item_id}",
                    label_visibility="collapsed",
                    format_func=lambda code: SONG_BOOK_OPTIONS.get(code, code)
                )
            with song_col2:
                st.caption("Song Number")
                
                song_num = st.number_input(
                    f"Song # ({item_id})",
                    min_value=0,
                    max_value=1000,
                    key=f"song_{item_id}",
                    value=default_song_num,
                    label_visibility="collapsed"
                )

            with song_col3:
                st.caption("Song Source")
                existing_source_folder = str(
                    st.session_state.get(
                        f"song_source_{item_id}",
                        item.get("source_folder", "") if isinstance(item, dict) else ""
                    )
                ).strip().lower()
                # Default to Spanish for new/unselected song entries; still respect an
                # explicit prior English choice (a non-empty, non-"esp/..." source_folder).
                if existing_source_folder.startswith("esp"):
                    default_source_key = "esp"
                elif existing_source_folder:
                    default_source_key = "eng"
                else:
                    default_source_key = "esp"
                source_choice = st.selectbox(
                    f"Source ({item_id})",
                    ["eng", "esp"],
                    index=1 if default_source_key == "esp" else 0,
                    key=f"song_source_choice_{item_id}",
                    label_visibility="collapsed",
                    format_func=lambda code: "English (ehsf)" if code == "eng" else "Spanish (ehsf/esp)"
                )

                if source_choice == "esp":
                    source_folder = f"esp/{book}"
                else:
                    source_folder = book
                st.session_state[f"song_source_{item_id}"] = source_folder

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
                    verses_key = f"verses_{item_id}"
                    # See the leader_key seeding above: only takes effect
                    # before this key's first-ever render, which is what
                    # lets "Load Past Service" restore a prior deselection
                    # instead of always defaulting back to "all verses".
                    if verses_key not in st.session_state and isinstance(item.get("verses"), list):
                        st.session_state[verses_key] = [v for v in item["verses"] if v in available_verses]
                    selected_verses = st.multiselect(
                        f"Verses ({item_id})",
                        options=available_verses,
                        default=available_verses,
                        key=verses_key,
                        label_visibility="collapsed"
                    )
                else:
                    st.caption("Select song number to load verses")
            with song_col5:
                st.caption("Chorus")
                if available_chorus:
                    chorus_key = f"chorus_{item_id}"
                    if chorus_key not in st.session_state and isinstance(item.get("chorus"), list):
                        st.session_state[chorus_key] = [c for c in item["chorus"] if c in available_chorus]
                    selected_chorus = st.multiselect(
                        f"Chorus After Verse ({item_id})",
                        options=available_chorus,
                        default=available_chorus,
                        key=chorus_key,
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

                selected_source_folder = source_folder or st.session_state.get(f"song_source_{item_id}", "")
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
            reading_number_key = f"reading_number_{item_id}"
            if reading_number_key not in st.session_state and item.get("reading") is not None:
                st.session_state[reading_number_key] = str(item["reading"])
            reading_number_str = st.text_input(
                "Scripture reading number (optional)",
                key=reading_number_key,
                help="Optional manual override if you need to track or force a specific reading number."
            )
            eng_passage_key = f"reading_eng_passage_{item_id}"
            esp_passage_key = f"reading_esp_passage_{item_id}"
            item_lang = item.get("lang") if isinstance(item.get("lang"), list) else []
            if eng_passage_key not in st.session_state and len(item_lang) > 0:
                st.session_state[eng_passage_key] = item_lang[0].get("passage", "")
            if esp_passage_key not in st.session_state and len(item_lang) > 1:
                st.session_state[esp_passage_key] = item_lang[1].get("passage", "")
            eng_passage = st.text_input("English passage", key=eng_passage_key)
            esp_passage = st.text_input("Spanish passage (optional)", key=esp_passage_key)
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
            reading_index_key = f"reading_index_{item_id}"
            if reading_index_key not in st.session_state:
                try:
                    st.session_state[reading_index_key] = int(item.get("reading", 0))
                except (TypeError, ValueError):
                    st.session_state[reading_index_key] = 0
            reading_col, index_button_col = st.columns([4, 1])
            with reading_col:
                # No `value=` here -- Streamlit warns (and it's ambiguous)
                # about setting both a widget's default and its
                # session_state; the seed above already covers every case,
                # including a fresh item with no "reading" field yet.
                reading_index = st.number_input(
                    "Reading slide index (0-based)",
                    min_value=0,
                    key=reading_index_key,
                )
            with index_button_col:
                st.write("")
                with st.popover("View Index"):
                    section_md = get_readings_index_section(item_type)
                    if section_md:
                        st.markdown(section_md)
                    else:
                        st.caption("Reading index reference not available.")
            readings_input[item_id] = {"reading": int(reading_index)}
        elif item_type == 'sermon' and item_id:
            st.info("Sermon details will be added later by another person.")
            readings_input[item_id] = {"title": "", "título": ""}
        elif item_type == 'announcements-title' and item_id:
            st.info("This slide just shows \"Announcements\", then fades to black.")
            readings_input[item_id] = {"title": "", "título": ""}
        elif item_type in ['lesson', 'report'] and item_id:
            title_en_key = f"title_en_{item_id}"
            title_es_key = f"title_es_{item_id}"
            if title_en_key not in st.session_state and item.get("title"):
                st.session_state[title_en_key] = item["title"]
            if title_es_key not in st.session_state and item.get("título"):
                st.session_state[title_es_key] = item["título"]
            title_en = st.text_input("Title (English)", key=title_en_key)
            title_es = st.text_input("Title (Spanish)", key=title_es_key)
            readings_input[item_id] = {"title": title_en, "título": title_es}
        elif item_type in ['welcome', 'invitation'] and item_id:
            desc_key = f"desc_{item_id}"
            if desc_key not in st.session_state and item.get("desc"):
                st.session_state[desc_key] = item["desc"]
            desc = st.text_input("Display text (optional)", key=desc_key)
            if desc:
                readings_input[item_id] = {"desc": desc}

# Rendered after flow_tab/search_tab's own content (not alongside them, up
# at the st.tabs() call) so that if its button below triggers a rerun to
# make the load feel instant, that rerun can't cut off flow_tab or
# search_tab's widgets before they've rendered this pass -- an early
# st.rerun() prunes session_state for anything not yet instantiated in the
# current pass (see the Add Item handler's own comment on this above).
with load_past_tab:
    st.caption(
        "Reuse a previously generated service as a starting point -- reloads its "
        "full order (songs, leaders, readings) into the Custom Template Builder "
        "above, ready to tweak before generating again."
    )
    saved_services = list_saved_services()
    if not saved_services:
        st.info("No previously generated services found yet under worship/.")
    else:
        def _saved_service_label(entry):
            when = entry["isodate"].replace("T", " ") if entry["isodate"] else entry["path"].stem
            return f"{when} — {entry['template'] or 'custom'} ({entry['item_count']} items)"

        chosen = st.selectbox(
            "Past service",
            saved_services,
            format_func=_saved_service_label,
            key="load_past_service_choice",
        )
        if st.button("Load into Custom Builder", key="load_past_service_button"):
            # A deep copy via json round-trip: these dicts must not alias the
            # cached `saved_services` list still referenced elsewhere on this
            # same page render.
            st.session_state["load_past_service_pending"] = json.loads(json.dumps(chosen["items"]))
            st.rerun()

# Generate Button
st.divider()
missing_song_slots = [slot for slot in locals().get("missing_song_slots", []) if slot]
if missing_song_slots:
    st.warning("Select a song number for each song item before generating the presentation.")

# The Song Leader field is only meaningful on the normal (non-custom)
# templates, where exactly one song item carries the "Song Leader" position;
# custom templates give every song its own distinct leader field instead, so
# there's no single required one to enforce there.
missing_song_leader = (
    selected_template != CUSTOM_TEMPLATE_KEY
    and not str(leaders_input.get('Song Leader', '')).strip()
)
if missing_song_leader:
    st.warning("Song Leader name is required before generating the presentation.")

col_left, col_generate, col_right = st.columns([1, 1.2, 1])

with col_generate:
    if st.button("🚀 Generate & Download PowerPoint", type="primary", use_container_width=True, disabled=(len(missing_song_slots) > 0 or missing_song_leader)):
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
