"""In-FreeCAD fault scorer for the G2 validators.

Run under FreeCADCmd with the scoring opt-in set, so that importing this module for its helpers
never starts a scoring run::

    FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd score_g2_infc.py
    $env:FREECAD_BUDDY_RUN_FAULT_SCORER="1"; FreeCADCmd score_g2_infc.py

For every ``case.yaml`` in this suite: open the paired ``fixture.FCStd``, resolve the case's
``planted_op`` in ``planted_ops.REGISTRY``, and run it through ``usecases.transaction.run_mutation``
— the production mutation bracket. The validator the case declares in ``targets_validator`` decides
what the run is graded on:

``run_mutation``
    the rollback path the bracket actually took. Every rollback-boundary case requires the bracket
    to PROVE restoration; what separates a planted defect from a control is whether the abort fast
    path could prove it on its own. A planted defect is detected when the bracket had to escalate
    to the snapshot restore (``rolled_back_via_snapshot``) or could not prove the rollback at all —
    both mean the undo boundary did not hold. A control is clean when it committed or when abort
    alone proved the restoration (``rolled_back_verified``).
``audit_references``
    the TNP audit block ``post_verify`` computed: a planted defect is detected when the audit
    flagged a finding whose verdict is neither ``PASS`` nor ``RE_BASELINED``.
``assertions``
    ``benchmarks.harness.assertions.evaluate`` measured against the commanded parameters the case's
    ``planted_ops.CHECKS`` entry declares: a planted defect is detected when a check fails.

Computes sensitivity / false alarm + a Wilson CI per validator, hashes each validator's sources and
the cases scored over it into ``validator_sha``, and merge-writes only those blocks of
``_registry/validators.yaml`` through the shared ``merge_validators_yaml``, so no scorer clobbers
another's. Prints a per-case table to stderr and exits non-zero when a bar is missed.

An op that cannot be driven on this build (``planted_ops.UNDRIVEABLE``) is excluded from its
validator's population and reported by name with its reason. Scoring it as a miss would blame the
validator for a trigger the suite cannot pull; silently counting it as a pass would inflate the
score. A validator left with no driveable case is reported as not scored rather than as 0.0.

pyyaml is an external-process dependency (AD-12); this scorer runs inside FreeCADCmd and so parses
the small fixed ``case.yaml`` shape itself.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import traceback
from collections.abc import Mapping
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# The export scorer owns the shared read-merge-write for validators.yaml; import it by path so
# every scorer writes through one merge-writer and none full-clobbers another's blocks.
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import planted_ops  # noqa: E402
from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.usecases import stats, transaction  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05

_USECASES = SRC / "freecad_buddy" / "usecases"
# The source files whose bytes make up each validator's ``validator_sha``. Kept byte-identical to
# score_g2_validators.VALIDATOR_SOURCES and runner._VALIDATOR_SOURCES so a clean working tree reads
# as CURRENT rather than stale whichever path last wrote the block.
VALIDATOR_SOURCES = {
    "assertions": (
        REPO_ROOT / "benchmarks" / "harness" / "assertions.py",
        _USECASES / "assertions.py",
        _USECASES / "verify.py",
    ),
    "run_mutation": (
        _USECASES / "transaction.py",
        SRC / "freecad_buddy" / "contracts" / "fingerprint.py",
        _USECASES / "result_projection.py",
    ),
    "fingerprint": (_USECASES / "fingerprint.py",),
    "audit_references": (_USECASES / "tnp_guard.py", _USECASES / "result_projection.py"),
    "verify_sketch": (_USECASES / "verify.py",),
}

_HEADER = (
    "# Per-validator fault-suite binding (validation-harness-design.md §6).\n"
    "# A score is citable only while validator_sha matches the working tree "
    "(edit the validator to stale it).\n"
)


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _scalar(text: str, key: str) -> str | None:
    """The value of a top-level ``key: value`` line, unquoted, or ``None``."""
    match = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip().strip("'\"")


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed G2 fault ``case.yaml`` shape.

    Only the keys the scorer acts on are read: the id, the validator the case targets, the fault
    kind/expectation pair, the planted op and the fixture file name.

    :raises SuiteError: a required key is missing or the kind/expectation pair disagrees.
    """
    text = case_yaml.read_text(encoding="utf-8")
    case_id = _scalar(text, "id")
    if not case_id:
        raise SuiteError(f"{case_yaml}: no 'id'")
    targets = _scalar(text, "targets_validator")
    if not targets:
        raise SuiteError(f"case {case_id!r}: no 'targets_validator'")
    kind = _scalar(text, "  kind") or _scalar(text, "kind")
    expectation = _scalar(text, "  expectation") or _scalar(text, "expectation")
    if (kind == "planted_defect") != (expectation == "DETECT") or (kind == "clean_control") != (
        expectation == "PASS_CLEAN"
    ):
        raise SuiteError(
            f"case {case_id!r}: fault.kind {kind!r} disagrees with expectation {expectation!r} "
            "(planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
        )
    planted_op = _scalar(text, "planted_op")
    if not planted_op:
        raise SuiteError(f"case {case_id!r}: no 'planted_op'")
    return {
        "id": case_id,
        "validator": targets.split("@", 1)[0],
        "expectation": expectation,
        "planted_op": planted_op,
        "fixture": _scalar(text, "fixture"),
        "dir": case_yaml.parent,
    }


