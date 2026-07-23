"""G0 gate runner (FreeCAD-free, contracts-only).

Loads the declarative ``gate.yaml``, runs every criterion against a ``StubBridge`` (every tool
-> "not implemented"), builds one contracts ``ValidationReport`` per criterion via
``harness.report_build``, aggregates, and prints a summary.

Exit codes (honest-fail, NON-defeasible):
  0  every criterion passed (unreachable in --stub: the stub never implements a tool)
  1  at least one criterion failed (the expected --stub result)
  2  usage / loader error — unknown gate, malformed / non-mapping / empty-criteria gate,
     criterion missing ``id``, ``--criterion`` matching nothing. NEVER exit 0 on zero
     criteria (that would let an empty gate report green), NEVER a traceback.

Invoked by file path (``python benchmarks/runner.py --gate G0 --stub``) and importable as
``benchmarks.runner`` from ``tests/external``.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

BENCHMARKS_ROOT = Path(__file__).resolve().parent

# File-path invocation (`python benchmarks/runner.py`) puts benchmarks/ on sys.path, not the
# repo root — so `import benchmarks.harness` fails. Add the repo root so the package resolves
# under both entry spellings (file-path and `import benchmarks.runner`).
_REPO_ROOT = BENCHMARKS_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.harness.evidence import collect_g0_2, ingest_report  # noqa: E402
from benchmarks.harness.report_build import (  # noqa: E402
    build_report,
    evidence_report,
    not_collected_report,
    stub_outcome,
)
from benchmarks.harness.verdict import (  # noqa: E402
    ArtifactError,
    bind_hash,
    compute_verdict,
)
from freecad_buddy.contracts.report import Check  # noqa: E402

# Known gates map to their benchmark dir (uppercase ids only; lowercase is a usage error).
KNOWN_GATES = {"G0": "g0"}

_EXIT_USAGE = 2
_EXIT_FAIL = 1
_EXIT_OK = 0

_REGISTRY_YAML = BENCHMARKS_ROOT / "_registry" / "validators.yaml"
_SUBCOMMANDS = {"run", "verdict", "attest"}

# Criteria whose evidence is dropped by an external in-FreeCAD/CI collector into evidence/.
_INGESTED_CRITERIA = {"G0.1", "G0.3", "G0.5"}
# The G0.4 matrix legs that BOTH must be present + green: a single present green leg is never
# enough (both blocking legs must be proven).
_REQUIRED_G0_4_LEGS = ("1.0.x", "1.1.x")
_G0_4_MIN_TESTS = 30

# Validator source sets, hashed the SAME way the fault scorers hash them (concatenated
# read_bytes over the same source files) so a clean working tree is CURRENT, not stale.
_SRC = _REPO_ROOT / "src" / "freecad_buddy"
_VALIDATOR_SOURCES = {
    "verify_shape": (
        _SRC / "usecases" / "verify.py",
        _SRC / "usecases" / "fingerprint.py",
    ),
}


class UsageError(Exception):
    """A usage / loader error -> exit 2 with a one-line message, never a traceback."""


class StubBridge:
    """Bridge stand-in: every tool call returns a structured "not implemented" outcome."""

    def call(self, _tool: str, **_kwargs) -> dict:
        return stub_outcome()


def _load_gate(gate: str) -> list[dict]:
    """Load and validate ``gate.yaml`` for ``gate``; return its non-empty criteria list.

    Raises ``UsageError`` on any loader problem so the caller can exit 2 cleanly.
    """
    if gate not in KNOWN_GATES:
        raise UsageError(f"unknown gate '{gate}' (known: {', '.join(sorted(KNOWN_GATES))})")

    gate_file = BENCHMARKS_ROOT / KNOWN_GATES[gate] / "gate.yaml"
    if not gate_file.is_file():
        raise UsageError(f"gate definition not found: {gate_file}")

    try:
        data = yaml.safe_load(gate_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        # OSError covers a race-deleted / unreadable gate.yaml after the is_file() check —
        # still a usage error (exit 2), never an escaping traceback (runner contract).
        raise UsageError(f"unreadable gate.yaml ({gate_file}): {exc.__class__.__name__}") from exc

    if not isinstance(data, dict):
        raise UsageError(f"gate.yaml must be a mapping, got {type(data).__name__}: {gate_file}")

    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        # Zero / missing criteria must NOT report green — that would defeat the entry gate.
        raise UsageError(f"gate.yaml has no criteria: {gate_file}")

    for entry in criteria:
        if not isinstance(entry, dict) or "id" not in entry:
            raise UsageError(f"criterion missing 'id' in {gate_file}")

    return criteria


def _load_gate_def(gate: str) -> dict:
    """Load ``gate.yaml`` ONCE and return the full validated mapping (for run/verdict/attest).

    Reuses ``_load_gate``'s validated criteria (no raw re-read of the file), then validates
    gate-level fields: ``required_tokens``, if present, MUST be a list (a scalar string would
    otherwise be iterated char-by-char in leg-d) — a scalar raises ``UsageError`` (exit-2). Any
    YAML/loader error already surfaces from ``_load_gate`` as ``UsageError``, never a traceback.
    """
    criteria = _load_gate(gate)
    gate_file = BENCHMARKS_ROOT / KNOWN_GATES[gate] / "gate.yaml"
    try:
        data = yaml.safe_load(gate_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UsageError(f"unreadable gate.yaml ({gate_file}): {exc.__class__.__name__}") from exc
    if not isinstance(data, dict):
        raise UsageError(f"gate.yaml must be a mapping: {gate_file}")
    data["criteria"] = criteria

    required_tokens = data.get("required_tokens")
    if required_tokens is not None and not isinstance(required_tokens, list):
        raise UsageError(
            f"gate.yaml 'required_tokens' must be a list, got "
            f"{type(required_tokens).__name__}: {gate_file}"
        )
    return data


def _validator_src_hasher(name: str) -> str:
    """SHA-256 over a validator's concatenated source files (matches the fault scorers).

    An unknown validator or an unreadable source file returns ``""`` — a hash that matches no
    real ``validator_sha``, so leg-b reports the validator stale rather than escaping an
    ``OSError`` as a traceback (the runner contract forbids tracebacks).
    """
    sources = _VALIDATOR_SOURCES.get(name)
    if sources is None:
        return ""
    hasher = hashlib.sha256()
    for path in sources:
        try:
            hasher.update(path.read_bytes())
        except OSError:
            return ""
    return hasher.hexdigest()


def _run_dir(gate: str, run_id: str) -> Path:
    return BENCHMARKS_ROOT / "gate-artifacts" / KNOWN_GATES[gate] / run_id


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write ``data`` as pretty JSON atomically (tmp + os.replace).

    On any failure between the tmp write and the replace, the tmp file is removed so a crash mid
    write does not leave a stray ``<criterion>.json.tmp`` accumulating in ``reports/``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _ingest_g0_4(run_dir: Path) -> dict:
    """Combine the pinned G0.4 matrix-leg evidence into ONE report — both legs required.

    Emits one check per required leg (``_REQUIRED_G0_4_LEGS``): a leg whose
    ``evidence/G0.4.<leg>.json`` is ABSENT (or malformed, or not green, or below the test bar)
    is a failing ``INVALID_INPUT`` check. A single present green leg can NEVER green G0.4.
    """
    evidence_dir = run_dir / "evidence"
    checks: list[Check] = []
    for leg in _REQUIRED_G0_4_LEGS:
        path = evidence_dir / f"G0.4.{leg}.json"
        checks.append(_g0_4_leg_check(leg, path))
    return evidence_report("G0.4", checks)


def _g0_4_leg_check(leg: str, path: Path) -> Check:
    """Build one G0.4 leg check: present ∧ green ∧ >=30 tests, else a failing INVALID_INPUT."""
    if not path.is_file():
        return {
            "id": f"G0.4.{leg}",
            "measured": None,
            "expected": "green ∧ >=30 tests",
            "passed": False,
            "detail": {
                "code": "invalid_input.g0_4_leg_absent",
                "message": f"G0.4 leg {leg} evidence absent: {path.name}",
            },
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "id": f"G0.4.{leg}",
            "measured": None,
            "expected": "green ∧ >=30 tests",
            "passed": False,
            "detail": {
                "code": "invalid_input.g0_4_leg_malformed",
                "message": f"G0.4 leg {leg} malformed ({exc.__class__.__name__})",
            },
        }
    green = isinstance(data, dict) and data.get("green") is True
    test_count = data.get("test_count") if isinstance(data, dict) else None
    enough = isinstance(test_count, int) and test_count >= _G0_4_MIN_TESTS
    passed = green and enough
    return {
        "id": f"G0.4.{leg}",
        "measured": {"green": green, "test_count": test_count},
        "expected": {"green": True, "test_count": f">={_G0_4_MIN_TESTS}"},
        "passed": passed,
        "detail": {
            "code": "ok" if passed else "invalid_input.g0_4_leg_not_green",
            "message": (f"G0.4 leg {leg}: green={green} test_count={test_count}"),
        },
    }


def _collect_report(criterion: dict, run_dir: Path):
    """Collect one criterion's ``ValidationReport`` for the ``run`` command."""
    criterion_id = criterion["id"]
    if criterion_id == "G0.2":
        from freecad_buddy.hosts.tool_catalog import tool_specs

        return collect_g0_2(list(tool_specs()))
    if criterion_id == "G0.4":
        return _ingest_g0_4(run_dir)
    if criterion_id in _INGESTED_CRITERIA:
        return ingest_report(criterion_id, run_dir / "evidence" / f"{criterion_id}.json")
    return not_collected_report(criterion_id, f"no collector for {criterion_id}")


