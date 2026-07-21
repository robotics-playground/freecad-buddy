"""Assertion vocabulary + anchor-frame declaration types (design §1/§13, AD-13).

Minimal Phase-0 stub. Assertions measure geometry in a declared anchor frame; the full
assertion vocabulary lands in Phase 3 (verification-design.md). Only the anchor-frame
declaration type a Phase-0 consumer references is defined here — no speculative P3
vocabulary.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class AnchorFrame(TypedDict, total=False):
    """Declared reference frame an assertion measures geometry in (AD-13)."""

    origin: list[float]  # [3] point, mm
    axes: list[list[float]]  # basis vectors; frame the measurement is taken in
    units: Literal["mm"]
