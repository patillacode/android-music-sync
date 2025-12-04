"""Core export logic for Apple Music library."""

import logging
import shutil
import time
from pathlib import Path
from typing import Callable

from ..models.config import ExportProfile
from ..models.library import Library, Track
from ..utils.formatters import format_size, format_time
from ..utils.validators import get_disk_space, sanitize_filename
from .library import LibraryParser
from .playlist import PlaylistFilter
from .state import StateManager

logger = logging.getLogger(__name__)


class ExportStats:
    """Statistics for an export operation."""

    def __init__(self):
        self.total_tracks = 0
        self.total_playlists = 0
        self.total_size = 0
        self.bytes_copied = 0
        self.files_copied = 0
        self.files_skipped = 0
        self.playlists_exported = 0
        self.playlists_skipped = 0
        self.start_time: float | None = None
        self.end_time: float | None = None

    @property
    def elapsed_time(self) -> float:
        """Time elapsed in seconds."""
        if not self.start_time:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def speed_bytes_per_sec(self) -> float:
        """Copy speed in bytes per second."""
        if self.elapsed_time == 0:
            return 0.0
        return self.bytes_copied / self.elapsed_time


class MusicExporter:
    """Exports Apple Music library to output directory."""

    def __init__(
        self,
        profile: ExportProfile,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self.profile = profile
        self.progress_callback = progress_callback

        self.library_path = profile.library_path
        self.output_dir = profile.output_dir
        self.music_output = self.output_dir / "Music"
        self.playlists_output = self.output_dir / "Playlists"

        self.state_manager = StateManager(self.output_dir / ".export_state.json")
        self.stats = ExportStats()

        # Create playlist filter
        self.playlist_filter = PlaylistFilter(
            mode=profile.playlist_mode,
            patterns=profile.playlist_patterns,
            min_track_count=profile.min_track_count,
            exclude_distinguished=profile.exclude_distinguished,
        )

    def export(self) -> ExportStats:
        """
        Perform the export operation.

        Returns:
            ExportStats object with operation statistics
        """
        logger.info(f"Starting export from {self.library_path}")
        self.stats.start_time = time.time()

        # Parse library
        logger.debug("Parsing library...")
        parser = LibraryParser(self.library_path)
        library = parser.parse()

        logger.info(
            f"Library loaded: {library.track_count} tracks, {library.playlist_count} playlists"
        )

        # Calculate stats
        self.stats.total_tracks = library.track_count
        self.stats.total_playlists = len(
            self.playlist_filter.filter_playlists(library.playlists)
        )
        self.stats.total_size = library.total_size

        # Check disk space
        if not self.profile.dry_run:
            self._check_disk_space()

        # Determine which tracks to export (based on playlist filter)
        selected_track_ids = self._get_selected_track_ids(library)

        # Export music files
        self._export_music_files(library, selected_track_ids)

        # Export playlists
        self._export_playlists(library)

        # Save state
        if not self.profile.dry_run:
            self.state_manager.mark_export_complete(self.stats.bytes_copied)
            self.state_manager.save()

        self.stats.end_time = time.time()
        logger.info(
            f"Export complete: {self.stats.files_copied} files copied, "
            f"{self.stats.files_skipped} skipped"
        )

        return self.stats

    def _get_selected_track_ids(self, library: Library) -> set[str] | None:
        """Get set of track IDs to export based on playlist filter."""
        if self.profile.playlist_mode == "all":
            return None  # Export all tracks

        return self.playlist_filter.get_selected_track_ids(library.playlists)

    def _check_disk_space(self) -> None:
        """Check if there's sufficient disk space."""
        available, total = get_disk_space(self.output_dir)
        required = self.stats.total_size

        if required > available:
            raise RuntimeError(
                f"Insufficient disk space!\n"
                f"  Required: {format_size(required)}\n"
                f"  Available: {format_size(available)}"
            )

        logger.debug(
            f"Disk space check: {format_size(required)} required, "
            f"{format_size(available)} available"
        )

    def _export_music_files(
        self, library: Library, selected_track_ids: set[str] | None
    ) -> None:
        """Export music files incrementally."""
        logger.info("Exporting music files...")

        if not self.profile.dry_run:
            self.music_output.mkdir(parents=True, exist_ok=True)

        # Filter tracks if needed
        if selected_track_ids:
            tracks_to_export = {
                tid: track
                for tid, track in library.tracks.items()
                if tid in selected_track_ids
            }
        else:
            tracks_to_export = library.tracks

        total = len(tracks_to_export)
        logger.info(f"Processing {total} tracks...")

        for idx, (track_id, track) in enumerate(tracks_to_export.items(), 1):
            self._export_track(track, idx, total)

    def _export_track(self, track: Track, current: int, total: int) -> None:
        """Export a single track."""
        # Build destination path
        artist = sanitize_filename(track.artist)
        album = sanitize_filename(track.album)
        filename = track.location.name

        dest_path = self.music_output / artist / album / filename

        # Check if file needs to be copied
        if self.profile.dry_run:
            self.stats.files_skipped += 1
            return

        should_copy = self.state_manager.is_file_changed(track.location)

        if should_copy and dest_path.exists():
            # Also check if destination exists and is same size
            if dest_path.stat().st_size == track.size:
                should_copy = False

        if should_copy:
            # Copy file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(track.location, dest_path)

            self.state_manager.update_file(track.location)
            self.stats.bytes_copied += track.size
            self.stats.files_copied += 1

            logger.debug(f"Copied: {filename}")
        else:
            self.stats.files_skipped += 1
            logger.debug(f"Skipped (unchanged): {filename}")

        # Report progress
        if self.progress_callback:
            progress_pct = (current / total) * 100 if total > 0 else 0
            self.progress_callback(
                {
                    "type": "track",
                    "current": current,
                    "total": total,
                    "progress_pct": progress_pct,
                    "track_name": track.name,
                    "artist": track.artist,
                    "bytes_copied": self.stats.bytes_copied,
                    "speed": self.stats.speed_bytes_per_sec,
                }
            )

    def _export_playlists(self, library: Library) -> None:
        """Export playlists as M3U files."""
        logger.info("Exporting playlists...")

        if not self.profile.dry_run:
            self.playlists_output.mkdir(parents=True, exist_ok=True)

        # Filter playlists
        playlists_to_export = self.playlist_filter.filter_playlists(library.playlists)

        total = len(playlists_to_export)
        logger.info(f"Processing {total} playlists...")

        for idx, playlist in enumerate(playlists_to_export, 1):
            self._export_playlist(playlist, library, idx, total)

    def _export_playlist(
        self, playlist, library: Library, current: int, total: int
    ) -> None:
        """Export a single playlist as M3U file."""
        m3u_path = self.playlists_output / f"{sanitize_filename(playlist.name)}.m3u"

        # Check if playlist changed
        if self.profile.dry_run:
            self.stats.playlists_skipped += 1
            return

        should_export = self.state_manager.is_playlist_changed(
            playlist.name, playlist.track_ids
        )

        if should_export:
            # Generate M3U content
            with open(m3u_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")

                for track_id in playlist.track_ids:
                    track = library.tracks.get(track_id)
                    if not track:
                        continue

                    # Build relative path from Playlists/ to Music/
                    artist = sanitize_filename(track.artist)
                    album = sanitize_filename(track.album)
                    filename = track.location.name

                    relative_path = f"../Music/{artist}/{album}/{filename}"

                    # Write extended info
                    duration_sec = track.duration // 1000
                    f.write(f"#EXTINF:{duration_sec},{track.artist} - {track.name}\n")
                    f.write(f"{relative_path}\n")

            self.state_manager.update_playlist(playlist.name, playlist.track_ids)
            self.stats.playlists_exported += 1

            logger.debug(f"Exported playlist: {playlist.name}")
        else:
            self.stats.playlists_skipped += 1
            logger.debug(f"Skipped playlist (unchanged): {playlist.name}")

        # Report progress
        if self.progress_callback:
            progress_pct = (current / total) * 100 if total > 0 else 0
            self.progress_callback(
                {
                    "type": "playlist",
                    "current": current,
                    "total": total,
                    "progress_pct": progress_pct,
                    "playlist_name": playlist.name,
                }
            )

    def print_summary(self) -> None:
        """Print export summary to console."""
        print(f"\n{'=' * 60}")
        print("Export Summary")
        print(f"{'=' * 60}")
        print("Music files:")
        print(f"  - New/Modified: {self.stats.files_copied}")
        print(f"  - Skipped (unchanged): {self.stats.files_skipped}")
        print(f"  - Data copied: {format_size(self.stats.bytes_copied)}")
        print("Playlists:")
        print(f"  - Exported: {self.stats.playlists_exported}")
        print(f"  - Skipped (unchanged): {self.stats.playlists_skipped}")
        print(f"\nOutput directory: {self.output_dir}")
        print(f"Time elapsed: {format_time(self.stats.elapsed_time)}")
        print(f"{'=' * 60}")
