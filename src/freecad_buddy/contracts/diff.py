"""Geometry diff: the preview and revision-diff payload shape.

Field names ``touched/new/deleted/fingerprint_before`` match the audit identifiers
rather than introducing synonyms.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.document import DocHandle
from freecad_buddy.contracts.mutation import TnpAuditBlock
from freecad_buddy.contracts.status import TerminalStatus


class ScalarDelta(TypedDict):
    before: float
    after: float
    delta: float
    units: str


class CountDelta(TypedDict):
    before: int
    after: int
    delta: int


class BBoxDelta(TypedDict):
    before: list[float]
    after: list[float]
    center_shift: list[float]
    units: str


class ComDelta(TypedDict):
    before: list[float]
    after: list[float]
    shift: list[float]
    units: str


class DiffDeltas(TypedDict, total=False):
    volume: ScalarDelta  # required
    area: ScalarDelta  # required
    bbox: BBoxDelta  # required
    com: ComDelta  # required


class DiffCounts(TypedDict, total=False):
    faces: CountDelta  # required
    edges: CountDelta  # required
    vertices: CountDelta  # required
    solids: CountDelta  # required


class RecomputeError(TypedDict, total=False):
    object: str  # required
    error: str  # required


class DiffValidity(TypedDict, total=False):
    is_valid: bool  # required
    recompute_clean: bool  # required
    recompute_errors: list[RecomputeError]  # required; attributed to the op
    pre_existing_errors: list[RecomputeError]  # required; present before the preview ran
    status: TerminalStatus | None  # required; the op's terminal status
    explanation: str | None  # required; the op's post_verify explanation


class DiffRender(TypedDict, total=False):
    available: bool  # required
    reason: str | None  # required


class GeometryDiff(TypedDict, total=False):
    schema: Literal["fcb.geometry-diff/1"]
    op: dict
    doc: DocHandle
    deltas: DiffDeltas  # required
    counts: DiffCounts  # required
    touched: list[str]
    new: list[str]
    deleted: list[str]
    validity: DiffValidity  # required
    tnp_precheck: TnpAuditBlock  # required
    fingerprint_before: str
    render: DiffRender | None
