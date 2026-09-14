"""The spec-to-part designer loop: plan -> execute -> measure -> repair, capped at 3.

One human approves the plan once. Everything after that is unsupervised self-repair:

1. **Execute** the approved plan's steps over the existing Phase-2 tool surface. Every mutation
   goes through ``usecases.sketches`` / ``usecases.features``, which go through ``run_mutation``.
   This module opens no transaction and writes no geometry.
2. **Measure** the produced artifact with the injected deterministic grader — never the plan. A
   loop that detected a corrupted plan by reading the plan would pass the G3.4 fault suite while
   catching no real deviant part (AD-13).
3. **Judge**, but only on an iteration whose geometry assertions all passed. The verdict is
   conjunctive, so a judge call on a geometry failure could not change the outcome and would spend
   one of only three repair iterations for no information (AD-21 cadence).
4. **Repair** from the discrepancy vector plus the judge's findings. Not from a raw error string,
   and never from the plan text alone.

**Convergence is the verdict, never the count.** :func:`contracts.designer.converged` is the only
test, and it reads ``geometry_pass AND visual_pass``. Exhausting the cap yields ``CAP_EXHAUSTED``,
which is a FAILURE and is reported as one — a loop that returned "done" because it ran out of
iterations is the exact defect G3.4's "zero silent bad parts" rule exists to prevent.

**Every call site rebinds the document.** ``run_mutation`` returns ``(document, envelope)`` and the
snapshot-restore path closes and reopens the document (DW-71), so the object a handle held can be
dead by the time a mutation returns. Every ``_apply_step`` return is rebound into the registry.

**A failed run is reconstructable from its workdir alone.** The plan, each iteration's discrepancy
vector, the judge verdicts, the repair decisions and the AD-24 wall-clock are written under
``<workdir>/designer-runs/<run_id>/`` as the run proceeds, not at the end — a run that crashes
mid-iteration still leaves everything up to that point.

Stdlib + FreeCAD App API only. The grader, the visual leg and the repairer arrive injected, the
same way the renderer and the judge client arrive as ports: ``benchmarks/harness/assertions.py``
is outermost tooling and this ring may not import it.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from freecad_buddy.contracts import (
    CONVERGENCE_RULE,
    MAX_REPAIRS,
    VISUAL_CHECK_ID,
    VISUAL_UNAVAILABLE_CODE,
    Check,
    DesignPlan,
    Discrepancy,
    GeometryGrader,
    IterationRecord,
    JudgeFinding,
    Repairer,
    RunRecord,
    RunStatus,
    StepAuthorizer,
    VisualLeg,
    converged,
)
from freecad_buddy.usecases import features, sketches
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, workdir_root

logger = logging.getLogger("freecad_buddy.usecases.designer_loop")

# Where a run's artifacts land, under the session workdir (AD-25) so the session-start sweep can
# reach what a crashed run left behind.
_RUNS_DIRNAME = "designer-runs"

# The two tool modules a plan step may name. A step naming anything else is refused rather than
# resolved by attribute lookup on an arbitrary module, which would let a plan reach code the
# Phase-2 surface does not expose.
_TOOL_MODULES = {"sketch_": sketches, "feature_": features}


class PlanRefused(ValueError):
    """The plan was not approved, or names a step outside the Phase-2 tool surface.

    A ``ValueError``: an unapproved or unresolvable plan is bad input, not a failing part, and
    must never be reported as a part that did not converge.
    """


def run_designer_loop(
    registry: DocumentRegistry,
    plan: DesignPlan,
    checks: list,
    grader: GeometryGrader,
    visual_leg: VisualLeg,
    repairer: Repairer | None = None,
    authorizer: StepAuthorizer | None = None,
    doc: str | None = None,
    run_id: str = "",
    anchor_frame: dict | None = None,
    audit_sink: object = None,
    extra_tools: dict | None = None,
    max_repairs: int = MAX_REPAIRS,
) -> RunRecord:
    """Drive ``plan`` to convergence or to the cap; return the run record.

    :param registry: the document registry; the loop rebinds it after every mutation.
    :param plan: the approved plan. An unapproved plan raises rather than being executed.
    :param checks: the spec's compiled ``assertions.checks`` the grader measures against. These
        were authored independently of any plan (AD-19) and are what "geometry passed" means.
    :param grader: the deterministic assertion measurement, injected (``GeometryGrader``).
    :param visual_leg: the conjunctive visual half, injected (``VisualLeg``).
    :param repairer: proposes the next plan from the discrepancy vector plus the judge's findings.
        ``None`` runs a single attempt and reports whatever it reached — an honest "no repairer
        was supplied", never a pass.
    :param authorizer: mints each step's ``confirm``. The loop drives the confirm gate rather than
        bypassing it; ``None`` supplies no confirm, which the gate accepts only under an
        auto-approve posture and otherwise refuses as a step failure.
    :param doc: the document handle the plan builds into.
    :param run_id: the id threaded through every artifact this run writes. Minted from the clock
        when the caller supplies none, so a run is never unidentifiable.
    :param anchor_frame: the case's declared ``assertions.anchor_frame``, passed to the grader.
    :param audit_sink: the sink each mutation's audit lines are written through.
    :param extra_tools: ``{name: callable}`` a plan step may name beyond the Phase-2 surface.
        Named explicitly so a plan can reach only what the caller listed.
    :param max_repairs: the self-repair cap. Defaults to ``MAX_REPAIRS`` and is a parameter only so
        a test can drive the cap path in one iteration; a production run never lowers it, and
        raising it makes the result incomparable to a committed G3.1 number.
    :raises PlanRefused: the plan is unapproved or names a step outside the Phase-2 surface.
    """
    run_id = run_id or f"designer-{time.strftime('%Y%m%d-%H%M%S')}-{id(plan) & 0xFFFF:04x}"
    _require_approved(plan)
    _require_resolvable(plan, extra_tools)

    workdir = _run_workdir(run_id)
    _write_artifact(workdir, "plan.json", plan)

    started = time.monotonic()
    iterations: list[IterationRecord] = []
    current = plan
    repair: dict | None = None

    for index in range(max_repairs + 1):
        record = _run_iteration(
            registry,
            current,
            checks,
            grader,
            visual_leg,
            authorizer,
            doc,
            index,
            repair,
            anchor_frame,
            audit_sink,
            extra_tools,
        )
        iterations.append(record)
        _write_artifact(workdir, f"iteration-{index:02d}.json", record)

        if converged(record["geometry_pass"], record["visual_pass"]):
            return _finish(run_id, plan, iterations, "CONVERGED", started, workdir, doc, None)

        # The cap is checked AFTER the verdict, never instead of it: an iteration that converged on
        # its last allowed attempt is done, and one that did not is a failure whichever iteration
        # it was.
        if index >= max_repairs:
            break

        proposal = _propose_repair(repairer, current, record)
        if proposal is None:
            return _finish(
                run_id,
                plan,
                iterations,
                "CAP_EXHAUSTED",
                started,
                workdir,
                doc,
                _no_repair_detail(repairer, record),
            )
        current, repair = proposal
        _write_artifact(workdir, f"repair-{index + 1:02d}.json", repair)

    return _finish(
        run_id,
        plan,
        iterations,
        "CAP_EXHAUSTED",
        started,
        workdir,
        doc,
        f"the loop spent all {max_repairs} self-repair(s) and did not satisfy "
        f"{CONVERGENCE_RULE}; this is a FAILURE, not a finish",
    )


# ------------------------------------------------------------------------------------------
# One iteration: execute, measure, judge
# ------------------------------------------------------------------------------------------


def _run_iteration(
    registry: DocumentRegistry,
    plan: DesignPlan,
    checks: list,
    grader: GeometryGrader,
    visual_leg: VisualLeg,
    authorizer: StepAuthorizer | None,
    doc: str | None,
    index: int,
    repair: dict | None,
    anchor_frame: dict | None,
    audit_sink: object,
    extra_tools: dict | None,
) -> IterationRecord:
    """Execute one plan, measure the artifact it produced, and judge it if geometry passed."""
    started = time.monotonic()
    executed, failure = _execute(registry, plan, doc, authorizer, audit_sink, extra_tools)

    results = _grade(registry, grader, checks, doc, anchor_frame)
    geometry_pass = bool(results) and all(result.get("passed") is True for result in results)
    discrepancy = discrepancy_vector(results)

    # A step that never applied leaves an artifact the spec's assertions still measure — a plan
    # whose last operation failed produces a part missing that feature, and the assertions say so.
    # The failure is recorded as diagnostics beside the measurement rather than in place of it.
    visual = visual_leg(doc, geometry_pass) if doc is not None else _no_document_check()

    return {
        "schema": "fcb.designer-iteration/1",
        "index": index,
        "geometry_pass": geometry_pass,
        "visual_pass": bool(visual.get("passed")),
        "checks": list(results),
        "discrepancy": discrepancy,
        "judge_findings": _findings(visual),
        "visual_detail": visual.get("detail"),
        "repair": repair,
        "executed_steps": executed,
        "step_failure": failure,
        "elapsed_s": round(time.monotonic() - started, 6),
    }


def _execute(
    registry: DocumentRegistry,
    plan: DesignPlan,
    doc: str | None,
    authorizer: StepAuthorizer | None,
    audit_sink: object,
    extra_tools: dict | None,
) -> tuple[list[str], str | None]:
    """Apply every step of ``plan`` in order; return the steps applied and the first failure.

    Execution stops at the first step that does not report ``OK``: a plan's later steps are built
    on its earlier ones, so continuing past a failure applies operations to geometry that is not
    the geometry they were planned against.

    The document is rebound after every step, without exception (DW-71). The snapshot-restore
    rollback path closes and reopens the document, so a call site that kept the object it passed in
    would hold a dead handle for the rest of the run.

    A step that raises anything is recorded as a failed step, not re-raised. A mid-plan exception
    would otherwise lose every artifact the run had already written and every measurement it could
    still take — and the loop can still measure: a part missing its last feature is a part the
    spec's assertions have an opinion about.
    """
    applied: list[str] = []
    for position, step in enumerate(plan.get("steps") or []):
        tool = step.get("tool", "")
        args = dict(step.get("args") or {})
        try:
            envelope = _apply_step(registry, tool, args, doc, authorizer, audit_sink, extra_tools)
        except ValidationError as exc:
            return applied, f"step {position} ({tool}) was refused: {exc}"
        except Exception as exc:  # noqa: BLE001 - a raising step is a failed step, never a crash
            logger.warning("plan step %d (%s) raised", position, tool, exc_info=True)
            return applied, f"step {position} ({tool}) raised {type(exc).__name__}: {exc}"
        status = envelope.get("status")
        if status != "OK":
            detail = envelope.get("detail") or {}
            return applied, f"step {position} ({tool}) returned {status}: {detail.get('message')}"
        applied.append(tool)
    return applied, None


def _apply_step(
    registry: DocumentRegistry,
    tool: str,
    args: dict,
    doc: str | None,
    authorizer: StepAuthorizer | None,
    audit_sink: object,
    extra_tools: dict | None,
) -> dict:
    """Authorize one Phase-2 tool call, apply it, and rebind the document it leaves behind.

    The confirm is minted per step through the injected authorizer, so the gate is driven rather
    than bypassed and the approval records read as the real ones.

    The rebind is what DW-71 requires at every call site without exception. The tool functions
    already rebind through ``run_mutation``'s returned document, and this re-resolves and rebinds
    on top of that — a no-op on the fast path, and the correcting write on any path where the
    document the registry holds is not the one the caller started with.
    """
    function = _resolve_tool(tool, extra_tools)
    confirm = authorizer(tool, args, doc) if authorizer is not None else None
    envelope = function(registry, doc=doc, confirm=confirm, audit_sink=audit_sink, **args)
    registry.rebind(doc, registry.with_document(doc, lambda _handle, document: document))
    return envelope


def _resolve_tool(tool: str, extra_tools: dict | None = None):
    """The callable ``tool`` names: an ``extra_tools`` entry, else the Phase-2 surface.

    ``extra_tools`` is consulted first and is how the fault suite supplies its own deterministic
    profile source. It is an explicit named table rather than an open namespace: a plan may reach
    only what the caller listed, so resolving an arbitrary attribute can never let an approved plan
    call code nothing exposed.

    :raises PlanRefused: the name is in neither table. A plan step naming an unreachable tool is a
        broken plan, not a failing part.
    """
    if extra_tools and tool in extra_tools:
        return extra_tools[tool]
    for prefix, module in _TOOL_MODULES.items():
        if tool.startswith(prefix):
            function = getattr(module, tool, None)
            if function is None:
                raise PlanRefused(f"step names {tool!r}, which {module.__name__} does not expose")
            return function
    raise PlanRefused(
        f"step names {tool!r}, which is outside the Phase-2 tool surface "
        f"({', '.join(sorted(_TOOL_MODULES))}*) and the caller's extra tools "
        f"({sorted(extra_tools or ())})"
    )


def _grade(
    registry: DocumentRegistry,
    grader: GeometryGrader,
    checks: list,
    doc: str | None,
    anchor_frame: dict | None,
) -> list[Check]:
    """Measure the produced artifact against the spec's compiled checks.

    The document is resolved and handed to the grader, so what is measured is the geometry on the
    document rather than anything the plan or a tool envelope claimed. A grader that raises yields
    one failing check naming the exception: a measurement that could not be taken is a failure to
    grade, and reporting it as a pass is the one outcome that must never happen.
    """
    if doc is None:
        return [_grader_failed("the loop holds no document handle to measure")]
    try:
        document = registry.with_document(doc, lambda _handle, resolved: resolved)
        return list(grader(document, list(checks or []), anchor_frame))
    except Exception as exc:  # noqa: BLE001 - an ungradable artifact is a failure, never a pass
        logger.warning("the geometry grader raised", exc_info=True)
        return [_grader_failed(f"the grader raised {type(exc).__name__}: {exc}")]


def _grader_failed(message: str) -> Check:
    """The check a failed measurement reports: not measured, therefore not passed."""
    return {
        "id": "assert.grader",
        "measured": None,
        "measured_kind": None,
        "expected": None,
        "tolerance": None,
        "passed": False,
        "detail": {"code": "invalid_input.grader_failed", "message": message, "objects": []},
    }


def _no_document_check() -> Check:
    """The visual check a run with no document reports: nothing to judge, therefore not done."""
    return {
        "id": VISUAL_CHECK_ID,
        "measured": None,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": False,
        "detail": {
            "code": VISUAL_UNAVAILABLE_CODE,
            "message": "the loop holds no document handle, so no part could be judged",
            "objects": [],
        },
    }


# ------------------------------------------------------------------------------------------
# The discrepancy vector and the repair
# ------------------------------------------------------------------------------------------


def discrepancy_vector(results: list[Check]) -> list[Discrepancy]:
    """The failing checks as measured-vs-expected pairs — the loop's repair input.

    Shaped as repair input rather than as a report: each entry carries what the artifact actually
    measures beside what the spec asked for, which is what lets a repair size a hole rather than
    only know that a hole check failed. Passing checks are omitted — a repair driven by every
    measurement would have to rediscover which of them is the problem.
    """
    vector: list[Discrepancy] = []
    for result in results:
        if result.get("passed") is True:
            continue
        detail = result.get("detail") or {}
        vector.append(
            {
                "check_id": result.get("id", "assert.unknown"),
                "measured": result.get("measured"),
                "expected": result.get("expected"),
                "tolerance": result.get("tolerance"),
                "message": str(detail.get("message", "")),
            }
        )
    return vector


def detect_spec_violation(results: list[Check], preferred: str | None = None) -> Discrepancy | None:
    """An assertion proving the produced artifact violates its spec, or ``None`` when none does.

    This is the ``corrupted_plan`` validator the G3.4 fault cases target
    (``targets_validator: corrupted_plan@usecases.designer_loop.detect_spec_violation``). It reads
    only the measurement results, so a violation is always something the artifact carries — a
    version that inspected the plan text would flag a corrupted plan while catching nothing a real
    deviant part does, and pass the fault suite for the wrong reason.

    ``preferred`` names one assertion a caller wants reported when it is among the failures — a
    fault case's ``detected_by``. It is a reporting preference and never a detection condition: a
    corruption usually trips several assertions at once (a wrong bore diameter moves the volume
    too), and the answer to "was it detected" is the same either way. Returning the named one lets
    a fault report say which measurement the case was authored around. When ``preferred`` is absent
    from the failures, the first failure in the spec's declared order is returned rather than
    nothing, because the part IS in violation.
    """
    vector = discrepancy_vector(results)
    if not vector:
        return None
    if preferred is not None:
        for entry in vector:
            if entry["check_id"] == preferred or entry["check_id"] == f"assert.{preferred}":
                return entry
    return vector[0]


def _findings(visual: Check) -> list[JudgeFinding]:
    """The judge's findings off the visual check, or an empty list when it carries none.

    ``verify_visual`` puts the findings verbatim in ``measured`` rather than a count, exactly so
    the repair can read where to look. A check that failed for an unavailable judge carries
    ``measured: None`` and yields nothing to repair from, which is why the detail travels beside
    it on the iteration record.
    """
    measured = visual.get("measured")
    return list(measured) if isinstance(measured, list) else []


def _propose_repair(
    repairer: Repairer | None, plan: DesignPlan, record: IterationRecord
) -> tuple[DesignPlan, dict] | None:
    """Ask the repairer for the next plan; return it with the decision record, or ``None``.

    The repairer is handed the discrepancy vector and the judge's findings — never the raw
    envelope text and never the plan alone. A repairer that raises is treated as one that could not
    propose a repair: the run ends at the iteration reached and says why, which is honest, while
    letting the exception escape would lose every artifact the run already measured.
    """
    if repairer is None:
        return None
    try:
        repaired = repairer(plan, record["discrepancy"], record["judge_findings"])
    except Exception:  # noqa: BLE001 - a raising repairer ends the run, never crashes it
        logger.warning("the repairer raised", exc_info=True)
        return None
    if repaired is None:
        return None
    return repaired, {
        "for_iteration": record["index"],
        "addressed": [entry["check_id"] for entry in record["discrepancy"]],
        "judge_views": sorted({str(f.get("view")) for f in record["judge_findings"]}),
        "steps_before": [step.get("tool") for step in plan.get("steps") or []],
        "steps_after": [step.get("tool") for step in repaired.get("steps") or []],
        "rationale": repaired.get("rationale"),
    }


def _no_repair_detail(repairer: Repairer | None, record: IterationRecord) -> str:
    """Why a run that had cap left still stopped: no repairer, or none could be proposed."""
    if repairer is None:
        return (
            f"iteration {record['index']} did not satisfy {CONVERGENCE_RULE} and no repairer was "
            f"supplied, so no repair was attempted; this is a FAILURE, not a finish"
        )
    return (
        f"the repairer proposed no repair for iteration {record['index']}, which did not satisfy "
        f"{CONVERGENCE_RULE}; this is a FAILURE, not a finish"
    )


# ------------------------------------------------------------------------------------------
# Inputs and the run record
# ------------------------------------------------------------------------------------------


def _require_approved(plan: DesignPlan) -> None:
    """Reject a plan the human did not approve.

    :raises PlanRefused: ``approved`` is not True. The one approval is the whole human step in the
        epic; executing a plan without it would make the loop unsupervised from the start rather
        than after the approval.
    """
    if plan.get("approved") is not True:
        raise PlanRefused(
            "the plan is not approved: the designer loop executes exactly one human-approved "
            "plan, and an unapproved plan is a refusal rather than a default-approve"
        )


def _require_resolvable(plan: DesignPlan, extra_tools: dict | None) -> None:
    """Resolve every step's tool before any geometry is written.

    Resolving up front rather than per step is what keeps a half-built part from being measured
    against a spec it was never going to satisfy: a plan whose fourth step names a tool that does
    not exist is a broken plan, and the first three steps' geometry would otherwise be graded as a
    failing part.

    :raises PlanRefused: a step names no tool, or one outside the Phase-2 surface.
    """
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanRefused("the plan declares no steps, so it builds nothing to measure")
    for position, step in enumerate(steps):
        if not isinstance(step, dict) or not step.get("tool"):
            raise PlanRefused(f"step {position} names no tool: {step!r}")
        _resolve_tool(step["tool"], extra_tools)


def _run_workdir(run_id: str) -> Path | None:
    """The run's artifact directory under the session workdir, created on demand.

    A directory that cannot be created is logged and yields ``None``: a run that cannot write its
    artifacts still has to produce its verdict, and failing the part for an unwritable workdir
    would report a disk problem as a geometry one. The run record carries ``workdir: None`` so the
    gap is visible rather than inferred from an empty directory.
    """
    path = workdir_root() / _RUNS_DIRNAME / run_id
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.warning("could not create the designer run workdir %s", path, exc_info=True)
        return None
    return path


def _write_artifact(workdir: Path | None, name: str, payload: object) -> None:
    """Write one run artifact as JSON, as the run proceeds rather than at the end.

    Written per iteration on purpose: a run that crashes mid-repair must still leave everything it
    measured up to that point, which is what makes a failed run reconstructable from its workdir
    alone. ``default=repr`` keeps a value the grader returned that JSON cannot encode from losing
    the whole artifact.
    """
    if workdir is None:
        return
    try:
        (workdir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=repr), encoding="utf-8"
        )
    except OSError:
        logger.warning("could not write the run artifact %s", workdir / name, exc_info=True)


def _finish(
    run_id: str,
    plan: DesignPlan,
    iterations: list[IterationRecord],
    status: RunStatus,
    started: float,
    workdir: Path | None,
    doc: str | None,
    detail: str | None,
) -> RunRecord:
    """Assemble the run record, write it, and return it.

    ``converged`` is computed from the last iteration's two legs rather than from ``status``, so
    the record carries the verdict and the terminal status as two independently readable facts.
    Nothing here consults the iteration count.
    """
    last = iterations[-1] if iterations else None
    record: RunRecord = {
        "schema": "fcb.designer-run/1",
        "run_id": run_id,
        "spec_id": plan.get("spec_id", ""),
        "status": status,
        "converged": bool(
            last is not None and converged(last["geometry_pass"], last["visual_pass"])
        ),
        "convergence_rule": CONVERGENCE_RULE,
        "repairs_used": max(len(iterations) - 1, 0),
        "max_repairs": MAX_REPAIRS,
        "plan": plan,
        "iterations": iterations,
        "document": doc,
        # AD-24 basis: tool-call entry to envelope return, model time included, spanning every
        # repair iteration including the judge and the drawing generation. Always reported, never
        # suppressed for being over budget — the gate judges the number, the loop does not hide it.
        "elapsed_s": round(time.monotonic() - started, 6),
        "workdir": str(workdir) if workdir is not None else None,
        "detail": detail,
    }
    _write_artifact(workdir, "run.json", record)
    return record


def summarize_run(record: RunRecord) -> str:
    """One line: what the run concluded and by which rule.

    A non-converged run says so in the first word. Naming the rule beside the outcome is what keeps
    a reader from inferring done-ness from the repair count that follows it.
    """
    if record["converged"]:
        return (
            f"Designer run {record['run_id']} CONVERGED by {record['convergence_rule']} after "
            f"{record['repairs_used']} repair(s) in {record['elapsed_s']:.1f}s."
        )
    return (
        f"Designer run {record['run_id']} did NOT converge ({record['status']}) after "
        f"{record['repairs_used']} repair(s) in {record['elapsed_s']:.1f}s: {record['detail']}"
    )


__all__ = [
    "PlanRefused",
    "detect_spec_violation",
    "discrepancy_vector",
    "run_designer_loop",
    "summarize_run",
]
