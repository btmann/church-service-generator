# Church Service Generator - Streamlit UI

A simple, user-friendly web interface for generating church worship presentations without needing technical knowledge.

## Features

- 📅 **Date & Time Selection**: Pick your service date and time
- 🎨 **Template Selection**: Choose from predefined service templates
- 🎵 **Song Entry**: Add songs by book and number
- 👥 **Leader Assignment**: Enter names for service leaders
- 🚀 **One-Click Generation**: Automatically creates JSON specs and PowerPoint presentations
- 💾 **Automatic File Management**: Organized output in worship folder

## Quick Start

### Option 1: Run Locally (Development)

**Prerequisites:**
- Python 3.7 or higher
- pip package manager

**Setup:**

```bash
# Navigate to project directory
cd /path/to/church-service-generator

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-ui.txt

# Run the app
python -m streamlit run ui.py
```

The app will open in your browser at `http://localhost:8501`

### Option 2: Standalone Executable (OneDrive Distribution)

See **Packaging for Distribution** section below.

## How It Works

1. **Select Service Details**
   - Choose date and time for your worship service
   - Select a template (e.g., "sunday-am", "sunday-pm")

2. **Enter Songs**
   - For each song position in the template
   - Select the song book (PFTL, PHSS, EH, SHS)
   - Enter the song number
   - Each song needs a book and number

3. **Assign Leaders**
   - Enter names for each leader position
   - Required positions vary by template

4. **Generate**
   - Click "Generate Presentation"
   - The app creates:
     - JSON spec files in `worship/specs/YYYY/MM/DD/HHMM/`
     - PowerPoint deck at `worship/YYYY/YYYYMMDD-HHMM.pptx`

## Packaging for Distribution (OneDrive)

### Build Standalone Executable

For **macOS**:
```bash
pip install pyinstaller
./packaging/build-macos.sh  # Updates to include ui.py and streamlit
```

For **Windows**:
```powershell
pip install pyinstaller
./packaging/build-windows.ps1  # Updates to include ui.py and streamlit
```

### PyInstaller Configuration

Create `ui.spec` file (already created automatically by build scripts):

```python
# Key settings for streamlit packaging
a = Analysis(
    ['launch-ui.py'],
    ...
    hiddenimports=['streamlit', 'altair', 'click', ...],
    ...
)
```

### Manual PyInstaller Build

```bash
pyinstaller \
  --onefile \
  --windowed \
  --icon=icon.icns \  # macOS
  --add-data="worship:worship" \
  --add-data="assets:assets" \
  --hidden-import=streamlit \
  launch-ui.py
```

This creates:
- **macOS**: `dist/launch-ui.app` → Distribute via OneDrive
- **Windows**: `dist/launch-ui.exe` → Distribute via OneDrive

### Distributing via OneDrive

1. **Build the executable** (see above)

2. **Create OneDrive structure:**
   ```
   OneDrive/Church Service Generator/
   ├── launch-ui.app (macOS) or launch-ui.exe (Windows)
   ├── worship/
   │   ├── templates/
   │   ├── specs/
   │   ├── schedules/
   │   └── styles/
   ├── assets/
   └── ehsf/  (song data)
   ```

3. **Share with users:**
   - Sync OneDrive folder locally
   - Users double-click the executable
   - Browser opens automatically with the UI

4. **Output Location:**
   - Generated files appear in `worship/YYYY/` folder within OneDrive
   - Users can easily find and share files

## Troubleshooting

### Streamlit Not Found
```bash
pip install streamlit --upgrade
```

### Port Already in Use
```bash
streamlit run ui.py --server.port 8502
```

### Module Import Errors
- Ensure all dependencies in `requirements-ui.txt` are installed
- Check Python version: `python --version` (should be 3.7+)

### Song Not Found
- Verify song exists in `ehsf/{book}/{number}/` directory
- Check book code: pftl, phss, eh, shs

### Template Not Found
- Verify template JSON exists in `worship/templates/{template}.json`
- Check template name in dropdown

## Architecture

```
user input (Streamlit UI)
    ↓
worship file creation (spec, songs, leaders, readings JSONs)
    ↓
JSON merge (combines template + user data)
    ↓
PowerPoint generation (slides.py make_worship_deck)
    ↓
Output files (JSON + PPTX)
```

## Environment Variables

Optional configuration:

```bash
# Change default port
export STREAMLIT_SERVER_PORT=8502

# Disable analytics
export STREAMLIT_CLIENT_TELEMETRY_OPTOUT=true

# Set logging level
export STREAMLIT_LOGGER_LEVEL=info
```

## Development Notes

- Uses `worship.py` functions for JSON generation
- Uses `slides.py` functions for PowerPoint creation
- Session state manages generated file tracking
- File paths are relative to project root

## Files

- `ui.py` - Main Streamlit application
- `launch-ui.py` - Launcher script for executable packaging
- `requirements-ui.txt` - Python dependencies
- `packaging/build-*.sh/.ps1` - Build scripts for executables

## Support

For issues with:
- **Song generation**: Check `slides.py` documentation
- **Worship specs**: Check `worship.py` documentation
- **Asset files**: Check `assets/` and `ehsf/` directories

---

*Church Service Generator - Making worship preparation simple and accessible*
