"""Fault scorer for the G4 validators (run under uv via ``runner.py faults G4``).

Computes sensitivity / false-alarm + a Wilson CI over the cases each validator ACTUALLY RAN, and
records an explicit ``not_scored`` reason for a validator whose population is empty rather than
writing a fabricated ``0.0``. A zero that means "the validator missed every defect" and a zero
that means "no defect was driveable" are different facts, and a registry that spells them the
same way lets an unmeasured validator be cited as a measured one.

Planting a G4 fault means submitting a job and measuring how the service resolved it. No service
exists (stories 5.2-5.4), so ``drive_g4_faults.py`` resolves each case against the stub seam and
this scorer reads the per-case outcomes it wrote. The handoff matches every other gate's, which is
what lets the real supervisor replace the stub later with no scorer change.

What that bounds is carried onto every row through the driver's ``graded_by`` and
``independence_caveat``: these bars show the SUITE separates planted faults from clean controls
against a mapping authored before any service existed — the entry-gate property (AD-19). They are
not a service measurement, and the rows say so beside the numbers rather than in a separate note.

Writes only the G4 validator blocks of ``_registry/validators.yaml`` through the shared
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
#
# All four name the stub seam today because the stub IS the implementation under test: it fixes
# the status vocabulary and the shape rules the cases were authored against. When stories 5.2-5.4
# land, each name gains the real module beside the seam and the digest changes, which stales these
# rows exactly as it should — a score measured over a stub must not survive the real service.
VALIDATOR_SOURCES = {
    "job_lifecycle": (REPO_ROOT / "benchmarks" / "g4" / "stub_service.py",),
    "supervisor_recheck": (REPO_ROOT / "benchmarks" / "g4" / "stub_service.py",),
    "revision_diff": (REPO_ROOT / "benchmarks" / "g4" / "stub_service.py",),
    "soak_status": (REPO_ROOT / "benchmarks" / "g4" / "stub_service.py",),
}

# The suite path recorded on each registry row. It is a LABEL for a reader, not the selector: the
# scorer and runner both fold in cases by `targets_validator`, so `soak_status` — whose cases are
# spread over three runtime-fault legs — names the three rather than claiming the whole root, which
# would read as owning the other validators' legs too.
_SUITE_BY_VALIDATOR = {
    "job_lifecycle": "g4/fault-injection/lifecycle/",
    "supervisor_recheck": "g4/fault-injection/wrong-part/",
    "revision_diff": "g4/fault-injection/revision-diff/",
    "soak_status": "g4/fault-injection/{timeout,oom,crash}/",
}

# Validators cited by a G4 criterion but carrying no fault suite yet. Scored as explicitly
# unmeasured rather than omitted: a validator with no registry row reports "not in registry" at
# leg-b, which reads as a wiring mistake, while an empty-suite row states the real gap.
_SUITELESS_VALIDATORS: frozenset[str] = frozenset()

# The fixture value a case declares when its fault is planted by the driver rather than carried in
# a file. The job submission IS the fixture; there is nothing to find on disk.
_DRIVEN_FIXTURES = frozenset({"driven-by-job-service"})

# Where the driver leaves the per-case outcomes it measured.
DRIVEN_RESULTS = {name: HERE / f"{name}.json" for name in VALIDATOR_SOURCES}

_DRIVER = "drive_g4_faults.py"


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _load_case(case_yaml: Path) -> dict:
    data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SuiteError(f"{case_yaml}: case.yaml must be a mapping, got {type(data).__name__}")
    data["dir"] = case_yaml.parent
    return data


def _suite_case_files() -> list[Path]:
    """Every G4 fault ``case.yaml``, ordered by its suite-relative POSIX path.

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
    produces for it, so an unwritten validator reads as stale on both sides rather than as a
    digest nothing backs.
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
        if (kind == "planted_defect") != (expectation == "DETECT") or (
            kind == "clean_control"
        ) != (expectation == "PASS_CLEAN"):
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: fault.kind {kind!r} disagrees with "
                f"expectation {expectation!r} (planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
            )
    planted = [c for c in cases if c["fault"]["expectation"] == "DETECT"]
    controls = [c for c in cases if c["fault"]["expectation"] == "PASS_CLEAN"]
    return planted, controls


