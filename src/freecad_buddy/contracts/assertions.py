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
