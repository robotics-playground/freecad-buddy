"""Data contracts package: the shared wire vocabulary.

Single import surface for the data contract types and helpers.
"""

from freecad_buddy.contracts.assertions import AnchorFrame
from freecad_buddy.contracts.audit import AuditRecord
from freecad_buddy.contracts.capabilities import CapabilityBanner
from freecad_buddy.contracts.diff import (
    BBoxDelta,
    ComDelta,
    CountDelta,
    DiffCounts,
    DiffDeltas,
    DiffRender,
    DiffValidity,
    GeometryDiff,
    RecomputeError,
    ScalarDelta,
)
from freecad_buddy.contracts.document import (
    DocHandle,
    GeometricSelector,
    MappedNameSelector,
    Selector,
)
from freecad_buddy.contracts.envelope import ImageRef, ResultEnvelope, mirror_text, summary_text
from freecad_buddy.contracts.feature import (
    DatumKind,
    ExtrudeType,
    FeatureState,
    PatternKind,
    ShapeSummary,
)
from freecad_buddy.contracts.fingerprint import (
    FingerprintRecord,
    MassProps,
    ObjectFingerprint,
    fingerprints_equal,
    massprops_equal,
)
from freecad_buddy.contracts.job import JobStatus
from freecad_buddy.contracts.mutation import (
    MutationBlock,
    PostVerifyBlock,
    RefFinding,
    RefVerdict,
    RollbackProof,
    TnpAuditBlock,
    TnpStatus,
)
from freecad_buddy.contracts.render import (
    FocusSpec,
    RenderPort,
    RenderResult,
    SceneSpec,
    StyleSpec,
)
from freecad_buddy.contracts.report import (
    Check,
    MeasuredKind,
    ReportBanner,
    ValidationReport,
    WilsonCI,
    derive_verdict,
    require_wilson_ci_for_rates,
)
from freecad_buddy.contracts.rpc import (
    RpcError,
    RpcErrorData,
    RpcErrorFrame,
    RpcHelloParams,
    RpcHelloRequest,
    RpcHelloResponse,
    RpcHelloResult,
    RpcRequest,
    RpcSuccess,
)
from freecad_buddy.contracts.sketch import (
    ConstraintRef,
    ConstraintSpec,
    ConstraintType,
    GeometryKind,
    GeometrySpec,
    PointPos,
    Quantity,
    SketchState,
)
from freecad_buddy.contracts.status import ErrorDetail, JobState, TerminalStatus

__all__ = [
    "AnchorFrame",
    "AuditRecord",
    "BBoxDelta",
    "CapabilityBanner",
    "Check",
    "ComDelta",
    "ConstraintRef",
    "ConstraintSpec",
    "ConstraintType",
    "CountDelta",
    "DatumKind",
    "DiffCounts",
    "DiffDeltas",
    "DiffRender",
    "DiffValidity",
    "DocHandle",
    "ErrorDetail",
    "ExtrudeType",
    "FeatureState",
    "FingerprintRecord",
    "FocusSpec",
    "GeometricSelector",
    "GeometryDiff",
    "GeometryKind",
    "GeometrySpec",
    "ImageRef",
    "JobState",
    "JobStatus",
    "MappedNameSelector",
    "MassProps",
    "MeasuredKind",
    "MutationBlock",
    "ObjectFingerprint",
    "PatternKind",
    "PointPos",
    "PostVerifyBlock",
    "Quantity",
    "RecomputeError",
    "RefFinding",
    "RefVerdict",
    "RenderPort",
    "RenderResult",
    "ReportBanner",
    "ResultEnvelope",
    "RollbackProof",
    "RpcError",
    "RpcErrorData",
    "RpcErrorFrame",
    "RpcHelloParams",
    "RpcHelloRequest",
    "RpcHelloResponse",
    "RpcHelloResult",
    "RpcRequest",
    "RpcSuccess",
    "ScalarDelta",
    "SceneSpec",
    "Selector",
    "ShapeSummary",
    "SketchState",
    "StyleSpec",
    "TerminalStatus",
    "TnpAuditBlock",
    "TnpStatus",
    "ValidationReport",
    "WilsonCI",
    "derive_verdict",
    "fingerprints_equal",
    "massprops_equal",
    "mirror_text",
    "require_wilson_ci_for_rates",
    "summary_text",
]
