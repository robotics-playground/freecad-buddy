"""The design job: run the Phase 3 designer loop inside a Phase 4 worker.

This is the payload story 5.2 left a seam for. It runs in the WORKER process, where FreeCAD is
legal, and it is registered by importing this module — a callable cannot cross a fresh
interpreter, so the spec names the module and the worker imports it.

Two rules from the layers above are carried here rather than re-litigated:

- **The payload never names its own terminal status.** It returns an envelope or raises; the
  supervisor's ``status_map`` decides. A payload that could call itself ``OK`` would be the
  unchecked worker claim the whole design refuses. ``PlanRefused`` is the one exception worth
  catching explicitly: it is a ``ValueError``, and an uncaught one crosses the process boundary as
  a crash rather than the ``INVALID_INPUT`` it actually is.
- **Geometry and visual convergence are two facts, never one.** The visual leg is unavailable
  wherever no judge backend and no GUI exist, so a collapsed boolean would report every
  geometry-passing part as a failure and make the geometry result unmeasurable.

The grader and the visual leg are INJECTED. The benchmark's grader lives in ``benchmarks/``, the
outermost ring, and ``usecases`` may not import it — so a caller supplies them rather than this
module reaching outward for one.
"""

from __future__ import annotations

import time
from typing import Callable

from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.job import JobSpec
from freecad_buddy.hosts.phase4.worker import register

KIND = "design"

# What a design job's payload carries. Validated here rather than in the contract because the
# shape is this job kind's own — ``JobSpec.payload`` is deliberately an open mapping.
_REQUIRED_PAYLOAD_KEYS = ("plan", "checks")


class DesignRequestInvalid(ValueError):
    """The design payload is not a runnable request. Maps to ``INVALID_INPUT``."""


def run_design(spec: JobSpec) -> ResultEnvelope:
    """Run one design job and report what the loop reached.

    Returns an envelope whose ``status`` reflects the RUN, not the job: the supervisor re-derives
    the job's terminal status from it. ``OK`` here means the loop converged on both legs; anything
    else names which leg did not.
    """
    payload = spec.get("payload") or {}
    _require_payload(payload)

    from freecad_buddy.usecases import designer_loop
    from freecad_buddy.usecases.documents import DocumentRegistry

    registry = DocumentRegistry()
    spec_id = str(payload.get("spec_id") or spec.get("job_id") or "design")
    handle = registry.document_create(label=_document_label(spec_id))["structured_content"]["doc"]

    grader = _resolve(payload.get("grader_module"), "grader")
    visual_leg = _resolve(payload.get("visual_module"), "visual_leg")

    started = time.monotonic()
    try:
        record = designer_loop.run_designer_loop(
            registry,
            payload["plan"],
            payload["checks"],
            grader,
            visual_leg(registry, payload.get("spec_text", "")),
            doc=handle,
            run_id=str(spec.get("job_id") or spec_id),
            anchor_frame=payload.get("anchor_frame"),
            authorizer=_authorizer(registry),
        )
    except designer_loop.PlanRefused as exc:
        # A refused plan is bad INPUT, not a crashed worker. Without this the boundary would
        # report WORKER_CRASHED and a caller would look for a bug instead of fixing the plan.
        raise DesignRequestInvalid(str(exc)) from exc

    return _envelope(record, spec_id, time.monotonic() - started)


def _require_payload(payload: dict) -> None:
    """Refuse a payload that cannot be run, naming what is missing."""
    if not isinstance(payload, dict):
        raise DesignRequestInvalid(f"payload must be a mapping, got {type(payload).__name__}")
    missing = [key for key in _REQUIRED_PAYLOAD_KEYS if not payload.get(key)]
    if missing:
        raise DesignRequestInvalid(f"design payload is missing {', '.join(missing)}")


def _document_label(spec_id: str) -> str:
    """A FreeCAD-safe document label derived from the spec id."""
    return spec_id.replace("-", "_")


