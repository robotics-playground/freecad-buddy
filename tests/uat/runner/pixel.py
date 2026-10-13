"""Scripted pixel checks on a window capture, placed by the probe's view geometry.

Coordinates: the probe gives the 3D view rectangle and each object's projected ``screen_center``
in global device pixels; ``list_windows`` gives the window bounds in desktop pixels; the capture
is that window, scaled by ``capture width / window width``. One monitor only.

Background is taken per row from the view's left and right edge pixels, so a vertical gradient
background reads as background. A pixel whose largest channel difference from the background
exceeds ``GEOMETRY_THRESHOLD`` is non-background.

The 3D view also holds FreeCAD overlays: the navigation cube, the corner axis and the Tasks
panel, whose text and borders are thin lines over the background. So the model's extent is not
every non-background pixel: the view is cut into ``BLOCK_PX`` blocks, a block is solid when most
of its pixels are non-background, and the extent is the connected set of solid blocks that holds
a sampled ``screen_center``. A line one or two pixels wide never makes a block solid, so it
cannot join an overlay to the model.
"""

GEOMETRY_THRESHOLD = 24
EDGE_INSET_PX = 2
# Capture pixels. Small enough that the 2.5 % margin a fit leaves (17 px on a 700 px view) is at
# least two blocks; large enough that the 1-2 px lines of the Tasks overlay stay below
# SOLID_FRACTION (measured on a FreeCAD 1.1.4 capture at device pixel ratio 1.25).
BLOCK_PX = 8
SOLID_FRACTION = 0.6


def _difference(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


class Placement:
    """Maps global device pixels into a capture."""

    def __init__(self, window, image):
        self.window = window
        self.scale_x = image.width / window["width"]
        self.scale_y = image.height / window["height"]

    def point(self, x, y):
        return (
            int((x - self.window["x"]) * self.scale_x),
            int((y - self.window["y"]) * self.scale_y),
        )

    def box(self, rect):
        """``[x, y, width, height]`` to ``(left, top, right, bottom)``, right and bottom open."""
        left, top = self.point(rect[0], rect[1])
        right, bottom = self.point(rect[0] + rect[2], rect[1] + rect[3])
        return left, top, right, bottom


def inside_capture(box, image):
    """Whether ``box`` lies wholly inside the capture; outside it a pixel read wraps or raises."""
    left, top, right, bottom = box
    return 0 <= left < right <= image.width and 0 <= top < bottom <= image.height


def background_rows(image, box):
    """Background colour per row of ``box``.

    When the two edge pixels of a row disagree, something touches one edge; the background is
    then the edge pixel closer to the row above.
    """
    left, top, right, bottom = box
    rows, previous = {}, None
    for y in range(top, bottom):
        at_left = image.rgb(left + EDGE_INSET_PX, y)
        at_right = image.rgb(right - 1 - EDGE_INSET_PX, y)
        if previous is None or _difference(at_left, at_right) <= GEOMETRY_THRESHOLD:
            colour = at_left
        else:
            colour = min((at_left, at_right), key=lambda c: _difference(c, previous))
        rows[y] = previous = colour
    return rows


def is_geometry(image, x, y, background):
    return _difference(image.rgb(x, y), background[y]) > GEOMETRY_THRESHOLD


def solid_blocks(image, box, background):
    """Set of ``(column, row)`` block indices inside ``box`` that are mostly non-background."""
    left, top, right, bottom = box
    needed = SOLID_FRACTION * BLOCK_PX * BLOCK_PX
    solid = set()
    for row, block_top in enumerate(range(top, bottom - BLOCK_PX + 1, BLOCK_PX)):
        for column, block_left in enumerate(range(left, right - BLOCK_PX + 1, BLOCK_PX)):
            count = sum(
                is_geometry(image, x, y, background)
                for y in range(block_top, block_top + BLOCK_PX)
                for x in range(block_left, block_left + BLOCK_PX)
            )
            if count >= needed:
                solid.add((column, row))
    return solid


def _component(solid, seed):
    found, pending = {seed}, [seed]
    while pending:
        column, row = pending.pop()
        for d_column in (-1, 0, 1):
            for d_row in (-1, 0, 1):
                neighbour = (column + d_column, row + d_row)
                if neighbour in solid and neighbour not in found:
                    found.add(neighbour)
                    pending.append(neighbour)
    return found


def _extent(blocks, box, columns, rows):
    left, top, right, bottom = box
    first_column = min(c for c, _ in blocks)
    last_column = max(c for c, _ in blocks)
    first_row = min(r for _, r in blocks)
    last_row = max(r for _, r in blocks)
    width = (last_column - first_column + 1) * BLOCK_PX
    height = (last_row - first_row + 1) * BLOCK_PX
    return {
        "box": [
            left + first_column * BLOCK_PX,
            top + first_row * BLOCK_PX,
            left + (last_column + 1) * BLOCK_PX,
            top + (last_row + 1) * BLOCK_PX,
        ],
        "fraction": max(width / (right - left), height / (bottom - top)),
        "touches_edge": (
            first_column == 0
            or first_row == 0
            or last_column == columns - 1
            or last_row == rows - 1
        ),
    }


def measure(image, window, view_rect, centers):
    """Sample each ``screen_center`` and measure the extent of the model under them.

    ``centers`` maps a name to a global ``[x, y]`` or ``None``. Returns a JSON-safe dict:
    ``view_box`` (capture pixels), ``samples[name] = {"point", "rgb", "geometry"}``, and
    ``extent = {"box", "fraction", "touches_edge"}``, ``None`` when no sample hit a solid
    block. ``fraction`` is the larger of extent width / view width and extent height / view
    height; ``touches_edge`` is true when the extent reaches the outermost block row or column.
    """
    placement = Placement(window, image)
    box = placement.box(view_rect)
    left, top, right, bottom = box
    background = background_rows(image, box)
    solid = solid_blocks(image, box, background)
    samples, extent_blocks = {}, set()
    for name, center in centers.items():
        if center is None:
            samples[name] = {"point": None, "rgb": None, "geometry": False}
            continue
        x, y = placement.point(*center)
        inside = left <= x < right and top <= y < bottom
        samples[name] = {
            "point": [x, y],
            "rgb": list(image.rgb(x, y)) if inside else None,
            "geometry": inside and is_geometry(image, x, y, background),
        }
        seed = ((x - left) // BLOCK_PX, (y - top) // BLOCK_PX)
        if inside and seed in solid:
            extent_blocks |= _component(solid, seed)
    columns, rows = (right - left) // BLOCK_PX, (bottom - top) // BLOCK_PX
    extent = _extent(extent_blocks, box, columns, rows) if extent_blocks else None
    return {"view_box": list(box), "samples": samples, "extent": extent}


def golden_difference(image, golden, box):
    """Fraction of pixels inside ``box`` that differ from the golden capture; sizes must match."""
    if (image.width, image.height) != (golden.width, golden.height):
        return {
            "error": f"size {image.width}x{image.height} differs from golden "
            f"{golden.width}x{golden.height}"
        }
    left, top, right, bottom = box
    changed = sum(
        _difference(image.rgb(x, y), golden.rgb(x, y)) > GEOMETRY_THRESHOLD
        for y in range(top, bottom)
        for x in range(left, right)
    )
    total = (right - left) * (bottom - top)
    return {"changed_fraction": changed / total if total else 0.0}
