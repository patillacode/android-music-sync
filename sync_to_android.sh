#!/bin/bash
#
# sync_to_android.sh
# Sync Apple Music library to Android phone
# Usage: ./sync_to_android.sh [--clean|--dry-run]
#

set -e  # Exit on error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/apple_music_export.py"
LIBRARY_PATH="./Library.xml"
OUTPUT_DIR="$SCRIPT_DIR/output"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_header() {
    echo -e "${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if Python script exists
check_python_script() {
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        print_error "Python export script not found: $PYTHON_SCRIPT"
        echo "Please ensure apple_music_export.py is in the same directory as this script."
        exit 1
    fi
}

# Check if library exists
check_library() {
    if [ ! -f "$LIBRARY_PATH" ]; then
        print_error "Apple Music library not found at: $LIBRARY_PATH"
        echo ""
        echo "Common locations to check:"
        echo "  - $HOME/Music/Music/Library.xml"
        echo "  - $HOME/Music/iTunes/iTunes Music Library.xml"
        echo ""
        echo "To use a different location, edit LIBRARY_PATH in this script."
        exit 1
    fi
}

# Clean output directory if requested
clean_output() {
    if [ -d "$OUTPUT_DIR" ]; then
        print_warning "Cleaning output directory: $OUTPUT_DIR"
        rm -rf "$OUTPUT_DIR"
        print_success "Directory cleaned"
    fi
}

# Main sync process
main() {
    print_header "================================================"
    print_header "  Apple Music → Android Sync"
    print_header "================================================"
    echo ""

    # Handle flags
    DRY_RUN_FLAG=""
    PLAYLIST_ARGS=""
    CLEAN_REQUESTED=0

    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                CLEAN_REQUESTED=1
                shift
                ;;
            --dry-run)
                DRY_RUN_FLAG="--dry-run"
                print_warning "DRY-RUN MODE: No files will be copied"
                echo ""
                shift
                ;;
            --playlists)
                PLAYLIST_ARGS="$PLAYLIST_ARGS --playlists \"$2\""
                shift 2
                ;;
            --playlist-file)
                PLAYLIST_ARGS="$PLAYLIST_ARGS --playlist-file \"$2\""
                shift 2
                ;;
            --list-playlists)
                # List playlists and exit (skip pre-flight checks)
                check_python_script
                python3 "$PYTHON_SCRIPT" --library "$LIBRARY_PATH" --list-playlists
                exit $?
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Usage: $0 [--clean|--dry-run|--list-playlists] [--playlists 'name1,name2'] [--playlist-file file.txt]"
                exit 1
                ;;
        esac
    done

    # Apply --clean only if not a dry-run
    if [ "$CLEAN_REQUESTED" -eq 1 ]; then
        if [ -n "$DRY_RUN_FLAG" ]; then
            print_warning "--clean ignored in dry-run mode (output directory preserved)"
            echo ""
        else
            clean_output
            echo ""
        fi
    fi

    # Pre-flight checks
    print_header "Running pre-flight checks..."
    check_python_script
    check_library
    print_success "All checks passed"
    echo ""

    # Run Python export script
    print_header "Exporting music library..."
    echo ""

    if eval python3 \"$PYTHON_SCRIPT\" --library \"$LIBRARY_PATH\" --output \"$OUTPUT_DIR\" $DRY_RUN_FLAG $PLAYLIST_ARGS; then
        echo ""
        print_success "Export completed successfully!"
    else
        print_error "Export failed. Check error messages above."
        exit 1
    fi

    echo ""
    print_header "================================================"
    print_header "  Next Steps: Transfer to Android"
    print_header "================================================"
    echo ""
    echo "Your music is ready at: $OUTPUT_DIR"
    echo ""
    echo "To transfer using LocalSend:"
    echo "  1. Open LocalSend on your Mac and Android phone"
    echo "  2. Ensure both devices are on the same WiFi"
    echo "  3. Select the entire AndroidSync folder to send"
    echo "  4. On your phone, save to: Internal Storage/Music/"
    echo ""
    echo "First time setup:"
    echo "  - This will transfer the full ~20GB (may take 10-30 min)"
    echo ""
    echo "Subsequent syncs:"
    echo "  - Only new/changed files are exported"
    echo "  - Use LocalSend's 'incremental' or 'overwrite' option"
    echo "  - Much faster than first sync"
    echo ""
    print_header "================================================"
}

# Run main
main "$@"
