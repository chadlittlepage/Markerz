"""Tests for Frame.io EDL importer."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from markerz.importers.frameio_edl import parse_frameio_edl


def _write_edl(tmp_path: Path, content: str) -> Path:
    edl = tmp_path / "test.edl"
    edl.write_text(dedent(content))
    return edl


class TestParseFrameioEdl:
    def test_single_marker(self, tmp_path: Path) -> None:
        edl = _write_edl(
            tmp_path,
            """\
            TITLE: Test
            FCM: NON DROP FRAME

            001  001  C  V  00:00:02:04  00:00:02:04  00:00:02:04  00:00:02:04
            @Alex, Apr 14 14 11:02pm
             This is a comment. |C:ResolveColorPurple |M:Alex |D:0

            """,
        )
        markers = parse_frameio_edl(edl)
        assert len(markers) == 1
        assert markers[0].timecode == "00:00:02:04"
        assert markers[0].author == "Alex"
        assert markers[0].color == "Purple"
        assert "This is a comment" in markers[0].comment
        # Metadata tags should be stripped
        assert "|C:" not in markers[0].comment
        assert "|M:" not in markers[0].comment

    def test_multiple_markers(self, tmp_path: Path) -> None:
        edl = _write_edl(
            tmp_path,
            """\
            TITLE: Test
            FCM: NON DROP FRAME

            001  001  C  V  00:00:02:04  00:00:02:04  00:00:02:04  00:00:02:04
            @Alex, Apr 14 14 11:02pm
             First comment |C:ResolveColorRed |M:Alex |D:0

            002  001  C  V  00:01:30:00  00:01:30:00  00:01:30:00  00:01:30:00
            @Bob, Apr 14 14 11:05pm
             Second comment |C:ResolveColorBlue |M:Bob |D:0

            """,
        )
        markers = parse_frameio_edl(edl)
        assert len(markers) == 2
        assert markers[0].timecode == "00:00:02:04"
        assert markers[0].color == "Red"
        assert markers[1].timecode == "00:01:30:00"
        assert markers[1].color == "Blue"

    def test_unknown_color_defaults_blue(self, tmp_path: Path) -> None:
        edl = _write_edl(
            tmp_path,
            """\
            TITLE: Test
            FCM: NON DROP FRAME

            001  001  C  V  00:00:10:00  00:00:10:00  00:00:10:00  00:00:10:00
            @User, Jan 1 25 12:00pm
             Comment |C:UnknownColor |M:User |D:0

            """,
        )
        markers = parse_frameio_edl(edl)
        assert markers[0].color == "Blue"

    def test_multiline_comment(self, tmp_path: Path) -> None:
        edl = _write_edl(
            tmp_path,
            """\
            TITLE: Test
            FCM: NON DROP FRAME

            001  001  C  V  00:00:58:03  00:00:58:03  00:00:58:03  00:00:58:03
            @Alex, Apr 14 14 11:02pm
             First part of comment.
             Second part of comment. |C:ResolveColorGreen |M:Alex |D:0

            """,
        )
        markers = parse_frameio_edl(edl)
        assert len(markers) == 1
        assert "First part" in markers[0].comment
        assert "Second part" in markers[0].comment

    def test_real_file(self) -> None:
        """Test with the actual sample EDL if available."""
        path = Path.home() / "Desktop" / "DeadJeni_FullEdit_121725_LOCKED_REF.edl"
        if not path.exists():
            return
        markers = parse_frameio_edl(path)
        assert len(markers) == 19
        assert markers[0].timecode == "00:00:02:04"
        assert markers[0].color == "Purple"
        assert markers[0].author == "Alex Brewer-Disarufino"