def _suite_case_files() -> list[Path]:
    """Every G2 fault ``case.yaml``, ordered by its suite-relative POSIX path.

    The exact-name filter keeps the set platform-independent: ``rglob`` is case-insensitive on
    Windows, so a miscased ``Case.YAML`` would otherwise be scored and hashed there and not on
    Linux CI.
    """
    return sorted(
        (p for p in HERE.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(HERE).as_posix(),
    )


def load_cases() -> list[dict]:
    """Every case in the suite, parsed."""
    return [_load_case(path) for path in _suite_case_files()]


def _validator_sha(name: str, cases: list[dict]) -> str:
    """SHA-256 over a validator's sources and the cases scored against it.

    The suite is part of the validator: a score-preserving case edit changes the population the
    committed sensitivity was measured over, so it must stale the run too. Each case contributes
    its suite-relative path and its bytes, length-prefixed so the concatenation is unambiguous.

    A validator with no cases digests its sources under an explicit empty-suite marker, so its
    digest is never the source-only hash a populated suite could also produce.

    :raises SuiteError: the validator is unknown, or a source file or case is unreadable.
    """
    sources = VALIDATOR_SOURCES.get(name)
    if sources is None:
        raise SuiteError(f"unknown validator {name!r} (no source set declared)")
    digest = hashlib.sha256()
    for path in sources:
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            raise SuiteError(f"unreadable validator source {path}: {exc}") from exc
    paths = [p for p in _suite_case_files() if _load_case(p)["validator"] == name]
    if not paths:
        digest.update(b"\x00no-fault-suite")
        return digest.hexdigest()
    for case_yaml in paths:
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


def _audit_flagged(envelope: dict) -> bool:
    """Whether the mutation's TNP audit reported a finding that is not PASS / RE_BASELINED."""
    block = (envelope.get("structured_content") or {}).get("mutation") or {}
    audit = (block.get("post_verify") or {}).get("tnp_audit") or {}
    findings = audit.get("findings") or []
    return any(f.get("verdict") not in ("PASS", "RE_BASELINED") for f in findings)


def _assertions_failed(document: object, case: dict) -> tuple[bool, str]:
    """Grade ``document`` against the case's commanded parameters.

    :returns: ``(any_check_failed, detail)``. A case declaring no checks is a suite error rather
        than a silent pass, because an ungraded case would count as a clean control either way.
    :raises SuiteError: the case declares no commanded parameters to be graded against.
    """
    checks = planted_ops.CHECKS.get(case["id"])
    if not checks:
        raise SuiteError(
            f"case {case['id']!r} targets 'assertions' but planted_ops.CHECKS declares no "
            "commanded parameters for it"
        )
    results = assertions.evaluate(document, checks)
    failed = [r for r in results if not r.get("passed")]
    detail = "; ".join(str(r.get("detail", {}).get("message", "")) for r in failed)
    return bool(failed), detail


def _run_case(case: dict) -> tuple[bool, str]:
    """Drive one case's ``planted_op`` through ``run_mutation``; return ``(detected, verdict)``.

    ``detected`` is what the case's target validator concluded — the bracket refused to commit,
    the TNP audit flagged a reference, or an assertion failed. ``verdict`` is the short string the
    per-case table prints.

    :raises planted_ops.OpNotDriveable: the op has no reachable trigger on this build.
    """
    import FreeCAD as App

    from freecad_buddy.usecases.documents import DocumentRegistry

    op = planted_ops.resolve(case["planted_op"])
    fixture = case["dir"] / (case["fixture"] or "fixture.FCStd")
    if not fixture.is_file():
        raise SuiteError(f"case {case['id']!r}: fixture not found: {fixture}")

    registry = DocumentRegistry()
    handle = registry.document_open(str(fixture))["structured_content"]["doc"]
    document = registry.with_document(handle, lambda _h, d: d)
    try:
        document, envelope = transaction.run_mutation(document, handle, case["planted_op"], op)
        registry.rebind(handle, document)
        status = envelope.get("status")

        if case["validator"] == "run_mutation":
            block = (envelope.get("structured_content") or {}).get("mutation") or {}
            proof = block.get("rollback_proven")
            rolled_back = bool(block.get("rolled_back"))
            # The bracket held when it committed, or when the abort alone re-hashed back to the
            # pre-op state. Needing the snapshot, or failing to prove restoration at all, is the
            # boundary defect these cases plant.
            held = status == "OK" or (rolled_back and proof == "rolled_back_verified")
            return not held, f"{status}/{proof}"
        if case["validator"] == "audit_references":
            flagged = _audit_flagged(envelope)
            # A bracket that refused to commit also caught the fault; the audit is one of the
            # checks post_verify runs, so either signal is a detection by this validator's guard.
            return (flagged or status != "OK"), f"{status}/{'FLAGGED' if flagged else 'CLEAN'}"
        if case["validator"] == "assertions":
            if status != "OK":
                # The op never landed, so there is no geometry for the grader to measure. That is
                # a suite problem, not an assertion verdict, and must not read as a detection.
                raise SuiteError(
                    f"case {case['id']!r}: the mutation did not commit ({status}), so "
                    "assertions.evaluate had no result to grade"
                )
            failed, detail = _assertions_failed(document, case)
            return failed, f"OK/{'FAIL' if failed else 'PASS'} {detail}"[:60]
        raise SuiteError(f"case {case['id']!r}: unscorable validator {case['validator']!r}")
    finally:
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)


