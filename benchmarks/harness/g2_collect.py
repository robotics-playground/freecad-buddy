"""Per-criterion collectors for the G2 gate (FreeCAD-free, contracts-only).

Each collector turns a list of ``benchmarks.g2.case_run.CaseOutcome``-shaped results into one
contracts ``ValidationReport`` whose verdict is DERIVED from measured checks. Every threshold is
read from the criterion's ``pass_rule`` in ``gate.yaml``, never duplicated here, so editing the
gate changes what decides the criterion.

An outcome list that could not be produced (no FreeCAD, no command resolver) yields a failing
``INVALID_INPUT`` report naming what was missing — never a vacuous pass and never a skip.

FreeCAD-free to import: the collectors read plain mappings off the outcomes they are handed.
"""

from __future__ import annotations

import re

from benchmarks.harness.report_build import evidence_report, not_collected_report
from freecad_buddy.contracts.report import Check, ValidationReport, require_wilson_ci_for_rates

# A ``pass_rule`` states its bar as a percentage: ">=85% first-attempt pass", "100% of executed
# ops ...", "FullyConstrained == True in >=90% ...". The first percentage in the rule is the bar.
_RATE_IN_RULE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# G2.4's rule is a count ("5/5 flagged"), not a percentage.
_FRACTION_IN_RULE = re.compile(r"(\d+)\s*/\s*(\d+)\s+flagged")


def rate_bar(pass_rule: str) -> float | None:
    """The pass-rate a criterion's ``pass_rule`` declares, as a fraction, or ``None``.

    :param pass_rule: the criterion's declared rule text from ``gate.yaml``.
    """
    match = _RATE_IN_RULE.search(pass_rule or "")
    return float(match.group(1)) / 100.0 if match else None


def flagged_bar(pass_rule: str) -> int | None:
    """The number of scenarios a ``pass_rule`` requires flagged, or ``None``.

    :param pass_rule: the criterion's declared rule text from ``gate.yaml``.
    """
    match = _FRACTION_IN_RULE.search(pass_rule or "")
    return int(match.group(1)) if match else None


def _rate_check(check_id: str, measured: float, bar: float, label: str) -> Check:
    return {
        "id": check_id,
        "measured": round(measured, 4),
        "measured_kind": "rate",
        "expected": f">={bar}",
        "passed": measured >= bar,
        "detail": {
            "code": "ok" if measured >= bar else "invalid_input.below_pass_rule",
            "message": f"{label}: {measured:.4f} vs bar {bar}",
        },
    }


def _rate_report(
    criterion: dict, checks: list, successes: int, population: int
) -> ValidationReport:
    """A criterion report whose banner carries the Wilson interval for its measured rate.

    A rate check declares ``measured_kind: "rate"``, which obliges the report to carry a
    ``banner.wilson_ci`` describing the interval — a bare rate with no interval is the thing
    AD-14 forbids, and ``require_wilson_ci_for_rates`` refuses to build one. The interval is over
    the case population the rate was measured on, after the repeats of each case were folded into
    one verdict.

    :param criterion: the ``gate.yaml`` criterion mapping, read for its id.
    :param checks: the criterion's measured checks, including its rate check.
    :param successes: how many cases satisfied the rate check.
    :param population: how many cases the rate was measured over.
    """
    from freecad_buddy.usecases.stats import wilson_ci

    report = evidence_report(
        criterion["id"],
        checks,
        {"freecad_version": "headless", "wilson_ci": wilson_ci(successes, population)},
    )
    require_wilson_ci_for_rates(report)
    return report


def _executed(outcomes: list) -> list:
    """The outcomes that ran an op, whether it committed or rolled back.

    ``case_run._apply`` returns an ``INVALID_INPUT`` envelope carrying no ``mutation`` block for
    an unresolvable tool name or a confirm the gate refused, and ``run_case`` then skips the undo.
    Such a row is driven but executed nothing, so counting it against a rule reading "100 % of
    **executed** ops" measures the wrong population: it makes a benchmark performing exactly at
    G2.1's >=85 % bar structurally unable to pass G2.2 or G2.3.

    The mutation block is the discriminator rather than the terminal status. A rolled-back op
    executed and carries a full block, but ``run_mutation`` emits ``"OK"`` only on the commit
    path, so selecting by status would drop every op whose verify failed — which is exactly the
    population G2.2's rollback clause and G2.3's snapshot-restore check exist to judge.
    """
    return [o for o in _driven(outcomes) if isinstance(getattr(o, "mutation", None), dict)]