def run_command(gate: str, run_id: str) -> int:
    """Collect + write one report per criterion into the run dir; exit on re-derived verdicts."""
    gate_def = _load_gate_def(gate)
    run_dir = _run_dir(gate, run_id)
    reports_dir = run_dir / "reports"
    reports: list[dict] = []
    for criterion in gate_def["criteria"]:
        report = _collect_report(criterion, run_dir)
        _atomic_write_json(reports_dir / f"{criterion['id']}.json", report)
        reports.append(report)

    all_ok = all(report["verdict"] == "OK" for report in reports)
    _print_run_summary(gate, reports)
    return _EXIT_OK if all_ok else _EXIT_FAIL


def _print_run_summary(gate: str, reports: list[dict]) -> None:
    print(f"run {gate}: wrote {len(reports)} reports")
    for report in reports:
        criterion_id = report["subject"]["criterion"]
        verdict = report["verdict"]
        status = "PASS" if verdict == "OK" else "FAIL"
        print(f"  {criterion_id}: {status} (verdict={verdict})")


def verdict_command(gate: str, run_id: str) -> int:
    """Compute the pure four-leg verdict over the stored run dir; exit 0 (PASS) / 1 (FAIL)."""
    gate_def = _load_gate_def(gate)
    run_dir = _run_dir(gate, run_id)
    if not run_dir.is_dir():
        raise UsageError(f"run '{run_id}' not found: {run_dir}")

    validators = _load_validators()
    try:
        result = compute_verdict(run_dir, gate_def, validators, _validator_src_hasher)
    except ArtifactError as exc:
        raise UsageError(str(exc)) from exc

    print(f"verdict {gate} --run {run_id}:")
    for criterion_id in sorted(result.per_criterion):
        print(f"  {criterion_id}: {result.per_criterion[criterion_id]}")
    for failure in result.failures:
        print(f"  FAILURE {failure}")
    print(f"gate {gate}: {'PASS' if result.passed else 'FAIL'}")
    return _EXIT_OK if result.passed else _EXIT_FAIL


