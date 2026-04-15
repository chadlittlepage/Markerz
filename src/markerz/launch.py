"""Launch Markerz as an external pywebview window connected to Resolve."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import webview  # pywebview

from markerz import __version__
from markerz.timecode import (
    frame_to_timecode,
    get_timeline_fps,
    get_timeline_start_frame,
    timecode_to_frame,
)

# Add Resolve scripting modules
_MOD_PATH = (
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
)
if os.path.isdir(_MOD_PATH) and _MOD_PATH not in sys.path:
    sys.path.insert(0, _MOD_PATH)

import DaVinciResolveScript as dvr  # noqa: E402, N813

# ---------------------------------------------------------------------------
# Settings / Presets
# ---------------------------------------------------------------------------

_SETTINGS_DIR = Path.home() / ".markerz"
_SETTINGS_PATH = _SETTINGS_DIR / "settings.json"
_PRESETS_DIR = _SETTINGS_DIR / "presets"


def _load_settings() -> dict[str, Any]:
    try:
        return json.loads(_SETTINGS_PATH.read_text()) if _SETTINGS_PATH.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings(settings: dict[str, Any]) -> None:
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(settings, indent=2))


# ---------------------------------------------------------------------------
# Marker helpers
# ---------------------------------------------------------------------------

COLOR_HEX = {
    "Blue": "#3B82F6",
    "Cyan": "#06B6D4",
    "Green": "#22C55E",
    "Yellow": "#EAB308",
    "Red": "#EF4444",
    "Pink": "#EC4899",
    "Purple": "#A855F7",
    "Fuchsia": "#D946EF",
    "Rose": "#F43F5E",
    "Lavender": "#A78BFA",
    "Sky": "#38BDF8",
    "Mint": "#34D399",
    "Lemon": "#FDE047",
    "Sand": "#D4A574",
    "Cocoa": "#8B6914",
    "Cream": "#FEF3C7",
}


def _marker_snapshot(raw: dict[int, dict[str, Any]]) -> dict[int, tuple[str, str, str, int]]:
    return {
        int(f): (d.get("color", ""), d.get("name", ""), d.get("note", ""), d.get("duration", 1))
        for f, d in raw.items()
    }


# ---------------------------------------------------------------------------
# JS API
# ---------------------------------------------------------------------------


class MarkerzAPI:
    """Exposed to JavaScript via pywebview bridge."""

    _MAX_UNDO = 100

    def __init__(self, resolve: Any, timeline: Any, fps: float, start_frame: int) -> None:
        self.resolve = resolve
        self.pm = resolve.GetProjectManager()
        self.timeline = timeline
        self.fps = fps
        self.start_frame = start_frame
        self._settings = _load_settings()
        self._undo_stack: list[dict[int, dict[str, Any]]] = []
        self._snapshot: dict[int, tuple[str, str, str, int]] = {}
        self._timeline_name = timeline.GetName() if timeline else ""
        self._last_playhead_frame: int = -1
        self._window: webview.Window | None = None
        self._polling = threading.Event()
        self._lock = threading.Lock()

    # --- Markers ---

    def get_markers(self) -> list[dict[str, Any]]:
        raw = self.timeline.GetMarkers() or {}
        self._snapshot = _marker_snapshot(raw)
        markers = []
        for frame, data in raw.items():
            frame_int = int(frame)
            absolute = frame_int + self.start_frame
            markers.append(
                {
                    "frame": frame_int,
                    "tc": frame_to_timecode(absolute, self.fps, 0),
                    "color": data.get("color", "Blue"),
                    "name": data.get("name", ""),
                    "note": data.get("note", ""),
                    "duration": data.get("duration", 1),
                    "duration_tc": frame_to_timecode(data.get("duration", 1), self.fps, 0),
                }
            )
        return sorted(markers, key=lambda m: m["frame"])

    def get_timeline_info(self) -> dict[str, Any]:
        return {
            "name": self._timeline_name,
            "fps": self.fps,
            "start_frame": self.start_frame,
            "version": __version__,
        }

    # --- Playhead ---

    def get_playhead_tc(self) -> str:
        try:
            return str(self.timeline.GetCurrentTimecode())
        except Exception:
            return "00:00:00:00"

    def set_playhead(self, tc: str) -> None:
        try:
            self.timeline.SetCurrentTimecode(tc)
        except Exception:
            pass

    # --- Mutations ---

    def add_marker(self, tc: str, color: str, name: str, note: str, dur_tc: str) -> str:
        self._save_undo()
        try:
            frame = timecode_to_frame(tc, self.fps, 0) - self.start_frame
        except ValueError:
            return "Invalid timecode"
        try:
            dur = max(1, timecode_to_frame(dur_tc, self.fps, 0))
        except ValueError:
            dur = 1
        if self.timeline.AddMarker(frame, color, name, note, dur, ""):
            return f"Added {color} marker"
        return "Failed (frame may already have a marker)"

    def edit_marker(
        self, old_frame: int, tc: str, color: str, name: str, note: str, dur_tc: str
    ) -> str:
        self._save_undo()
        try:
            new_frame = timecode_to_frame(tc, self.fps, 0) - self.start_frame
        except ValueError:
            return "Invalid timecode"
        try:
            dur = max(1, timecode_to_frame(dur_tc, self.fps, 0))
        except ValueError:
            dur = 1

        if not self.timeline.DeleteMarkerAtFrame(int(old_frame)):
            return "Failed to delete old marker"

        if self.timeline.AddMarker(new_frame, color, name, note, dur, ""):
            new_tc = frame_to_timecode(new_frame + self.start_frame, self.fps, 0)
            return f"Updated marker at {new_tc}"

        # Restore original on failure
        raw = self._undo_stack[-1] if self._undo_stack else {}
        orig = raw.get(int(old_frame), {})
        if orig:
            self.timeline.AddMarker(
                int(old_frame),
                orig.get("color", "Blue"),
                orig.get("name", ""),
                orig.get("note", ""),
                orig.get("duration", 1),
                "",
            )
        return "Failed to update (restored original)"

    def delete_markers(self, frames: list[int]) -> int:
        self._save_undo()
        deleted = 0
        for f in frames:
            if self.timeline.DeleteMarkerAtFrame(int(f)):
                deleted += 1
        return deleted

    def undo(self) -> str:
        if not self._undo_stack:
            return "Nothing to undo"
        snapshot = self._undo_stack.pop()
        current = self.timeline.GetMarkers() or {}
        for frame in list(current.keys()):
            self.timeline.DeleteMarkerAtFrame(int(frame))
        restored = 0
        for frame, data in snapshot.items():
            if self.timeline.AddMarker(
                int(frame),
                data.get("color", "Blue"),
                data.get("name", ""),
                data.get("note", ""),
                data.get("duration", 1),
                data.get("customData", ""),
            ):
                restored += 1
        return f"Undo: restored {restored} markers"

    def _save_undo(self) -> None:
        raw = self.timeline.GetMarkers() or {}
        self._undo_stack.append(dict(raw))
        if len(self._undo_stack) > self._MAX_UNDO:
            self._undo_stack.pop(0)

    # --- Import ---

    def open_file_dialog(self, title: str, filters: str) -> str | None:
        if not self._window:
            return None
        # Temporarily lower always-on-top so file dialog isn't hidden behind
        self._window.on_top = False
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("EDL files (*.edl)", "CSV files (*.csv)", "All files (*.*)"),
            )
        finally:
            self._window.on_top = True
        if result and len(result) > 0:
            return str(result[0])
        return None

    def import_preview(self, filepath: str) -> dict[str, Any]:
        ext = Path(filepath).suffix.lower()
        tcs: list[str] = []
        colors: list[str] = []

        try:
            if ext == ".csv":
                from markerz.importers.csv_edl import parse_csv_edl

                for m in parse_csv_edl(filepath):
                    tcs.append(m.timecode)
                    colors.append(m.color)
            else:
                content = Path(filepath).read_text(encoding="utf-8", errors="replace")
                is_frameio = "|C:" in content and "|M:" in content
                if is_frameio:
                    from markerz.importers.frameio_edl import parse_frameio_edl

                    for em in parse_frameio_edl(filepath):
                        tcs.append(em.timecode)
                        colors.append(em.color)
                else:
                    from markerz.importers.standard_edl import parse_standard_edl

                    for sm in parse_standard_edl(filepath):
                        tcs.append(sm.timecode)
                        colors.append(sm.color)
        except Exception as e:
            return {"error": str(e)}

        if not tcs:
            return {"error": "No markers found in file"}

        fps_val = self.fps
        fps_str = f"{fps_val:.3f}" if fps_val != int(fps_val) else str(int(fps_val))

        return {
            "filepath": filepath,
            "filename": Path(filepath).name,
            "format": ext.upper().lstrip("."),
            "count": len(tcs),
            "fps": fps_str,
            "first_tc": tcs[0],
            "last_tc": tcs[-1],
            "colors": ", ".join(sorted(set(colors))),
        }

    def commit_import(self, filepath: str, start_tc: str) -> str:
        self._save_undo()
        ext = Path(filepath).suffix.lower()
        tcs: list[str] = []
        names: list[str] = []
        notes: list[str] = []
        colors: list[str] = []
        durations: list[int] = []

        try:
            if ext == ".csv":
                from markerz.importers.csv_edl import parse_csv_edl

                for m in parse_csv_edl(filepath):
                    tcs.append(m.timecode)
                    names.append(m.name)
                    notes.append(m.note)
                    colors.append(m.color)
                    if m.duration_tc:
                        try:
                            d = timecode_to_frame(m.duration_tc, self.fps, 0)
                            t = timecode_to_frame(m.timecode, self.fps, 0)
                            durations.append(max(1, d - t))
                        except ValueError:
                            durations.append(1)
                    else:
                        durations.append(1)
            else:
                content = Path(filepath).read_text(encoding="utf-8", errors="replace")
                is_frameio = "|C:" in content and "|M:" in content
                if is_frameio:
                    from markerz.importers.frameio_edl import parse_frameio_edl

                    for em in parse_frameio_edl(filepath):
                        tcs.append(em.timecode)
                        names.append(em.author)
                        notes.append(em.comment)
                        colors.append(em.color)
                        durations.append(em.duration)
                else:
                    from markerz.importers.standard_edl import parse_standard_edl

                    for sm in parse_standard_edl(filepath):
                        tcs.append(sm.timecode)
                        names.append(sm.clip_name)
                        notes.append("")
                        colors.append(sm.color)
                        try:
                            ri = timecode_to_frame(sm.timecode, self.fps, 0)
                            ro = timecode_to_frame(sm.record_out, self.fps, 0)
                            durations.append(max(1, ro - ri))
                        except ValueError:
                            durations.append(1)
        except Exception as e:
            return f"Import error: {e}"

        if not tcs:
            return "No markers found"

        # TC offset
        try:
            orig = timecode_to_frame(tcs[0], self.fps, 0)
            user = timecode_to_frame(start_tc, self.fps, 0)
            tc_offset = user - orig
        except ValueError:
            tc_offset = 0

        added = 0
        failed = 0
        for i, tc in enumerate(tcs):
            try:
                frame = timecode_to_frame(tc, self.fps, 0) + tc_offset
            except ValueError:
                failed += 1
                continue
            if self.timeline.AddMarker(frame, colors[i], names[i], notes[i], durations[i], ""):
                added += 1
            else:
                failed += 1

        msg = f"Imported {added} markers"
        if failed:
            msg += f" ({failed} failed)"
        return msg

    # --- Settings ---

    def get_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._settings.update(settings)
        _save_settings(self._settings)

    # --- Presets ---

    def get_presets(self) -> list[str]:
        _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(p.stem for p in _PRESETS_DIR.glob("*.json"))

    def save_preset(self, name: str, settings: dict[str, Any]) -> None:
        _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        # Save everything except window geometry
        preset = {k: v for k, v in settings.items() if k not in ("geometry",)}
        (_PRESETS_DIR / f"{name}.json").write_text(json.dumps(preset, indent=2))

    def load_preset(self, name: str) -> dict[str, Any]:
        path = _PRESETS_DIR / f"{name}.json"
        if not path.exists():
            return self._settings
        try:
            preset = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return self._settings
        # Merge preset into settings, preserving geometry
        geo = self._settings.get("geometry")
        self._settings.update(preset)
        if geo:
            self._settings["geometry"] = geo
        _save_settings(self._settings)
        return dict(self._settings)

    def delete_preset(self, name: str) -> None:
        path = _PRESETS_DIR / f"{name}.json"
        if path.exists():
            path.unlink()

    def import_preset(self) -> str | None:
        if not self._window:
            return None
        self._window.on_top = False
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("JSON files (*.json)", "All files (*.*)"),
            )
        finally:
            self._window.on_top = True
        if not result or not result[0]:
            return None
        src = Path(result[0])
        try:
            data = json.loads(src.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        name = src.stem
        _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        (_PRESETS_DIR / f"{name}.json").write_text(json.dumps(data, indent=2))
        return name

    def export_preset(self, name: str) -> None:
        path = _PRESETS_DIR / f"{name}.json"
        if not path.exists() or not self._window:
            return
        self._window.on_top = False
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=f"{name}.json",
                file_types=("JSON files (*.json)",),
            )
        finally:
            self._window.on_top = True
        if result:
            dest = result if isinstance(result, str) else result[0]
            if dest:
                Path(dest).write_text(path.read_text())

    # --- Polling ---

    def _start_polling(self) -> None:
        self._polling.set()
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _stop_polling(self) -> None:
        self._polling.clear()

    def _poll_loop(self) -> None:
        playhead_counter = 0
        while self._polling.is_set() and self._window:
            time.sleep(0.1)  # 100ms poll for snappy playhead tracking
            if not self._polling.is_set():
                break

            # Playhead sync (every 100ms)
            try:
                with self._lock:
                    tc = str(self.timeline.GetCurrentTimecode())
                    frame = timecode_to_frame(tc, self.fps, 0) - self.start_frame
                if frame != self._last_playhead_frame:
                    self._last_playhead_frame = frame
                    self._window.evaluate_js(f'updatePlayhead("{tc}", {frame})')
            except Exception:
                pass

            # Marker data + timeline sync (every 1s = 10 ticks)
            playhead_counter += 1
            if playhead_counter >= 10:
                playhead_counter = 0
                try:
                    proj = self.pm.GetCurrentProject()
                    if not proj:
                        continue
                    tl = proj.GetCurrentTimeline()
                    if not tl:
                        continue

                    tl_name = tl.GetName()
                    with self._lock:
                        if tl_name != self._timeline_name:
                            self.timeline = tl
                            self.fps = get_timeline_fps(tl)
                            self.start_frame = get_timeline_start_frame(tl)
                            self._timeline_name = tl_name
                            self._window.evaluate_js(f'onTimelineChanged("{tl_name}")')
                        else:
                            raw = tl.GetMarkers() or {}
                            snapshot = _marker_snapshot(raw)
                            if snapshot != self._snapshot:
                                self.timeline = tl
                                self._window.evaluate_js("onMarkersChanged()")
                except Exception:
                    pass

    # --- Window events ---

    def _on_loaded(self) -> None:
        self._start_polling()

    def _on_closing(self) -> None:
        self._stop_polling()
        # Save window geometry
        if self._window:
            self._settings["geometry"] = [
                self._window.x,
                self._window.y,
                self._window.width,
                self._window.height,
            ]
            _save_settings(self._settings)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    """Launch the Markerz floating window."""
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        print("ERROR: Cannot connect to DaVinci Resolve.")
        print("Make sure Resolve is running with scripting set to Local.")
        sys.exit(1)

    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    timeline = project.GetCurrentTimeline() if project else None

    if not timeline:
        print("ERROR: No active timeline. Open a timeline in Resolve first.")
        sys.exit(1)

    fps = get_timeline_fps(timeline)
    start_frame = get_timeline_start_frame(timeline)

    project_name = project.GetName() if project else "Unknown"
    timeline_name = timeline.GetName() if timeline else "Unknown"
    print(f"Connected: {project_name} / {timeline_name}")

    api = MarkerzAPI(resolve, timeline, fps, start_frame)
    settings = _load_settings()
    geo = settings.get("geometry", [200, 150, 520, 650])

    # Resolve web directory (works both in dev and PyInstaller bundle)
    if getattr(sys, "frozen", False):
        web_dir = str(Path(sys._MEIPASS) / "markerz" / "web")  # type: ignore[attr-defined]
    else:
        web_dir = str(Path(__file__).parent / "web")

    window = webview.create_window(
        f"Markerz v{__version__} - {timeline_name}",
        url=os.path.join(web_dir, "index.html"),
        js_api=api,
        width=geo[2],
        height=geo[3],
        x=geo[0],
        y=geo[1],
        on_top=True,
        min_size=(400, 300),
    )
    api._window = window

    window.events.loaded += api._on_loaded
    window.events.closing += api._on_closing

    print(f"Markerz v{__version__} - window open.")
    webview.start(debug=False)
    print("Markerz closed.")


if __name__ == "__main__":
    run()
