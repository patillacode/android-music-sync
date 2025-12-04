"""Utility functions for auto-discovering Library.xml."""

from datetime import datetime
from pathlib import Path


def auto_detect_library() -> tuple[Path, int] | None:
    """
    Auto-detect Library.xml in common locations.

    Returns:
        Tuple of (path, age_in_days) or None if not found
    """
    search_paths = [
        Path.cwd() / "Library.xml",
        Path.home() / "Music" / "Music" / "Library.xml",
        Path.home() / "Music" / "iTunes" / "iTunes Music Library.xml",
    ]

    for path in search_paths:
        if path.exists():
            age_days = _get_file_age_days(path)
            return path, age_days

    return None


def _get_file_age_days(path: Path) -> int:
    """Get age of file in days."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    age = datetime.now() - mtime
    return age.days
