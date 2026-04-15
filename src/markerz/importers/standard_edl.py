"""Import standard CMX3600 EDL files as Resolve timeline markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Standard EDL event line pattern (flexible spacing)
_EVENT_RE = re.compile(
    r"^(\d{3})\s+\S+\s+\w+\s+\w+\s+"
    r"(\d{2}:\d{2}:\d{2}:\d{2})\s+"
    r"(\d{2}:\d{2}:\d{2}:\d{2})\s+"
    r"(\d{2}:\d{2}:\d{2}:\d{2})\s+"
    r"(\d{2}:\d{2}:\d{2}:\d{2})"
)


@dataclass
class EDLMarker:
    """A parsed marker from a standard EDL."""

    timecode: str  # Record In
    source_in: str
    source_out: str
    record_out: str
    clip_name: str
    color: str = "Blue"


def parse_standard_edl(filepath: str | Path) -> list[EDLMarker]:
    """Parse a standard CMX3600 EDL and return markers at each edit point.

    Uses Record In timecode for marker placement, clip name from
    '* FROM CLIP NAME:' lines.
    """
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    markers: list[EDLMarker] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        match = _EVENT_RE.match(line)
        if not match:
            i += 1
            continue

        source_in = match.group(2)
        source_out = match.group(3)
        record_in = match.group(4)
        record_out = match.group(5)

        # Look for clip name on following lines
        clip_name = ""
        j = i + 1
        while j < len(lines) and j <= i + 5:
            next_line = lines[j].strip()
            if next_line.startswith("* FROM CLIP NAME:"):
                clip_name = next_line.split(":", 1)[1].strip()
                break
            if next_line.startswith("*"):
                # Other comment/metadata line, keep looking
                j += 1
                continue
            if _EVENT_RE.match(next_line):
                break
            j += 1

        markers.append(
            EDLMarker(
                timecode=record_in,
                source_in=source_in,
                source_out=source_out,
                record_out=record_out,
                clip_name=clip_name,
            )
        )

        i += 1

    return markers
