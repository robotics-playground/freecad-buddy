"""G1 actor-run harness: drive the eval through a backend, grade it, escalate, emit reports.

Given a ``Backend`` and the read-only profile registry, this runs each broken-doc error-diagnosis
case ×R through the actor, grades every answer with the independent Story 2.1
``DeterministicGrader`` (never the actor — no self-grading), and applies the tiered n10→n30
escalation from decision 008: grade the 10 ``tier: n10`` cases first; the tier PASSES at ≥8/10;
only a perfect 10/10 escalates to the full n=30. One ``ValidationReport`` per case×repeat is
emitted, plus a per-tier Wilson CI on the case-level pass rate (majority-of-R).

The live backend is operator-gated (``FREECAD_BUDDY_G1_ACTOR_BACKEND=live``); absent, the caller
supplies the offline ``ScriptedBackend`` double and the run is fully deterministic. This module
is FreeCAD-free tooling under ``benchmarks/`` and reuses the shared grader, stats, and report
builders — it forks none of them.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SRC = REPO_ROOT / "src"
for _extra in (str(SRC), str(REPO_ROOT), str(HERE)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from benchmarks.harness.actor import Actor, Backend  # noqa: E402
from freecad_buddy.contracts.report import Check, ReportBanner, ValidationReport, derive_verdict  # noqa: E402
from freecad_buddy.usecases import stats  # noqa: E402
from grader import DeterministicGrader, GraderClient, GraderVerdict  # noqa: E402

BROKEN_DOCS = HERE / "dev" / "broken-docs"
RUBRIC = HERE / "rubric.md"

N10_PASS_THRESHOLD = 8
N10_ESCALATE_THRESHOLD = 10
N30_PASS_RATE = 0.80
DEFAULT_REPEATS = 3

# The summarized-tree query the assistant must use instead of a raw dump (latency/context
# invariant). The harness asserts the actor's recorded calls stay within the read-only surface
# and never reach for a non-summarized tree dump.
SUMMARIZED_TREE_TOOL = "query_tree_summary"


@dataclass(frozen=True)
class CaseResult:
    """One graded broken-doc case: its id, tier, per-repeat pass flags, and majority verdict."""

    case_id: str
    tier: str
    repeat_passes: list[bool]
    passed: bool
    reports: list[ValidationReport]


@dataclass(frozen=True)
class TierResult:
    """One tier's aggregate: the graded cases, the pass count, tier-pass flag, and Wilson CI."""

    tier: str
    cases: list[CaseResult]
    passed_count: int
    passed: bool
    wilson_ci: dict


@dataclass(frozen=True)
class ActorRunResult:
    """The full run: the n10 tier, whether it escalated, the n30 tier (or None), and all reports."""

    n10: TierResult
    escalated: bool
    n30: TierResult | None
    reports: list[ValidationReport]


def _load_broken_cases() -> list[dict]:
    """Load every broken-doc ``case.yaml``, validating each is a well-formed, uniquely-tiered case.

    Raises ``ValueError`` on an empty/absent set, a malformed case (non-mapping or missing ``id``),
    a duplicate id, or a tier tag that is neither ``n10`` nor ``n30`` — a case dropped by any of
    these would be graded in no tier and vanish from the run silently.
    """
    cases: list[dict] = []
    seen_ids: set[str] = set()
    for case_yaml in sorted(BROKEN_DOCS.rglob("case.yaml")):
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "id" not in data:
            raise ValueError(f"malformed broken-doc case (non-mapping or no id): {case_yaml}")
        if data.get("tier") not in ("n10", "n30"):
            raise ValueError(
                f"broken-doc case {data['id']!r} has invalid tier {data.get('tier')!r}"
            )
        if data["id"] in seen_ids:
            raise ValueError(f"duplicate broken-doc case id: {data['id']!r}")
        seen_ids.add(data["id"])
        data["_dir"] = case_yaml.parent
        cases.append(data)
    if not cases:
        raise ValueError(f"no broken-doc cases found under {BROKEN_DOCS}")
    return cases


def _question_for(case: dict) -> str:
    return "The document fails to recompute. Which object is in error and why?"


def _off_profile_call(tool_calls: list, allowed: set[str]) -> str | None:
    """The first recorded tool call whose name is outside the read-only allow-list, or ``None``.

    A compliant actor only ever calls tools in the read-only profile, and inspects the tree solely
    via ``query_tree_summary`` — the profile exposes no raw full-tree dump. Any recorded call to a
    name outside the allow-list (a fabricated raw dump, or any off-surface tool) is flagged, rather
    than pattern-matching a ``_tree`` suffix that a differently-named dump would evade.
    """
    for call in tool_calls:
        name = getattr(call, "name", None)
        if name and name not in allowed:
            return name
    return None


