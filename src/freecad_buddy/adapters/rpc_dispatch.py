"""Method registry and the single dispatch error boundary.

``dispatch`` is the one place use-case exceptions become ``ResultEnvelope`` statuses from the
closed set: validation errors map to ``INVALID_INPUT``, a marshal timeout to ``TIMEOUT``,
FreeCAD/recompute failures and anything unexpected to ``RECOMPUTE_ERROR``. The exception
class, message, and a truncated traceback are attached, and the traceback is also written to
stderr. ``dispatch`` never raises across the boundary.
"""

from __future__ import annotations

import logging
import sys
import traceback
from dataclasses import dataclass, field
from typing import Callable

from freecad_buddy.adapters.marshal import MarshalTimeout
from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.usecases.documents import ValidationError

logger = logging.getLogger("freecad_buddy.dispatch")

_TRACEBACK_LIMIT = 4000

# Client-error classes: expected traffic (bad handle/object/path/param). These log a single line,
# not a traceback — only unexpected faults spill a full stack to stderr/addon.log.
_EXPECTED_CLIENT_STATUSES = frozenset({"INVALID_INPUT", "TIMEOUT"})


@dataclass(frozen=True)
class RpcMethod:
    """A dispatchable use-case entry: its name, handler, input schema, and audit metadata."""

    name: str
    handler: Callable[..., ResultEnvelope]
    input_schema: dict = field(default_factory=dict)
    description: str = ""
    timeout_s: float = 30.0
    mutating: bool = False
    audit_event: str = "mutation"
    internal: bool = False


def _error_envelope(status: str, exc: BaseException, *, unexpected: bool = False) -> ResultEnvelope:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    # A client error (INVALID_INPUT — unknown handle/object/path, bad param) is expected traffic,
    # not a fault: log it as one scannable line, and reserve the full traceback (stderr + addon.log)
    # for the RECOMPUTE_ERROR/WORKER_CRASHED class so the error channel stays readable.
    if unexpected or status not in _EXPECTED_CLIENT_STATUSES:
        sys.stderr.write(tb)
    else:
        logger.info("%s: %s", status, str(exc) or type(exc).__name__)
    data: dict = {"exception": type(exc).__name__, "traceback": tb[:_TRACEBACK_LIMIT]}
    if unexpected:
        data["unexpected"] = True
    detail = {
        "code": status,
        "message": str(exc) or type(exc).__name__,
        "data": data,
    }
    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,  # type: ignore[typeddict-item]
        "detail": detail,  # type: ignore[typeddict-item]
        "structured_content": structured,
        "text": mirror_text(structured),
    }


class MethodRegistry:
    """Registers ``RpcMethod``s and dispatches by name through the error boundary."""

    def __init__(self) -> None:
        self._methods: dict[str, RpcMethod] = {}

    def register(self, method: RpcMethod) -> None:
        self._methods[method.name] = method

    def get(self, name: str) -> RpcMethod | None:
        return self._methods.get(name)

    def names(self) -> list[str]:
        return list(self._methods.keys())

    def methods(self) -> list[RpcMethod]:
        return list(self._methods.values())

    def dispatch(self, name: str, params: dict) -> ResultEnvelope:
        """Invoke a registered method, mapping any exception onto the closed status set."""
        method = self._methods.get(name)
        if method is None:
            return _error_envelope("INVALID_INPUT", ValidationError(f"unknown method: {name}"))
        try:
            return method.handler(**params)
        except ValidationError as exc:
            return _error_envelope("INVALID_INPUT", exc)
        except MarshalTimeout as exc:
            # A timed-out call may still be running, so the session stays document-suspect until
            # a fingerprint check confirms state.
            envelope = _error_envelope("TIMEOUT", exc)
            envelope["detail"]["data"]["marshal_timeout"] = True  # type: ignore[index]
            envelope["detail"]["data"]["maybe_still_running"] = True  # type: ignore[index]
            return envelope
        except (TypeError, ValueError, KeyError) as exc:
            # Bad params shape reaching a handler is caller-side invalid input.
            return _error_envelope("INVALID_INPUT", exc)
        except Exception as exc:  # noqa: BLE001 - single boundary: nothing raises past here
            return _error_envelope("RECOMPUTE_ERROR", exc, unexpected=True)
