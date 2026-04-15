"""Timecode utilities for frame/TC conversion."""

from __future__ import annotations

from typing import Any


def get_timeline_fps(timeline: Any) -> float:
    """Get the timeline frame rate as a float."""
    fps_str = timeline.GetSetting("timelineFrameRate")
    if not fps_str:
        return 24.0
    return float(fps_str)


def get_timeline_start_frame(timeline: Any) -> int:
    """Get the timeline start frame."""
    return int(timeline.GetStartFrame())


def frame_to_timecode(frame: int, fps: float, start_frame: int = 0) -> str:
    """Convert an absolute frame number to HH:MM:SS:FF timecode."""
    relative = frame - start_frame
    if relative < 0:
        relative = 0

    total_seconds = relative / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    frames = int(relative % fps)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def timecode_to_frame(tc: str, fps: float, start_frame: int = 0) -> int:
    """Convert HH:MM:SS:FF timecode to an absolute frame number."""
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode format: {tc}")

    hours, minutes, seconds, frames = (int(p) for p in parts)
    total_frames = int((hours * 3600 + minutes * 60 + seconds) * fps + frames)
    return total_frames + start_frame
