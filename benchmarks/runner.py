"""G0 gate runner (external uv process, FreeCAD-free, contracts-only — AD-12/AD-17/AD-19).

Loads the declarative ``gate.yaml``, runs every criterion against a ``StubBridge`` (every tool
-> "not implemented"), builds one contracts ``ValidationReport`` per criterion via
``harness.report_build``, aggregates, and prints a summary.

Exit codes (honest-fail, NON-defeasible):
  0  every criterion passed (unreachable in --stub: the stub never implements a tool)
  1  at least one criterion failed (the expected --stub result)
  2  usage / loader error — unknown gate, malformed / non-mapping / empty-criteria gate,
     criterion missing ``id``, ``--criterion`` matching nothing. NEVER exit 0 on zero
     criteria (that would defeat AD-19), NEVER a traceback.

Invoked by file path (``python benchmarks/runner.py --gate G0 --stub``) and importable as
``benchmarks.runner`` from ``tests/external``.
"""

from __future__ import annotations

import argparse
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

from benchmarks.harness.report_build import build_report, stub_outcome  # noqa: E402

# Known gates map to their benchmark dir (uppercase ids only; lowercase is a usage error).
KNOWN_GATES = {"G0": "g0"}

_EXIT_USAGE = 2
_EXIT_FAIL = 1
_EXIT_OK = 0


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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = _parse_args(argv)
    except SystemExit:
        # argparse already printed a usage message; normalize to the usage exit code.
        return _EXIT_USAGE

    try:
        if args.case is not None:
            raise UsageError("--case is not supported in stub mode")
        # --stub is the only mode this story ships (no live bridge until Story 1.4/1.6).
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
