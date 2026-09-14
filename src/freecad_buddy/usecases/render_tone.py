"""Render tone oracle: does a rendered PNG actually show a part? (AD-34)

``verify_render_tone(path)`` reads a PNG and returns a verdict on whether its interior carries a
face tone separable from the background. The rule is **two-sided** on purpose: a render that
saturates to white and a render that collapses to black are both unusable, and each one-sided half
of the check passes the other's defect. It is the same measurement the in-FreeCAD camera sweep
asserts, so the fault suite and the test cannot drift apart.

Stdlib only — the PNG is decoded here rather than through Qt, so the oracle runs in the external
uv environment with no FreeCAD and no GUI stack.
"""

from __future__ import annotations

import struct
import zlib

# Interior sampling excludes the outer 10 % of the span on each axis: the render framing leaves a
# ~20 % margin, so a mean taken over the whole image is dominated by background whatever the face
# does. Interior samples are the non-background pixels inside that region.
_INTERIOR_MARGIN = 0.10

# A lit face fills tens of thousands of pixels at a normal render size. The white-face defect left
# only the anti-aliased outline — a few hundred pixels — so the floor is part of the verdict, not a
# harness detail: without it a render with no face at all passes on its edge pixels alone.
_MIN_INTERIOR_SAMPLES = 500

# The absolute floor above cannot catch the defect on its own, because the sample count scales with
# the render size: the same white-face `front` render yields ~138 samples at a small size but 1,276
# at 240x240, comfortably over any fixed floor, while its tone (99.7) and background difference
# (155) both look healthy — an outline is dark and separable, so every absolute condition passes on
# a render showing no face at all.
#
# Coverage is size-independent and separates them cleanly. Measured at 240x240 against the golden
# box: the defect covers 3.5 % of the interior, while the thinnest correct render (`top`, the box
# seen end-on) covers 24.3 % and the rest run 35-69 %. The floor sits near the geometric midpoint
# of that gap, leaving about 2x of margin on each side.
_MIN_INTERIOR_COVERAGE = 0.12

# The face must differ from the background on some channel, and sit clear of both saturated ends.
_MIN_BACKGROUND_DIFFERENCE = 24
_TONE_FLOOR = 20
_TONE_CEILING = 235

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_RGB, _RGBA = 2, 6


class RenderToneError(ValueError):
    """Raised when the image cannot be decoded, so no tone verdict is possible."""


def verify_render_tone(path: str) -> dict:
    """Return the tone verdict for the PNG at ``path``.

    The returned dict carries ``passed`` plus the evidence behind it: ``tone`` (the mean interior
    RGB, ``None`` when nothing was sampled), ``background``, ``samples``, ``coverage`` (the
    non-background fraction of the interior), ``difference`` (the largest per-channel gap from the
    background), and ``reasons`` naming every failed condition.
    """
    width, height, pixels = _read_png_rgb(path)
    background, tone, samples = _interior_tone(width, height, pixels)
    interior_area = int(width * (1 - 2 * _INTERIOR_MARGIN)) * int(
        height * (1 - 2 * _INTERIOR_MARGIN)
    )
    coverage = samples / interior_area if interior_area else 0.0

    reasons: list[str] = []
    if samples < _MIN_INTERIOR_SAMPLES:
        reasons.append(
            f"only {samples} interior samples (< {_MIN_INTERIOR_SAMPLES}); the render shows no "
            f"face, just its anti-aliased outline"
        )
    if coverage < _MIN_INTERIOR_COVERAGE:
        reasons.append(
            f"the face covers {coverage:.1%} of the interior (< {_MIN_INTERIOR_COVERAGE:.0%}); "
            f"only the anti-aliased outline is non-background, so the face rendered at the "
            f"background tone"
        )
    difference = None
    if tone is not None:
        difference = max(abs(t - b) for t, b in zip(tone, background))
        if difference < _MIN_BACKGROUND_DIFFERENCE:
            reasons.append(
                f"tone differs from the background by {difference:.1f}/255 "
                f"(< {_MIN_BACKGROUND_DIFFERENCE}); the face is not separable"
            )
        for channel, value in enumerate(tone):
            if not _TONE_FLOOR <= value <= _TONE_CEILING:
                reasons.append(
                    f"channel {channel} is {value:.1f}, outside [{_TONE_FLOOR}, {_TONE_CEILING}]"
                )

    return {
        "passed": not reasons,
        "tone": tone,
        "background": background,
        "samples": samples,
        "coverage": coverage,
        "difference": difference,
        "reasons": reasons,
    }


