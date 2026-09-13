"""FreeCAD-free tests for the render tone oracle and its fault suite.

Runs in the uv leg: ``verify_render_tone`` decodes the PNG with stdlib only, so the oracle and its
whole fault suite are checkable without FreeCAD, Qt, or a GL context. Covers the oracle's own rule
(both saturated ends, the separability bar, the coverage floor, the PNG decoder) and then scores
the committed suite against the G0 bars.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "render-fault-injection"
sys.path.insert(0, str(SCORER_DIR))

from freecad_buddy.usecases.render_tone import (  # noqa: E402
    RenderToneError,
    verify_render_tone,
)

import score_render_tone as scorer  # noqa: E402  # isort: skip

SIZE = 120
BACKGROUND = (255, 255, 255)
FACE_MARGIN = 0.18


def _write_png(path: Path, pixels, size: int = SIZE, color_type: int = 2) -> None:
    """Write ``pixels`` (row-major RGB) as an 8-bit PNG, RGB or RGBA per ``color_type``."""
    channels = 3 if color_type == 2 else 4
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            pixel = pixels[y * size + x]
            raw.extend(pixel)
            if channels == 4:
                raw.append(255)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + tag
            + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, color_type, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _face(face_color, size: int = SIZE):
    """A background field with a centered rectangular face in ``face_color``."""
    low, high = int(size * FACE_MARGIN), int(size * (1 - FACE_MARGIN))
    return [
        face_color if (low <= x < high and low <= y < high) else BACKGROUND
        for y in range(size)
        for x in range(size)
    ]


def _outline(size: int = SIZE):
    """Only a 2 px outline is non-background -- the white-face defect's signature."""
    low, high = int(size * FACE_MARGIN), int(size * (1 - FACE_MARGIN))
    pixels = []
    for y in range(size):
        for x in range(size):
            vertical = (low <= x < low + 2 or high - 2 <= x < high) and low <= y < high
            horizontal = (low <= y < low + 2 or high - 2 <= y < high) and low <= x < high
            pixels.append((100, 100, 100) if (vertical or horizontal) else BACKGROUND)
    return pixels


def _verdict_for(tmp_path: Path, pixels, **kwargs) -> dict:
    path = tmp_path / "render.png"
    _write_png(path, pixels, **kwargs)
    return verify_render_tone(str(path))


def test_a_well_lit_face_passes(tmp_path):
    # Arrange
    pixels = _face((150, 155, 160))

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert verdict["passed"], verdict["reasons"]
    assert verdict["tone"] == pytest.approx((150.0, 155.0, 160.0))


def test_a_white_saturated_face_is_rejected(tmp_path):
    # Arrange — above the band ceiling, the shipped defect's end.
    pixels = _face((246, 248, 250))

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert not verdict["passed"]
    assert any("outside" in reason for reason in verdict["reasons"])


def test_a_black_saturated_face_is_rejected(tmp_path):
    # Arrange — below the band floor, the defect the ambient term originally fixed.
    pixels = _face((6, 6, 8))

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert not verdict["passed"]
    assert any("outside" in reason for reason in verdict["reasons"])


def test_the_check_is_two_sided(tmp_path):
    """Neither saturated end passes -- a one-sided rule is how the defect shipped."""
    # Arrange
    white = _face((250, 251, 252))
    black = _face((3, 3, 4))

    (tmp_path / "w").mkdir()
    (tmp_path / "b").mkdir()

    # Act
    white_verdict = _verdict_for(tmp_path / "w", white)
    black_verdict = _verdict_for(tmp_path / "b", black)

    # Assert
    assert not white_verdict["passed"]
    assert not black_verdict["passed"]


