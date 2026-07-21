"""Anchor-frame declaration type for assertions.

Assertions measure geometry in a declared anchor frame. Only the anchor-frame
declaration type is defined here.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class AnchorFrame(TypedDict, total=False):
    """Declared reference frame an assertion measures geometry in."""

    origin: list[float]  # [3] point, mm
    axes: list[list[float]]  # basis vectors; frame the measurement is taken in
    units: Literal["mm"]
