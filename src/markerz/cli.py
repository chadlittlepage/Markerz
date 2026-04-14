"""CLI interface for Markerz."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from markerz import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Markerz - DaVinci Resolve marker management."""


@cli.command()
@click.option("--track", "-t", default=1, help="Video track number.")
@click.option("--color", "-c", default=None, help="Filter by marker color.")
@click.option("--search", "-s", default=None, help="Search marker names/notes.")
def list(track: int, color: str | None, search: str | None) -> None:
    """List all markers on the current timeline."""
    from markerz.markers import get_all_markers
    from markerz.resolve_connection import connect

    ctx = connect()
    marker_set = get_all_markers(ctx.timeline, track)

    if color:
        markers = marker_set.filter_by_color(color)
    elif search:
        markers = marker_set.filter_by_name(search)
    else:
        markers = marker_set.markers

    if not markers:
        console.print("[dim]No markers found.[/dim]")
        return

    table = Table(title=f"Markers ({len(markers)})")
    table.add_column("Frame", style="cyan", justify="right")
    table.add_column("Color", style="bold")
    table.add_column("Name")
    table.add_column("Note")
    table.add_column("Duration", justify="right")
    table.add_column("Source", style="dim")

    for m in markers:
        source = m.clip_name if m.source == "clip" else "timeline"
        table.add_row(str(m.frame), m.color, m.name, m.note, str(m.duration), source)

    console.print(table)


@cli.command()
@click.argument("frame", type=int)
@click.option("--color", "-c", default="Blue", help="Marker color.")
@click.option("--name", "-n", default="", help="Marker name.")
@click.option("--note", default="", help="Marker note.")
@click.option("--duration", "-d", default=1, help="Marker duration in frames.")
def add(frame: int, color: str, name: str, note: str, duration: int) -> None:
    """Add a marker to the timeline at FRAME."""
    from markerz.markers import add_timeline_marker
    from markerz.resolve_connection import connect

    ctx = connect()
    if add_timeline_marker(ctx.timeline, frame, color, name, note, duration):
        console.print(f"[green]Added {color} marker at frame {frame}[/green]")
    else:
        console.print(f"[red]Failed to add marker at frame {frame}[/red]")


@cli.command()
@click.argument("frame", type=int)
def delete(frame: int) -> None:
    """Delete a timeline marker at FRAME."""
    from markerz.markers import delete_timeline_marker
    from markerz.resolve_connection import connect

    ctx = connect()
    if delete_timeline_marker(ctx.timeline, frame):
        console.print(f"[green]Deleted marker at frame {frame}[/green]")
    else:
        console.print(f"[red]No marker found at frame {frame}[/red]")


@cli.command()
@click.option("--color", "-c", required=True, help="Delete all markers of this color.")
def purge(color: str) -> None:
    """Delete all timeline markers of a given color."""
    from markerz.markers import delete_markers_by_color
    from markerz.resolve_connection import connect

    ctx = connect()
    if delete_markers_by_color(ctx.timeline, color):
        console.print(f"[green]Deleted all {color} markers[/green]")
    else:
        console.print(f"[red]No {color} markers found[/red]")


@cli.command()
@click.option("--track", "-t", default=1, help="Video track number.")
@click.option("--output", "-o", default=None, help="Output file path.")
def export(track: int, output: str | None) -> None:
    """Export markers to CSV."""
    from markerz.markers import export_markers_csv, get_all_markers
    from markerz.resolve_connection import connect

    ctx = connect()
    marker_set = get_all_markers(ctx.timeline, track)
    csv_data = export_markers_csv(marker_set)

    if output:
        with open(output, "w") as f:
            f.write(csv_data)
        console.print(f"[green]Exported {len(marker_set.markers)} markers to {output}[/green]")
    else:
        console.print(csv_data)


@cli.command()
def status() -> None:
    """Check Resolve connection and show timeline info."""
    from markerz.markers import get_timeline_markers
    from markerz.resolve_connection import connect

    ctx = connect()
    tl_markers = get_timeline_markers(ctx.timeline)

    console.print("[green]Connected to Resolve[/green]")
    console.print(f"  Project:  {ctx.project.GetName()}")
    console.print(f"  Timeline: {ctx.timeline.GetName()}")
    console.print(f"  Timeline markers: {len(tl_markers.markers)}")
    if tl_markers.colors_used:
        console.print(f"  Colors: {', '.join(sorted(tl_markers.colors_used))}")
