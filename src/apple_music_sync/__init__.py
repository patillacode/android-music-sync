"""Apple Music to Android Sync - Export your music library with a beautiful TUI."""

__version__ = "2.0.0"
__author__ = "Dvitto"

from .core.exporter import MusicExporter
from .models.config import ExportProfile

__all__ = ["MusicExporter", "ExportProfile", "__version__"]
