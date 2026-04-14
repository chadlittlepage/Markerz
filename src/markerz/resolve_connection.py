"""DaVinci Resolve API connection and wrapper."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

_MODULE_PATHS = [
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
    os.path.expanduser(
        "~/Library/Application Support/Blackmagic Design/"
        "DaVinci Resolve/Developer/Scripting/Modules"
    ),
    "/opt/resolve/Developer/Scripting/Modules",
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve"
    r"\Support\Developer\Scripting\Modules",
]


@dataclass
class ResolveContext:
    """Holds references to the active Resolve session objects."""

    resolve: Any
    project_manager: Any
    project: Any
    timeline: Any


def get_resolve() -> Any | None:
    """Get the DaVinci Resolve application object."""
    for path in _MODULE_PATHS:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

    try:
        import DaVinciResolveScript as DvrScript  # noqa: N813

        return DvrScript.scriptapp("Resolve")
    except (ImportError, AttributeError):
        return None


def connect() -> ResolveContext:
    """Connect to Resolve and return a context with all session objects."""
    resolve = get_resolve()
    if not resolve:
        raise SystemExit(
            "Could not connect to DaVinci Resolve.\n"
            "Make sure Resolve is running with scripting enabled "
            "(Preferences > System > General > External scripting using)."
        )

    pm = resolve.GetProjectManager()
    if not pm:
        raise SystemExit("Connected to Resolve but could not access the Project Manager.")

    project = pm.GetCurrentProject()
    if not project:
        raise SystemExit("No project is currently open in Resolve.")

    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise SystemExit("No timeline is currently active. Open a timeline and try again.")

    return ResolveContext(
        resolve=resolve,
        project_manager=pm,
        project=project,
        timeline=timeline,
    )


def get_timeline_clips(timeline: Any, track: int = 1) -> list[Any]:
    """Get all clips from a video track, sorted by start frame."""
    track_count = timeline.GetTrackCount("video")
    if track > track_count:
        raise SystemExit(
            f"Video track {track} does not exist. Timeline has {track_count} video track(s)."
        )

    items = timeline.GetItemListInTrack("video", track)
    if not items:
        return []

    return sorted(items, key=lambda c: c.GetStart())
