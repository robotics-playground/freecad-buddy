"""Stdlib PNG decoder for window captures: 8-bit RGB or RGBA, not interlaced, any filter type."""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {2: 3, 6: 4}


class PngError(ValueError):
    pass


class Image:
    """Decoded pixels; ``rows[y]`` holds ``width * channels`` bytes."""

    def __init__(self, width, height, channels, rows):
        self.width = width
        self.height = height
        self.channels = channels
        self.rows = rows

    def rgb(self, x, y):
        start = x * self.channels
        return tuple(self.rows[y][start : start + 3])


def _chunks(data):
    position = len(SIGNATURE)
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position : position + 8])
        yield kind, data[position + 8 : position + 8 + length]
        position += 12 + length


def _paeth(left, up, up_left):
    estimate = left + up - up_left
    to_left, to_up, to_up_left = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
    if to_left <= to_up and to_left <= to_up_left:
        return left
    return up if to_up <= to_up_left else up_left


def _unfilter(kind, line, previous, stride):
    """Undo one scanline filter (PNG spec section 9.2); ``stride`` is bytes per pixel."""
    if kind == 0:
        return line
    out = bytearray(line)
    if kind == 2:
        return bytearray((value + above) & 0xFF for value, above in zip(line, previous))
    for i in range(len(out)):
        left = out[i - stride] if i >= stride else 0
        if kind == 1:
            out[i] = (out[i] + left) & 0xFF
        elif kind == 3:
            out[i] = (out[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif kind == 4:
            up_left = previous[i - stride] if i >= stride else 0
            out[i] = (out[i] + _paeth(left, previous[i], up_left)) & 0xFF
        else:
            raise PngError(f"unknown filter type {kind}")
    return out


def decode(data):
    if not data.startswith(SIGNATURE):
        raise PngError("not a PNG file")
    header, compressed = None, []
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed.append(body)
    if header is None:
        raise PngError("no IHDR chunk")
    width, height, depth, color_type, _, _, interlace = header
    if depth != 8 or color_type not in _CHANNELS or interlace:
        raise PngError(
            f"unsupported PNG: bit depth {depth}, colour type {color_type}, interlace {interlace}"
        )
    channels = _CHANNELS[color_type]
    stride = width * channels
    raw = zlib.decompress(b"".join(compressed))
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        previous = _unfilter(raw[start], raw[start + 1 : start + 1 + stride], previous, channels)
        rows.append(bytes(previous))
    return Image(width, height, channels, rows)


def read(path):
    with open(path, "rb") as handle:
        return decode(handle.read())
