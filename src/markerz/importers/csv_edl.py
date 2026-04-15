"""Import CSV EDL/cut list exports as Resolve timeline markers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CSVMarker:
    """A parsed marker from a CSV EDL export."""

    timecode: str
    name: str
    note: str
    color: str
    duration_tc: str


def parse_csv_edl(filepath: str | Path) -> list[CSVMarker]:
    """Parse a CSV EDL/cut list and return markers at each edit point.

    Supports columns: Event, Reel, Track, Transition, Source In, Source Out,
    Record In, Record Out, Clip Name.

    Creates a marker at each Record In timecode with the Clip Name.
    """
    path = Path(filepath)
    text = path.read_text(encoding="utf-8", errors="replace")
    reader = csv.DictReader(text.splitlines())

    markers: list[CSVMarker] = []
    seen_tc: set[str] = set()

    for row in reader:
        # Try common column names for timecode
        tc = (
            row.get("Record In")
            or row.get("record_in")
            or row.get("Timecode")
            or row.get("timecode")
            or row.get("TC")
            or row.get("In")
            or ""
        ).strip()

        if not tc or tc in seen_tc:
            continue
        seen_tc.add(tc)

        # Clip name or marker name
        name = (
            row.get("Clip Name")
            or row.get("clip_name")
            or row.get("Name")
            or row.get("name")
            or row.get("Marker Name")
            or ""
        ).strip()

        # Note/comment
        note = (
            row.get("Note")
            or row.get("note")
            or row.get("Notes")
            or row.get("Comment")
            or row.get("comment")
            or ""
        ).strip()

        # Color
        color = (row.get("Color") or row.get("color") or row.get("Marker Color") or "Blue").strip()
        if color not in {
            "Blue",
            "Cyan",
            "Green",
            "Yellow",
            "Red",
            "Pink",
            "Purple",
            "Fuchsia",
            "Rose",
            "Lavender",
            "Sky",
            "Mint",
            "Lemon",
            "Sand",
            "Cocoa",
            "Cream",
        }:
            color = "Blue"

        # Duration
        duration_tc = (row.get("Duration") or row.get("duration") or "").strip()
        if not duration_tc:
            # Calculate from Record In / Record Out if available
            record_out = (
                row.get("Record Out") or row.get("record_out") or row.get("Out") or ""
            ).strip()
            if record_out:
                duration_tc = record_out
            else:
                duration_tc = ""

        markers.append(
            CSVMarker(
                timecode=tc,
                name=name,
                note=note,
                color=color,
                duration_tc=duration_tc,
            )
        )

    return markers