def _build_case_report(
    case: dict, answer: str | None, passed: bool, rationale: str
) -> ValidationReport:
    """Build one contracts ``ValidationReport`` for a graded case×repeat.

    A PASS is an ``OK`` verdict; a FAIL (wrong/other object, or no parseable final answer) maps to
    ``SPEC_FAILED`` via ``derive_verdict`` — the failing check's ``detail.code`` is a plain
    ``spec_failed.*`` code so it never misclassifies as ``INVALID_INPUT``/``RECOMPUTE_ERROR``.
    """
    expected = case.get("expected", {})
    if passed:
        code = "ok"
    elif answer is None:
        code = "spec_failed.no_final_answer"
    else:
        code = "spec_failed.wrong_diagnosis"
    check: Check = {
        "id": case["id"],
        "measured": answer,
        "expected": f"{expected.get('object')}: {expected.get('cause')}",
        "passed": passed,
        "detail": {"code": code, "message": rationale},
    }
    banner: ReportBanner = {"freecad_version": "actor-run", "element_map_version": None}
    report: ValidationReport = {
        "schema": "fcb.validation-report/1",
        "banner": banner,
        "subject": {"criterion": case.get("criterion", "G1.2"), "gate": "G1", "case": case["id"]},
        "checks": [check],
    }
    report["verdict"] = derive_verdict(report)
    return report


def _grade_case(
    actor: Actor,
    backend: Backend,
    grader: GraderClient,
    rubric: str,
    case: dict,
    repeats: int,
) -> CaseResult:
    """Run one case ×``repeats`` through the actor+backend and grade every answer.

    Per-repeat: drive the backend to a final answer, grade it against the case's expected findings
    (``{object, cause_keywords}``), record one report. The case-level verdict is majority-of-R.
    """
    question = _question_for(case)
    expected = case.get("expected", {})
    repeat_passes: list[bool] = []
    reports: list[ValidationReport] = []
    allowed = set(actor.tool_names())
    for _ in range(repeats):
        result = actor.run(backend, case["id"], question)
        off_profile = _off_profile_call(result.tool_calls, allowed)
        if off_profile is not None:
            raise ValueError(
                f"case {case['id']!r}: actor called off-profile tool {off_profile!r} "
                f"(read-only surface only; tree access via {SUMMARIZED_TREE_TOOL})"
            )
        try:
            verdict = grader.grade(question, result.final_answer or "", rubric, expected)
        except ValueError as exc:
            # A malformed case (blank expected object / empty cause keywords) is an authoring
            # error in the fixture, not a passing answer — surface it as a typed fail, not a crash.
            verdict = GraderVerdict(pass_=False, matched_expected=False, rationale=str(exc))
        repeat_passes.append(verdict.pass_)
        reports.append(
            _build_case_report(case, result.final_answer, verdict.pass_, verdict.rationale)
        )
    passed = sum(repeat_passes) * 2 > repeats
    return CaseResult(case["id"], case.get("tier", "n30"), repeat_passes, passed, reports)


def _tier_result(tier: str, cases: list[CaseResult], pass_threshold: int) -> TierResult:
    passed_count = sum(1 for c in cases if c.passed)
    passed = passed_count >= pass_threshold
    return TierResult(tier, cases, passed_count, passed, stats.wilson_ci(passed_count, len(cases)))


def run_actor_eval(
    actor: Actor,
    backend: Backend,
    *,
    grader: GraderClient | None = None,
    repeats: int = DEFAULT_REPEATS,
) -> ActorRunResult:
    """Grade the broken-doc error-diagnosis set with tiered n10→n30 escalation (decision 008).

    Grades the 10 ``tier: n10`` cases first; the tier PASSES at ≥8/10. Only a perfect 10/10
    escalates to the 20 ``tier: n30`` cases. Reports the Wilson CI on each tier's case-level pass
    rate. Grading is done exclusively by ``grader`` (the independent ``DeterministicGrader`` by
    default) — the actor never grades itself.
    """
    grader = grader or DeterministicGrader()
    rubric = RUBRIC.read_text(encoding="utf-8")
    cases = _load_broken_cases()
    n10_cases = [c for c in cases if c.get("tier") == "n10"]
    n30_cases = [c for c in cases if c.get("tier") == "n30"]

    if len(n10_cases) != N10_ESCALATE_THRESHOLD:
        raise ValueError(
            f"expected exactly {N10_ESCALATE_THRESHOLD} tier:n10 cases, got {len(n10_cases)} "
            f"(decision 008: grade n=10 first, escalate on a perfect 10/10)"
        )

    n10_graded = [_grade_case(actor, backend, grader, rubric, c, repeats) for c in n10_cases]
    n10 = _tier_result("n10", n10_graded, N10_PASS_THRESHOLD)

    reports: list[ValidationReport] = [r for c in n10_graded for r in c.reports]

    escalated = n10.passed_count >= N10_ESCALATE_THRESHOLD
    n30: TierResult | None = None
    if escalated:
        # A full-set tier grades all 30 cases (the 10 n10 already graded above + the 20 n30) so the
        # escalated Wilson CI is measured over n=30, per decision 008.
        n30_graded = [_grade_case(actor, backend, grader, rubric, c, repeats) for c in n30_cases]
        for c in n30_graded:
            reports.extend(c.reports)
        full = n10_graded + n30_graded
        n30 = _tier_result("n30", full, math.ceil(N30_PASS_RATE * len(full)))

    return ActorRunResult(n10=n10, escalated=escalated, n30=n30, reports=reports)


__all__ = [
    "ActorRunResult",
    "CaseResult",
    "TierResult",
    "run_actor_eval",
    "N10_PASS_THRESHOLD",
    "N10_ESCALATE_THRESHOLD",
    "N30_PASS_RATE",
    "DEFAULT_REPEATS",
    "SUMMARIZED_TREE_TOOL",
]
