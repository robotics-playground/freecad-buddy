"""Fault scorer for the G3 validators (run under uv via ``runner.py faults G3``).

Computes sensitivity / false-alarm + a Wilson CI over the cases each validator ACTUALLY RAN, and
records an explicit ``not_scored`` reason for a validator whose population is empty rather than
writing a fabricated ``0.0``. A zero that means "the validator missed every defect" and a zero
that means "no defect was driveable" are different facts, and a registry that spells them the
same way lets an unmeasured validator be cited as a measured one.

Planting a G3 fault means driving a plan through the designer loop and measuring what it built.
The loop exists as of story 4.5, so the ``corrupted_plan`` and ``g3_assertions`` cases are now
driven — but the driving happens *inside* FreeCAD, where the geometry lives, so this uv-side
scorer reads the per-case outcomes ``score_g3_infc.py`` wrote rather than re-running them. A run
whose results file is absent or stale is reported ``not_scored`` naming that, never scored as
zero: an undriven defect says nothing about the validator's sensitivity.

The visual-judge cases are driven too, and their verdicts come from a judge grading the rendered
images against ``visual-judge/RUBRIC.md`` — a vision model reached over a client, or a
vision-capable agent reading the PNGs directly. Either writes a verdict per case to
``visual_judge.json`` and this scorer computes the bar from that, exactly as it does for the
in-FreeCAD drivers. Decision 017 governs the automatic IN-LOOP judge (``usecases/verify_visual.py``,
driven headless with no agent attached); it never governed a one-off offline grading, and reading it
as a blanket ban is what kept this row unscored after the suite was gradeable.

Writes only the G3 validator blocks of ``_registry/validators.yaml`` through the shared
``merge_validators_yaml``, so no other gate's block is clobbered. Exits 0 when the suite is
structurally sound, 1 when it is not.
"""

from __future__ import annotations

import datetime
import hashlib
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# The export scorer owns the shared read-merge-write for validators.yaml; import it by path so
# every scorer writes through one merge-writer and none full-clobbers another's blocks.
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import stats  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05

# The source files whose bytes make up each validator's ``validator_sha``. These MUST match
# runner.py's ``_VALIDATOR_SOURCES`` entries for the same names, or a clean working tree reads
# as stale at gate-verdict time.
VALIDATOR_SOURCES = {
    "g3_assertions": (REPO_ROOT / "benchmarks" / "harness" / "assertions.py",),
    # Three files, matching runner.py's entry: the entry-gate seam that fixes the verdict schema,
    # the use case that owns the fail-closed rule and the legibility gate, and the client carrying
    # the rubric. AD-19 requires a rubric edit to stale the sensitivity run, so the client's bytes
    # belong in the digest.
    "visual_judge": (
        REPO_ROOT / "benchmarks" / "g3" / "judge.py",
        SRC / "freecad_buddy" / "usecases" / "verify_visual.py",
        SRC / "freecad_buddy" / "adapters" / "visual_judge_client.py",
    ),
    "corrupted_plan": (SRC / "freecad_buddy" / "usecases" / "designer_loop.py",),
    # Cited by G3.2 and G3.3 and targeted by NO fault case. It is scored anyway so the registry
    # carries a row: `check_validator_currency` reports a missing row as "not in registry", a
    # structural failure that survives Phase 3 landing, whereas a row whose `not_scored` names the
    # absent suite is the honest statement and is discharged the moment a suite exists.
    "verify_recompute": (SRC / "freecad_buddy" / "usecases" / "verify.py",),
}

_SUITE_BY_VALIDATOR = {
    "g3_assertions": "g3/fault-injection/assertions/",
    "visual_judge": "g3/fault-injection/visual-judge/",
    "corrupted_plan": "g3/fault-injection/corrupted-plan/",
    "verify_recompute": "g3/fault-injection/recompute/",
}

# Validators that are cited by a G3 criterion but have no fault suite yet. Scored as explicitly
# unmeasured rather than omitted: a validator with no registry row reports "not in registry" at
# leg-b, which reads as a wiring mistake, while an empty-suite row states the real gap.
_SUITELESS_VALIDATORS: frozenset[str] = frozenset()

