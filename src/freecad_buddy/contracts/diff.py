"""Geometry diff (design §8) — preview payload (AD-10) + G4.2 revision-diff shape.

Field names ``touched/new/deleted/fingerprint_before`` MUST match the audit
identifiers (§12.4) — no synonyms.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.document import DocHandle


class ScalarDelta(TypedDict):
    before: float
    after: float
    delta: float
    units: str


class CountDelta(TypedDict):
    before: int
    after: int
    delta: int


class GeometryDiff(TypedDict, total=False):
    schema: Literal["fcb.geometry-diff/1"]
    op: dict
    doc: DocHandle
    deltas: dict  # required
    counts: dict  # required
    touched: list[str]
    new: list[str]
    deleted: list[str]
    validity: dict  # required
    tnp_precheck: dict  # required
    fingerprint_before: str
    render: dict | None