def test_an_outline_only_render_is_rejected_by_the_coverage_floor(tmp_path):
    """The shipped defect: healthy tone, healthy contrast, but no face.

    Every absolute condition passes here -- the outline's tone sits inside the band and differs
    sharply from the background. Only coverage separates it from a real render.
    """
    # Arrange
    pixels = _outline()

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert not verdict["passed"]
    assert any("covers" in reason for reason in verdict["reasons"])
    assert 20 <= min(verdict["tone"]) and max(verdict["tone"]) <= 235
    assert verdict["difference"] >= 24


def test_a_face_too_close_to_the_background_is_rejected(tmp_path):
    # Arrange — separable in principle, but under the 24/255 bar.
    pixels = _face((243, 244, 245))

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert not verdict["passed"]
    assert any("separable" in reason for reason in verdict["reasons"])


def test_coverage_is_reported_as_the_non_background_interior_fraction(tmp_path):
    # Arrange
    pixels = _face((150, 155, 160))

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert — the face spans (1 - 2*0.18) of each axis inside an interior of (1 - 2*0.10).
    assert verdict["coverage"] == pytest.approx((0.64 / 0.80) ** 2, rel=0.05)


def test_an_rgba_png_decodes_the_same_as_rgb(tmp_path):
    # Arrange
    pixels = _face((150, 155, 160))
    (tmp_path / "rgb").mkdir()
    (tmp_path / "rgba").mkdir()

    # Act
    rgb = _verdict_for(tmp_path / "rgb", pixels, color_type=2)
    rgba = _verdict_for(tmp_path / "rgba", pixels, color_type=6)

    # Assert
    assert rgb["tone"] == rgba["tone"]
    assert rgb["samples"] == rgba["samples"]


def test_a_non_png_raises_rather_than_guessing(tmp_path):
    # Arrange
    path = tmp_path / "not.png"
    path.write_bytes(b"this is not a PNG at all")

    # Act
    act = lambda: verify_render_tone(str(path))  # noqa: E731

    # Assert
    with pytest.raises(RenderToneError):
        act()


def test_an_all_background_render_reports_no_samples(tmp_path):
    # Arrange
    pixels = [BACKGROUND] * (SIZE * SIZE)

    # Act
    verdict = _verdict_for(tmp_path, pixels)

    # Assert
    assert not verdict["passed"]
    assert verdict["samples"] == 0
    assert verdict["tone"] is None


def _scored() -> dict:
    return scorer.score()


def test_the_committed_suite_meets_the_bars():
    # Arrange / Act
    result = _scored()

    # Assert
    assert result["sensitivity"] >= scorer.SENSITIVITY_BAR, result["rows"]
    assert result["false_alarm"] <= scorer.FALSE_ALARM_BAR, result["rows"]


def test_every_planted_defect_is_detected_and_every_control_passes():
    # Arrange / Act
    rows = _scored()["rows"]

    # Assert
    assert not [row for row in rows if row[2] == "MISSED"], rows
    assert not [row for row in rows if row[2] == "FALSE_ALARM"], rows


def test_the_suite_clears_the_planted_and_control_floors():
    # Arrange / Act
    result = _scored()

    # Assert
    assert result["planted"] >= scorer.MIN_PLANTED, result["planted"]
    assert result["controls"] >= scorer.MIN_CONTROLS, result["controls"]


def test_the_captured_defect_is_in_the_suite_and_detected():
    """The suite must grade the real broken render, not only images the builder draws."""
    # Arrange / Act
    rows = _scored()["rows"]

    # Assert
    captured = [row for row in rows if row[0] == "g0-render-captured-white-face-front"]
    assert captured, [row[0] for row in rows]
    assert captured[0][2] == "DETECTED", captured


def test_every_named_camera_has_a_clean_control():
    """A control per camera, so a rig that breaks only one view still shows up as a false alarm."""
    # Arrange
    expected = {"iso", "front", "top", "bottom", "left", "right", "back", "custom"}

    # Act
    rows = _scored()["rows"]

    # Assert
    controls = {
        row[0].rsplit("-", 1)[-1] for row in rows if row[0].startswith("g0-render-clean-control-")
    }
    assert controls == expected
