"""Contracts ring: stdlib-only data contracts (AD-1). No third-party, no FreeCAD imports.

Single import surface for the wire vocabulary (AD-17): every downstream story consumes
these types and helpers, none invents its own variant.
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
)
from freecad_buddy.contracts.job import JobStatus
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
    "GeometricSelector",
    "GeometryDiff",
    "ImageRef",
    "JobState",
    "JobStatus",
    "MappedNameSelector",
    "MassProps",
    "ObjectFingerprint",
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
    "Selector",
    "TerminalStatus",
    "ValidationReport",
    "WilsonCI",
    "derive_verdict",
    "fingerprints_equal",
    "mirror_text",
]
