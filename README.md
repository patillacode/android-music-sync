# Apple Music → Android Sync

Clean, incremental sync solution for exporting Apple Music libraries to Android devices.

## Features

- **Incremental sync** - Only exports new/modified files
- **Dry-run mode** - Preview exports without copying files
- **Progress tracking** - Real-time progress bars with speed/ETA
- **Safety checks** - Disk space validation, confirmation prompts
- **No dependencies** - Uses Python standard library only
- **M3U playlists** - Universal playlist format

## Quick Start

### Prerequisites

- Python 3.8+ (pre-installed on macOS)
- macOS Catalina or later with Apple Music
- [LocalSend](https://localsend.org/) for WiFi file transfer

### Setup

**1. Export your Apple Music library:**

```bash
# In Apple Music: File → Library → Export Library...
# Save as 'Library.xml' in this project directory
```

**2. Preview the export (dry-run):**

```bash
./sync_to_android.sh --dry-run
```

**3. Run the export:**

```bash
./sync_to_android.sh
```

The script will:
- Export music files to `./output/Music/[Artist]/[Album]/`
- Generate M3U playlists in `./output/Playlists/`
- Show real-time progress with speed and ETA
- Create state file for incremental syncs

**4. Transfer to Android:**

Use LocalSend to transfer the `./output` folder to your Android device at `Internal Storage/Music/`.

## How It Works

### Incremental Sync

The exporter tracks file signatures (size + mtime) and playlist content hashes in `.export_state.json`. On subsequent runs:

- **Music files**: Only copied if source file changed or destination missing
- **Playlists**: Only regenerated if track list changed
- **Performance**: Full export ~15-30 min, incremental updates ~seconds

### Architecture

```
Apple Music Library.xml (metadata)
        ↓
apple_music_export.py (parser + exporter)
        ↓
output/ (staged for transfer)
├── Music/[Artist]/[Album]/[Track]
└── Playlists/[Playlist].m3u
        ↓
LocalSend (WiFi transfer)
        ↓
Android /Internal Storage/Music/
```

## Usage

### Basic Commands

| Command | Description |
|---------|-------------|
| `./sync_to_android.sh` | Run full export |
| `./sync_to_android.sh --dry-run` | Preview without copying files |
| `./sync_to_android.sh --clean` | Delete output and re-export everything |
| `./apple_music_export.py --help` | Show all options |

### Common Workflows

**First-time export:**
```bash
# 1. Export Library.xml from Apple Music
# 2. Run dry-run to check
./sync_to_android.sh --dry-run

# 3. If everything looks good, export
./sync_to_android.sh
```

**Adding new music:**
```bash
# 1. Re-export Library.xml from Apple Music (File → Library → Export Library...)
# 2. Run incremental sync
./sync_to_android.sh

# 3. Transfer only the changed files via LocalSend
```

**Direct Python usage:**
```bash
# Custom paths
python3 apple_music_export.py --library Library.xml --output ~/exports

# Dry-run
python3 apple_music_export.py --dry-run
```

## Configuration

### File Paths

| Path | Purpose | Default |
|------|---------|---------|
| Library.xml | Apple Music metadata | `~/Music/Music/Library.xml` |
| Output directory | Exported files | `./output` |
| State file | Incremental sync tracker | `./output/.export_state.json` |

**Tip:** Place `Library.xml` in the project directory for convenience:
```bash
./apple_music_export.py --library Library.xml --dry-run
```

### Customization

Edit `sync_to_android.sh` to change defaults:

```bash
LIBRARY_PATH="$HOME/Music/Music/Library.xml"  # Line 13
OUTPUT_DIR="$SCRIPT_DIR/output"               # Line 14
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| **Library file not found** | Export from Apple Music: File → Library → Export Library. Save as `Library.xml` in project directory. |
| **Library.xml is X days old** | Re-export from Apple Music to get latest changes. |
| **Insufficient disk space** | Free up space or use external drive. Update `OUTPUT_DIR` in `sync_to_android.sh`. |
| **M3U playlists not working** | Ensure `Music/` and `Playlists/` folders are in the same parent directory on Android. |
| **Permission denied** | Run `chmod +x apple_music_export.py sync_to_android.sh` |

## Advanced

### Android Music Player Setup

**Poweramp (Recommended):**
1. Settings → Folders and Library → Select music folder
2. Settings → Library → Playlists → Import from M3U files

**VLC:**
Auto-detects M3U playlists when pointed to music folder.

### Automated Sync with Syncthing

For automatic file syncing between Mac and Android:

1. Install [Syncthing](https://syncthing.net/) on both devices
2. Configure Syncthing to sync the `./output` folder
3. Run `./sync_to_android.sh` after adding music
4. Files automatically transfer in background

### Direct Python API

```python
from apple_music_export import AppleMusicExporter

exporter = AppleMusicExporter(
    library_path="Library.xml",
    output_dir="./output",
    dry_run=False
)
exporter.export()
```

## Technical Details

**Filename sanitization:** Removes invalid characters `<>:"/\|?*`, limits to 200 chars

**Playlist format:** M3U with relative paths (`../Music/Artist/Album/Track.mp3`)

**State tracking:** JSON file with file signatures and playlist hashes

**Progress calculation:** Tracks bytes copied, estimates speed and ETA

**Safety features:**
- Disk space check before export
- Confirmation prompt for exports > 10GB
- XML freshness warning if > 7 days old
- Graceful error handling

## Project Structure

```
android-music-sync/
├── apple_music_export.py    # Core export logic (Python)
├── sync_to_android.sh        # Wrapper script (Bash)
├── Library.xml               # Apple Music metadata (user-provided)
├── output/                   # Export destination (gitignored)
│   ├── .export_state.json   # Incremental sync state
│   ├── Music/               # Music files
│   └── Playlists/           # M3U playlists
└── README.md                # This file
```

## Requirements

- **Python 3.8+** - Built into macOS
- **Apple Music** - macOS Catalina or later
- **LocalSend** - [Download](https://localsend.org/)
- **Android device** - Sufficient storage for music library

No external Python packages required.

## License

MIT (or whatever license you prefer)
