"""CLI entry point using Typer."""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from .config.defaults import DEFAULT_PROFILE
from .config.manager import ConfigManager
from .core.exporter import MusicExporter
from .models.config import ExportProfile
from .utils.discovery import auto_detect_library

app = typer.Typer(
    name="apple-music-sync",
    help="Export Apple Music library to Android with beautiful TUI",
    add_completion=False,
)

console = Console()


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging based on verbosity flags."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, markup=True, console=console)],
    )


@app.command()
def main(
    # TUI control
    tui: bool = typer.Option(
        True,
        "--tui/--no-tui",
        help="Launch interactive TUI (default: auto-detect)",
    ),
    # Profile management
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use saved profile",
    ),
    list_profiles: bool = typer.Option(
        False,
        "--list-profiles",
        help="List all saved profiles",
    ),
    # Legacy/CLI flags
    library: Optional[Path] = typer.Option(
        None,
        "--library",
        help="Path to Library.xml",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output directory",
    ),
    playlists: Optional[str] = typer.Option(
        None,
        "--playlists",
        help="Comma-separated playlist names/patterns",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview without copying files",
    ),
    list_playlists: bool = typer.Option(
        False,
        "--list-playlists",
        help="List all available playlists",
    ),
    # Output control
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Detailed output",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output",
    ),
):
    """Apple Music → Android sync tool."""
    setup_logging(verbose, quiet)

    config_manager = ConfigManager()

    # Handle list operations (quick exit)
    if list_profiles:
        _list_profiles(config_manager)
        return

    if list_playlists:
        _list_playlists(library)
        return

    # Determine mode: TUI vs CLI
    legacy_flags_used = any([library, output, playlists, dry_run])

    if not tui or legacy_flags_used:
        # CLI mode (non-interactive)
        _run_cli_mode(
            config_manager=config_manager,
            profile_name=profile,
            library=library,
            output=output,
            playlists=playlists,
            dry_run=dry_run,
            verbose=verbose,
        )
    else:
        # TUI mode (interactive)
        from .ui.app import AppleMusicSyncApp
        app_instance = AppleMusicSyncApp()
        app_instance.run()


def _list_profiles(config_manager: ConfigManager) -> None:
    """List all available profiles."""
    profiles = config_manager.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles found.[/yellow]")
        console.print("\nCreate a profile with: apple-music-sync --save-profile <name>")
        return

    console.print(f"\n[bold]Available Profiles ({len(profiles)}):[/bold]\n")

    for name in profiles:
        try:
            prof = config_manager.load_profile(name)
            console.print(f"  • [cyan]{name}[/cyan]")
            if prof.description:
                console.print(f"    {prof.description}")
        except Exception:
            console.print(f"  • [red]{name}[/red] (corrupted)")

    console.print()


def _list_playlists(library_path: Optional[Path]) -> None:
    """List all playlists in the library."""
    from .core.library import LibraryParser

    # Auto-detect library if not specified
    if not library_path:
        detected = auto_detect_library()
        if detected:
            library_path, age_days = detected
            if age_days > 7:
                console.print(
                    f"[yellow]⚠️  Library.xml is {age_days} days old.[/yellow]"
                )
        else:
            console.print("[red]❌ Library.xml not found.[/red]")
            console.print("\nSpecify path with: --library /path/to/Library.xml")
            sys.exit(1)

    try:
        parser = LibraryParser(library_path)
        library = parser.parse()

        # Filter out distinguished playlists
        user_playlists = [p for p in library.playlists if not p.is_distinguished]

        console.print(f"\n[bold]Available Playlists ({len(user_playlists)}):[/bold]\n")

        for idx, playlist in enumerate(
            sorted(user_playlists, key=lambda p: p.name.lower()), 1
        ):
            console.print(
                f"  {idx:3}. [cyan]{playlist.name}[/cyan] ({playlist.track_count} tracks)"
            )

        console.print(f"\n{'=' * 60}")
        console.print("\nUsage examples:")
        console.print(
            f'  apple-music-sync --playlists "{user_playlists[0].name if user_playlists else "Example"}"'
        )
        console.print('  apple-music-sync --playlists "music*"')
        console.print(f"{'=' * 60}\n")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


def _run_cli_mode(
    config_manager: ConfigManager,
    profile_name: Optional[str],
    library: Optional[Path],
    output: Optional[Path],
    playlists: Optional[str],
    dry_run: bool,
    verbose: bool,
) -> None:
    """Run in CLI mode (non-interactive)."""
    # Load or create profile
    if profile_name:
        try:
            export_profile = config_manager.load_profile(profile_name)
            console.print(f"[green]✓[/green] Using profile: {profile_name}")
        except FileNotFoundError:
            console.print(f"[red]❌ Profile not found: {profile_name}[/red]")
            sys.exit(1)
    else:
        # Create profile from CLI args
        export_profile = DEFAULT_PROFILE.model_copy()

    # Override with CLI args
    if library:
        export_profile.library_path = library
    if output:
        export_profile.output_dir = output
    if dry_run:
        export_profile.dry_run = True
    if playlists:
        export_profile.playlist_mode = "include"
        export_profile.playlist_patterns = [p.strip() for p in playlists.split(",")]

    # Auto-detect library if not specified
    if not export_profile.library_path.exists():
        detected = auto_detect_library()
        if detected:
            lib_path, age_days = detected
            export_profile.library_path = lib_path

            if age_days > 7:
                console.print(
                    f"[yellow]⚠️  Library.xml is {age_days} days old. "
                    f"Consider re-exporting from Apple Music.[/yellow]\n"
                )
        else:
            console.print(
                "[red]❌ Library.xml not found.[/red]\n\n"
                "[bold]Setup Required:[/bold]\n"
                "1. Open Apple Music app\n"
                "2. Menu: File → Library → Export Library...\n"
                "3. Save as 'Library.xml' in current directory\n"
            )
            sys.exit(1)

    # Show what will be exported
    console.print(f"\n[bold]Export Configuration:[/bold]")
    console.print(f"  Library: {export_profile.library_path}")
    console.print(f"  Output: {export_profile.output_dir}")
    console.print(f"  Mode: {export_profile.playlist_mode}")
    if export_profile.playlist_patterns:
        console.print(f"  Patterns: {', '.join(export_profile.playlist_patterns)}")
    if dry_run:
        console.print("  [yellow]DRY RUN - No files will be copied[/yellow]")
    console.print()

    # Run export
    try:
        exporter = MusicExporter(export_profile)
        stats = exporter.export()

        # Print summary
        exporter.print_summary()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    app()
