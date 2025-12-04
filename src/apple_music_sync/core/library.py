"""Library parsing for Apple Music Library.xml files."""

import plistlib
from pathlib import Path
from urllib.parse import unquote

from ..models.library import Library, Playlist, Track


class LibraryParser:
    """Parser for Apple Music Library.xml files."""

    def __init__(self, library_path: Path):
        self.library_path = library_path

    def parse(self) -> Library:
        """Parse Library.xml and return Library model."""
        if not self.library_path.exists():
            raise FileNotFoundError(f"Library file not found: {self.library_path}")

        try:
            with open(self.library_path, "rb") as f:
                plist_data = plistlib.load(f)
        except Exception as e:
            raise ValueError(
                f"Failed to parse Library.xml: {e}\nFile may be corrupted."
            ) from e

        tracks = self._parse_tracks(plist_data.get("Tracks", {}))
        playlists = self._parse_playlists(plist_data.get("Playlists", []))

        return Library(tracks=tracks, playlists=playlists)

    def _parse_tracks(self, tracks_data: dict) -> dict[str, Track]:
        """Parse tracks from plist data."""
        tracks = {}

        for track_id, track_data in tracks_data.items():
            location = track_data.get("Location")
            if not location:
                continue

            path = self._parse_file_url(location)
            if not path.exists():
                continue

            track = Track(
                track_id=track_id,
                name=track_data.get("Name", "Unknown"),
                artist=track_data.get("Artist", "Unknown Artist"),
                album=track_data.get("Album", "Unknown Album"),
                location=path,
                size=track_data.get("Size", 0),
                duration=track_data.get("Total Time", 0),
            )
            tracks[track_id] = track

        return tracks

    def _parse_playlists(self, playlists_data: list) -> list[Playlist]:
        """Parse playlists from plist data."""
        playlists = []

        for playlist_data in playlists_data:
            # Skip distinguished (system) playlists
            is_distinguished = playlist_data.get("Distinguished Kind") is not None

            playlist_items = playlist_data.get("Playlist Items", [])
            if not playlist_items and not is_distinguished:
                # Skip empty playlists (but keep empty system playlists)
                continue

            track_ids = [str(item["Track ID"]) for item in playlist_items]

            playlist = Playlist(
                name=playlist_data.get("Name", "Untitled"),
                track_ids=track_ids,
                is_distinguished=is_distinguished,
            )
            playlists.append(playlist)

        return playlists

    @staticmethod
    def _parse_file_url(location: str) -> Path:
        """Convert file:// URL to filesystem path."""
        # Remove file:// prefix
        if location.startswith("file://"):
            location = location[7:]

        # URL decode
        location = unquote(location)

        return Path(location)
