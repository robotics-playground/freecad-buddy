"""Assertion vocabulary and anchor-frame types (verification-design.md §7).

The eleven §7.2 primitive names form a closed vocabulary: a check naming any other ``fn`` is
malformed input, never a skipped check. A spec declares its anchor frame as ``{kind, ref}``;
the resolver reports the frame it resolved, or why it could not, in the report banner.
"""

from __future__ import annotations

from typing import Literal, TypedDict, get_args

AssertionFn = Literal[
    "is_valid_solid",
    "count_cylindrical_holes",
    "hole_diameter",
    "hole_position",
    "hole_spacing",
    "hole_through",
    "distance_between",
    "angle_between",
    "expect_bbox",
    "expect_extent",
    "expect_volume",
]

ASSERTION_FNS: frozenset[str] = frozenset(get_args(AssertionFn))

# Checks that read a shape fact directly instead of going through the §7.2 measurement code.
SHAPE_CHECK_FNS: frozenset[str] = frozenset(
    {"expect_solid_count", "expect_valid", "expect_watertight"}
)

# Every ``fn`` a ``verify_shape`` check may name.
VERIFY_SHAPE_FNS: frozenset[str] = ASSERTION_FNS | SHAPE_CHECK_FNS

# Keys every check carries, then the keys each ``fn`` may add. ``pattern`` is accepted for
# ``hole_spacing`` but no measurement reads it.
CHECK_COMMON_KEYS: frozenset[str] = frozenset({"fn", "expect"})
CHECK_OPTIONAL_KEYS: dict[str, frozenset[str]] = {
    "is_valid_solid": frozenset(),
    "count_cylindrical_holes": frozenset({"select"}),
    "hole_diameter": frozenset({"tol", "select"}),
    "hole_position": frozenset({"tol", "select"}),
    "hole_spacing": frozenset({"tol", "select", "select_a", "select_b", "pattern"}),
    "hole_through": frozenset({"select"}),
    "distance_between": frozenset({"tol", "select_a", "select_b"}),
    "angle_between": frozenset({"tol", "select_a", "select_b"}),
    "expect_bbox": frozenset({"tol"}),
    "expect_extent": frozenset({"tol", "direction"}),
    "expect_volume": frozenset({"tol"}),
    "expect_solid_count": frozenset(),
    "expect_valid": frozenset(),
    "expect_watertight": frozenset(),
}

# Keys a ``fn`` cannot be measured without, beyond ``CHECK_COMMON_KEYS``.
CHECK_REQUIRED_KEYS: dict[str, frozenset[str]] = {
    "expect_extent": frozenset({"direction"}),
    "distance_between": frozenset({"select_a", "select_b"}),
    "angle_between": frozenset({"select_a", "select_b"}),
}

AnchorFrameKind = Literal["named_datum", "base_sketch_plane", "largest_planar_face"]

ANCHOR_FRAME_KINDS: frozenset[str] = frozenset(get_args(AnchorFrameKind))


class DeclaredAnchorFrame(TypedDict, total=False):
    """The anchor frame a spec declares: a closed ``kind`` and the object it names.

    ``ref`` names an object by ``Name`` or unique ``Label`` for ``named_datum`` and
    ``base_sketch_plane``; it is ``None`` for ``largest_planar_face``.
    """

    kind: AnchorFrameKind  # required
    ref: str | None


class AnchorFrame(TypedDict, total=False):
    """Reference frame an assertion measured geometry in, as resolved for the report banner.

    ``kind`` is ``global`` when no frame was declared. ``entity`` names what the frame was
    resolved from: the object ``Name`` for a named frame, the face's mapped name (its indexed
    name when the shape carries no element map) for ``largest_planar_face``. ``unresolved``
    carries the reason a declared frame could not be resolved; ``origin`` and ``axes`` are then
    absent.
    """

    kind: AnchorFrameKind | Literal["global"]  # required
    ref: str | None
    entity: str | None
    origin: list[float]  # [3] point, mm
    axes: list[list[float]]  # frame X, Y, Z unit vectors in document coordinates
    units: Literal["mm"]
    unresolved: str | None