def _committed(outcomes: list) -> list:
    """The outcomes whose op committed, which are the only ones there is anything to undo for.

    Narrower than :func:`_executed` by exactly the rolled-back ops: ``run_case`` skips
    ``document_undo`` for them, so they carry no ``undo`` record and counting them in an undo
    rate would report a missing expectation as a failed undo.
    """
    return [o for o in _driven(outcomes) if getattr(o, "status", None) == "OK"]


def _targets(outcome: object, validators: list) -> bool:
    """Whether the case's declared ``targets_validator`` names one of ``validators``.

    A case declares it as ``<name>@<module path>``; the name before the ``@`` is what a
    criterion's ``cited_validators`` lists. A case declaring nothing targets nothing, which keeps
    a fault suite out of a criterion's population until it says which validator it is aimed at.
    """
    declared = getattr(outcome, "targets_validator", None)
    if not isinstance(declared, str):
        return False
    return declared.split("@", 1)[0] in validators


def _is_fault(outcome: object) -> bool:
    """Whether the outcome came from a fault case rather than the command benchmark."""
    return getattr(outcome, "fault_kind", None) is not None


def _unexecuted_note(driven: list, applied: list) -> str:
    """How many driven cases never executed an op, for the criterion's message."""
    refused = {o.case_id for o in driven} - {o.case_id for o in applied}
    return (
        f" ({len(refused)} driven case(s) executed no op: {', '.join(sorted(refused))})"
        if (refused)
        else ""
    )


def _failed_check(check_id: str, message: str) -> Check:
    return {
        "id": check_id,
        "measured": None,
        "expected": None,
        "passed": False,
        "detail": {"code": "invalid_input.g2_criterion_unmet", "message": message},
    }


def _note(messages: list[str], message: str) -> None:
    """Record a per-case failure message once, however many repeats produced it."""
    if message not in messages:
        messages.append(message)


def _driven(outcomes: list) -> list:
    """The outcomes that were actually driven — an unresolved case measured nothing."""
    return [o for o in outcomes if getattr(o, "status", None) != "UNRESOLVED"]


def _undriven_report(criterion: dict, outcomes: list) -> ValidationReport | None:
    """The uncollected report for a split that did not fully execute, or ``None`` when it did.

    An unresolved case measured nothing, so counting a rate over only the cases that ran would
    divide by a denominator the split silently shrank: 39 refused commands and one clean pass
    would report a 100 % rate. Any unresolved case makes the criterion uncollected instead.

    :param criterion: the ``gate.yaml`` criterion mapping, read for its id.
    :param outcomes: the split's case outcomes.
    """
    unresolved = _unresolved_reasons(outcomes)
    if not unresolved and outcomes:
        return None
    return not_collected_report(
        criterion["id"],
        "split not fully driven: " + ("; ".join(unresolved) or "no case outcomes"),
    )


def _unresolved_reasons(outcomes: list) -> list[str]:
    seen: list[str] = []
    for outcome in outcomes:
        if getattr(outcome, "status", None) != "UNRESOLVED":
            continue
        reason = getattr(outcome, "error", None) or "unresolved"
        if reason not in seen:
            seen.append(reason)
    return seen


def _majority_passed(outcomes: list) -> dict[str, bool]:
    """Whether each case passed a majority of its repeats, keyed by case id."""
    return _majority_by_case(outcomes, lambda outcome: bool(outcome.passed))


