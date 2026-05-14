#!/usr/bin/env python3
"""
Streamlit UI for Church Service Generator
Allows non-technical users to generate worship presentations easily
"""

import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
import sys

# Add current directory to path to import worship and slides modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worship
import slides

# Configuration
WORSHIP_ROOT = "worship/"
TEMPLATES_ROOT = WORSHIP_ROOT + "templates/"
SPECS_ROOT = WORSHIP_ROOT + "specs/"

# Streamlit page config
st.set_page_config(
    page_title="Church Service Generator",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⛪ Church Service Generator")
st.markdown("Generate beautiful worship presentations in seconds")

# Initialize session state
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = None


def get_available_templates():
    """Load list of available templates"""
    templates = []
    if os.path.exists(TEMPLATES_ROOT):
        for file in os.listdir(TEMPLATES_ROOT):
            if file.endswith('.json'):
                templates.append(file.replace('.json', ''))
    return sorted(templates)


def load_template(template_name):
    """Load template and return the order items"""
    template_path = TEMPLATES_ROOT + template_name + ".json"
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except UnicodeDecodeError:
        with open(template_path, 'r', encoding='latin-1') as f:
            data = json.load(f)
    return data.get('order', [])


def get_song_positions(template_items):
    """Extract song positions from template"""
    songs = {}
    for item in template_items:
        if 'song' in item.get('type', ''):
            songs[item['id']] = item
    return songs


def get_leader_positions(template_items):
    """Extract leader positions from template"""
    leaders = {}
    for item in template_items:
        if 'position' in item:
            position_name = item['position']
            leaders[position_name] = item
    return leaders


def create_worship_files(date, time, template, songs_data, leaders_data):
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
    
    # Create spec.json
    spec = {
        'isodate': isodate,
        'template': template,
        'language': 'eng',
        'type': 'Sun - AM'
    }
    with open(specbase + "-spec.json", 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=4)
    
    # Create songs.json
    with open(specbase + "-songs.json", 'w', encoding='utf-8') as f:
        json.dump({'songs': songs_data}, f, ensure_ascii=False, indent=4)
    
    # Create leaders.json
    with open(specbase + "-leaders.json", 'w', encoding='utf-8') as f:
        json.dump({'leaders': leaders_data}, f, ensure_ascii=False, indent=4)
    
    # Create readings.json (empty for now)
    readings = {}
    for item in load_template(template):
        if item.get('type') == 'reading':
            readings[item['id']] = {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}
        elif item.get('type') == 'ls-am':
            readings[item['id']] = {"reading": ""}
        elif item.get('type') in ['sermon', 'lesson', 'report']:
            readings[item['id']] = {"title": "", "título": ""}
    
    with open(specbase + "-readings.json", 'w', encoding='utf-8') as f:
        json.dump({'readings': readings}, f, ensure_ascii=False, indent=4)
    
    return specbase, jsonbase


def generate_presentation(date, time, template, songs_data, leaders_data):
    """Generate the complete presentation"""
    try:
        # Step 1: Create worship files
        specbase, jsonbase = create_worship_files(date, time, template, songs_data, leaders_data)
        
        # Step 2: Generate JSON (mimics worship.py generate_json)
        def load_json_safe(path):
            """Load JSON file with encoding fallback"""
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except UnicodeDecodeError:
                with open(path, 'r', encoding='latin-1') as f:
                    return json.load(f)
        
        spec = load_json_safe(specbase + "-spec.json")
        songs = load_json_safe(specbase + "-songs.json")['songs']
        leaders = load_json_safe(specbase + "-leaders.json")['leaders']
        readings = load_json_safe(specbase + "-readings.json")['readings']
        
        # Load template and merge data (already handles encoding via load_template)
        template_items = load_template(template)
        
        for item in template_items:
            if 'position' in item:
                if item['position'] in leaders:
                    item['leader'] = leaders[item['position']]
            if 'id' in item:
                if item['id'] in songs:
                    item.update(songs[item['id']])
                if item['id'] in readings:
                    item.update(readings[item['id']])
        
        spec['items'] = template_items
        
        # Write final JSON
        with open(jsonbase + ".json", 'w') as f:
            json.dump(spec, f, ensure_ascii=False, indent=4)
        
        # Step 3: Generate PPTX
        outfile = jsonbase + ".pptx"
        slides.make_worship_deck(jsonbase + ".json")
        
        return True, jsonbase + ".json", outfile
    except Exception as e:
        return False, str(e), None


# Main UI layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📅 Service Details")
    service_date = st.date_input("Service Date", value=datetime.now())
    service_time = st.time_input("Service Time", value=datetime.strptime("10:30", "%H:%M").time())
    
    templates = get_available_templates()
    selected_template = st.selectbox("Template", templates)

with col2:
    st.subheader("👥 Leaders")
    if selected_template:
        template_items = load_template(selected_template)
        leader_positions = get_leader_positions(template_items)
        
        leaders_input = {}
        for pos_name in sorted(leader_positions.keys()):
            leaders_input[pos_name] = st.text_input(pos_name)

# Song Entry Section
if selected_template:
    st.subheader("🎵 Songs")
    template_items = load_template(selected_template)
    song_positions = get_song_positions(template_items)
    
    songs_input = {}
    
    if song_positions:
        cols = st.columns(len(song_positions))
        
        for idx, (song_id, song_item) in enumerate(song_positions.items()):
            with cols[idx % len(cols)]:
                st.write(f"**{song_id}**")
                book = st.selectbox(
                    f"Book ({song_id})",
                    ["pftl", "phss", "eh", "shs"],
                    key=f"book_{song_id}"
                )
                song_num = st.number_input(
                    f"Song # ({song_id})",
                    min_value=1,
                    max_value=1000,
                    key=f"song_{song_id}",
                    value=1
                )
                
                songs_input[song_id] = {
                    "book": book,
                    "song": str(song_num),
                    "coda": 0
                }
    else:
        st.info("This template has no songs")

# Generate Button
st.divider()
col_generate, col_status = st.columns([1, 2])

with col_generate:
    if st.button("🚀 Generate Presentation", type="primary", use_container_width=True):
        with st.spinner("🔄 Generating presentation..."):
            success, result, output_file = generate_presentation(
                service_date,
                service_time,
                selected_template,
                songs_input,
                leaders_input
            )
        
        if success:
            st.session_state.generated_files = {
                'json': result,
                'pptx': output_file
            }
            st.success("✅ Presentation generated successfully!")
            st.balloons()
        else:
            st.error(f"❌ Error generating presentation: {result}")

# Display generated files info
if st.session_state.generated_files:
    st.divider()
    st.subheader("📦 Output Files")
    
    json_file = st.session_state.generated_files['json']
    pptx_file = st.session_state.generated_files['pptx']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**JSON:** {json_file}")
        if os.path.exists(json_file):
            st.caption(f"✓ Created")
    
    with col2:
        st.write(f"**PPTX:** {pptx_file}")
        if os.path.exists(pptx_file):
            st.caption(f"✓ Created")
            # Offer download
            with open(pptx_file, 'rb') as f:
                st.download_button(
                    label="📥 Download PPTX",
                    data=f.read(),
                    file_name=os.path.basename(pptx_file),
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )

st.divider()
st.caption("Church Service Generator • Ready to deploy")
