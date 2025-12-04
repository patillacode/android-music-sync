"""Minimal main menu with keyboard navigation."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from ...core.library import LibraryParser
from ...models.config import ExportProfile
from ...utils.formatters import format_size


class MainMenuScreen(Screen):
    """Minimal keyboard-driven main menu."""

    BINDINGS = [
        Binding("1", "export_all", "Export All", show=False),
        Binding("2", "select_playlists", "Select Playlists", show=False),
        Binding("3", "profiles", "Profiles", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    CSS = """
    MainMenuScreen {
        align: center middle;
    }

    #content {
        width: 80;
        height: auto;
        padding: 2;
    }

    .text {
        color: $text;
    }

    .dim {
        color: $text-muted;
    }

    .warning {
        color: $warning;
    }

    .error {
        color: $error;
    }

    .success {
        color: $success;
    }
    """

    def compose(self) -> ComposeResult:
        """Create minimal menu UI."""
        yield Static(id="content")

    def on_mount(self) -> None:
        """Update menu when screen loads."""
        self._update_display()

    def _update_display(self) -> None:
        """Render the menu text."""
        lines = []

        # Header
        lines.append("┌─ Apple Music → Android Sync ─────────────────────────────────────┐")
        lines.append("│                                                                   │")

        # Library status
        app = self.app
        if not app.library_path:
            lines.append("│  [error]⚠ Library.xml not found[/error]                                      │")
            lines.append("│    Place Library.xml in current directory or ~/Music/Music/      │")
        else:
            # Load library
            try:
                if not app.library:
                    parser = LibraryParser(app.library_path)
                    app.library = parser.parse()

                lines.append("│  [success]✓ Library loaded[/success]                                             │")

                # Show path (truncate if too long)
                path_str = str(app.library_path)
                if len(path_str) > 60:
                    path_str = "..." + path_str[-57:]
                lines.append(f"│    Path: {path_str:<58}│")

                # Age warning
                if app.library_age_days > 7:
                    lines.append(f"│    [warning]Age: {app.library_age_days} days old (consider updating)[/warning]                  │")
                else:
                    lines.append(f"│    Age: {app.library_age_days} days{' ' * (60 - len(str(app.library_age_days)) - 10)}│")

                lines.append(f"│    Tracks: {app.library.track_count:,}{' ' * (57 - len(f'{app.library.track_count:,}'))}│")
                lines.append(f"│    Playlists: {app.library.playlist_count}{' ' * (54 - len(str(app.library.playlist_count)))}│")
                size_str = format_size(app.library.total_size)
                lines.append(f"│    Size: {size_str}{' ' * (59 - len(size_str))}│")

                # Selected playlists info
                if app.selected_playlist_names:
                    count = len(app.selected_playlist_names)
                    lines.append(f"│    [success]Selected: {count} playlist(s)[/success]{' ' * (44 - len(str(count)))}│")

            except Exception as e:
                lines.append(f"│  [error]❌ Error loading library: {str(e)[:38]}[/error]{' ' * (25 - min(38, len(str(e))))}│")

        lines.append("│                                                                   │")
        lines.append("├───────────────────────────────────────────────────────────────────┤")
        lines.append("│                                                                   │")

        # Menu options
        lines.append("│  [1] Export All Playlists                                         │")
        lines.append("│  [2] Select Playlists                                             │")
        lines.append("│  [3] Manage Profiles                                              │")
        lines.append("│                                                                   │")
        lines.append("│  [q] Quit                                                         │")
        lines.append("│                                                                   │")
        lines.append("└───────────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append("[dim]Press a number to select an option, or 'q' to quit[/dim]")

        content = "\n".join(lines)
        self.query_one("#content", Static).update(content)

    def action_export_all(self) -> None:
        """Start export with all playlists."""
        if not self.app.library:
            self.notify("Please load a library first", severity="warning")
            return

        from .export import ExportProgressScreen

        profile = ExportProfile(
            name="Export All",
            description="Export all playlists",
            library_path=self.app.library_path,
            output_dir=Path.cwd() / "output",
            playlist_mode="all",
            playlist_patterns=[]
        )

        self.app.push_screen(ExportProgressScreen(profile, None))

    def action_select_playlists(self) -> None:
        """Go to playlist selection."""
        if not self.app.library:
            self.notify("Please load a library first", severity="warning")
            return

        from .playlist_select import PlaylistSelectScreen
        self.app.push_screen(PlaylistSelectScreen())

    def action_profiles(self) -> None:
        """Profiles management (placeholder)."""
        self.notify("Profile management not yet implemented", severity="info")

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.app.exit()
