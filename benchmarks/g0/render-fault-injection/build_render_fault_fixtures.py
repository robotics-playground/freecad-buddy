"""Build the planted render PNGs for the render-tone fault suite.

Run under any interpreter (stdlib only -- no FreeCAD, no Qt)::

    uv run python benchmarks/g0/render-fault-injection/build_render_fault_fixtures.py

The clean controls are *captured* renders committed alongside their case, not synthesized here:
a control must be what the shipped renderer actually produces, or a false-alarm rate measured
against it means nothing. Re-capture them with ``capture_render_controls.py`` under FreeCADCmd.

Most planted cases are synthesized here, because each encodes a defect the fixed renderer no longer
produces -- an all-white face is exactly the bug this suite guards against regressing.

``captured-white-face-front`` is the exception and is NOT rebuilt by this script: it is the real
defect, captured from the renderer while the headlight was still aimed on-axis. Keep it committed.
A suite of only synthesized defects proves the oracle rejects images this file draws; that one case
proves it rejects what the broken renderer actually emitted.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent

SIZE = 240
BACKGROUND = (255, 255, 255)

# The planted face occupies the same fraction of the frame the real framing leaves (~1/1.2 of the
# binding axis), so a synthesized case has a realistic interior sample count and the suite measures
# the tone rule rather than a geometry difference.
FACE_MARGIN = 0.18


def _write_png(path: Path, pixels: list[tuple[int, int, int]], size: int = SIZE) -> None:
    """Write ``pixels`` (row-major RGB) as an 8-bit non-interlaced RGB PNG."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0 (None) — the decoder under test handles all five
        for x in range(size):
            raw.extend(pixels[y * size + x])

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + tag
            + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _face_render(face_color: tuple[int, int, int], size: int = SIZE) -> list:
    """A background field with a centered rectangular face in ``face_color``."""
    low, high = int(size * FACE_MARGIN), int(size * (1 - FACE_MARGIN))
    pixels = []
    for y in range(size):
        for x in range(size):
            inside = low <= x < high and low <= y < high
            pixels.append(face_color if inside else BACKGROUND)
    return pixels


def _outline_only(size: int = SIZE) -> list:
    """The white-face defect: the face is background-colored, leaving only its anti-aliased edge.

    This reproduces the shipped bug's measured signature. `front`/`top`/`right`/`back` rendered the
    face at rgb(255,255,255) -- identical to the background -- so the only non-background pixels
    were the partly-covered edge pixels: a 2 px band of mid-grey around the silhouette, covering
    3.5 % of the interior against 24-69 % for a real render.

    Note which condition catches it. Its tone (~100) sits inside the band and it differs from the
    background by ~155, so every absolute condition PASSES -- an outline is dark and separable.
    Only the coverage floor detects it, which is why that floor exists.
    """
    low, high = int(size * FACE_MARGIN), int(size * (1 - FACE_MARGIN))
    pixels = []
    for y in range(size):
        for x in range(size):
            on_vertical = (low <= x < low + 2 or high - 2 <= x < high) and low <= y < high
            on_horizontal = (low <= y < low + 2 or high - 2 <= y < high) and low <= x < high
            pixels.append((100, 100, 100) if (on_vertical or on_horizontal) else BACKGROUND)
    return pixels


CASES = {
    # The planted defect this story exists to catch: ambient alone saturating the face to white.
    "all-white-render": _outline_only(),
    # A face tinted just short of the ceiling still carries no usable shading.
    "near-white-face": _face_render((246, 248, 250)),
    # The opposite saturated end — the defect the ambient term was originally added to fix.
    "all-black-face": _face_render((6, 6, 8)),
    "near-black-face": _face_render((14, 15, 17)),
    # Separable tone, but so close to the background that the shape reads as a flat field.
    "low-contrast-face": _face_render((243, 244, 245)),
}


def main() -> int:
    for case_id, pixels in CASES.items():
        directory = HERE / case_id
        directory.mkdir(parents=True, exist_ok=True)
        _write_png(directory / "render.png", pixels)
        sys.stderr.write(f"  wrote {case_id}/render.png\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