# Validators whose verdicts this scorer cannot produce itself: it renders no image and calls no
# judge, so with no graded results file it measures nothing however driveable the fixtures are.
#
# The gap is the absence of VERDICTS, not the absence of a credential. A judge may be a vision
# model reached over a client or a vision-capable agent reading the PNGs directly; either way it
# records a verdict per case in the validator's results file and the bar is computed from that.
# Decision 017 governs the automatic IN-LOOP judge (``usecases/verify_visual.py``, driven headless
# with no agent attached) and never governed a one-off offline grading — reading it as a blanket
# ban is what kept this row unscored after the suite was gradeable.
_LIVE_CALL_VALIDATORS = frozenset({"visual_judge"})

_LIVE_CALL_GAP = (
    "and no judge verdict was recorded: this scorer renders no image and calls no judge, so the "
    "visual leg is measured only when a judge — a vision model over a client, or a vision-capable "
    "agent reading the rendered PNGs — grades the suite against visual-judge/RUBRIC.md and writes "
    "its per-case verdicts to visual_judge.json. Absent that file the bar is unmeasured, never zero"
)


def _with_live_call_gap(not_scored: str | None) -> str:
    """Append the operator-gated live-call gap to a validator's ``not_scored`` reason.

    Applied even when the case arithmetic found no gap: driveable fixtures alone cannot produce a
    verdict here, so a row that stopped saying so would let an unmeasured judge read as measured.
    """
    if not_scored is None:
        return f"every fault case is driveable {_LIVE_CALL_GAP}"
    return f"{not_scored}; {_LIVE_CALL_GAP}"


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _load_case(case_yaml: Path) -> dict:
    data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SuiteError(f"{case_yaml}: case.yaml must be a mapping, got {type(data).__name__}")
    data["dir"] = case_yaml.parent
    return data


