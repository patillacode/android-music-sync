"""Playlist filtering logic."""

import fnmatch
from typing import Literal

from ..models.library import Playlist


class PlaylistFilter:
    """Filter playlists based on patterns and criteria."""

    def __init__(
        self,
        mode: Literal["all", "include", "exclude"] = "all",
        patterns: list[str] | None = None,
        min_track_count: int = 0,
        exclude_distinguished: bool = True,
    ):
        self.mode = mode
        self.patterns = patterns or []
        self.min_track_count = min_track_count
        self.exclude_distinguished = exclude_distinguished

    def should_export(self, playlist: Playlist) -> bool:
        """Determine if playlist should be exported."""
        # Filter out distinguished (system) playlists
        if self.exclude_distinguished and playlist.is_distinguished:
            return False

        # Filter by minimum track count
        if playlist.track_count < self.min_track_count:
            return False

        # Apply pattern matching
        if self.mode == "all":
            return True
        elif self.mode == "include":
            return self._matches_any_pattern(playlist.name)
        elif self.mode == "exclude":
            return not self._matches_any_pattern(playlist.name)

        return True

    def _matches_any_pattern(self, name: str) -> bool:
        """Check if name matches any of the patterns."""
        if not self.patterns:
            return False

        return any(self._matches_pattern(name, pattern) for pattern in self.patterns)

    @staticmethod
    def _matches_pattern(name: str, pattern: str) -> bool:
        """Match name against pattern (case-insensitive, supports wildcards)."""
        return fnmatch.fnmatch(name.lower(), pattern.lower())

    def filter_playlists(self, playlists: list[Playlist]) -> list[Playlist]:
        """Filter a list of playlists."""
        return [p for p in playlists if self.should_export(p)]

    def get_selected_track_ids(self, playlists: list[Playlist]) -> set[str]:
        """Get set of all track IDs in selected playlists."""
        selected = self.filter_playlists(playlists)
        track_ids = set()

        for playlist in selected:
            track_ids.update(playlist.track_ids)

        return track_ids