def _load_validators() -> dict:
    try:
        data = yaml.safe_load(_REGISTRY_YAML.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UsageError(
            f"unreadable validators.yaml ({_REGISTRY_YAML}): {exc.__class__.__name__}"
        ) from exc
    return data if isinstance(data, dict) else {}


def attest_command(gate: str, run_id: str, token_type: str, outcome: str) -> int:
    """Write a run-bound human token whose ``binds_reports_sha256`` covers the stored reports."""
    gate_def = _load_gate_def(gate)
    run_dir = _run_dir(gate, run_id)
    if not run_dir.is_dir():
        raise UsageError(f"run '{run_id}' not found: {run_dir}")

    expected_ids = [c["id"] for c in gate_def["criteria"] if "id" in c]
    from benchmarks.harness.verdict import load_reports

    try:
        reports = load_reports(run_dir, expected_ids)
    except ArtifactError as exc:
        raise UsageError(str(exc)) from exc

    date = datetime.date.today().isoformat()
    token = {
        "token_type": token_type,
        "gate": gate,
        "run_id": run_id,
        "binds_reports_sha256": bind_hash(reports),
        "outcome": outcome,
        "signed_by": os.environ.get("USER") or os.environ.get("USERNAME") or "operator",
        "date": date,
    }
    token_path = run_dir / "human" / f"{token_type}_{date}.json"
    _atomic_write_json(token_path, token)
    print(f"attest {gate} --run {run_id}: wrote {token_path.name} (outcome={outcome})")
    return _EXIT_OK


def _filter_criteria(criteria: list[dict], criterion_id: str | None) -> list[dict]:
    if criterion_id is None:
        return criteria
    selected = [c for c in criteria if c.get("id") == criterion_id]
    if not selected:
        raise UsageError(f"--criterion '{criterion_id}' matched no criterion")
    return selected


def run_gate(gate: str, criterion_id: str | None = None) -> tuple[list[dict], int]:
    """Run ``gate`` against the stub; return (reports, exit_code). Never raises UsageError:
    it is converted to an exit-2 signal by ``main`` — but here we let it propagate so callers
    (tests) can assert on it. The stub run itself never raises."""
    criteria = _filter_criteria(_load_gate(gate), criterion_id)
    bridge = StubBridge()
    reports: list[dict] = []
    for criterion in criteria:
        outcome = bridge.call(f"criterion:{criterion['id']}")
        reports.append(build_report(criterion, outcome))

    all_passed = all(r["verdict"] == "OK" for r in reports)
    return reports, (_EXIT_OK if all_passed else _EXIT_FAIL)


def _print_summary(gate: str, reports: list[dict]) -> None:
    print(f"gate {gate}: {len(reports)} criteria")
    for report in reports:
        criterion_id = report["subject"]["criterion"]
        verdict = report["verdict"]
        status = "PASS" if verdict == "OK" else "FAIL"
        print(f"  {criterion_id}: {status} (verdict={verdict})")
    failed = sum(1 for r in reports if r["verdict"] != "OK")
    print(f"gate {gate}: {failed}/{len(reports)} criteria FAILED")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="runner.py", description="G0 gate runner (stub, honest-failing)."
    )
    parser.add_argument("--gate", required=True, help="gate id, e.g. G0")
    parser.add_argument(
        "--stub", action="store_true", help="run against the stub bridge (required)"
    )
    parser.add_argument("--criterion", help="run a single criterion id, e.g. G0.3")
    # --case was accepted-but-ignored previously; reject it explicitly in stub mode.
    parser.add_argument("--case", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _parse_subcommand(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="runner.py", description="G0 gate runner.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "verdict"):
        sp = sub.add_parser(name)
        sp.add_argument("gate", help="gate id, e.g. G0")
        sp.add_argument("--run", dest="run_id", required=True, help="run id")
    attest = sub.add_parser("attest")
    attest.add_argument("gate", help="gate id, e.g. G0")
    attest.add_argument("--run", dest="run_id", required=True, help="run id")
    attest.add_argument("--type", dest="token_type", required=True, help="token type")
    attest.add_argument("--outcome", default="PASS", help="token outcome (PASS/FAIL)")
    return parser.parse_args(argv)


def _run_subcommand(argv: list[str]) -> int:
    try:
        args = _parse_subcommand(argv)
    except SystemExit:
        return _EXIT_USAGE
    try:
        if args.command == "run":
            return run_command(args.gate, args.run_id)
        if args.command == "verdict":
            return verdict_command(args.gate, args.run_id)
        return attest_command(args.gate, args.run_id, args.token_type, args.outcome)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # A leading run|verdict|attest token routes to the file-driven subcommands; a bare
    # --gate/--stub invocation stays on the untouched stub path (back-compat).
    if argv and argv[0] in _SUBCOMMANDS:
        return _run_subcommand(argv)

    try:
        args = _parse_args(argv)
    except SystemExit:
        # argparse already printed a usage message; normalize to the usage exit code.
        return _EXIT_USAGE

    try:
        if args.case is not None:
            raise UsageError("--case is not supported in stub mode")
        # --stub is the only mode shipped so far (no live bridge yet).
        # Require it explicitly so the flag is meaningful, not a silent no-op.
        if not args.stub:
            raise UsageError("only --stub mode is supported (no live bridge yet); pass --stub")
        reports, exit_code = run_gate(args.gate, args.criterion)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_USAGE

    _print_summary(args.gate, reports)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
