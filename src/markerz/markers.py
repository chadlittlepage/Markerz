"""Marker management for DaVinci Resolve timelines and clips."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_COLORS = [
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
]


@dataclass
class Marker:
    """Represents a single Resolve marker."""

    frame: int
    color: str
    name: str
    note: str
    duration: int
    custom_data: str = ""
    source: str = "timeline"  # "timeline" or "clip"
    clip_name: str = ""

    @property
    def timecode(self) -> str:
        """Placeholder for timecode conversion (requires timeline FPS)."""
        return str(self.frame)


@dataclass
class MarkerSet:
    """Collection of markers from a timeline or clip."""

    markers: list[Marker] = field(default_factory=list)

    def filter_by_color(self, color: str) -> list[Marker]:
        return [m for m in self.markers if m.color == color]

    def filter_by_name(self, query: str) -> list[Marker]:
        q = query.lower()
        return [m for m in self.markers if q in m.name.lower() or q in m.note.lower()]

    @property
    def colors_used(self) -> set[str]:
        return {m.color for m in self.markers}


def get_timeline_markers(timeline: Any) -> MarkerSet:
    """Read all markers from the timeline."""
    raw = timeline.GetMarkers() or {}
    markers = []
    for frame, data in raw.items():
        markers.append(
            Marker(
                frame=int(frame),
                color=data.get("color", "Blue"),
                name=data.get("name", ""),
                note=data.get("note", ""),
                duration=data.get("duration", 1),
                custom_data=data.get("customData", ""),
                source="timeline",
            )
        )
    return MarkerSet(markers=sorted(markers, key=lambda m: m.frame))


def get_clip_markers(clip: Any) -> MarkerSet:
    """Read all markers from a single clip."""
    raw = clip.GetMarkers() or {}
    clip_name = clip.GetName() or "Unknown"
    markers = []
    for frame, data in raw.items():
        markers.append(
            Marker(
                frame=int(frame),
                color=data.get("color", "Blue"),
                name=data.get("name", ""),
                note=data.get("note", ""),
                duration=data.get("duration", 1),
                custom_data=data.get("customData", ""),
                source="clip",
                clip_name=clip_name,
            )
        )
    return MarkerSet(markers=sorted(markers, key=lambda m: m.frame))


def get_all_markers(timeline: Any, track: int = 1) -> MarkerSet:
    """Get all markers from timeline and all clips on a track."""
    all_markers: list[Marker] = []

    # Timeline markers
    tl_set = get_timeline_markers(timeline)
    all_markers.extend(tl_set.markers)

    # Clip markers
    items = timeline.GetItemListInTrack("video", track)
    if items:
        for clip in items:
            clip_set = get_clip_markers(clip)
            all_markers.extend(clip_set.markers)

    return MarkerSet(markers=sorted(all_markers, key=lambda m: m.frame))


def add_timeline_marker(
    timeline: Any,
    frame: int,
    color: str = "Blue",
    name: str = "",
    note: str = "",
    duration: int = 1,
    custom_data: str = "",
) -> bool:
    """Add a marker to the timeline at the given frame."""
    return bool(timeline.AddMarker(frame, color, name, note, duration, custom_data))


def add_clip_marker(
    clip: Any,
    frame: int,
    color: str = "Blue",
    name: str = "",
    note: str = "",
    duration: int = 1,
    custom_data: str = "",
) -> bool:
    """Add a marker to a clip at the given frame offset."""
    return bool(clip.AddMarker(frame, color, name, note, duration, custom_data))


def delete_timeline_marker(timeline: Any, frame: int) -> bool:
    """Delete a timeline marker at the given frame."""
    return bool(timeline.DeleteMarkerAtFrame(frame))


def delete_clip_marker(clip: Any, frame: int) -> bool:
    """Delete a clip marker at the given frame offset."""
    return bool(clip.DeleteMarkerAtFrame(frame))


def delete_markers_by_color(timeline: Any, color: str) -> bool:
    """Delete all timeline markers of a given color."""
    return bool(timeline.DeleteMarkersByColor(color))


def export_markers_csv(marker_set: MarkerSet) -> str:
    """Export markers to CSV format."""
    lines = ["frame,color,name,note,duration,source,clip_name"]
    for m in marker_set.markers:
        name = m.name.replace('"', '""')
        note = m.note.replace('"', '""')
        clip = m.clip_name.replace('"', '""')
        lines.append(f'{m.frame},"{m.color}","{name}","{note}",{m.duration},"{m.source}","{clip}"')
    return "\n".join(lines)
