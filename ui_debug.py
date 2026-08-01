#!/usr/bin/env python3
"""
Debug version - test the generate_presentation logic
"""
import json
import os
from datetime import datetime
from pathlib import Path

# Load sample template and simulate data
def test_generation():
    """Test the generation logic with sample data"""
    
    # Load a real template
    template_name = "fifth-sunday-am-1"
    template_path = "worship/templates/" + template_name + ".json"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_data = json.load(f)
    
    template_items = template_data.get('order', [])
    print(f"✓ Loaded template with {len(template_items)} items")
    print(f"  Template items type: {type(template_items).__name__}")
    
    # Simulate song input
    songs_input = {
        'song-1': {'book': 'pftl', 'song': '738', 'coda': 0},
        'song-2': {'book': 'pftl', 'song': '123', 'coda': 0}
    }
    print(f"✓ Created songs_input with {len(songs_input)} songs")
    
    # Simulate leaders input  
    leaders_input = {
        'Announcements': 'John',
        'Scripture Reading': 'Mary',
        'Prayer Leader': 'Paul'
    }
    print(f"✓ Created leaders_input with {len(leaders_input)} leaders")
    
    # Create spec
    spec = {
        'isodate': '2026-05-13T10:30:00',
        'template': template_name,
        'language': 'eng',
        'type': 'Sun - AM'
    }
    
    # Write songs.json
    songs_file = {'songs': songs_input}
    with open('/tmp/test-songs.json', 'w') as f:
        json.dump(songs_file, f)
    print(f"✓ Wrote songs.json")
    
    # Write leaders.json
    leaders_file = {'leaders': leaders_input}
    with open('/tmp/test-leaders.json', 'w') as f:
        json.dump(leaders_file, f)
    print(f"✓ Wrote leaders.json")
    
    # Write readings.json
    readings = {}
    for item in template_items:
        if item.get('type') == 'reading':
            readings[item['id']] = {"lang": [{"passage": "", "pew": ""}, {"passage": ""}]}
    readings_file = {'readings': readings}
    with open('/tmp/test-readings.json', 'w') as f:
        json.dump(readings_file, f)
    print(f"✓ Wrote readings.json with {len(readings)} readings")
    
    # Now test the merge logic
    print("\n--- Testing merge logic ---")
    
    # Load songs back
    with open('/tmp/test-songs.json', 'r') as f:
        songs_data = json.load(f)
    songs = songs_data.get('songs', {})
    print(f"Loaded songs: type={type(songs).__name__}, len={len(songs)}")
    for key in list(songs.keys())[:2]:
        print(f"  {key}: {type(songs[key]).__name__}")
    
    # Load leaders back
    with open('/tmp/test-leaders.json', 'r') as f:
        leaders_data = json.load(f)
    leaders = leaders_data.get('leaders', {})
    print(f"Loaded leaders: type={type(leaders).__name__}, len={len(leaders)}")
    
    # Load readings back
    with open('/tmp/test-readings.json', 'r') as f:
        readings_data = json.load(f)
    readings = readings_data.get('readings', {})
    print(f"Loaded readings: type={type(readings).__name__}, len={len(readings)}")
    
    # Merge
    print("\n--- Merging ---")
    for idx, item in enumerate(template_items):
        print(f"Item {idx}: type={type(item).__name__}", end="")
        
        if not isinstance(item, dict):
            print(f" ERROR: Expected dict, got {type(item)}")
            raise ValueError(f"Item {idx} is not a dict")
        
        item_type = item.get('type', '?')
        item_id = item.get('id', '?')
        print(f", id={item_id}, type={item_type}")
        
        # Merge leader
        if 'position' in item:
            pos = item['position']
            if pos in leaders:
                item['leader'] = leaders[pos]
                print(f"  → Added leader for position '{pos}'")
        
        # Merge song/reading
        if 'id' in item:
            item_id = item['id']
            if item_id in songs:
                print(f"  → Merging song data for id '{item_id}'")
                song_data = songs[item_id]
                print(f"    Song data type: {type(song_data).__name__}")
                if isinstance(song_data, dict):
                    item.update(song_data)
                    print(f"    Updated item with: {list(song_data.keys())}")
                else:
                    print(f"    ERROR: Song data is not a dict: {song_data}")
                    
            if item_id in readings:
                print(f"  → Merging reading data for id '{item_id}'")
                reading_data = readings[item_id]
                if isinstance(reading_data, dict):
                    item.update(reading_data)
                    print(f"    Updated item with: {list(reading_data.keys())}")
    
    # Write final spec
    spec['items'] = template_items
    
    with open('/tmp/test-final.json', 'w') as f:
        json.dump(spec, f, indent=2)
    
    print(f"\n✓ Created final spec with {len(template_items)} items")
    
    # Now simulate what slides.py would do
    print("\n--- Simulating slides.py logic ---")
    with open('/tmp/test-final.json', 'r') as f:
        worship = json.load(f)
    
    print(f"Loaded worship: type(worship)={type(worship).__name__}")
    print(f"worship['items']: type={type(worship['items']).__name__}, len={len(worship['items'])}")
    
    for idx, item in enumerate(worship['items']):
        print(f"\nProcessing item {idx}: ", end="")
        if not isinstance(item, dict):
            print(f"ERROR: Not a dict, it's {type(item).__name__}")
            raise TypeError(f"Item {idx} is {type(item).__name__}, expected dict")
        
        item_type = item.get('type', 'unknown')
        print(f"type={item_type}")
        
        if 'song' in item_type:
            try:
                book = item.get('book', 'MISSING')
                song_num = item.get('song', 'MISSING')
                print(f"  → Song: book={book}, song={song_num}")
            except Exception as e:
                print(f"  → ERROR accessing song fields: {e}")
                raise

if __name__ == '__main__':
    try:
        test_generation()
        print("\n✅ All tests passed!")
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
