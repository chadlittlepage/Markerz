"""Tests for marker operations."""

from __future__ import annotations

from unittest.mock import MagicMock

from markerz.markers import (
    Marker,
    MarkerSet,
    export_markers_csv,
    get_clip_markers,
    get_timeline_markers,
)


def _make_mock_timeline(markers: dict[int, dict[str, str | int]]) -> MagicMock:
    tl = MagicMock()
    tl.GetMarkers.return_value = markers
    return tl


class TestGetTimelineMarkers:
    def test_empty_timeline(self) -> None:
        tl = _make_mock_timeline({})
        result = get_timeline_markers(tl)
        assert result.markers == []

    def test_returns_sorted_markers(self) -> None:
        tl = _make_mock_timeline(
            {
                100: {
                    "color": "Red",
                    "name": "A",
                    "note": "first",
                    "duration": 1,
                    "customData": "",
                },
                50: {
                    "color": "Blue",
                    "name": "B",
                    "note": "second",
                    "duration": 1,
                    "customData": "",
                },
            }
        )
        result = get_timeline_markers(tl)
        assert len(result.markers) == 2
        assert result.markers[0].frame == 50
        assert result.markers[1].frame == 100

    def test_none_markers(self) -> None:
        tl = MagicMock()
        tl.GetMarkers.return_value = None
        result = get_timeline_markers(tl)
        assert result.markers == []


class TestGetClipMarkers:
    def test_clip_markers_include_clip_name(self) -> None:
        clip = MagicMock()
        clip.GetMarkers.return_value = {
            10: {"color": "Green", "name": "X", "note": "", "duration": 1, "customData": ""},
        }
        clip.GetName.return_value = "Shot_001"
        result = get_clip_markers(clip)
        assert len(result.markers) == 1
        assert result.markers[0].clip_name == "Shot_001"
        assert result.markers[0].source == "clip"


class TestMarkerSet:
    def _make_set(self) -> MarkerSet:
        return MarkerSet(
            markers=[
                Marker(frame=10, color="Red", name="scene start", note="act 1", duration=1),
                Marker(frame=20, color="Blue", name="vfx", note="cleanup", duration=1),
                Marker(frame=30, color="Red", name="scene end", note="act 1 end", duration=1),
            ]
        )

    def test_filter_by_color(self) -> None:
        ms = self._make_set()
        reds = ms.filter_by_color("Red")
        assert len(reds) == 2

    def test_filter_by_name(self) -> None:
        ms = self._make_set()
        results = ms.filter_by_name("scene")
        assert len(results) == 2

    def test_filter_by_note(self) -> None:
        ms = self._make_set()
        results = ms.filter_by_name("cleanup")
        assert len(results) == 1

    def test_colors_used(self) -> None:
        ms = self._make_set()
        assert ms.colors_used == {"Red", "Blue"}


class TestExportCsv:
    def test_csv_output(self) -> None:
        ms = MarkerSet(
            markers=[
                Marker(frame=10, color="Red", name="test", note="a note", duration=1),
            ]
        )
        csv = export_markers_csv(ms)
        lines = csv.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "frame,color,name,note,duration,source,clip_name"
        assert "10" in lines[1]
        assert "Red" in lines[1]

    def test_csv_escapes_quotes(self) -> None:
        ms = MarkerSet(
            markers=[
                Marker(frame=1, color="Blue", name='a "quoted" name', note="", duration=1),
            ]
        )
        csv = export_markers_csv(ms)
        assert '""quoted""' in csv