def score() -> dict[str, dict]:
    """Score every cited validator over the driveable cases that target it.

    Returns ``{validator: result}``. Each result carries the planted/control counts actually
    scored, the detected/flagged tallies, the resulting rates, the per-case ``rows`` and any
    ``skipped`` cases with the reason each could not be driven. A validator with no driveable
    case carries a ``reason`` and is never presented as a measured zero.
    """
    by_validator: dict[str, list[dict]] = {}
    for case in load_cases():
        by_validator.setdefault(case["validator"], []).append(case)

    results: dict[str, dict] = {}
    for name in sorted(VALIDATOR_SOURCES):
        cases = by_validator.get(name, [])
        rows: list[tuple[str, str, str, str]] = []
        skipped: list[tuple[str, str]] = []
        detected = 0
        flagged = 0
        planted = 0
        controls = 0

        for case in cases:
            reason = planted_ops.UNDRIVEABLE.get(case["planted_op"])
            if reason:
                skipped.append((case["id"], reason))
                continue
            try:
                is_detected, verdict = _run_case(case)
            except planted_ops.OpNotDriveable as exc:
                skipped.append((case["id"], str(exc)))
                continue
            except SuiteError:
                raise
            except Exception as exc:  # noqa: BLE001 - a case that crashed was never graded
                skipped.append((case["id"], f"the run raised {type(exc).__name__}: {exc}"))
                sys.stderr.write(f"  !! {case['id']}: {traceback.format_exc()}\n")
                continue

            is_defect = case["expectation"] == "DETECT"
            if is_defect:
                planted += 1
                if is_detected:
                    detected += 1
                    outcome = "DETECTED"
                else:
                    outcome = "MISSED"
            else:
                controls += 1
                if is_detected:
                    flagged += 1
                    outcome = "FALSE_ALARM"
                else:
                    outcome = "PASS_CLEAN"
            rows.append((case["id"], case["expectation"], verdict, outcome))

        result = {
            "planted": planted,
            "controls": controls,
            "detected": detected,
            "flagged": flagged,
            "sensitivity": stats.sensitivity(detected, planted),
            "false_alarm": stats.false_alarm(flagged, controls),
            "wilson_ci": stats.wilson_ci(detected, planted),
            "rows": rows,
            "skipped": skipped,
        }
        if not cases:
            result["reason"] = "no fault case targets this validator"
        elif not rows:
            result["reason"] = (
                f"no driveable case: all {len(cases)} case(s) targeting this validator were skipped"
            )
        elif not planted:
            # Controls alone cannot measure sensitivity: stats.sensitivity(0, 0) is 0.0, which
            # would read as "every planted defect was missed" when none was driveable at all.
            result["reason"] = (
                f"no driveable planted defect: {controls} clean control(s) ran and "
                f"{len(skipped)} planted case(s) were skipped, so sensitivity is unmeasured "
                "rather than zero"
            )
        results[name] = result
    return results


