"""Minimal keyboard-driven TUI application."""

from textual.app import App
from textual.binding import Binding

from ..config.manager import ConfigManager
from ..models.library import Library
from ..utils.discovery import auto_detect_library
from .screens.main_menu import MainMenuScreen


class AppleMusicSyncApp(App):
    """Minimal keyboard-driven TUI for Apple Music Sync."""

    CSS = """
    Screen {
        background: $surface;
    }
    """

    TITLE = "Apple Music → Android Sync"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.library: Library | None = None
        self.library_path = None
        self.library_age_days = 0
        self.selected_playlist_names: set[str] = set()

    def on_mount(self) -> None:
        """Initialize app on startup."""
        # Try to auto-detect library
        detected = auto_detect_library()
        if detected:
            self.library_path, self.library_age_days = detected

        # Push main menu screen
        self.push_screen(MainMenuScreen())


if __name__ == "__main__":
    app = AppleMusicSyncApp()
    app.run()
