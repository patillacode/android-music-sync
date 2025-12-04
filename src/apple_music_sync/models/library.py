"""Data models for Apple Music library entities."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Track(BaseModel):
    """Represents a music track."""

    track_id: str
    name: str
    artist: str = "Unknown Artist"
    album: str = "Unknown Album"
    location: Path
    size: int  # bytes
    duration: int = 0  # milliseconds

    class Config:
        frozen = True


class Playlist(BaseModel):
    """Represents a playlist."""

    name: str
    track_ids: list[str] = Field(default_factory=list)
    is_distinguished: bool = False  # Apple system playlist

    @property
    def track_count(self) -> int:
        """Number of tracks in playlist."""
        return len(self.track_ids)


class Library(BaseModel):
    """Represents the entire Apple Music library."""

    tracks: dict[str, Track] = Field(default_factory=dict)
    playlists: list[Playlist] = Field(default_factory=list)

    @property
    def track_count(self) -> int:
        """Total number of tracks."""
        return len(self.tracks)

    @property
    def playlist_count(self) -> int:
        """Total number of playlists."""
        return len(self.playlists)

    @property
    def total_size(self) -> int:
        """Total size of all tracks in bytes."""
        return sum(track.size for track in self.tracks.values())