def _interior_tone(width: int, height: int, pixels: list) -> tuple:
    """Return ``(background, mean_tone, sample_count)`` over the non-background interior."""
    background = pixels[0]
    x_start, x_stop = int(width * _INTERIOR_MARGIN), int(width * (1 - _INTERIOR_MARGIN))
    y_start, y_stop = int(height * _INTERIOR_MARGIN), int(height * (1 - _INTERIOR_MARGIN))

    totals = [0, 0, 0]
    count = 0
    for y in range(y_start, y_stop):
        row = y * width
        for x in range(x_start, x_stop):
            pixel = pixels[row + x]
            if pixel == background:
                continue
            for channel, value in enumerate(pixel):
                totals[channel] += value
            count += 1
    if count == 0:
        return background, None, 0
    return background, tuple(total / count for total in totals), count


def _read_png_rgb(path: str) -> tuple[int, int, list]:
    """Decode an 8-bit RGB/RGBA PNG into ``(width, height, [(r, g, b), ...])``.

    Only the subset the offscreen renderer emits is supported — 8 bits per channel, no interlace,
    no palette. Anything else raises rather than guessing at the pixels.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != _PNG_SIGNATURE:
        raise RenderToneError(f"{path} is not a PNG")

    width = height = depth = color_type = interlace = None
    compressed = bytearray()
    position = 8
    while position + 8 <= len(data):
        length, chunk_type = struct.unpack(">I4s", data[position : position + 8])
        body = data[position + 8 : position + 8 + length]
        position += 12 + length
        if chunk_type == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", body[:13])
        elif chunk_type == b"IDAT":
            compressed += body
        elif chunk_type == b"IEND":
            break

    if width is None:
        raise RenderToneError(f"{path} has no IHDR chunk")
    if depth != 8 or color_type not in (_RGB, _RGBA) or interlace != 0:
        raise RenderToneError(
            f"{path}: unsupported PNG (depth={depth} color_type={color_type} "
            f"interlace={interlace}); expected 8-bit non-interlaced RGB/RGBA"
        )

    channels = 3 if color_type == _RGB else 4
    return width, height, _unfilter(zlib.decompress(bytes(compressed)), width, height, channels)


def _unfilter(raw: bytes, width: int, height: int, channels: int) -> list:
    """Reverse the per-scanline PNG filters and return the RGB triples in row-major order."""
    stride = width * channels
    pixels = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset : offset + stride])
        offset += stride
        _unfilter_line(line, previous, filter_type, channels, stride)
        for index in range(0, stride, channels):
            pixels.append((line[index], line[index + 1], line[index + 2]))
        previous = line
    return pixels


def _unfilter_line(line, previous, filter_type: int, channels: int, stride: int) -> None:
    """Apply the inverse of PNG filter ``filter_type`` to ``line`` in place (RFC 2083 §6)."""
    if filter_type == 0:
        return
    for index in range(stride):
        left = line[index - channels] if index >= channels else 0
        up = previous[index]
        up_left = previous[index - channels] if index >= channels else 0
        if filter_type == 1:
            line[index] = (line[index] + left) & 0xFF
        elif filter_type == 2:
            line[index] = (line[index] + up) & 0xFF
        elif filter_type == 3:
            line[index] = (line[index] + (left + up) // 2) & 0xFF
        elif filter_type == 4:
            line[index] = (line[index] + _paeth(left, up, up_left)) & 0xFF
        else:
            raise RenderToneError(f"unknown PNG filter type {filter_type}")


def _paeth(left: int, up: int, up_left: int) -> int:
    """The Paeth predictor: whichever neighbour the linear estimate lands closest to."""
    estimate = left + up - up_left
    to_left, to_up, to_up_left = (
        abs(estimate - left),
        abs(estimate - up),
        abs(estimate - up_left),
    )
    if to_left <= to_up and to_left <= to_up_left:
        return left
    return up if to_up <= to_up_left else up_left


__all__ = ["RenderToneError", "verify_render_tone"]
