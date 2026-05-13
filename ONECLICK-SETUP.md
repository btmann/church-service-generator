# OneClick Setup for OneDrive Users

## Simple Installation (No Command Line Required)

If you've downloaded this folder from OneDrive, follow these steps based on your computer type.

### macOS Users

1. **Double-click `launch-ui.app`**
   - A browser window will open automatically
   - You should see the Church Service Generator interface

2. **Use the interface:**
   - Select your service date and time
   - Choose a template
   - Enter song books and numbers
   - Enter leader names
   - Click "Generate Presentation"

3. **Find your files:**
   - Generated files appear in the `worship/YYYY/` folder
   - PowerPoint files have a `.pptx` extension
   - You can move these files anywhere you want

### Windows Users

1. **Double-click `launch-ui.exe`**
   - A browser window will open automatically
   - You should see the Church Service Generator interface

2. **Use the interface:**
   - Select your service date and time
   - Choose a template
   - Enter song books and numbers
   - Enter leader names
   - Click "Generate Presentation"

3. **Find your files:**
   - Generated files appear in the `worship\YYYY\` folder
   - PowerPoint files have a `.pptx` extension
   - You can move these files anywhere you want

---

## If Something Goes Wrong

### App won't open
- Make sure you're double-clicking the right file (`launch-ui.app` or `launch-ui.exe`)
- Wait 5-10 seconds for it to start the first time
- Check that you're connected to the internet (some features may need it)

### Browser shows an error
- Check that the required folders exist:
  - `worship/templates/` - should have template JSON files
  - `ehsf/` - should have song data
  - `assets/` - should have slide templates
- If folders are missing, the OneDrive sync may not be complete

### Song not found error
- Check the song book and number are correct
- Verify the song exists in the `ehsf/` folder

### PowerPoint won't open
- Make sure you have Microsoft PowerPoint or compatible software installed
- The file is saved in `worship/YYYY/` folder - navigate there to find it

---

## Advanced: Installing from Source

If you want to build the app yourself or modify it:

```bash
# Prerequisites: Python 3.7+
# 1. Install dependencies
pip install -r requirements-ui.txt

# 2. Run the app
python -m streamlit run ui.py

# 3. To package as executable:
pip install pyinstaller
pyinstaller --onefile --windowed launch-ui.py
```

See `UI-README.md` for detailed instructions.

---

## Questions?

This tool uses:
- **templates/** - Predefined service structures
- **schedules/** - Service timing options
- **styles/** - Presentation themes
- **specs/** - Generated service specifications
- **ehsf/** - Song data (books, numbers, lyrics)
- **assets/** - PowerPoint templates and backgrounds

All generated files are saved to `worship/` folder structure.
