"""Tests for timecode utilities."""

from __future__ import annotations

from unittest.mock import MagicMock

from markerz.timecode import (
    frame_to_timecode,
    get_timeline_fps,
    get_timeline_start_frame,
    timecode_to_frame,
)


class TestFrameToTimecode:
    def test_zero_frame(self) -> None:
        assert frame_to_timecode(0, 24.0, 0) == "00:00:00:00"

    def test_one_second(self) -> None:
        assert frame_to_timecode(24, 24.0, 0) == "00:00:01:00"

    def test_with_frames(self) -> None:
        assert frame_to_timecode(25, 24.0, 0) == "00:00:01:01"

    def test_one_minute(self) -> None:
        assert frame_to_timecode(24 * 60, 24.0, 0) == "00:01:00:00"

    def test_one_hour(self) -> None:
        assert frame_to_timecode(24 * 3600, 24.0, 0) == "01:00:00:00"

    def test_with_start_offset(self) -> None:
        # Frame 86424 with start at 86400 = 1 second into timeline
        assert frame_to_timecode(86424, 24.0, 86400) == "00:00:01:00"

    def test_30fps(self) -> None:
        assert frame_to_timecode(30, 30.0, 0) == "00:00:01:00"

    def test_negative_relative(self) -> None:
        # Frame before start should clamp to 0
        assert frame_to_timecode(0, 24.0, 100) == "00:00:00:00"


class TestTimecodeToFrame:
    def test_zero(self) -> None:
        assert timecode_to_frame("00:00:00:00", 24.0, 0) == 0

    def test_one_second(self) -> None:
        assert timecode_to_frame("00:00:01:00", 24.0, 0) == 24

    def test_with_frames(self) -> None:
        assert timecode_to_frame("00:00:01:12", 24.0, 0) == 36

    def test_with_start_offset(self) -> None:
        assert timecode_to_frame("00:00:01:00", 24.0, 86400) == 86424

    def test_semicolon_separator(self) -> None:
        # Drop frame notation uses semicolons
        assert timecode_to_frame("00;00;01;00", 24.0, 0) == 24

    def test_invalid_format(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Invalid timecode"):
            timecode_to_frame("00:00:00", 24.0, 0)


class TestGetTimelineFps:
    def test_returns_fps(self) -> None:
        tl = MagicMock()
        tl.GetSetting.return_value = "24.0"
        assert get_timeline_fps(tl) == 24.0

    def test_returns_default(self) -> None:
        tl = MagicMock()
        tl.GetSetting.return_value = None
        assert get_timeline_fps(tl) == 24.0

    def test_integer_fps(self) -> None:
        tl = MagicMock()
        tl.GetSetting.return_value = "30"
        assert get_timeline_fps(tl) == 30.0


class TestGetTimelineStartFrame:
    def test_returns_start(self) -> None:
        tl = MagicMock()
        tl.GetStartFrame.return_value = 86400
        assert get_timeline_start_frame(tl) == 86400
