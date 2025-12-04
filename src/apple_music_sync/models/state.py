"""Export state models for incremental sync tracking."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class FileSignature(BaseModel):
    """Signature for detecting file changes."""

    path: str
    size: int
    mtime: float

    def is_changed(self, current_path: Path) -> bool:
        """Check if file has changed since last export."""
        if not current_path.exists():
            return True
        stat = current_path.stat()
        return stat.st_size != self.size or stat.st_mtime != self.mtime


class PlaylistSignature(BaseModel):
    """Signature for detecting playlist changes."""

    name: str
    track_ids_hash: str  # MD5 hash of track ID list
    track_count: int


class ExportState(BaseModel):
    """Persistent export state for incremental sync."""

    version: str = "2.0.0"
    last_export: Optional[datetime] = None
    library_path: Path
    output_dir: Path

    exported_files: dict[str, FileSignature] = Field(default_factory=dict)
    exported_playlists: dict[str, PlaylistSignature] = Field(default_factory=dict)

    # Statistics
    total_exports: int = 0
    total_bytes_exported: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = self.model_dump()
        data["library_path"] = str(self.library_path)
        data["output_dir"] = str(self.output_dir)
        if self.last_export:
            data["last_export"] = self.last_export.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ExportState":
        """Create from dictionary loaded from JSON."""
        if "library_path" in data:
            data["library_path"] = Path(data["library_path"])
        if "output_dir" in data:
            data["output_dir"] = Path(data["output_dir"])
        if "last_export" in data and isinstance(data["last_export"], str):
            data["last_export"] = datetime.fromisoformat(data["last_export"])
        return cls(**data)
