"""Configuration models for export profiles and app settings."""

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ExportProfile(BaseModel):
    """Export profile configuration."""

    # Metadata
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    created: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None

    # Paths
    library_path: Path = Path("~/Music/Music/Library.xml")
    output_dir: Path = Path("./output")

    # Export options
    dry_run: bool = False

    # Playlist filtering
    playlist_mode: Literal["all", "include", "exclude"] = "all"
    playlist_patterns: list[str] = Field(default_factory=list)

    # Filters
    min_track_count: int = 0
    exclude_distinguished: bool = True

    @field_validator("library_path", "output_dir")
    @classmethod
    def expand_paths(cls, v: Path) -> Path:
        """Expand user paths like ~/"""
        return v.expanduser().resolve()

    def to_dict(self) -> dict:
        """Convert to dictionary for TOML serialization."""
        data = self.model_dump()
        # Convert Path objects to strings for TOML
        data["library_path"] = str(self.library_path)
        data["output_dir"] = str(self.output_dir)
        # Convert datetime to ISO string
        data["created"] = self.created.isoformat()
        if self.last_used:
            data["last_used"] = self.last_used.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ExportProfile":
        """Create from dictionary loaded from TOML."""
        # Convert string paths back to Path objects
        if "library_path" in data:
            data["library_path"] = Path(data["library_path"])
        if "output_dir" in data:
            data["output_dir"] = Path(data["output_dir"])
        # Convert ISO strings back to datetime
        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        if "last_used" in data and isinstance(data["last_used"], str):
            data["last_used"] = datetime.fromisoformat(data["last_used"])
        return cls(**data)


class AppConfig(BaseModel):
    """Application-level configuration."""

    version: str = "2.0.0"
    last_profile: Optional[str] = None
    auto_detect_library: bool = True

    # UI settings
    theme: Literal["dark", "light", "auto"] = "dark"
    show_warnings: bool = True
    confirm_large_exports: bool = True
    large_export_threshold_gb: int = 10

    # Paths
    default_library: Path = Path("~/Music/Music/Library.xml")
    default_output: Path = Path("./output")
    library_age_warning_days: int = 7

    @field_validator("default_library", "default_output")
    @classmethod
    def expand_paths(cls, v: Path) -> Path:
        """Expand user paths."""
        return v.expanduser().resolve()