def _render_block(name: str, sha: str, run: dict, suite: str) -> str:
    """Render one validator's ``validators.yaml`` block for the shared merge-writer.

    A validator whose score was not measured carries ``not_scored`` naming why. Without it the
    block is indistinguishable from a real measurement: a zero sensitivity beside a date, a run id
    and a Wilson interval reads as "measured and scored zero", and an ``n: 0`` interval spanning
    ``[0, 1]`` reads as evidence rather than as its absence.
    """
    wilson = run["wilson_ci"]
    block = (
        f"{name}:\n"
        f"  suite: {suite}\n"
        f'  validator_sha: "{sha}"\n'
        "  last_run:\n"
        f"    run_id: {run['run_id']}\n"
        f"    sensitivity: {run['sensitivity']}\n"
        f"    false_alarm: {run['false_alarm']}\n"
        f"    date: {run['date']}\n"
    )
    if run.get("not_scored"):
        # The reason is free text carrying colons and commas, which YAML reads as structure
        # unless the scalar is quoted.
        reason = str(run["not_scored"]).replace('"', "'")
        block += f'    not_scored: "{reason}"\n'
    if run.get("skipped"):
        block += f"    skipped_cases: {run['skipped']}\n"
    return block + (
        "    wilson_ci:\n"
        f"      rate: {wilson['rate']}\n"
        f"      low: {wilson['low']}\n"
        f"      high: {wilson['high']}\n"
        f"      n: {wilson['n']}\n"
        f"      r: {wilson['r']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Score the G2 validators in FreeCAD; write their blocks unless ``--check`` is passed.

    ``--check`` computes and asserts the bars WITHOUT writing ``validators.yaml``, so CI verifies
    the committed scores against the current suites while the working tree stays clean.
    """
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    results = score()

    today = date.today().isoformat()
    rendered: dict[str, str] = {}
    failed = False
    cases = load_cases()

    for name, result in results.items():
        for case_id, expectation, verdict, outcome in result["rows"]:
            sys.stderr.write(
                f"  {name:18s} {case_id:46s} {expectation:11s} {verdict:22s} {outcome}\n"
            )
        for case_id, reason in result["skipped"]:
            sys.stderr.write(f"  {name:18s} {case_id:46s} NOT DRIVEABLE: {reason}\n")
        sys.stderr.write(
            f"  {name:18s} planted={result['planted']:2d} controls={result['controls']:2d} "
            f"detected={result['detected']:2d} flagged={result['flagged']:2d} "
            f"sensitivity={result['sensitivity']:.3f} false_alarm={result['false_alarm']:.3f}\n"
        )
        if result.get("reason"):
            sys.stderr.write(f"  {'':18s} NOT SCORED: {result['reason']}\n")

        wilson = result["wilson_ci"]
        run = {
            "run_id": f"g2-{today}-1",
            "sensitivity": round(result["sensitivity"], 4),
            "false_alarm": round(result["false_alarm"], 4),
            "date": today,
            "not_scored": result.get("reason") or "",
            "skipped": len(result["skipped"]) or "",
            "wilson_ci": {
                "rate": round(wilson["rate"], 4),
                "low": round(wilson["low"], 4),
                "high": round(wilson["high"], 4),
                "n": wilson["n"],
                "r": wilson["r"],
            },
        }
        rendered[name] = _render_block(
            name, _validator_sha(name, cases), run, "g2/fault-injection/"
        )
        if (
            result.get("reason")
            or result["sensitivity"] < SENSITIVITY_BAR
            or result["false_alarm"] > FALSE_ALARM_BAR
        ):
            failed = True

    if not check_only:
        existing = (
            VALIDATORS_YAML.read_text(encoding="utf-8") if VALIDATORS_YAML.exists() else _HEADER
        )
        VALIDATORS_YAML.write_text(merge_validators_yaml(existing, rendered), encoding="utf-8")
        sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")
    else:
        sys.stderr.write("  --check: validators.yaml not written\n")

    if failed:
        sys.stderr.write(
            "  BARS NOT MET: sensitivity<0.95, false_alarm>0.05, or a validator was not scored\n"
        )
        return 1
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_FAULT_SCORER"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit scoring-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether direct execution or an explicit opt-in asked for a scoring run.

    An import never scores: ``__name__`` is the module name and the flag is absent. FreeCADCmd
    sets ``__name__`` to the file stem rather than ``"__main__"``, so the launched-script path is
    matched against ``sys.argv[1]`` too.
    """
    if _run_requested_in(os.environ):
        return True
    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        try:
            return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
        except OSError:
            return False
    return False


if _run_requested():
    sys.exit(main())
