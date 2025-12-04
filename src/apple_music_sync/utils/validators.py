"""Utility functions for validation (disk space, paths, etc.)."""

import os
from pathlib import Path


def get_disk_space(path: Path) -> tuple[int, int]:
    """
    Get available and total disk space in bytes.

    Returns:
        Tuple of (available_bytes, total_bytes)
    """
    if not path.exists():
        path = path.parent

    stat = os.statvfs(path)
    available = stat.f_bavail * stat.f_frsize
    total = stat.f_blocks * stat.f_frsize
    return available, total


def has_sufficient_space(required_bytes: int, output_path: Path) -> bool:
    """Check if there's sufficient disk space for export."""
    available, _ = get_disk_space(output_path)
    return available >= required_bytes


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitize string for use as filename/directory name.

    Removes invalid characters and limits length.
    """
    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")

    # Remove leading/trailing dots and spaces
    name = name.strip(". ")

    # Limit length
    if len(name) > max_length:
        name = name[:max_length]

    return name or "Unknown"
