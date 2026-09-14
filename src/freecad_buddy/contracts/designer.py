"""Designer-loop wire types: the plan, the discrepancy vector, and the run record.

The loop's inputs and outputs are shaped here so a run's artifacts are readable without the code
that wrote them. Three ideas carry the story:

``DesignPlan``
    the ordered step list the designer proposes from a spec and the human approves ONCE. A step
    names a Phase-2 tool and its arguments; the loop executes it and never writes geometry itself.
``Discrepancy``
    one failing assertion's measured-vs-expected pair. The vector of these, plus the judge's
    findings, is the repair input — never a raw error string and never the plan text.
``IterationRecord`` / ``RunRecord``
    what the loop wrote per iteration and for the run. A failed run must be reconstructable from
    its workdir alone, so every field a reader needs to answer "what happened" lives here rather
    than only in the agent's context.

``convergence`` is a derived field with one rule, stated in ``CONVERGENCE_RULE`` and enforced by
``converged``: geometry AND visual. The iteration cap appears nowhere in it. A loop that returned
"done" on the cap is the exact defect G3.4 exists to catch, so the cap is expressed as a separate
terminal status (``CAP_EXHAUSTED``) that is never ``CONVERGED``.

Stdlib only, per the contracts ring.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

from freecad_buddy.contracts.report import Check
from freecad_buddy.contracts.visual import JudgeFinding

# The hard self-repair cap (AD-21 / G3.4). A gate criterion, never a tuning knob: raising it
# changes what "pass within <=3 self-repairs" measured, so a run at a different cap is not
# comparable to a committed G3.1 number.
MAX_REPAIRS = 3

# The one convergence rule, spelled once so a reader of a run artifact and a reader of the code
# see the same sentence. ``converged`` is its only implementation.
CONVERGENCE_RULE = "geometry_pass AND visual_pass"

# How a run ended. Only ``CONVERGED`` is done.
#
# ``CAP_EXHAUSTED``    the loop spent all MAX_REPAIRS repairs and still did not converge. A
#                      FAILURE, reported as one.
# ``PLAN_REFUSED``     the human did not approve the plan, or no plan was produced.
# ``EXECUTION_FAILED`` a step could not be applied at all and no repair could be attempted.
RunStatus = Literal["CONVERGED", "CAP_EXHAUSTED", "PLAN_REFUSED", "EXECUTION_FAILED"]


class PlanStep(TypedDict, total=False):
    """One operation in an approved plan: a Phase-2 tool name and its arguments.

    ``tool`` names a callable on the ``usecases.sketches`` / ``usecases.features`` surface; the
    loop resolves it there and applies it through ``run_mutation``. ``intent`` is the spec
    sentence the step came from, carried so a discrepancy can be attributed to a step without
    re-reading the spec.
    """

    tool: str  # required
    args: dict  # required
    intent: str


class DesignPlan(TypedDict, total=False):
    """The ordered step list a human approves once, before any geometry is written."""

    schema: Literal["fcb.design-plan/1"]
    spec_id: str  # required
    spec_text: str  # required
    steps: list[PlanStep]  # required
    approved: bool  # required; False is a refusal, never "approve by default"
    approved_by: str | None
    rationale: str | None


class Discrepancy(TypedDict, total=False):
    """One failing assertion, shaped as repair input rather than as a report line.

    ``check_id`` is the assertion that failed (``assert.hole_diameter``), ``measured`` what the
    produced artifact actually carries and ``expected`` what the spec asked for. The pair is the
    whole point: a repair driven by "hole_diameter failed" cannot size a hole, while one driven by
    "measured 8.0, expected 5.5" can.
    """

    check_id: str  # required
    measured: float | str | bool | list | None  # required
    expected: float | str | bool | list | None  # required
    tolerance: dict | None
    message: str


class IterationRecord(TypedDict, total=False):
    """What one plan execution produced: its measurements, its verdicts and its repair decision.

    ``geometry_pass`` and ``visual_pass`` are the two legs of ``CONVERGENCE_RULE``; ``discrepancy``
    and ``judge_findings`` are what the next iteration's repair reads. ``repair`` records what the
    loop decided to change, so a reader can tell a repair that addressed the discrepancy from one
    that guessed.
    """

    schema: Literal["fcb.designer-iteration/1"]
    index: int  # required; 0 is the first attempt, 1..MAX_REPAIRS are the repairs
    geometry_pass: bool  # required
    visual_pass: bool  # required
    checks: list[Check]
    discrepancy: list[Discrepancy]  # required; empty when geometry passed
    judge_findings: list[JudgeFinding]
    visual_detail: dict | None  # the visual check's detail when it did not pass
    repair: dict | None  # what this iteration changed, or None on the first attempt
    executed_steps: list[str]
    step_failure: str | None
    elapsed_s: float


class RunRecord(TypedDict, total=False):
    """One designer run end to end, keyed by ``run_id`` and written to the session workdir.

    ``status`` is the terminal outcome and ``converged`` its conjunctive half; the two are kept
    separate so no reader has to infer done-ness from a status string. ``elapsed_s`` is the AD-24
    measurement — tool-call entry to envelope return, model time included — spanning every repair
    iteration including the judge and the drawing generation.
    """

    schema: Literal["fcb.designer-run/1"]
    run_id: str  # required
    spec_id: str  # required
    status: RunStatus  # required
    converged: bool  # required
    convergence_rule: str  # required; the CONVERGENCE_RULE sentence, verbatim
    repairs_used: int  # required
    max_repairs: int  # required
    plan: DesignPlan
    iterations: list[IterationRecord]  # required
    document: str | None
    elapsed_s: float
    workdir: str | None
    detail: str | None


def converged(geometry_pass: bool, visual_pass: bool) -> bool:
    """Whether a run is done, by the one rule: geometry AND visual.

    The single implementation of ``CONVERGENCE_RULE``. It takes no iteration count and no cap,
    because neither can make a part correct — a loop that reported done on the cap would produce a
    silently bad part, which is the failure G3.4's "zero silent bad parts" rule exists to prevent.
    """
    return bool(geometry_pass) and bool(visual_pass)


@runtime_checkable
class GeometryGrader(Protocol):
    """The deterministic assertion measurement the loop injects, never imports.

    The shipped implementation is ``benchmarks/harness/assertions.evaluate``, which lives in the
    outermost benchmark ring; a use case may not import it. Injecting it keeps the loop's control
    flow testable against a scripted grader and keeps the grader independent of the code it
    grades (AD-13).
    """

    def __call__(self, document: object, checks: list, anchor_frame: dict | None = None) -> list:
        """Return one ``Check`` per entry in ``checks``, measured over ``document``."""


@runtime_checkable
class VisualLeg(Protocol):
    """The conjunctive visual half of done, injected the same way as the grader.

    Wraps ``usecases.verify_visual.verify_visual`` with the ports it needs already bound, so the
    loop passes only what varies per iteration. Returns the ``visual.judge`` check.
    """

    def __call__(self, doc: str, geometry_passed: bool) -> Check:
        """Return the ``visual.judge`` check for ``doc`` on this iteration."""


@runtime_checkable
class StepAuthorizer(Protocol):
    """Mints the ``confirm`` one plan step's mutation is authorized by.

    The confirm gate is part of the Phase-2 tool surface, so the loop drives it rather than
    bypassing it — but minting a real preview token means calling ``preview_dry_run`` against the
    host's op table, which lives outside this ring. The authorizer is therefore injected: the
    benchmark driver wires it to a real preview (the proven G2 path, giving approval records that
    read ``mode: "preview_token"``), and a deterministic test wires it to the auto-approve posture.

    Returning ``None`` runs the step with no confirm, which the gate accepts only under an
    auto-approve posture and otherwise refuses — a refusal the loop reports as a step failure.
    """

    def __call__(self, tool: str, args: dict, doc: str | None) -> dict | None:
        """Return the ``confirm`` mapping for this step, or ``None`` to supply none."""


@runtime_checkable
class Repairer(Protocol):
    """Produces the next plan from the failing one plus what the measurements found.

    Takes the discrepancy vector and the judge's findings — never a raw error string and never the
    plan text alone. Returns ``None`` when it cannot propose a repair, which ends the run at the
    iteration reached rather than spending the remaining cap on a repeat of the same plan.
    """

    def __call__(
        self,
        plan: DesignPlan,
        discrepancy: list[Discrepancy],
        judge_findings: list[JudgeFinding],
    ) -> DesignPlan | None:
        """Return the repaired plan, or ``None`` when no repair can be proposed."""


__all__ = [
    "CONVERGENCE_RULE",
    "MAX_REPAIRS",
    "DesignPlan",
    "Discrepancy",
    "GeometryGrader",
    "IterationRecord",
    "PlanStep",
    "Repairer",
    "RunRecord",
    "RunStatus",
    "StepAuthorizer",
    "VisualLeg",
    "converged",
]
