"""Import Frame.io EDL marker exports into Resolve timeline markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Frame.io uses ResolveColor prefixed names in the |C: tag
FRAMEIO_COLOR_MAP: dict[str, str] = {
    "ResolveColorBlue": "Blue",
    "ResolveColorCyan": "Cyan",
    "ResolveColorGreen": "Green",
    "ResolveColorYellow": "Yellow",
    "ResolveColorRed": "Red",
    "ResolveColorPink": "Pink",
    "ResolveColorPurple": "Purple",
    "ResolveColorFuchsia": "Fuchsia",
    "ResolveColorRose": "Rose",
    "ResolveColorLavender": "Lavender",
    "ResolveColorSky": "Sky",
    "ResolveColorMint": "Mint",
    "ResolveColorLemon": "Lemon",
    "ResolveColorSand": "Sand",
    "ResolveColorCocoa": "Cocoa",
    "ResolveColorCream": "Cream",
}

# Regex for EDL event line: 001  001  C  V  HH:MM:SS:FF ...
_EVENT_RE = re.compile(
    r"^\d{3}\s+\d{3}\s+\w+\s+\w+\s+"
    r"(\d{2}:\d{2}:\d{2}:\d{2})\s+"
)

# Regex for metadata tags in the comment line
_COLOR_RE = re.compile(r"\|C:(\S+)")
_AUTHOR_RE = re.compile(r"\|M:(.+?)(?:\s*\||\s*$)")
_DURATION_RE = re.compile(r"\|D:(\d+)")


@dataclass
class FrameIOMarker:
    """A parsed marker from a Frame.io EDL export."""

    timecode: str
    author: str
    comment: str
    color: str
    duration: int


def parse_frameio_edl(filepath: str | Path) -> list[FrameIOMarker]:
    """Parse a Frame.io EDL file and return a list of markers.

    Frame.io EDL format:
        001  001  C  V  00:00:02:04  00:00:02:04  00:00:02:04  00:00:02:04
        @Author Name, Date
         Comment text |C:ResolveColorPurple |M:Author Name |D:0
    """
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    markers: list[FrameIOMarker] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for EDL event line
        match = _EVENT_RE.match(line)
        if not match:
            i += 1
            continue

        timecode = match.group(1)

        # Next line(s) contain author and comment
        author = ""
        comment_parts: list[str] = []
        i += 1

        # Author line starts with @
        if i < len(lines) and lines[i].strip().startswith("@"):
            author_line = lines[i].strip()
            # Extract author name (before the comma/date)
            author_match = re.match(r"@(.+?),\s*", author_line)
            if author_match:
                author = author_match.group(1).strip()
            i += 1

        # Comment lines follow until next event or blank
        while i < len(lines):
            cline = lines[i]
            # Stop at next event or empty line
            if not cline.strip() or _EVENT_RE.match(cline.strip()):
                break
            comment_parts.append(cline)
            i += 1

        full_comment = " ".join(comment_parts).strip()

        # Extract metadata from comment
        color = "Blue"  # default
        color_match = _COLOR_RE.search(full_comment)
        if color_match:
            raw_color = color_match.group(1)
            color = FRAMEIO_COLOR_MAP.get(raw_color, "Blue")

        author_from_meta = ""
        meta_author = _AUTHOR_RE.search(full_comment)
        if meta_author:
            author_from_meta = meta_author.group(1).strip()
        if author_from_meta:
            author = author_from_meta

        duration = 1
        dur_match = _DURATION_RE.search(full_comment)
        if dur_match:
            duration = max(1, int(dur_match.group(1)))

        # Strip metadata tags from comment for clean display
        clean_comment = _COLOR_RE.sub("", full_comment)
        clean_comment = _AUTHOR_RE.sub("", clean_comment)
        clean_comment = _DURATION_RE.sub("", clean_comment)
        clean_comment = re.sub(r"\s*\|\s*", " ", clean_comment).strip()

        markers.append(
            FrameIOMarker(
                timecode=timecode,
                author=author,
                comment=clean_comment,
                color=color,
                duration=duration,
            )
        )

    return markers