def _majority_by_case(outcomes: list, predicate) -> dict[str, bool]:
    """Whether ``predicate`` held for a majority of each case's repeats, keyed by case id.

    A split is driven at R repeats per case, so ``outcomes`` holds one row per case per repeat.
    Every criterion grades cases, not rows: a rule reading "100 % of cases" or "5/5 flagged"
    counts distinct cases, and folding the repeats first is what makes R a majority vote rather
    than a multiplier on the population.

    :param outcomes: the split's case outcomes, one per case per repeat.
    :param predicate: called with one outcome, returning whether that repeat satisfied the check.
    """
    tallies: dict[str, list[bool]] = {}
    for outcome in outcomes:
        tallies.setdefault(outcome.case_id, []).append(bool(predicate(outcome)))
    return {
        case_id: sum(1 for held in results if held) * 2 > len(results)
        for case_id, results in tallies.items()
    }


def collect_g2_1(criterion: dict, outcomes: list) -> ValidationReport:
    """Grade the command benchmark: the majority-of-R pass rate against the criterion's bar.

    A case whose command errored counts as a failed case, never as an exclusion; a case that was
    never driven makes the criterion uncollected rather than shrinking the denominator.
    """
    bar = rate_bar(criterion.get("pass_rule", ""))
    if bar is None:
        return not_collected_report(criterion["id"], "pass_rule declares no rate bar")
    unresolved = _unresolved_reasons(outcomes)
    if unresolved or not outcomes:
        return not_collected_report(
            criterion["id"],
            "command benchmark not driven: " + ("; ".join(unresolved) or "no case outcomes"),
        )
    # The fault suites validate validators and never count toward this pass rate (`gate.yaml`,
    # and validation-harness-design.md §1). A dev `run G2` drives them into the same outcome
    # list, and a planted defect is designed to fail its assertions — counting one here would
    # report the benchmark as failing commands it never ran.
    commands = [o for o in outcomes if not _is_fault(o)]
    if not commands:
        return not_collected_report(
            criterion["id"], "command benchmark not driven: the run holds only fault cases"
        )
    majority = _majority_passed(commands)
    passing = sum(1 for passed in majority.values() if passed)
    rate = passing / len(majority)
    return _rate_report(
        criterion,
        [_rate_check("G2.1.rate", rate, bar, "majority-of-R first-attempt pass rate")],
        passing,
        len(majority),
    )


def collect_g2_2(criterion: dict, outcomes: list) -> ValidationReport:
    """Grade universal post-verify + rollback over every executed op.

    Every executed op must carry a ``post_verify`` record, and every failed verify must carry
    ``rolled_back`` with a proven rollback and a human-readable explanation. An op whose rollback
    is recorded but unproven is a failure, not a missing record.
    """
    bar = rate_bar(criterion.get("pass_rule", ""))
    if bar is None:
        return not_collected_report(criterion["id"], "pass_rule declares no rate bar")
    undriven = _undriven_report(criterion, outcomes)
    if undriven is not None:
        return undriven
    driven = _driven(outcomes)
    applied = _executed(outcomes)
    if not applied:
        return not_collected_report(
            criterion["id"], "no driven case executed an op: nothing to measure post-verify over"
        )

    def _has_record(outcome) -> bool:
        mutation = outcome.mutation if isinstance(outcome.mutation, dict) else {}
        return isinstance(mutation.get("post_verify"), dict)

    with_record = _majority_by_case(applied, _has_record)
    rollback_failures: list[str] = []
    for outcome in applied:
        mutation = outcome.mutation if isinstance(outcome.mutation, dict) else {}
        post_verify = mutation.get("post_verify")
        if not isinstance(post_verify, dict):
            _note(rollback_failures, f"{outcome.case_id}: executed op carries no post_verify")
            continue
        if post_verify.get("passed") is True:
            continue
        if mutation.get("rolled_back") is not True:
            _note(rollback_failures, f"{outcome.case_id}: failed verify without rollback")
        elif not mutation.get("rollback_proven"):
            _note(rollback_failures, f"{outcome.case_id}: rollback recorded but unproven")
        elif not str(post_verify.get("explanation") or "").strip():
            _note(rollback_failures, f"{outcome.case_id}: rollback without an explanation")

    recorded = sum(1 for held in with_record.values() if held)
    checks = [
        _rate_check(
            "G2.2.post_verify",
            recorded / len(with_record),
            bar,
            "executed ops with a post_verify" + _unexecuted_note(driven, applied),
        )
    ]
    checks.append(
        _failed_check("G2.2.rollback", "; ".join(rollback_failures))
        if rollback_failures
        else {
            "id": "G2.2.rollback",
            "measured": 0,
            "expected": 0,
            "passed": True,
            "detail": {"code": "ok", "message": "every failed verify rolled back with a reason"},
        }
    )
    return _rate_report(criterion, checks, recorded, len(with_record))


