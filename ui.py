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
            radial-gradient(circle at 15% 10%, rgba(189, 225, 255, 0.35), transparent 40%),
            radial-gradient(circle at 80% 15%, rgba(255, 233, 196, 0.45), transparent 34%),
            linear-gradient(180deg, #f7f7f2 0%, #eef3f6 100%);
    }
    .hero {
        padding: 1.1rem 1.3rem;
        border-radius: 14px;
        background: linear-gradient(120deg, #153042 0%, #26516b 56%, #356f8a 100%);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 10px 26px rgba(20, 37, 48, 0.20);
        margin-bottom: 0.8rem;
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
        border: 1px solid #d6e2ea;
        border-radius: 12px;
        padding: 0.55rem 0.85rem 0.75rem 0.85rem;
        background: rgba(255, 255, 255, 0.66);
    }
    @media (max-width: 900px) {
        .hero h1 {
            font-size: 1.45rem;
        }
    }
    </style>
    <div class="hero">
        <h1>Church Service Generator</h1>
        <p>Build your worship deck with cleaner planning, auto-pulled data, and manual overrides where needed.</p>
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
col1, col2 = st.columns([1, 1])

templates = get_available_templates()
selected_template = None
template_items = []
songs_input = {}
leaders_input = {}
readings_input = {}
leader_positions = {}

with col1:
    st.markdown('<div class="section-heading">Service Details</div>', unsafe_allow_html=True)
    service_date = st.date_input("Service Date", value=datetime.now())
    service_time = st.time_input("Service Time", value=datetime.strptime("10:30", "%H:%M").time())
    service_type = st.selectbox("Service Type", SERVICE_TYPE_OPTIONS, index=1)
    if templates:
        selected_template = st.selectbox("Template", templates)
    else:
        st.error("No templates found in worship/templates")

if selected_template:
    template_items = load_template(selected_template)

    counts = {}
    for item in template_items:
        if isinstance(item, dict):
            item_type = item.get('type', 'unknown')
            counts[item_type] = counts.get(item_type, 0) + 1

    if counts:
        summary = ", ".join([f"{k}: {v}" for k, v in sorted(counts.items())])
        st.caption(f"Template items: {summary}")

with col2:
    st.markdown('<div class="section-heading">Leaders and Reading Pull</div>', unsafe_allow_html=True)
    if selected_template:
        leader_positions = get_leader_positions(template_items)
        keep_manual_overrides = st.checkbox(
            "Keep manual values when pulling",
            value=True,
            help="When checked, non-empty fields you already edited will not be overwritten by API results.",
            key="keep_manual_overrides"
        )
        st.markdown('<span class="note-chip">Pulled values are editable after fill</span>', unsafe_allow_html=True)

        if st.button("Pull Assigned Names and Scripture", use_container_width=True, key="pull_assignments_btn"):
            try:
                wdate = service_date.strftime("%Y-%m-%d")
                wtime = service_time.strftime("%H:%M:%S")

                fetched_leaders_data = worship.fetch_leaders(wdate, wtime, service_type)
                fetched_leaders = fetched_leaders_data.get('leaders', {}) if isinstance(fetched_leaders_data, dict) else {}
                if not isinstance(fetched_leaders, dict):
                    fetched_leaders = {}
                leaders_error = fetched_leaders_data.get('_error') if isinstance(fetched_leaders_data, dict) else None
                leaders_warning = fetched_leaders_data.get('_warning') if isinstance(fetched_leaders_data, dict) else None

                fetched_readings_seed = build_default_readings(template_items)
                fetched_readings_data = worship.fetch_readings(wdate, fetched_readings_seed, service_type)
                fetched_readings = fetched_readings_data.get('readings', {}) if isinstance(fetched_readings_data, dict) else {}
                if not isinstance(fetched_readings, dict):
                    fetched_readings = {}
                readings_error = fetched_readings_data.get('_error') if isinstance(fetched_readings_data, dict) else None
                readings_warning = fetched_readings_data.get('_warning') if isinstance(fetched_readings_data, dict) else None

                filled_leaders = 0
                unmatched_positions = []

                for pos_name in sorted(leader_positions.keys()):
                    if pos_name in fetched_leaders and isinstance(fetched_leaders[pos_name], str):
                        leader_key = f"leader_{pos_name}"
                        if not should_keep_existing(leader_key, fetched_leaders[pos_name], keep_manual_overrides):
                            st.session_state[leader_key] = fetched_leaders[pos_name]
                            filled_leaders += 1
                    else:
                        unmatched_positions.append(pos_name)

                filled_readings = 0
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
                                eng_pew = lang[0].get('pew', '')
                                eng_passage_key = f"reading_eng_passage_{item_id}"
                                eng_pew_key = f"reading_eng_pew_{item_id}"
                                if not should_keep_existing(eng_passage_key, eng_passage, keep_manual_overrides):
                                    st.session_state[eng_passage_key] = eng_passage
                                if not should_keep_existing(eng_pew_key, eng_pew, keep_manual_overrides):
                                    st.session_state[eng_pew_key] = eng_pew
                                if lang[0].get('passage', ''):
                                    filled_readings += 1
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
                                filled_readings += 1
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
                        if entry.get('title', '') or entry.get('título', ''):
                            filled_readings += 1

                if leaders_error:
                    st.warning(f"Leader pull issue: {leaders_error}")
                if leaders_warning:
                    st.info(f"Leader pull note: {leaders_warning}")
                if readings_error:
                    st.warning(f"Reading pull issue: {readings_error}")
                if readings_warning:
                    st.info(f"Reading pull note: {readings_warning}")

                if unmatched_positions and len(unmatched_positions) == len(leader_positions):
                    st.info("No leader names matched this template's position labels. You can still enter names manually.")
                elif unmatched_positions:
                    st.info("Some leader positions were not returned: " + ", ".join(unmatched_positions))

                st.success(f"Pulled data. Leaders filled: {filled_leaders}. Reading fields filled: {filled_readings}.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not pull assignments: {e}")

        if leader_positions:
            for pos_name in sorted(leader_positions.keys()):
                leaders_input[pos_name] = st.text_input(pos_name, key=f"leader_{pos_name}")
        else:
            st.info("This template has no leader fields")

# Song Entry Section
if selected_template:
    st.markdown('<div class="section-heading">Songs</div>', unsafe_allow_html=True)
    song_positions = get_song_positions(template_items)
    if song_positions:
        num_cols = min(3, max(1, len(song_positions)))
        cols = st.columns(num_cols)
        for idx, (song_id, song_item) in enumerate(song_positions.items()):
            with cols[idx % num_cols]:
                st.write(f"**{song_id}**")
                default_book = song_item.get("book", "pftl") if isinstance(song_item, dict) else "pftl"
                default_song = song_item.get("song", "1") if isinstance(song_item, dict) else "1"
                try:
                    default_song_num = int(default_song)
                except (TypeError, ValueError):
                    default_song_num = 1

                book_options = ["pftl", "phss", "eh", "shs"]
                default_book_index = book_options.index(default_book) if default_book in book_options else 0
                book = st.selectbox(
                    f"Book ({song_id})",
                    book_options,
                    index=default_book_index,
                    key=f"book_{song_id}"
                )
                song_num = st.number_input(
                    f"Song # ({song_id})",
                    min_value=1,
                    max_value=1000,
                    key=f"song_{song_id}",
                    value=default_song_num
                )

                available_verses, available_chorus, song_error = get_song_structure(book, int(song_num))

                selected_verses = None
                if available_verses:
                    selected_verses = st.multiselect(
                        f"Verses ({song_id})",
                        options=available_verses,
                        default=available_verses,
                        key=f"verses_{song_id}"
                    )
                elif song_error:
                    st.caption(f"Could not load verses/chorus for {book}-{int(song_num):03d}: {song_error}")

                selected_chorus = None
                if available_chorus:
                    selected_chorus = st.multiselect(
                        f"Chorus After Verse ({song_id})",
                        options=available_chorus,
                        default=available_chorus,
                        key=f"chorus_{song_id}"
                    )

                song_payload = {
                    "book": book,
                    "song": str(song_num),
                    "coda": 0
                }

                # Only write verse overrides when the user changes defaults.
                if available_verses and selected_verses is not None:
                    if len(selected_verses) == 0:
                        st.warning(f"{song_id}: No verses selected. Using all verses.")
                    elif selected_verses != available_verses:
                        song_payload["verses"] = selected_verses

                # Empty chorus selection means omit all chorus slides.
                if available_chorus and selected_chorus is not None:
                    if len(selected_chorus) == 0:
                        song_payload["chorus"] = [0]
                    elif selected_chorus != available_chorus:
                        song_payload["chorus"] = selected_chorus

                songs_input[song_id] = song_payload
    else:
        st.info("This template has no songs")

    # Dynamic non-song fields driven by template item types
    st.markdown('<div class="section-heading">Reading and Other Items</div>', unsafe_allow_html=True)
    other_items = [it for it in template_items if isinstance(it, dict)]

    for idx, item in enumerate(other_items):
        item_id = item.get('id')
        item_type = item.get('type', 'unknown')
        if not item_id:
            continue

        label = f"{item_type} ({item_id})"

        if item_type == 'reading':
            with st.expander(label, expanded=False):
                reading_number_str = st.text_input(
                    "Scripture reading number (optional)",
                    key=f"reading_number_{item_id}",
                    help="Optional manual override if you need to track or force a specific reading number."
                )
                eng_passage = st.text_input("English passage", key=f"reading_eng_passage_{item_id}")
                pew = st.text_input("Pew reference (optional)", key=f"reading_eng_pew_{item_id}")
                esp_passage = st.text_input("Spanish passage (optional)", key=f"reading_esp_passage_{item_id}")
                reading_payload = {
                    "lang": [
                        {"passage": eng_passage, "pew": pew},
                        {"passage": esp_passage}
                    ]
                }
                if reading_number_str.strip().isdigit():
                    reading_payload["reading"] = int(reading_number_str.strip())
                readings_input[item_id] = reading_payload
        elif item_type in ['ls-am', 'collection']:
            with st.expander(label, expanded=False):
                reading_index = st.number_input(
                    "Reading slide index (0-based)",
                    min_value=0,
                    max_value=50,
                    value=0,
                    key=f"reading_index_{item_id}"
                )
                readings_input[item_id] = {"reading": int(reading_index)}
        elif item_type in ['sermon', 'lesson', 'report']:
            with st.expander(label, expanded=False):
                title_en = st.text_input("Title (English)", key=f"title_en_{item_id}")
                title_es = st.text_input("Title (Spanish)", key=f"title_es_{item_id}")
                readings_input[item_id] = {"title": title_en, "título": title_es}
        elif item_type in ['prayer', 'welcome', 'invitation']:
            with st.expander(label, expanded=False):
                desc = st.text_input("Display text (optional)", key=f"desc_{item_id}_{idx}")
                if desc:
                    readings_input[item_id] = {"desc": desc}

# Generate Button
st.divider()
col_generate, col_status = st.columns([1, 2])

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
            st.success("✅ Presentation generated successfully!")
            st.balloons()
        else:
            st.error(f"❌ Error generating presentation: {result}")
            if isinstance(debug_info, str) and debug_info:
                st.write("**Debug Information:**")
                st.code(debug_info, language="python")
