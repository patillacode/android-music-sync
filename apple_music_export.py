#!/usr/bin/env python3
"""
Apple Music Library Exporter
Exports music files and playlists from Apple Music to a staging directory.
Supports incremental exports - only processes new/modified files on subsequent runs.
"""

import hashlib
import json
import os
import plistlib
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote


class AppleMusicExporter:
    def __init__(
        self,
        library_path: str,
        output_dir: str,
        dry_run: bool = False,
        include_playlists: Optional[List[str]] = None,
        playlist_file: Optional[str] = None,
    ):
        self.library_path = Path(library_path).expanduser()
        self.output_dir = Path(output_dir).expanduser()
        self.state_file = self.output_dir / ".export_state.json"
        self.music_output = self.output_dir / "Music"
        self.playlists_output = self.output_dir / "Playlists"
        self.dry_run = dry_run

        # Load playlists from file if specified, otherwise use command-line list
        if playlist_file:
            self.include_playlists = self._load_playlist_file(playlist_file)
        else:
            self.include_playlists = include_playlists

        # Will be set in export() if playlist filtering is active
        self.selected_track_ids: Optional[set] = None

        # Load previous export state
        self.state = (
            self._load_state()
            if not dry_run
            else {"exported_files": {}, "exported_playlists": {}}
        )

        # Statistics
        self.stats: Dict[str, Any] = {
            "total_size": 0,
            "total_tracks": 0,
            "total_playlists": 0,
            "bytes_copied": 0,
            "start_time": None,  # Will be float when set
        }

    def _load_state(self) -> Dict[str, Any]:
        """Load the state from previous exports."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {"exported_files": {}, "exported_playlists": {}}

    def _save_state(self) -> None:
        """Save current export state."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _get_file_signature(self, file_path: Path) -> str:
        """Get a signature for a file (size + mtime)."""
        if not file_path.exists():
            return ""
        stat = file_path.stat()
        return f"{stat.st_size}:{stat.st_mtime}"

    def _parse_location(self, location: str) -> Path:
        """Parse file:// URL to filesystem path."""
        if location.startswith("file://"):
            # Remove file:// prefix and decode URL encoding
            path = unquote(location[7:])
            return Path(path)
        return Path(location)

    def _load_playlist_file(self, file_path: str) -> List[str]:
        """Load playlist names from config file."""
        playlists = []
        path = Path(file_path).expanduser()

        if not path.exists():
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    playlists.append(line)

        if not playlists:
            raise ValueError(
                f"Playlist file {file_path} is empty or contains only comments"
            )

        return playlists

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Match playlist name against pattern (supports wildcards)."""
        import fnmatch

        return fnmatch.fnmatch(name.lower(), pattern.lower())

    def _should_export_playlist(self, playlist_name: str) -> bool:
        """Check if playlist should be exported based on filters."""
        # If no include list specified, export all playlists
        if not self.include_playlists:
            return True

        # Check if playlist matches any include pattern
        return any(
            self._matches_pattern(playlist_name, pattern)
            for pattern in self.include_playlists
        )

    def _get_tracks_in_selected_playlists(self, playlists: List[Any]) -> set:
        """Get set of track IDs that are in selected playlists."""
        selected_track_ids = set()

        for playlist in playlists:
            # Skip distinguished (Apple Music system) playlists
            if playlist.get("Distinguished Kind") is not None:
                continue

            playlist_items = playlist.get("Playlist Items")
            if not playlist_items:
                continue

            name = playlist.get("Name", "Untitled")

            # Only include tracks from selected playlists
            if self._should_export_playlist(name):
                for item in playlist_items:
                    selected_track_ids.add(str(item["Track ID"]))

        return selected_track_ids

    def list_playlists(self) -> None:
        """List all available playlists in the library."""
        print("Reading Apple Music library...")

        # Validate library file exists
        if not self.library_path.exists():
            raise FileNotFoundError(
                f"Library file not found: {self.library_path}\n\n"
                f"📋 SETUP REQUIRED:\n"
                f"   1. Open Apple Music app\n"
                f"   2. Menu: File → Library → Export Library...\n"
                f"   3. Save the file as 'Library.xml'\n\n"
                f"📁 RECOMMENDED LOCATION (Most Convenient):\n"
                f"   Save to the project directory:\n"
                f"   {Path.cwd() / 'Library.xml'}\n"
            )

        # Parse library
        try:
            with open(self.library_path, "rb") as f:
                library = plistlib.load(f)
        except Exception as e:
            raise ValueError(
                f"Failed to parse Library.xml: {e}\nFile may be corrupted or not valid XML."
            )

        playlists = library.get("Playlists", [])

        # Filter to user playlists only (exclude Distinguished/system playlists)
        user_playlists = [
            p
            for p in playlists
            if p.get("Distinguished Kind") is None and p.get("Playlist Items")
        ]

        print(f"\n{'=' * 60}")
        print(f"Available Playlists ({len(user_playlists)} total)")
        print(f"{'=' * 60}\n")

        for idx, playlist in enumerate(
            sorted(user_playlists, key=lambda p: p.get("Name", "").lower()), 1
        ):
            name = playlist.get("Name", "Untitled")
            track_count = len(playlist.get("Playlist Items", []))
            print(f"  {idx:3}. {name} ({track_count} tracks)")

        print(f"\n{'=' * 60}")
        print("\nUsage examples:")
        print("  # Export specific playlists:")
        print(
            f'  ./sync_to_android.sh --playlists "{user_playlists[0].get("Name", "Example")}"'
        )
        print("\n  # Use wildcards:")
        print('  ./sync_to_android.sh --playlists "music*"')
        print(f"\n{'=' * 60}")

    def _get_disk_space(self) -> Tuple[int, int]:
        """Get available and total disk space in bytes."""
        stat = os.statvfs(
            self.output_dir.parent if self.output_dir.exists() else Path.home()
        )
        available = stat.f_bavail * stat.f_frsize
        total = stat.f_blocks * stat.f_frsize
        return available, total

    def _format_size(self, bytes_size) -> str:
        """Format bytes as human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"

    def _print_progress(self, current: int, total: int, item_name: str = "") -> None:
        """Print progress bar."""
        percent = (current / total * 100) if total > 0 else 0
        bar_length = 40
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        # Calculate speed and ETA
        if self.stats["start_time"] and self.stats["bytes_copied"] > 0:
            elapsed = time.time() - self.stats["start_time"]
            speed = self.stats["bytes_copied"] / elapsed
            remaining_bytes = self.stats["total_size"] - self.stats["bytes_copied"]
            eta = remaining_bytes / speed if speed > 0 else 0
            speed_str = f"{self._format_size(speed)}/s"
            eta_str = f"ETA: {self._format_time(eta)}"
        else:
            speed_str = ""
            eta_str = ""

        item_display = f" - {item_name[:40]}" if item_name else ""

        # Use \r to overwrite the line
        print(
            f"\r  [{bar}] {percent:5.1f}% ({current}/{total}){item_display}  {speed_str}  {eta_str}".ljust(
                120
            ),
            end="",
            flush=True,
        )

        if current == total:
            print()  # New line when complete

    def _calculate_export_size(
        self, tracks: Dict[str, Any], playlists: List[Any]
    ) -> None:
        """Calculate total export size."""
        # If playlist filtering is active, count only tracks in selected playlists
        if self.selected_track_ids:
            filtered_tracks = {
                tid: t for tid, t in tracks.items() if tid in self.selected_track_ids
            }
            self.stats["total_tracks"] = len(filtered_tracks)
            tracks_to_size = filtered_tracks
        else:
            self.stats["total_tracks"] = len(tracks)
            tracks_to_size = tracks

        self.stats["total_playlists"] = len(
            [
                p
                for p in playlists
                if p.get("Distinguished Kind") is None
                and p.get("Playlist Items")
                and self._should_export_playlist(p.get("Name", ""))
            ]
        )

        for track in tracks_to_size.values():
            location = track.get("Location")
            if location:
                source_path = self._parse_location(location)
                if source_path.exists():
                    self.stats["total_size"] += source_path.stat().st_size

    def _print_dry_run_summary(self) -> None:
        """Print dry-run summary without copying files."""
        available, total_disk = self._get_disk_space()

        print(f"\n{'=' * 60}")
        print("DRY-RUN SUMMARY (No files will be copied)")
        print(f"{'=' * 60}")

        # Show playlist filter info if active
        if self.include_playlists:
            print("\n📋 Playlist Filter:")
            print(f"  - Patterns: {', '.join(self.include_playlists)}")
            if self.selected_track_ids:
                print(
                    f"  - Tracks in selected playlists: {len(self.selected_track_ids)}"
                )

        print("\nLibrary:")
        print(f"  - Total tracks: {self.stats['total_tracks']}")
        print(f"  - Total playlists: {self.stats['total_playlists']}")
        print(f"  - Total size: {self._format_size(self.stats['total_size'])}")
        print("\nDisk Space:")
        print(f"  - Required: {self._format_size(self.stats['total_size'])}")
        print(f"  - Available: {self._format_size(available)}")
        if self.stats["total_size"] > available:
            print("  - Status: ❌ INSUFFICIENT SPACE")
        else:
            print("  - Status: ✓ Sufficient space")
        print(f"\nOutput directory: {self.output_dir}")
        print("\nRun without --dry-run flag to perform actual export.")
        print(f"{'=' * 60}")

    def export(self) -> None:
        """Main export function."""
        print("Reading Apple Music library...")

        # Validate library file exists
        if not self.library_path.exists():
            raise FileNotFoundError(
                f"Library file not found: {self.library_path}\n\n"
                f"📋 SETUP REQUIRED:\n"
                f"   1. Open Apple Music app\n"
                f"   2. Menu: File → Library → Export Library...\n"
                f"   3. Save the file as 'Library.xml'\n\n"
                f"📁 RECOMMENDED LOCATION (Most Convenient):\n"
                f"   Save to the project directory:\n"
                f"   {Path.cwd() / 'Library.xml'}\n\n"
                f"   Then run: ./apple_music_export.py --library Library.xml --dry-run\n\n"
                f"📁 ALTERNATIVE LOCATION:\n"
                f"   {Path.home() / 'Music/Music/Library.xml'}\n"
                f"   (or: ~/Music/iTunes/iTunes Music Library.xml)\n\n"
                f"💡 TIP: Placing it in the project folder is easier for version control\n"
                f"   and avoids conflicts with other applications."
            )

        # Check XML file age and warn if it's old
        xml_age_days = (time.time() - self.library_path.stat().st_mtime) / 86400
        if xml_age_days > 7:
            print(f"\n⚠️  WARNING: Library.xml is {xml_age_days:.1f} days old!")
            print("   Consider re-exporting from Apple Music for latest changes.\n")

        # Parse library
        try:
            with open(self.library_path, "rb") as f:
                library = plistlib.load(f)
        except Exception as e:
            raise ValueError(
                f"Failed to parse Library.xml: {e}\nFile may be corrupted or not valid XML."
            )

        tracks = library.get("Tracks", {})
        playlists = library.get("Playlists", [])

        # Calculate selected track IDs if playlist filtering is active
        if self.include_playlists:
            self.selected_track_ids = self._get_tracks_in_selected_playlists(playlists)
            print(
                f"📋 Playlist filter active: {len(self.selected_track_ids)} tracks in selected playlists"
            )

        # Calculate total size for progress reporting
        self._calculate_export_size(tracks, playlists)

        # Dry-run mode: just print statistics
        if self.dry_run:
            self._print_dry_run_summary()
            return

        # Check disk space
        available, total = self._get_disk_space()
        required = self.stats["total_size"]
        if required > available:
            raise RuntimeError(
                f"Insufficient disk space!\n"
                f"  Required: {self._format_size(required)}\n"
                f"  Available: {self._format_size(available)}\n"
                f"  Please free up space and try again."
            )

        # Confirmation for large exports
        if required > 10 * 1024**3:  # 10GB
            print(f"\n{'=' * 60}")
            print("⚠️  LARGE EXPORT WARNING")
            print(f"{'=' * 60}")
            print(f"Export size: {self._format_size(required)}")
            print(f"Available space: {self._format_size(available)}")
            print(f"Output directory: {self.output_dir}")
            response = input("\nProceed with export? (yes/N): ").strip().lower()
            if response not in ("y", "yes"):
                print("Export cancelled.")
                return
            print()

        self.stats["start_time"] = time.time()

        # Export music files
        new_files, skipped_files = self._export_music_files(tracks)

        # Export playlists
        new_playlists, skipped_playlists = self._export_playlists(playlists, tracks)

        # Save state
        self._save_state()

        # Print summary
        elapsed = time.time() - self.stats["start_time"]
        print(f"\n{'=' * 60}")
        print("Export Summary:")
        print(f"{'=' * 60}")
        print("Music files:")
        print(f"  - New/Modified: {new_files}")
        print(f"  - Skipped (unchanged): {skipped_files}")
        print(f"  - Data copied: {self._format_size(self.stats['bytes_copied'])}")
        print("Playlists:")
        print(f"  - New/Modified: {new_playlists}")
        print(f"  - Skipped (unchanged): {skipped_playlists}")
        print(f"\nOutput directory: {self.output_dir}")
        print(f"Time elapsed: {self._format_time(elapsed)}")
        print(f"{'=' * 60}")

    def _export_music_files(self, tracks: Dict[str, Any]) -> Tuple[int, int]:
        """Export music files incrementally."""
        print("\nExporting music files...")
        self.music_output.mkdir(parents=True, exist_ok=True)

        new_count = 0
        skipped_count = 0

        # Filter tracks if playlist filtering is active
        if self.selected_track_ids:
            filtered_tracks = {
                tid: t for tid, t in tracks.items() if tid in self.selected_track_ids
            }
            total = len(filtered_tracks)
            track_items = filtered_tracks.items()
        else:
            total = len(tracks)
            track_items = tracks.items()

        for idx, (track_id, track) in enumerate(track_items, 1):
            location = track.get("Location")
            if not location:
                continue

            source_path = self._parse_location(location)
            if not source_path.exists():
                continue

            # Get relative path structure (Artist/Album/Track.mp3)
            artist = track.get("Artist", "Unknown Artist")
            album = track.get("Album", "Unknown Album")
            filename = source_path.name

            # Sanitize directory names
            artist = self._sanitize_filename(artist)
            album = self._sanitize_filename(album)

            dest_path = self.music_output / artist / album / filename

            # Check if file needs to be copied
            file_sig = self._get_file_signature(source_path)
            file_key = str(source_path)

            if (
                file_key in self.state["exported_files"]
                and self.state["exported_files"][file_key] == file_sig
                and dest_path.exists()
            ):
                skipped_count += 1
            else:
                # Copy file
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                file_size = source_path.stat().st_size
                shutil.copy2(source_path, dest_path)

                # Update state and stats
                self.state["exported_files"][file_key] = file_sig
                self.stats["bytes_copied"] += file_size
                new_count += 1

            # Update progress every file
            track_name = f"{artist} - {track.get('Name', filename)}"
            self._print_progress(idx, total, track_name)

        return new_count, skipped_count

    def _export_playlists(
        self, playlists: List[Any], tracks: Dict[str, Any]
    ) -> Tuple[int, int]:
        """Export playlists as M3U files."""
        print("\nExporting playlists...")
        self.playlists_output.mkdir(parents=True, exist_ok=True)

        new_count = 0
        skipped_count = 0

        # Filter eligible playlists
        eligible_playlists = [
            p
            for p in playlists
            if p.get("Distinguished Kind") is None and p.get("Playlist Items")
        ]
        total_playlists = len(eligible_playlists)

        for idx, playlist in enumerate(eligible_playlists, 1):
            name = playlist.get("Name", "Untitled")

            # Check if playlist should be exported
            if not self._should_export_playlist(name):
                continue

            playlist_items = playlist.get("Playlist Items", [])

            # Generate playlist signature (track IDs hash)
            track_ids = [str(item["Track ID"]) for item in playlist_items]
            playlist_sig = hashlib.md5("".join(track_ids).encode()).hexdigest()

            # Check if playlist changed
            if (
                name in self.state["exported_playlists"]
                and self.state["exported_playlists"][name] == playlist_sig
            ):
                skipped_count += 1
            else:
                # Create M3U file
                m3u_path = (
                    self.playlists_output / f"{self._sanitize_filename(name)}.m3u"
                )

                with open(m3u_path, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")

                    for item in playlist_items:
                        track_id = str(item["Track ID"])
                        track = tracks.get(track_id)

                        if not track:
                            continue

                        location = track.get("Location")
                        if not location:
                            continue

                        source_path = self._parse_location(location)
                        if not source_path.exists():
                            continue

                        # Build relative path from playlists folder to music file
                        artist = self._sanitize_filename(
                            track.get("Artist", "Unknown Artist")
                        )
                        album = self._sanitize_filename(
                            track.get("Album", "Unknown Album")
                        )
                        filename = source_path.name

                        # Relative path from Playlists/ to Music/Artist/Album/Track.mp3
                        relative_path = f"../Music/{artist}/{album}/{filename}"

                        # Write extended info
                        duration = (
                            track.get("Total Time", 0) // 1000
                        )  # Convert ms to seconds
                        track_name = track.get("Name", filename)
                        f.write(f"#EXTINF:{duration},{artist} - {track_name}\n")
                        f.write(f"{relative_path}\n")

                # Update state
                self.state["exported_playlists"][name] = playlist_sig
                new_count += 1

            # Progress update
            print(f"  [{idx}/{total_playlists}] {name}", end="\r")

        print(f"\n  Completed: {total_playlists} playlists processed")
        return new_count, skipped_count

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize string for use as filename/directory name."""
        # Replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Remove leading/trailing dots and spaces
        name = name.strip(". ")

        # Limit length
        if len(name) > 200:
            name = name[:200]

        return name or "Unknown"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Export Apple Music library and playlists incrementally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal export
  %(prog)s

  # Dry-run to preview what would be exported
  %(prog)s --dry-run

  # Custom paths
  %(prog)s --library ~/custom/Library.xml --output ~/exports
        """,
    )
    # Default to ./Library.xml if it exists, otherwise ~/Music/Music/Library.xml
    default_library = (
        "./Library.xml"
        if Path("./Library.xml").exists()
        else "~/Music/Music/Library.xml"
    )
    parser.add_argument(
        "--library",
        default=default_library,
        help=(
            "Path to Apple Music Library.xml file. "
            "Export via: Apple Music → File → Library → Export Library. "
            "TIP: You can save it to the current directory as './Library.xml' "
            "for easier access (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--output",
        default="~/projects/android-music-sync/output",
        help="Output directory for exported files (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview export without copying files"
    )
    parser.add_argument(
        "--playlists",
        help=(
            "Comma-separated list of playlist names to export. "
            "Supports wildcards (e.g., 'Workout*'). "
            "If specified, ONLY these playlists and their tracks will be exported. "
            "Example: --playlists 'Gym,Running,Chill*'"
        ),
    )
    parser.add_argument(
        "--playlist-file",
        help=(
            "Path to text file containing playlist names (one per line). "
            "Supports wildcards and comments (lines starting with #). "
            "Command-line --playlists takes precedence if both specified. "
            "Example: --playlist-file playlists.txt"
        ),
    )
    parser.add_argument(
        "--list-playlists",
        action="store_true",
        help=(
            "List all available playlists in the library and exit. "
            "Useful for discovering playlist names before filtering. "
            "Does not perform any export."
        ),
    )

    args = parser.parse_args()

    # Handle --list-playlists (early exit, no export needed)
    if args.list_playlists:
        try:
            # Create minimal exporter just to list playlists
            exporter = AppleMusicExporter(
                args.library,
                args.output,
                dry_run=True,  # Not used, but required
            )
            exporter.list_playlists()
            exit(0)
        except FileNotFoundError as e:
            print(f"\n❌ Error: {e}")
            exit(1)
        except ValueError as e:
            print(f"\n❌ Error: {e}")
            exit(1)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            exit(1)

    # Parse playlist arguments
    include_playlists = None
    if args.playlists:
        # Command-line takes precedence
        include_playlists = [p.strip() for p in args.playlists.split(",")]
    elif args.playlist_file:
        # Will be loaded by AppleMusicExporter
        pass

    try:
        exporter = AppleMusicExporter(
            args.library,
            args.output,
            dry_run=args.dry_run,
            include_playlists=include_playlists,
            playlist_file=args.playlist_file if not args.playlists else None,
        )
        exporter.export()
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        exit(1)
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        exit(1)
    except RuntimeError as e:
        print(f"\n❌ Error: {e}")
        exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Export cancelled by user.")
        exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
