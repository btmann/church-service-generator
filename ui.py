#!/usr/bin/env python3
"""
Streamlit UI for Church Service Generator - FIXED VERSION
Allows non-technical users to generate worship presentations easily
"""

import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
import sys
import traceback

# Add current directory to path to import worship and slides modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worship
import slides

# Configuration
WORSHIP_ROOT = "worship/"
TEMPLATES_ROOT = WORSHIP_ROOT + "templates/"
SPECS_ROOT = WORSHIP_ROOT + "specs/"
SERVICE_TYPE_OPTIONS = ['Sun - EarlyAM', 'Sun - AM', 'Sun - PM', 'Wed', 'Gospel Meeting']
SERVICE_TIME_OPTIONS = ["10:30 AM", "4:00 PM", "5:00 PM", "7:00 PM"]
SERVICE_TIME_MAP = {
    "10:30 AM": "10:30",
    "4:00 PM": "16:00",
    "5:00 PM": "17:00",
    "7:00 PM": "19:00",
}
SONG_BOOK_OPTIONS = {
    "pftl": "Praise for the Lord",
    "phss": "Psalms, Hymns, and Spiritual Songs",
    "eh": "Embry Hills",
    "shs": "Sumphonia Hymn Supplement",
}

# Streamlit page config
st.set_page_config(
    page_title="Church Service Generator",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 12% 8%, rgba(71, 128, 166, 0.28), transparent 42%),
            radial-gradient(circle at 84% 12%, rgba(155, 123, 88, 0.22), transparent 38%),
            linear-gradient(180deg, #cfd9e1 0%, #bcc9d4 100%);
    }
    .block-container {
        max-width: 100%;
        margin-left: 0;
        margin-right: 0;
        padding-top: 1.0rem;
    }
    .hero-wrap {
        width: 100vw;
        margin-left: calc(50% - 50vw);
        margin-right: calc(50% - 50vw);
        padding: 0 0 0.8rem 0;
    }
    .hero {
        width: 100%;
        margin: 0;
        padding: 1.1rem 1.3rem;
        border-radius: 0;
        background: linear-gradient(120deg, #153042 0%, #26516b 56%, #356f8a 100%);
        color: #ffffff;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        border-bottom: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 10px 26px rgba(20, 37, 48, 0.20);
        margin-bottom: 0.35rem;
    }
    .hero h1 {
        margin: 0 0 0.15rem 0;
        font-size: 1.8rem;
        letter-spacing: 0.2px;
    }
    .hero p {
        margin: 0;
        font-size: 0.96rem;
        opacity: 0.92;
    }
    .section-heading {
        margin: 0.35rem 0 0.25rem 0;
        color: #173c4e;
        font-size: 1.08rem;
        font-weight: 700;
        letter-spacing: 0.2px;
    }
    .note-chip {
        display: inline-block;
        margin-top: 0.4rem;
        padding: 0.22rem 0.55rem;
        border-radius: 999px;
        border: 1px solid #b6cbd9;
        background: #f4f9fc;
        color: #254d62;
        font-size: 0.8rem;
    }
    div[data-testid="stVerticalBlock"] div:has(> div > .section-heading) {
        border: 1px solid #9fb2c2;
        border-radius: 12px;
        padding: 0.35rem 0.65rem 0.5rem 0.65rem;
        background: rgba(255, 255, 255, 0.86);
        box-shadow: 0 6px 16px rgba(28, 53, 70, 0.12);
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.35rem;
    }
    div[data-testid="stDateInput"],
    div[data-testid="stTimeInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stTextInput"],
    div[data-testid="stNumberInput"],
    div[data-testid="stMultiSelect"] {
        display: grid;
        grid-template-columns: 210px 1fr;
        align-items: center;
        column-gap: 0.65rem;
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
    }
    div[data-testid="stWidgetLabel"] {
        margin-bottom: 0;
    }
    div[data-testid="stWidgetLabel"] > label {
        text-align: left;
        width: 100%;
        justify-content: flex-start;
    }
    @media (max-width: 900px) {
        .hero h1 {
            font-size: 1.45rem;
        }
        div[data-testid="stDateInput"],
        div[data-testid="stTimeInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stTextInput"],
        div[data-testid="stNumberInput"],
        div[data-testid="stMultiSelect"] {
            grid-template-columns: 1fr;
            row-gap: 0.2rem;
        }
    }
    </style>
    <div class="hero-wrap">
      <div class="hero">
          <h1>Church Service Generator</h1>
          <p>Build your worship deck with cleaner planning, auto-pulled data, and manual overrides where needed.</p>
      </div>
    </div>
    """,
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
    ehsf_root = Path("ehsf")
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


def create_worship_files(date, time, template, songs_data, leaders_data, readings_data=None, service_type='Sun - AM'):
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
        'template': template,
        'language': 'eng',
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
    for item in load_template(template):
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


def get_song_structure(book, song_num):
    """Return available verses and chorus slots for a song."""
    try:
        _, paths = slides.get_song_paths_new(book, int(song_num))
        meta = load_json_safe(paths['engbase'] + ".json")
        custom = paths['engbase'] + "-custom.json"
        if os.path.exists(custom):
            custom_data = load_json_safe(custom)
            if isinstance(custom_data, dict):
                meta.update(custom_data)

        verses = []
        chorus = []

        if isinstance(meta, dict):
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


def generate_presentation(date, time, template, songs_data, leaders_data, readings_data=None, service_type='Sun - AM'):
    """Generate the complete presentation"""
    try:
        # Step 1: Create worship files
        specbase, jsonbase = create_worship_files(date, time, template, songs_data, leaders_data, readings_data, service_type)
        
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
service_time_label = st.selectbox("Service Time", SERVICE_TIME_OPTIONS, index=0)
service_time = datetime.strptime(SERVICE_TIME_MAP[service_time_label], "%H:%M").time()
service_type = st.selectbox("Service Type", SERVICE_TYPE_OPTIONS, index=1)

if templates:
    template_choices = ["-- Select Template --"] + templates
    if "template_select" in st.session_state and st.session_state["template_select"] not in template_choices:
        st.session_state["template_select"] = "-- Select Template --"
    selected_template_choice = st.selectbox("Template", template_choices, index=0, key="template_select")
    if selected_template_choice in templates:
        selected_template = selected_template_choice
else:
    st.error("No templates found in worship/templates")

if not selected_template:
    st.info("Select template and date first. The rest of the form will appear after template selection.")
    st.stop()

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

if autofill_ran_for != autofill_signature:
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
        search_titles = sorted({entry["title"] for entry in song_search_index})
        searched_song = st.selectbox(
            "Find song by title",
            ["-- Search by title --"] + search_titles,
            index=0,
            key="song_search_lookup"
        )

        if searched_song != "-- Search by title --":
            matches = [
                entry
                for entry in song_search_index
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

    for idx, item in enumerate(template_items):
        if not isinstance(item, dict):
            continue

        item_type = item.get('type', 'unknown')
        item_id = item.get('id')
        position_name = item.get('position')
        item_label = f"{idx + 1}. {item_type}"
        if item_id:
            item_label += f" ({item_id})"

        st.markdown(f"**{item_label}**")

        if position_name and "prayer for" not in position_name.lower() and "reading" not in position_name.lower() and item_type not in ['prayer', 'reading', 'welcome']:
            leaders_input[position_name] = st.text_input(
                f"Leader: {position_name}",
                key=f"leader_{position_name}_{idx}"
            )

        if 'song' in item_type and item_id:
            default_book = item.get("book", "pftl") if isinstance(item, dict) else "pftl"
            default_song = item.get("song", "1") if isinstance(item, dict) else "1"
            try:
                default_song_num = int(default_song)
            except (TypeError, ValueError):
                default_song_num = 1

            song_col1, song_col2, song_col3, song_col4 = st.columns([0.9, 1.1, 2.0, 2.0])
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
                    min_value=1,
                    max_value=1000,
                    key=f"song_{item_id}_{idx}",
                    value=default_song_num,
                    label_visibility="collapsed"
                )

            available_verses, available_chorus, song_error = get_song_structure(book, int(song_num))

            selected_verses = None
            selected_chorus = None
            with song_col3:
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
                    st.caption("All verses")
            with song_col4:
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
                    st.caption("Default chorus")

            if song_error:
                st.caption(f"Could not load verses/chorus for {book}-{int(song_num):03d}: {song_error}")

            song_payload = {
                "book": book,
                "song": str(song_num),
                "coda": 0
            }

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
col_left, col_generate, col_right = st.columns([1, 1.2, 1])

with col_generate:
    if st.button("🚀 Generate Presentation", type="primary", use_container_width=True):
        with st.spinner("🔄 Generating presentation..."):
            success, result, debug_info = generate_presentation(
                service_date,
                service_time,
                selected_template,
                songs_input if 'songs_input' in locals() else {},
                leaders_input if 'leaders_input' in locals() else {},
                readings_input if 'readings_input' in locals() else {},
                service_type
            )
        
        if success:
            st.session_state.generated_files = {
                'json': result,
                'pptx': debug_info
            }
            st.toast("It worked. Presentation files were created.", icon="✅")
            st.success("Presentation generated successfully.")
            st.info(f"Find your files here:\n- JSON: {result}\n- PPTX: {debug_info}")
        else:
            st.error(f"❌ Error generating presentation: {result}")
            if isinstance(debug_info, str) and debug_info:
                st.write("**Debug Information:**")
                st.code(debug_info, language="python")