def _resolve(module_name, attribute: str) -> Callable:
    """Import ``module_name`` and return its ``attribute``.

    The grader and the visual leg are named by the REQUEST rather than chosen here, for the
    layering reason in the module docstring. A request naming neither is refused rather than
    silently graded by a default, because a default grader is a grader nobody chose.
    """
    if not module_name:
        raise DesignRequestInvalid(f"design payload names no {attribute}_module")
    module = __import__(str(module_name), fromlist=[attribute])
    resolved = getattr(module, attribute, None)
    if resolved is None:
        raise DesignRequestInvalid(f"{module_name} exposes no {attribute!r}")
    return resolved


def _authorizer(registry):
    """Build the ``StepAuthorizer`` that mints each step's confirm from a REAL preview.

    Every existing caller satisfies the confirm gate with a process-global
    ``confirm.set_auto_approve(True)``. That is a benchmark posture, and a service running
    untrusted job specs must not hold it: a process-wide flag applies to everything else sharing
    the interpreter, including a concurrently running job.

    So the service does what the gate actually asks for. ``preview_dry_run`` runs the step on a
    throwaway copy of the document, signs the operation it would perform, and returns a
    ``preview_id`` that is a self-authenticating token bound to those exact arguments. The gate
    accepts that and nothing else. The cost is real — every mutation runs twice, once on a copy —
    and it buys a service whose approvals are per-step and per-argument rather than a flag
    somebody left set.

    An unpreviewable step yields ``None``, which supplies no confirm; the gate then refuses it and
    the loop reports a step failure. That refusal is the correct answer, not a reason to fabricate
    a token.
    """
    from freecad_buddy.hosts.tool_catalog import preview_op_table
    from freecad_buddy.usecases import preview as preview_uc

    op_table = preview_op_table()

    def authorize(tool: str, args: dict, doc: str | None) -> dict | None:
        if tool not in op_table:
            return None
        try:
            envelope = preview_uc.preview_dry_run(
                registry,
                op_table,
                None,
                doc=doc,
                operation={"tool": tool, "args": args},
                render="off",
            )
        except Exception:  # noqa: BLE001 - an unpreviewable step is unconfirmed, never forced
            return None
        if envelope.get("status") != "OK":
            return None
        preview_id = (envelope.get("structured_content") or {}).get("preview_id")
        return {"preview_id": preview_id} if preview_id else None

    return authorize


def _envelope(record: dict, spec_id: str, elapsed_s: float) -> ResultEnvelope:
    """Report the run as an envelope, keeping the two convergence legs separate."""
    iterations = record.get("iterations") or []
    last = iterations[-1] if iterations else {}
    geometry_pass = bool(last.get("geometry_pass"))
    visual_pass = bool(last.get("visual_pass"))
    converged = bool(record.get("converged"))

    content = {
        "spec_id": spec_id,
        "run": record,
        # The two legs, reported separately and named so a reader cannot mistake one for the
        # conjunction. `converged` is the conjunction and is carried beside them, not instead.
        "geometry_pass": geometry_pass,
        "visual_pass": visual_pass,
        "converged": converged,
        "repairs_used": record.get("repairs_used"),
        "elapsed_s": elapsed_s,
    }
    status = "OK" if converged else "SPEC_FAILED"
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,
        "detail": None if converged else {"code": "design.not_converged",
                                          "message": _why(record, geometry_pass, visual_pass)},
        "structured_content": content,
        "text": f"{spec_id}: geometry={geometry_pass} visual={visual_pass} converged={converged}",
    }


def _why(record: dict, geometry_pass: bool, visual_pass: bool) -> str:
    """Name which leg failed, so a reader is not left to infer it from two booleans."""
    if not geometry_pass:
        return f"geometry assertions failed after {record.get('repairs_used', 0)} repair(s)"
    if not visual_pass:
        last = (record.get("iterations") or [{}])[-1]
        detail = last.get("visual_detail") or {}
        return f"visual leg did not pass: {detail.get('message', 'no detail recorded')}"
    return str(record.get("status") or "did not converge")


register(KIND, run_design)