def collect_g2_3(criterion: dict, outcomes: list) -> ValidationReport:
    """Grade exact undo: ``matches_pre_op`` over every benchmark op.

    ``matches_pre_op`` of ``None`` means no expectation was supplied, which is a collector defect
    rather than a passing undo, so it is counted as a failure.
    """
    bar = rate_bar(criterion.get("pass_rule", ""))
    if bar is None:
        return not_collected_report(criterion["id"], "pass_rule declares no rate bar")
    undriven = _undriven_report(criterion, outcomes)
    if undriven is not None:
        return undriven
    driven = _driven(outcomes)
    # Two populations, not one. Only a committed op has anything to undo, while the snapshot
    # restore only ever accompanies a rollback — so grading both over one list would either
    # hide the restores or count each rolled-back op as an undo that failed to match.
    applied = _committed(outcomes)
    if not applied:
        return not_collected_report(
            criterion["id"], "no driven case executed an op: nothing to undo"
        )

    missing_expectation: list[str] = []
    for outcome in applied:
        undo = outcome.undo if isinstance(outcome.undo, dict) else {}
        if undo.get("matches_pre_op") is None:
            _note(missing_expectation, outcome.case_id)

    via_snapshot: list[str] = []
    for outcome in _executed(outcomes):
        mutation = outcome.mutation if isinstance(outcome.mutation, dict) else {}
        if mutation.get("rollback_proven") == "rolled_back_via_snapshot":
            _note(via_snapshot, outcome.case_id)

    matched = _majority_by_case(
        applied,
        lambda o: (o.undo if isinstance(o.undo, dict) else {}).get("matches_pre_op") is True,
    )
    reached = sum(1 for held in matched.values() if held)
    checks = [
        _rate_check(
            "G2.3.undo",
            reached / len(matched),
            bar,
            "ops whose undo reached the pre-op hash" + _unexecuted_note(driven, applied),
        )
    ]
    if missing_expectation:
        checks.append(
            _failed_check(
                "G2.3.expectation",
                "undo returned no matches_pre_op verdict (no expect_fingerprint reached "
                "document_undo) for: " + ", ".join(missing_expectation),
            )
        )
    checks.append(
        {
            "id": "G2.3.snapshot_path",
            "measured": len(via_snapshot),
            "expected": "reported",
            "passed": True,
            "detail": {
                "code": "ok",
                "message": f"snapshot-restore path taken by: {', '.join(via_snapshot) or 'none'}",
            },
        }
    )
    return _rate_report(criterion, checks, reached, len(matched))


