"""Minimal keyboard-driven playlist selection."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Input, Static


class PlaylistSelectScreen(Screen):
    """Keyboard-driven playlist selector with vim-like navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("space", "toggle_select", "Toggle", show=False),
        Binding("a", "select_all", "Select All", show=False),
        Binding("n", "select_none", "Clear", show=False),
        Binding("enter", "confirm", "Continue", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("/", "focus_filter", "Filter", show=False),
    ]

    CSS = """
    PlaylistSelectScreen {
        align: center middle;
    }

    #container {
        width: 90;
        height: auto;
        padding: 2;
    }

    #filter-input {
        width: 100%;
        margin-bottom: 1;
        border: solid $primary;
    }

    .text {
        color: $text;
    }

    .dim {
        color: $text-muted;
    }

    .selected {
        color: $success;
    }

    .cursor {
        background: $primary 30%;
    }
    """

    def __init__(self):
        super().__init__()
        self.cursor = 0
        self.selected: set[str] = set()
        self.filter_text = ""
        self.filtered_playlists = []

    def compose(self) -> ComposeResult:
        """Create minimal UI."""
        yield Input(placeholder="Filter... (press / to focus, ESC to clear)", id="filter-input")
        yield Static(id="container")

    def on_mount(self) -> None:
        """Load playlists when screen loads."""
        # Copy existing selections
        self.selected = set(getattr(self.app, "selected_playlist_names", set()))
        self._load_playlists()
        self._update_display()

    def _load_playlists(self) -> None:
        """Load and filter playlists."""
        app = self.app
        if not app.library:
            return

        # Filter to user playlists only
        user_playlists = [p for p in app.library.playlists if not p.is_distinguished]

        # Apply filter
        if self.filter_text:
            self.filtered_playlists = [
                p for p in user_playlists
                if self.filter_text.lower() in p.name.lower()
            ]
        else:
            self.filtered_playlists = user_playlists

        # Sort by name
        self.filtered_playlists.sort(key=lambda p: p.name.lower())

        # Clamp cursor
        if self.cursor >= len(self.filtered_playlists):
            self.cursor = max(0, len(self.filtered_playlists) - 1)

    def _update_display(self) -> None:
        """Render the playlist list."""
        lines = []

        # Header
        lines.append("┌─ Select Playlists ────────────────────────────────────────────────────────────┐")
        lines.append("│                                                                                │")

        if not self.filtered_playlists:
            lines.append("│  [dim]No playlists found[/dim]                                                        │")
            lines.append("│                                                                                │")
        else:
            # Show selection count
            count = len(self.selected)
            lines.append(f"│  [success]{count} selected[/success]{' ' * (71 - len(str(count)))}│")
            lines.append("│                                                                                │")

            # Show playlists (limited to visible area)
            visible_start = max(0, self.cursor - 10)
            visible_end = min(len(self.filtered_playlists), visible_start + 20)

            for idx in range(visible_start, visible_end):
                playlist = self.filtered_playlists[idx]
                is_selected = playlist.name in self.selected
                is_cursor = idx == self.cursor

                # Checkbox
                checkbox = "[x]" if is_selected else "[ ]"

                # Truncate name if too long
                name = playlist.name
                track_info = f"({playlist.track_count} tracks)"
                max_name_len = 72 - len(checkbox) - len(track_info) - 5

                if len(name) > max_name_len:
                    name = name[:max_name_len - 3] + "..."

                # Format line
                line = f"│ {checkbox} {name}"
                padding = 74 - len(checkbox) - len(name) - len(track_info)
                line += " " * padding + track_info + " │"

                # Apply cursor highlighting
                if is_cursor:
                    line = f"[reverse]{line}[/reverse]"

                # Apply selection color
                if is_selected:
                    line = line.replace(checkbox, f"[success]{checkbox}[/success]")

                lines.append(line)

            # Show scroll indicator
            if len(self.filtered_playlists) > 20:
                lines.append("│                                                                                │")
                lines.append(f"│  [dim]Showing {visible_start + 1}-{visible_end} of {len(self.filtered_playlists)}[/dim]{' ' * (60 - len(str(visible_start + 1)) - len(str(visible_end)) - len(str(len(self.filtered_playlists))))}│")

        lines.append("│                                                                                │")
        lines.append("├────────────────────────────────────────────────────────────────────────────────┤")
        lines.append("│                                                                                │")
        lines.append("│  [j/k] or [↑/↓] Move    [space] Toggle    [a] All    [n] None                 │")
        lines.append("│  [/] Filter    [enter] Continue    [esc] Cancel                                │")
        lines.append("│                                                                                │")
        lines.append("└────────────────────────────────────────────────────────────────────────────────┘")

        content = "\n".join(lines)
        self.query_one("#container", Static).update(content)

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        if self.cursor < len(self.filtered_playlists) - 1:
            self.cursor += 1
            self._update_display()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        if self.cursor > 0:
            self.cursor -= 1
            self._update_display()

    def action_toggle_select(self) -> None:
        """Toggle selection at cursor."""
        if not self.filtered_playlists:
            return

        playlist = self.filtered_playlists[self.cursor]
        if playlist.name in self.selected:
            self.selected.discard(playlist.name)
        else:
            self.selected.add(playlist.name)

        self._update_display()

    def action_select_all(self) -> None:
        """Select all visible playlists."""
        for playlist in self.filtered_playlists:
            self.selected.add(playlist.name)
        self._update_display()

    def action_select_none(self) -> None:
        """Clear all selections."""
        self.selected.clear()
        self._update_display()

    def action_confirm(self) -> None:
        """Confirm selection and return."""
        if not self.selected:
            self.notify("Please select at least one playlist", severity="warning")
            return

        # Store in app
        self.app.selected_playlist_names = self.selected
        self.app.pop_screen()
        self.notify(f"Selected {len(self.selected)} playlists", severity="success")

    def action_cancel(self) -> None:
        """Cancel and return."""
        self.app.pop_screen()

    def action_focus_filter(self) -> None:
        """Focus the filter input."""
        self.query_one("#filter-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "filter-input":
            self.filter_text = event.value
            self._load_playlists()
            self._update_display()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle filter input submission (unfocus)."""
        self.query_one("#container").focus()
