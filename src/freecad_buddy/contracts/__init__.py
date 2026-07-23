"""Data contracts package: the shared wire vocabulary.

Single import surface for the data contract types and helpers.
"""

from freecad_buddy.contracts.assertions import AnchorFrame
from freecad_buddy.contracts.audit import AuditRecord
from freecad_buddy.contracts.diff import CountDelta, GeometryDiff, ScalarDelta
from freecad_buddy.contracts.document import (
    DocHandle,
    GeometricSelector,
    MappedNameSelector,
    Selector,
)
from freecad_buddy.contracts.envelope import ImageRef, ResultEnvelope, mirror_text
from freecad_buddy.contracts.fingerprint import (
    FingerprintRecord,
    MassProps,
    ObjectFingerprint,
    fingerprints_equal,
    massprops_equal,
)
from freecad_buddy.contracts.job import JobStatus
from freecad_buddy.contracts.render import (
    FocusSpec,
    RenderPort,
    RenderResult,
    SceneSpec,
    StyleSpec,
)
from freecad_buddy.contracts.report import (
    Check,
    ReportBanner,
    ValidationReport,
    WilsonCI,
    derive_verdict,
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
from freecad_buddy.contracts.status import ErrorDetail, JobState, TerminalStatus

__all__ = [
    "AnchorFrame",
    "AuditRecord",
    "Check",
    "CountDelta",
    "DocHandle",
    "ErrorDetail",
    "FingerprintRecord",
    "FocusSpec",
    "GeometricSelector",
    "GeometryDiff",
    "ImageRef",
    "JobState",
    "JobStatus",
    "MappedNameSelector",
    "MassProps",
    "ObjectFingerprint",
    "RenderPort",
    "RenderResult",
    "ReportBanner",
    "ResultEnvelope",
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
    "StyleSpec",
    "TerminalStatus",
    "ValidationReport",
    "WilsonCI",
    "derive_verdict",
    "fingerprints_equal",
    "massprops_equal",
    "mirror_text",
]
