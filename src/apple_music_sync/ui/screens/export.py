"""Minimal export progress display."""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from ...core.exporter import MusicExporter
from ...models.config import ExportProfile
from ...utils.formatters import format_size, format_time


class ExportProgressScreen(Screen):
    """Minimal progress display with live updates."""

    BINDINGS = [
        Binding("c", "cancel", "Cancel", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    CSS = """
    ExportProgressScreen {
        align: center middle;
    }

    #content {
        width: 80;
        height: auto;
        padding: 2;
    }
    """

    def __init__(self, profile: ExportProfile, selected_playlists: Optional[set[str]] = None):
        super().__init__()
        self.profile = profile
        self.selected_playlists = selected_playlists
        self.exporter: Optional[MusicExporter] = None
        self.worker: Optional[Worker] = None

        # Progress tracking
        self.current_playlist = ""
        self.current_track = ""
        self.total_tracks = 0
        self.processed_tracks = 0
        self.copied_files = 0
        self.skipped_files = 0
        self.bytes_copied = 0
        self.start_time = 0
        self.is_complete = False
        self.is_cancelled = False

    def compose(self) -> ComposeResult:
        """Create minimal progress UI."""
        yield Static(id="content")

    def on_mount(self) -> None:
        """Start export when screen loads."""
        import time
        self.start_time = time.time()
        self._start_export()

    def _start_export(self) -> None:
        """Start the export process in a worker thread."""
        # Create exporter with progress callback
        self.exporter = MusicExporter(
            profile=self.profile,
            progress_callback=self._handle_progress
        )

        # Apply playlist filter if selections were made
        if self.selected_playlists:
            self.profile.playlist_mode = "include"
            self.profile.playlist_patterns = list(self.selected_playlists)

        # Start export in background worker
        self.worker = self.run_worker(self._run_export, exclusive=True)

    def _run_export(self) -> dict:
        """Run export in worker thread (blocking)."""
        try:
            stats = self.exporter.export()
            return {
                "success": True,
                "stats": stats
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _handle_progress(self, event: dict) -> None:
        """Handle progress updates from exporter."""
        event_type = event.get("type")

        if event_type == "start":
            self.total_tracks = event.get("total_tracks", 0)
            self.call_from_thread(self._update_display)

        elif event_type == "playlist_start":
            self.current_playlist = event.get("playlist_name", "")
            self.call_from_thread(self._update_display)

        elif event_type == "track_start":
            self.current_track = event.get("track_name", "")
            self.call_from_thread(self._update_display)

        elif event_type == "track_complete":
            self.processed_tracks += 1
            if event.get("copied"):
                self.copied_files += 1
                self.bytes_copied += event.get("size", 0)
            else:
                self.skipped_files += 1
            self.call_from_thread(self._update_display)

        elif event_type == "complete":
            self.is_complete = True
            self.call_from_thread(self._show_summary, event.get("stats"))

    def _update_display(self) -> None:
        """Render the progress display."""
        lines = []

        # Header
        if self.is_complete:
            lines.append("┌─ Export Complete ─────────────────────────────────────────────────────┐")
        else:
            lines.append("┌─ Exporting ───────────────────────────────────────────────────────────┐")

        lines.append("│                                                                        │")

        # Progress bar
        if self.total_tracks > 0:
            progress_pct = int((self.processed_tracks / self.total_tracks) * 100)
            bar_width = 60
            filled = int((progress_pct / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"│  {bar}  │")
            lines.append(f"│  {progress_pct:3}%  ({self.processed_tracks:,} / {self.total_tracks:,} tracks){' ' * (48 - len(f'{self.processed_tracks:,}') - len(f'{self.total_tracks:,}'))}│")
        else:
            lines.append("│  Preparing...                                                          │")

        lines.append("│                                                                        │")

        # Current status
        if self.current_playlist and not self.is_complete:
            playlist_name = self.current_playlist
            if len(playlist_name) > 65:
                playlist_name = playlist_name[:62] + "..."
            lines.append(f"│  Playlist: {playlist_name:<61}│")

        if self.current_track and not self.is_complete:
            track_name = self.current_track
            if len(track_name) > 65:
                track_name = track_name[:62] + "..."
            lines.append(f"│  Track: {track_name:<64}│")

        if not self.is_complete and (self.current_playlist or self.current_track):
            lines.append("│                                                                        │")

        # Statistics
        lines.append("├────────────────────────────────────────────────────────────────────────┤")
        lines.append("│                                                                        │")
        lines.append(f"│  Copied:     {self.copied_files:,} files{' ' * (53 - len(f'{self.copied_files:,}'))}│")
        lines.append(f"│  Skipped:    {self.skipped_files:,} files{' ' * (53 - len(f'{self.skipped_files:,}'))}│")

        size_str = format_size(self.bytes_copied)
        lines.append(f"│  Data:       {size_str}{' ' * (60 - len(size_str))}│")

        # Speed and time
        import time
        elapsed = time.time() - self.start_time
        elapsed_str = format_time(int(elapsed))
        lines.append(f"│  Elapsed:    {elapsed_str}{' ' * (60 - len(elapsed_str))}│")

        if elapsed > 0 and self.bytes_copied > 0:
            speed_bps = self.bytes_copied / elapsed
            speed_mbps = speed_bps / (1024 * 1024)
            lines.append(f"│  Speed:      {speed_mbps:.2f} MB/s{' ' * (51 - len(f'{speed_mbps:.2f}'))}│")

        lines.append("│                                                                        │")
        lines.append("├────────────────────────────────────────────────────────────────────────┤")
        lines.append("│                                                                        │")

        if self.is_complete:
            lines.append("│  [q] Close                                                             │")
        else:
            lines.append("│  [c] Cancel                                                            │")

        lines.append("│                                                                        │")
        lines.append("└────────────────────────────────────────────────────────────────────────┘")

        content = "\n".join(lines)
        self.query_one("#content", Static).update(content)

    def _show_summary(self, stats: dict) -> None:
        """Show completion summary."""
        self._update_display()

    def action_cancel(self) -> None:
        """Cancel the export."""
        if not self.is_complete and self.worker and self.worker.state == WorkerState.RUNNING:
            self.worker.cancel()
            self.is_cancelled = True
            self.app.pop_screen()

    def action_close(self) -> None:
        """Close the screen."""
        if self.is_complete:
            self.app.pop_screen()
