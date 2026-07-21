"""Geometry diff: the preview and revision-diff payload shape.

Field names ``touched/new/deleted/fingerprint_before`` match the audit identifiers
rather than introducing synonyms.
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