def _driveable(case: dict, unscorable: dict[str, str]) -> bool:
    """Whether the case's fault can be planted AND decided by its own declaration.

    A case declaring a driven fixture plus a ``planted_op`` is planted by the driver, so there is
    no file to look for; a control needs no op. A ``pending`` case is neither. A case the driver
    reported unscorable is excluded too — its fault is invisible to the verdict its own spec
    declares, so counting it as a miss would blame the validator for a verdict the case cannot
    reach.

    All exclusions are SKIPPED rather than counted, which is the whole point of ``not_scored``: an
    undriven defect says nothing about the validator's sensitivity.
    """
    if case.get("id") in unscorable:
        return False
    fixture = case.get("fixture")
    if not isinstance(fixture, str) or fixture == "pending":
        return False
    if fixture in _DRIVEN_FIXTURES:
        if case["fault"]["kind"] == "clean_control":
            return True
        return isinstance(case.get("planted_op"), str) and bool(case["planted_op"])
    return (case["dir"] / fixture).is_file()


def _driven_results(name: str) -> dict | None:
    """The result file the driver wrote for ``name``, or ``None`` when it has not run."""
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

    outcomes = _driven_outcomes(results) or {}
    detected = sum(1 for c in driveable_planted if outcomes.get(c["id"]) == "DETECTED")
    flagged = sum(1 for c in driveable_controls if outcomes.get(c["id"]) == "FALSE_ALARM")
    ungraded = [c["id"] for c in driveable_planted + driveable_controls if c["id"] not in outcomes]

    not_scored = None
    if not cases:
        # Distinct from "cases exist but none is driveable": there is no suite at all, so the gap
        # is an unauthored fault suite rather than an unbuilt runtime.
        not_scored = (
            "no fault case targets this validator: it is cited by a G4 criterion but no suite "
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
            f"{len(ungraded)} driveable case(s) carry no measured outcome: run "
            f"`uv run python benchmarks/g4/fault-injection/{_DRIVER}`, whose results file this "
            f"scorer reads, then re-score. Ungraded: {sorted(ungraded)}"
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

    # A case the driver could not score shrinks the population the number was measured over. That
    # is a CAVEAT on a real measurement, not the absence of one, so it is carried separately from
    # `not_scored` — folding it in would make "8 of 8 detected, 2 cases their spec cannot decide"
    # read identically to "nothing was measured".
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
        # registry row. A rate is not self-describing: `sensitivity: 1.0` over n=3 reads as
        # authoritative unless the row also says what produced it. For G4 this is load-bearing —
        # the number was measured against a stub, and a row that omitted that would read as a
        # service result.
        **{
            key: (results or {})[key]
            for key in ("graded_by", "independence_caveat", "low_confidence", "record")
            if (results or {}).get(key)
        },
    }


def score() -> dict[str, dict]:
    """Score every declared G4 validator; return ``{validator: result}``."""
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
    # sees ``sensitivity: 1.0`` over a short ``n`` and has no way to learn which authored defects
    # were left out, or that the reason is their own spec rather than the validator.
    if run.get("excluded_reasons"):
        lines.append("    excluded_unscorable:\n")
        for case_id, reason in sorted(run["excluded_reasons"].items()):
            lines.append(f"      {case_id}: {reason!r}\n")
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
    """Score the G4 suites and merge-write their validator blocks.

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
            f"  {name:20s} planted={result['planted']:2d} "
            f"(driven {result['driveable_planted']:2d}) "
            f"controls={result['controls']:2d} (driven {result['driveable_controls']:2d}) "
            f"skipped={result['skipped']:2d}\n"
        )
        if result["not_scored"]:
            sys.stderr.write(f"  {'':20s} NOT SCORED: {result['not_scored']}\n")
        else:
            sys.stderr.write(
                f"  {'':20s} sensitivity={result['sensitivity']:.3f} "
                f"false_alarm={result['false_alarm']:.3f}\n"
            )
        for case_id, reason in sorted((result.get("excluded_reasons") or {}).items()):
            sys.stderr.write(f"  {'':20s} EXCLUDED {case_id}: {reason}\n")
        wilson = result["wilson_ci"]
        run = {
            "run_id": f"g4-{today}-1",
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
            f"  {len(unmeasured)} validator(s) UNMEASURED ({', '.join(unmeasured)}): the G4 bars "
            f"(sensitivity >= {SENSITIVITY_BAR}, false_alarm <= {FALSE_ALARM_BAR}) are not met "
            f"and no G4 verdict is citable.\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