def collect_g2_4(
    criterion: dict, outcomes: list, *, element_map_available: bool | None
) -> ValidationReport:
    """Grade the TNP guard: every provoking scenario flagged, no control falsely flagged.

    The element-map probe runs first: ``audit_references`` returns wholesale ``UNSUPPORTED`` when
    no element map is available, which must be an explicit criterion failure rather than a clean
    report.
    """
    if element_map_available is not True:
        return not_collected_report(
            criterion["id"],
            "element map unavailable: audit_references reports UNSUPPORTED, never clean",
        )
    required = flagged_bar(criterion.get("pass_rule", ""))
    if required is None:
        return not_collected_report(criterion["id"], "pass_rule declares no flagged count")
    # The criterion grades the TNP fault suite, not the command benchmark and not the other
    # fault suites. A dev command case declares no `fault.kind`, and a defect planted for a
    # different validator is one this guard is right to leave CLEAN — scoring either here would
    # report a false-clean naming a cause that never happened. The population is the cases whose
    # declared `targets_validator` names the validator this criterion cites.
    cited = criterion.get("cited_validators") or []
    driven = [o for o in _driven(outcomes) if _is_fault(o) and _targets(o, cited)]
    if not driven:
        return not_collected_report(
            criterion["id"],
            "no TNP scenario driven: "
            + (
                "; ".join(_unresolved_reasons(outcomes))
                or "the split holds no fault-declaring case"
            ),
        )

    # The rule counts SCENARIOS, not driven rows: a split is driven at R repeats per case, so
    # tallying rows would let one scenario flagged five times satisfy "5/5 flagged", and would
    # count a falsely-flagged control toward the same total. Fold each case's repeats into one
    # majority verdict first, then count distinct cases.
    def _is_flagged(outcome) -> bool:
        mutation = outcome.mutation if isinstance(outcome.mutation, dict) else {}
        post_verify = mutation.get("post_verify") or {}
        audit = post_verify.get("tnp_audit") if isinstance(post_verify, dict) else None
        return isinstance(audit, dict) and audit.get("status") == "FLAGGED"

    flagged_case = _majority_by_case(driven, _is_flagged)
    is_defect = {
        outcome.case_id: getattr(outcome, "fault_kind", None) != "clean_control"
        for outcome in driven
    }

    flagged = 0
    false_clean: list[str] = []
    false_flag: list[str] = []
    for case_id, was_flagged in flagged_case.items():
        if was_flagged and is_defect[case_id]:
            flagged += 1
        elif was_flagged:
            false_flag.append(case_id)
        elif is_defect[case_id]:
            false_clean.append(case_id)

    checks: list[Check] = [
        {
            "id": "G2.4.flagged",
            "measured": flagged,
            "expected": required,
            "passed": flagged >= required,
            "detail": {
                "code": "ok" if flagged >= required else "invalid_input.tnp_scenarios_unflagged",
                "message": f"{flagged} scenarios flagged, rule requires {required}",
            },
        }
    ]
    if false_clean:
        checks.append(
            _failed_check("G2.4.false_clean", f"reported clean: {', '.join(false_clean)}")
        )
    if false_flag:
        checks.append(
            _failed_check("G2.4.false_flag", f"controls flagged: {', '.join(false_flag)}")
        )
    return evidence_report(criterion["id"], checks)


def collect_g2_5(criterion: dict, outcomes: list) -> ValidationReport:
    """Grade the sketch benchmark: the ``fully_constrained`` rate over the sketch cases.

    A sketch that never built reports ``False`` rather than being excluded, so a benchmark that
    failed to produce sketches cannot raise the rate by shrinking its denominator.
    """
    bar = rate_bar(criterion.get("pass_rule", ""))
    if bar is None:
        return not_collected_report(criterion["id"], "pass_rule declares no rate bar")
    undriven = _undriven_report(criterion, outcomes)
    if undriven is not None:
        return undriven
    sketches = [o for o in _driven(outcomes) if getattr(o, "op_type", "") == "sketch"]
    if not sketches:
        return not_collected_report(criterion["id"], "no sketch case in the split")

    def _constrained(outcome) -> bool:
        mutation = outcome.mutation if isinstance(outcome.mutation, dict) else {}
        post_verify = mutation.get("post_verify") or {}
        return isinstance(post_verify, dict) and post_verify.get("fully_constrained") is True

    per_case = _majority_by_case(sketches, _constrained)
    constrained = sum(1 for held in per_case.values() if held)
    return _rate_report(
        criterion,
        [
            _rate_check(
                "G2.5.fully_constrained",
                constrained / len(per_case),
                bar,
                "sketches reaching FullyConstrained",
            )
        ],
        constrained,
        len(per_case),
    )


def collect_g2_6(criterion: dict) -> ValidationReport:
    """Report G2.6 uncollected: no ablation harness exists to run.

    The ablation harness is shared infrastructure assigned to Epic 6, which is backlog, so no
    ablation runner, no McNemar and no newly-drafted-skill marker exist. The criterion fails with
    that dependency named rather than being synthesized or silently dropped.
    """
    return not_collected_report(
        criterion["id"],
        "no ablation harness: the ablation runner and paired-delta reporting are Epic-6 shared "
        "infrastructure (Epic 6 is backlog); see docs/decisions/015-g2-6-ablation-deferred.md",
    )