def _suite_case_files() -> list[Path]:
    """Every G3 fault ``case.yaml``, ordered by its suite-relative POSIX path.

    The exact-name filter keeps the set platform-independent: ``rglob`` is case-insensitive on
    Windows, so a miscased ``Case.YAML`` would otherwise be scored and hashed there and not on
    Linux CI.
    """
    return sorted(
        (p for p in HERE.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(HERE).as_posix(),
    )


def _validator_name(case: dict) -> str:
    """The validator a case targets, read from its ``targets_validator`` declaration."""
    declared = case.get("targets_validator")
    if not isinstance(declared, str) or not declared:
        raise SuiteError(f"case {case.get('id', '<no id>')!r}: missing 'targets_validator'")
    return declared.split("@", 1)[0]


def _validator_sha(name: str) -> str:
    """SHA-256 over a validator's sources and the cases scored against it.

    The suite is part of the validator: a score-preserving case edit changes the population the
    committed sensitivity was measured over, so it must stale the run too. Each case contributes
    its suite-relative path and its bytes, length-prefixed so the concatenation is unambiguous.

    A source file that cannot be read yields ``""`` — the same value ``runner.py``'s hasher
    produces for it, so an unwritten validator (``corrupted_plan``, whose loop is story 4.5) reads
    as stale on both sides rather than as a digest nothing backs.
    """
    sources = VALIDATOR_SOURCES.get(name)
    if sources is None:
        raise SuiteError(f"unknown validator {name!r} (no source set declared)")
    digest = hashlib.sha256()
    for path in sources:
        try:
            digest.update(path.read_bytes())
        except OSError:
            return ""
    cases = [p for p in _suite_case_files() if _validator_name(_load_case(p)) == name]
    if not cases:
        digest.update(b"\x00no-fault-suite")
        return digest.hexdigest()
    for case_yaml in cases:
        identity = case_yaml.relative_to(HERE).as_posix().encode("utf-8")
        try:
            content = case_yaml.read_bytes()
        except OSError as exc:
            raise SuiteError(f"unreadable case {case_yaml}: {exc}") from exc
        digest.update(len(identity).to_bytes(4, "big"))
        digest.update(identity)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _partition(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split cases into (planted defects, clean controls), rejecting a mis-tagged case.

    ``fault.kind`` and ``fault.expectation`` must agree, or the case is silently mis-partitioned
    and both bars are measured over the wrong population.
    """
    for case in cases:
        fault = case.get("fault")
        if not isinstance(fault, dict):
            raise SuiteError(f"case {case.get('id', '<no id>')!r}: 'fault' must be a mapping")
        kind = fault.get("kind")
        expectation = fault.get("expectation")
        if (kind == "planted_defect") != (expectation == "DETECT") or (kind == "clean_control") != (
            expectation == "PASS_CLEAN"
        ):
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: fault.kind {kind!r} disagrees with "
                f"expectation {expectation!r} (planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
            )
    planted = [c for c in cases if c["fault"]["expectation"] == "DETECT"]
    controls = [c for c in cases if c["fault"]["expectation"] == "PASS_CLEAN"]
    return planted, controls


# The fixture values a case declares when its fault is planted by a driver rather than carried in
# a file. ``driven-by-designer-loop`` runs a plan through the designer loop; the plan IS the
# fixture. ``driven-by-mutation-bracket`` runs a planted op through ``transaction.run_mutation``;
# the document the bracket leaves behind IS the fixture. Neither has a file to find on disk.
_DRIVEN_FIXTURES = frozenset({"driven-by-designer-loop", "driven-by-mutation-bracket"})

# Where the in-FreeCAD drivers leave the per-case outcomes they measured. ``verify_recompute`` has
# its own driver (``score_recompute_infc.py``) because it grades document state rather than a plan
# the designer loop executes; the two share nothing but this handoff shape.
DRIVEN_RESULTS = {
    "corrupted_plan": HERE / "corrupted_plan.json",
    "g3_assertions": HERE / "g3_assertions.json",
    "verify_recompute": HERE / "verify_recompute.json",
    # The visual leg's outcomes are not written by an in-FreeCAD driver. A judge reads the rendered
    # images and records a verdict per case, in this same shape. That judge may be a vision model
    # reached over a client, or a vision-capable AGENT inspecting the PNGs directly — the file does
    # not care which, and neither does the bar. Decision 017 governs the automatic IN-LOOP judge
    # (``usecases/verify_visual.py``, driven headless by the harness with no agent attached); it has
    # never governed a one-off offline grading of a fixed suite, and reading it that way is what
    # left this row unscored longer than it needed to be.
    "visual_judge": HERE / "visual_judge.json",
}

# The in-FreeCAD driver that writes each validator's results file, named in the ``not_scored``
# reason so a reader is told which command to run rather than the wrong one.
_DRIVER_BY_VALIDATOR = {
    "corrupted_plan": "score_g3_infc.py",
    "g3_assertions": "score_g3_infc.py",
    "verify_recompute": "score_recompute_infc.py",
    "visual_judge": (
        "render_visual_judge.py to build the images, then a judge grading them against "
        "visual-judge/RUBRIC.md and writing visual_judge.json"
    ),
}


def _driveable(case: dict, unscorable: dict[str, str]) -> bool:
    """Whether the case's fault can be planted AND decided by its own spec.

    Three shapes count. A case declaring one of the ``_DRIVEN_FIXTURES`` values plus a
    ``planted_op`` is planted by running that op through its driver, so there is no file to look
    for. A case naming a real fixture file is driveable when that file is on disk. A ``pending``
    case is neither. A case whose op the driver reported unscorable is excluded too — its fault is
    invisible to the verdict its spec declares, so counting it as a miss would blame the validator
    for a verdict the case cannot reach.

    All three exclusions are SKIPPED rather than counted, which is the whole point of
    ``not_scored``: an undriven defect says nothing about the validator's sensitivity.
    """
    if case.get("id") in unscorable:
        return False
    fixture = case.get("fixture")
    if not isinstance(fixture, str) or fixture == "pending":
        return False
    if fixture in _DRIVEN_FIXTURES:
        return isinstance(case.get("planted_op"), str) and bool(case["planted_op"])
    return (case["dir"] / fixture).is_file()


def _driven_results(name: str) -> dict | None:
    """The result file ``score_g3_infc.py`` wrote for ``name``, or ``None`` when it has not run.

    Read rather than recomputed: the measurement needs the geometry, which only exists inside
    FreeCAD. A missing or unreadable file yields ``None``, which the caller reports as
    ``not_scored`` — never as a set of misses.
    """
    path = DRIVEN_RESULTS.get(name)
    if path is None or not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _unscorable_cases(results: dict | None) -> dict[str, str]:
    """``{case_id: reason}`` for every case the driver could not score, from its results file."""
    if not results:
        return {}
    skipped = results.get("skipped")
    if not isinstance(skipped, list):
        return {}
    return {
        entry["id"]: str(entry.get("reason", ""))
        for entry in skipped
        if isinstance(entry, dict) and "id" in entry
    }


def _driven_outcomes(results: dict | None) -> dict[str, str] | None:
    """The ``{case_id: outcome}`` the driver measured, or ``None`` when it has not run."""
    if not results:
        return None
    rows = results.get("rows")
    if not isinstance(rows, list):
        return None
    return {row["id"]: row["outcome"] for row in rows if isinstance(row, dict) and "id" in row}


def score_validator(name: str, cases: list[dict]) -> dict:
    """Score one validator over the cases that actually ran; never invent a rate.

    Returns a result carrying the measured counts plus, when a bar could not be measured at all,
    a ``not_scored`` reason naming which arm was empty and why.
    """
    results = _driven_results(name)
    unscorable = _unscorable_cases(results)

    planted, controls = _partition(cases)
    driveable_planted = [c for c in planted if _driveable(c, unscorable)]
    driveable_controls = [c for c in controls if _driveable(c, unscorable)]
    skipped = len(planted) - len(driveable_planted) + len(controls) - len(driveable_controls)

    # The outcomes come from the run that drove them inside FreeCAD. A validator whose driver has
    # not run scores nothing rather than zero; the `ungraded` branch below names that.
    outcomes = _driven_outcomes(results) or {}
    detected = sum(1 for c in driveable_planted if outcomes.get(c["id"]) == "DETECTED")
    flagged = sum(1 for c in driveable_controls if outcomes.get(c["id"]) == "FALSE_ALARM")
    ungraded = [c["id"] for c in driveable_planted + driveable_controls if c["id"] not in outcomes]

    not_scored = None
    if not cases:
        # Distinct from "cases exist but none is driveable": there is no suite at all, so the gap
        # is an unauthored fault suite rather than an unbuilt runtime.
        not_scored = (
            "no fault case targets this validator: it is cited by a G3 criterion but no suite "
            "exists to measure it over, so neither sensitivity nor false_alarm is defined"
        )
    elif not driveable_planted and not driveable_controls:
        not_scored = (
            f"no driveable case: all {len(cases)} case(s) declare a pending fixture, so neither "
            f"sensitivity nor false_alarm was measured"
        )
    elif ungraded:
        # The cases CAN be driven and were not. Counting an undriven case as a miss would blame
        # the validator for a run nobody made, and counting it as clean would inflate the score;
        # naming the unrun driver is the only honest reading.
        not_scored = (
            f"{len(ungraded)} driveable case(s) carry no measured outcome: planting a G3 fault "
            f"needs the live document, so the cases are driven by "
            f"`FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd benchmarks/g3/fault-injection/"
            f"{_DRIVER_BY_VALIDATOR.get(name, 'score_g3_infc.py')}`, whose results file this "
            f"scorer reads. Run it and re-score. Ungraded: {sorted(ungraded)}"
        )
    elif not driveable_planted:
        not_scored = (
            f"no driveable planted defect: {len(driveable_controls)} clean control(s) ran and "
            f"{len(planted)} planted case(s) were skipped, so sensitivity is unmeasured rather "
            f"than zero"
        )
    elif not driveable_controls:
        not_scored = (
            f"no driveable clean control: {len(driveable_planted)} planted case(s) ran and "
            f"{len(controls)} control(s) were skipped, so false_alarm is vacuously 0 rather "
            f"than measured"
        )

    # Fires only when no verdicts were recorded. A results file carrying a graded row per case IS
    # the measurement, so a scorer that refused it whenever it held no credential of its own would
    # report "unmeasured" over a population that was in fact measured — the mirror image of the
    # fabricated score this whole registry exists to prevent.
    if name in _LIVE_CALL_VALIDATORS and not (driveable_planted or controls):
        not_scored = _with_live_call_gap(not_scored)

    # A case the driver could not score shrinks the population the number was measured over. That
    # is a CAVEAT on a real measurement, not the absence of one, so it is carried separately from
    # `not_scored` — folding it in would make "8 of 8 detected, 2 cases their spec cannot decide"
    # read identically to "nothing was measured". A reader who sees `sensitivity 1.0` over `n: 8`
    # still needs to find out which 2 are missing and why, which is what `excluded_reasons` is for.
    excluded = sorted(case["id"] for case in planted + controls if case.get("id") in unscorable)

    return {
        "planted": len(planted),
        "controls": len(controls),
        "driveable_planted": len(driveable_planted),
        "driveable_controls": len(driveable_controls),
        "skipped": skipped,
        "excluded": excluded,
        "excluded_reasons": {case_id: unscorable[case_id] for case_id in excluded},
        "detected": detected,
        "flagged": flagged,
        "sensitivity": stats.sensitivity(detected, len(driveable_planted)),
        "false_alarm": stats.false_alarm(flagged, len(driveable_controls)),
        "wilson_ci": stats.wilson_ci(detected, len(driveable_planted)),
        "not_scored": not_scored,
        # Provenance the results file carries about HOW the number was obtained, forwarded onto the
        # registry row. A rate is not self-describing: `sensitivity: 1.0` over n=5 reads as
        # authoritative unless the row also says who graded it and that its interval is wide. These
        # are the same class of disclosure as `excluded_unscorable` below — a caveat on a real
        # measurement, which belongs beside the number rather than only in a separate record.
        **{
            key: (results or {})[key]
            for key in ("graded_by", "independence_caveat", "low_confidence", "record")
            if (results or {}).get(key)
        },
    }


def score() -> dict[str, dict]:
    """Score every declared G3 validator; return ``{validator: result}``."""
    by_validator: dict[str, list[dict]] = {}
    for case_yaml in _suite_case_files():
        case = _load_case(case_yaml)
        by_validator.setdefault(_validator_name(case), []).append(case)

    unknown = sorted(set(by_validator) - set(VALIDATOR_SOURCES))
    if unknown:
        raise SuiteError(f"case(s) target undeclared validator(s): {', '.join(unknown)}")

    results: dict[str, dict] = {}
    for name in sorted(VALIDATOR_SOURCES):
        cases = by_validator.get(name, [])
        if not cases and name not in _SUITELESS_VALIDATORS:
            raise SuiteError(
                f"validator {name!r} has no fault case: a cited validator with no suite cannot "
                f"be measured, and an empty suite scores vacuously"
            )
        results[name] = score_validator(name, cases)
    return results


def _render_block(name: str, sha: str, run: dict) -> str:
    """Render one validator's validators.yaml block (merged via ``merge_validators_yaml``)."""
    wilson = run["wilson_ci"]
    lines = [
        f"{name}:\n",
        f"  suite: {_SUITE_BY_VALIDATOR[name]}\n",
        f'  validator_sha: "{sha}"\n',
        "  last_run:\n",
        f"    run_id: {run['run_id']}\n",
        f"    sensitivity: {run['sensitivity']}\n",
        f"    false_alarm: {run['false_alarm']}\n",
        f"    date: {run['date']}\n",
    ]
    if run.get("not_scored"):
        lines.append(f"    not_scored: {run['not_scored']!r}\n")
    if run.get("skipped_cases"):
        lines.append(f"    skipped_cases: {run['skipped_cases']}\n")
    # A measured rate whose population was narrowed must say so on the row. Without this a reader
    # sees ``sensitivity: 1.0`` over ``n: 8`` and has no way to learn that two authored defects
    # were left out, or that the reason is their own spec rather than the validator.
    if run.get("excluded_reasons"):
        lines.append("    excluded_unscorable:\n")
        for case_id, reason in sorted(run["excluded_reasons"].items()):
            lines.append(f"      {case_id}: {reason!r}\n")
    # How the number was obtained, when the results file declared it. A rate graded by a judge
    # rather than re-executed deterministically must say so beside the rate, or a reader takes a
    # 1.000 over n=5 for a stronger claim than it is.
    for key in ("graded_by", "independence_caveat", "low_confidence", "record"):
        if run.get(key):
            lines.append(f"    {key}: {run[key]!r}\n")
    lines.extend(
        [
            "    wilson_ci:\n",
            f"      rate: {wilson['rate']}\n",
            f"      low: {wilson['low']}\n",
            f"      high: {wilson['high']}\n",
            f"      n: {wilson['n']}\n",
            f"      r: {wilson['r']}\n",
        ]
    )
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Score the G3 suites and merge-write their validator blocks.

    ``--check`` computes the results WITHOUT writing, so CI can verify the suite's structure while
    the working tree stays clean.
    """
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    results = score()

    today = datetime.date.today().isoformat()
    blocks: dict[str, str] = {}
    for name, result in sorted(results.items()):
        sys.stderr.write(
            f"  {name:16s} planted={result['planted']:2d} "
            f"(driven {result['driveable_planted']:2d}) "
            f"controls={result['controls']:2d} (driven {result['driveable_controls']:2d}) "
            f"skipped={result['skipped']:2d}\n"
        )
        if result["not_scored"]:
            sys.stderr.write(f"  {'':16s} NOT SCORED: {result['not_scored']}\n")
        else:
            sys.stderr.write(
                f"  {'':16s} sensitivity={result['sensitivity']:.3f} "
                f"false_alarm={result['false_alarm']:.3f}\n"
            )
        for case_id, reason in sorted((result.get("excluded_reasons") or {}).items()):
            sys.stderr.write(f"  {'':16s} EXCLUDED {case_id}: {reason}\n")
        wilson = result["wilson_ci"]
        run = {
            "run_id": f"g3-{today}-1",
            "sensitivity": round(result["sensitivity"], 4),
            "false_alarm": round(result["false_alarm"], 4),
            "date": today,
            "not_scored": result["not_scored"],
            "skipped_cases": result["skipped"],
            "excluded_reasons": result.get("excluded_reasons") or {},
            "wilson_ci": {
                "rate": round(wilson["rate"], 4),
                "low": round(wilson["low"], 4),
                "high": round(wilson["high"], 4),
                "n": wilson["n"],
                "r": wilson["r"],
            },
            # Provenance the results file declared, forwarded so it lands on the row beside the
            # rate. A number is not self-describing: `sensitivity: 1.0` over n=5 reads as
            # authoritative unless the row also says who graded it and how wide the interval is.
            **{
                key: result[key]
                for key in ("graded_by", "independence_caveat", "low_confidence", "record")
                if result.get(key)
            },
        }
        blocks[name] = _render_block(name, _validator_sha(name), run)

    if check_only:
        sys.stderr.write("\n  --check: validators.yaml not written\n")
    else:
        existing = VALIDATORS_YAML.read_text(encoding="utf-8") if VALIDATORS_YAML.exists() else ""
        VALIDATORS_YAML.write_text(merge_validators_yaml(existing, blocks), encoding="utf-8")
        sys.stderr.write(f"\n  wrote {VALIDATORS_YAML}\n")

    unmeasured = sorted(name for name, r in results.items() if r["not_scored"])
    if unmeasured:
        sys.stderr.write(
            f"  {len(unmeasured)} validator(s) UNMEASURED ({', '.join(unmeasured)}): the G3 bars "
            f"(sensitivity >= {SENSITIVITY_BAR}, false_alarm <= {FALSE_ALARM_BAR}) are not met "
            f"and no G3 verdict is citable.\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
