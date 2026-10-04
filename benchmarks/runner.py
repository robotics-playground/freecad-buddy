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
import subprocess
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
from freecad_buddy.contracts.report import Check, require_wilson_ci_for_rates  # noqa: E402

# Known gates map to their benchmark dir (uppercase ids only; lowercase is a usage error).
KNOWN_GATES = {"G0": "g0", "G1": "g1", "G2": "g2", "G3": "g3"}
# Gates carrying a sealed held-out split. G0's suites are all open by design.
_SEALABLE_GATES = frozenset({"G1", "G2", "G3"})

_EXIT_USAGE = 2
_EXIT_FAIL = 1
_EXIT_OK = 0

_REGISTRY_YAML = BENCHMARKS_ROOT / "_registry" / "validators.yaml"
_SUBCOMMANDS = {"run", "verdict", "attest", "faults", "seal"}

# The unseal key is read ONLY from this env var — never committed, never a CI secret. `seal` and
# `run --exit` refuse (exit-2) without it; neither ever falls back to an offline default.
_UNSEAL_KEY_ENV = "FREECAD_BUDDY_UNSEAL_KEY"

# The minimum repeats a genuine exit eval runs at (R>=10 majority-of-R, decision 010). Offline this
# drives a clearly-labelled machinery dry-run over the scripted double, never the operator number.
_EXIT_REPEATS = 10

# Per-gate fault scorer routed by `faults <gate>` (relative to the repo root).
_FAULT_SCORERS = {
    "G1": Path("benchmarks") / "g1" / "fault-injection" / "score_grader.py",
    "G2": Path("benchmarks") / "g2" / "fault-injection" / "score_g2_validators.py",
    "G3": Path("benchmarks") / "g3" / "fault-injection" / "score_g3_validators.py",
}

# The repeats a G2 dev run drives each command at (R=5, the G2.1 criterion's declared R).
_G2_DEV_REPEATS = 5
# The splits a dev `run G2` drives. The command benchmark and the fault suite both feed the same
# outcome list; each collector selects its own population from it. `heldout/` is never here.
_G2_DEV_SPLITS = ("dev", "fault-injection")

# Criteria whose evidence is dropped by an external in-FreeCAD/CI collector into evidence/.
_INGESTED_CRITERIA = {"G0.1", "G0.3", "G0.5"}
# The G0.4 CI leg that must be present + green. Evidence for any other leg is ignored.
_REQUIRED_G0_4_LEGS = ("1.1.x",)
_G0_4_MIN_TESTS = 30

# Validator source sets, hashed the SAME way the fault scorers hash them (concatenated
# read_bytes over the same source files) so a clean working tree is CURRENT, not stale.
_SRC = _REPO_ROOT / "src" / "freecad_buddy"
_VALIDATOR_SOURCES = {
    "verify_shape": (
        _SRC / "usecases" / "verify.py",
        _SRC / "usecases" / "fingerprint.py",
        _SRC / "usecases" / "assertions.py",
    ),
    # The G1 grader's currency depends on the grader source, the rubric it encodes AND the fault
    # suite the score was measured over; a rubric edit changes the pass rule and a case edit
    # changes the measured population, so both must stale the score. Order matches
    # score_grader.py's hash (grader.py, rubric.md, then the suite folded in by
    # `_grader_suite_sources`) so a clean tree is CURRENT, not stale.
    "grader": (
        _REPO_ROOT / "benchmarks" / "g1" / "grader.py",
        _REPO_ROOT / "benchmarks" / "g1" / "rubric.md",
    ),
    # The five validators the G2 criteria cite. Each hashes its source plus the G2 fault cases
    # that target it, matching score_g2_validators.py's `_validator_sha` byte for byte so a clean
    # working tree reads as CURRENT rather than stale.
    "assertions": (
        _REPO_ROOT / "benchmarks" / "harness" / "assertions.py",
        _SRC / "usecases" / "assertions.py",
        _SRC / "usecases" / "verify.py",
    ),
    "run_mutation": (_SRC / "usecases" / "transaction.py",),
    "fingerprint": (_SRC / "usecases" / "fingerprint.py",),
    "audit_references": (_SRC / "usecases" / "tnp_guard.py",),
    "verify_sketch": (_SRC / "usecases" / "verify.py",),
    # The G3 corrupted-plan suite graded through verify_shape's §7.2 checks, plus the scorer that
    # classifies them. Its suite is folded in like a G2 validator's, then the dev specs its cases
    # name, matching score_g3_replay.py's `validator_sha` byte for byte.
    "spec_assertions": (
        _SRC / "usecases" / "assertions.py",
        _SRC / "usecases" / "verify.py",
        _REPO_ROOT / "benchmarks" / "g3" / "fault-injection" / "score_g3_replay.py",
    ),
}

# The G1 fault suite whose `case.yaml` set is folded into the `grader` hash.
_GRADER_SUITE_ROOT = _REPO_ROOT / "benchmarks" / "g1" / "fault-injection"

# The G2 fault suite whose `case.yaml` set is folded into each G2 validator's hash.
_G2_SUITE_ROOT = _REPO_ROOT / "benchmarks" / "g2" / "fault-injection"
_G3_SUITE_ROOT = _REPO_ROOT / "benchmarks" / "g3" / "fault-injection" / "corrupted-plan"
_G3_DEV_ROOT = _REPO_ROOT / "benchmarks" / "g3" / "dev"

# The validators whose suite fold-in selects only the cases under their suite root declaring
# that validator in `targets_validator` — a validator with no cases folds in an explicit
# empty-suite marker.
_TARGETED_SUITE_ROOTS = {
    "assertions": _G2_SUITE_ROOT,
    "run_mutation": _G2_SUITE_ROOT,
    "fingerprint": _G2_SUITE_ROOT,
    "audit_references": _G2_SUITE_ROOT,
    "verify_sketch": _G2_SUITE_ROOT,
    "spec_assertions": _G3_SUITE_ROOT,
}


class UsageError(Exception):
    """A usage / loader error -> exit 2 with a one-line message, never a traceback."""


class StubBridge:
    """Bridge stand-in: every tool call returns a structured "not implemented" outcome."""

    def call(self, _tool: str, **_kwargs) -> dict:
        return stub_outcome()


# The offline actor-run backend is gated behind this env var: only ``live`` wires an operator's
# real MCP backend (never in unattended CI). Any other value (or unset) runs the deterministic
# scripted double.
_ACTOR_BACKEND_ENV = "FREECAD_BUDDY_G1_ACTOR_BACKEND"


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


def _grader_suite_sources() -> list[tuple[bytes, Path]]:
    """The G1 fault suite's ``case.yaml`` files as (identity prefix, path) pairs.

    Each case contributes its suite-relative POSIX path as well as its bytes, so an added,
    removed, renamed or edited case all change the digest. Ordered by that same relative path to
    match score_grader.py's ordering. A missing suite tree yields an empty list, which the caller
    reports as stale. The exact-name filter keeps the digest platform-independent: ``rglob`` is
    case-insensitive on Windows, so a miscased ``Case.YAML`` would otherwise join the digest there
    and not on Linux CI.
    """
    cases = sorted(
        (p for p in _GRADER_SUITE_ROOT.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(_GRADER_SUITE_ROOT).as_posix(),
    )
    return [(p.relative_to(_GRADER_SUITE_ROOT).as_posix().encode("utf-8"), p) for p in cases]


def _validator_src_hasher(name: str) -> str:
    """SHA-256 over a validator's concatenated source files (matches the fault scorers).

    For ``grader`` the G1 fault suite's ``case.yaml`` set is folded in after the source files,
    mirroring score_grader.py's ``_validator_sha`` byte for byte. An empty suite returns ``""``
    rather than the source-only digest, which is a value the registry has already carried and
    would read as current over a deleted suite.

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
    if name == "grader":
        suite = _grader_suite_sources()
        if not suite:
            return ""
    elif name in _TARGETED_SUITE_ROOTS:
        suite = _targeted_suite_sources(name)
        if not suite:
            hasher.update(b"\x00no-fault-suite")
            return hasher.hexdigest()
        if name == "spec_assertions":
            suite = suite + _g3_dev_spec_sources(suite)
    else:
        return hasher.hexdigest()
    for identity, path in suite:
        try:
            content = path.read_bytes()
        except OSError:
            return ""
        hasher.update(len(identity).to_bytes(4, "big"))
        hasher.update(identity)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def _targeted_suite_sources(validator: str) -> list[tuple[bytes, Path]]:
    """The fault cases targeting ``validator``, as (identity prefix, path) pairs.

    Ordered by suite-relative POSIX path to match score_g2_validators.py's and
    score_g3_replay.py's ordering. Only cases whose ``targets_validator`` names this validator
    are folded in, so an edit to another validator's suite does not stale this one.
    """
    root = _TARGETED_SUITE_ROOTS[validator]
    cases = sorted(
        (p for p in root.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    selected = []
    for path in cases:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        declared = data.get("targets_validator") if isinstance(data, dict) else None
        if isinstance(declared, str) and declared.split("@", 1)[0] == validator:
            selected.append((path.relative_to(root).as_posix().encode("utf-8"), path))
    return selected


def _g3_dev_spec_sources(suite: list[tuple[bytes, Path]]) -> list[tuple[bytes, Path]]:
    """Each distinct G3 dev spec the ``suite`` cases name, as (identity prefix, path) pairs.

    Ordered by ``spec_ref`` under the identity ``dev/<spec_ref>/case.yaml``, matching
    score_g3_replay.py's `validator_sha`. An unreadable case names no spec, so the digest
    differs from the scorer's and reads as stale.
    """
    refs = set()
    for _, path in suite:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            refs.add(str(data.get("spec_ref")))
    return [
        (f"dev/{ref}/case.yaml".encode("utf-8"), _G3_DEV_ROOT / ref / "case.yaml")
        for ref in sorted(refs)
    ]


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
    """Build the G0.4 report from the pinned 1.1.x CI-leg evidence.

    Emits one check per required leg (``_REQUIRED_G0_4_LEGS``): a leg whose
    ``evidence/G0.4.<leg>.json`` is ABSENT (or malformed, or not green, or below the test bar)
    is a failing ``INVALID_INPUT`` check. A file for a leg outside that roster is never read.
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


def _collect_report(criterion: dict, run_dir: Path, live_outcomes=None):
    """Collect one criterion's ``ValidationReport`` for the ``run`` command.

    ``live_outcomes`` carries the driven case results the G2 collectors measure; it is ``None``
    when no live driver ran, which every G2 collector reports as an honest uncollected failure.
    """
    criterion_id = criterion["id"]
    if criterion_id == "G0.2":
        from freecad_buddy.hosts.tool_catalog import tool_specs

        return collect_g0_2(list(tool_specs()))
    if criterion_id == "G0.4":
        return _ingest_g0_4(run_dir)
    if criterion_id in _INGESTED_CRITERIA:
        return ingest_report(criterion_id, run_dir / "evidence" / f"{criterion_id}.json")
    collector = _G2_COLLECTORS.get(criterion_id)
    if collector is not None:
        return collector(criterion, live_outcomes or [])
    return not_collected_report(criterion_id, f"no collector for {criterion_id}")


def _collect_g2_4(criterion: dict, outcomes: list):
    """Collect G2.4 after probing element-map availability, which gates the whole criterion."""
    from benchmarks.harness import g2_collect

    return g2_collect.collect_g2_4(
        criterion, outcomes, element_map_available=_element_map_available()
    )


def _element_map_available() -> bool | None:
    """Whether the running build exposes an element map, or ``None`` outside FreeCAD.

    The probe needs the FreeCAD API, so outside it the answer is unknown rather than ``False`` —
    and unknown is not "available", so G2.4 still refuses to report clean.
    """
    try:
        from freecad_buddy.usecases import shim
    except ImportError:
        return None
    try:
        return bool(shim.element_map_available())
    except Exception:  # noqa: BLE001 - a probe that cannot run is unknown, never "available"
        return None


_G2_COLLECTORS = {}


def _install_g2_collectors() -> None:
    """Register the G2 criterion collectors, keyed by criterion id.

    Registered lazily so importing the runner does not import the collectors (and through them
    the contracts) before the repo root is on ``sys.path``.
    """
    from benchmarks.harness import g2_collect

    _G2_COLLECTORS.update(
        {
            "G2.1": g2_collect.collect_g2_1,
            "G2.2": g2_collect.collect_g2_2,
            "G2.3": g2_collect.collect_g2_3,
            "G2.4": _collect_g2_4,
            "G2.5": g2_collect.collect_g2_5,
            "G2.6": lambda criterion, _outcomes: g2_collect.collect_g2_6(criterion),
        }
    )


def run_command(gate: str, run_id: str) -> int:
    """Collect + write one report per criterion into the run dir; exit on re-derived verdicts."""
    gate_def = _load_gate_def(gate)
    run_dir = _run_dir(gate, run_id)
    _refuse_exit_run_dir(gate, run_id)
    reports_dir = run_dir / "reports"
    _install_g2_collectors()
    live_outcomes = _drive_live_cases(gate, run_dir)
    reports: list[dict] = []
    for criterion in gate_def["criteria"]:
        report = _collect_report(criterion, run_dir, live_outcomes)
        _atomic_write_json(reports_dir / f"{criterion['id']}.json", report)
        reports.append(report)

    all_ok = all(report["verdict"] == "OK" for report in reports)
    _print_run_summary(gate, reports)
    return _EXIT_OK if all_ok else _EXIT_FAIL


def _drive_live_cases(gate: str, run_dir: Path, splits: tuple[str, ...] = _G2_DEV_SPLITS) -> list:
    """Drive ``gate``'s cases through the live mutation path; return one outcome per repeat.

    Returns an empty list for a gate with no live driver, outside FreeCAD, or when no command
    resolver is wired — each of which the collectors report as an honest uncollected criterion
    rather than a pass. The resolver is what translates a case's natural-language ``spec`` into a
    tool call; no offline resolver exists, so an unattended run measures nothing and says so.

    Both the command benchmark and the fault suite are driven, because the criteria read different
    populations off the same outcome list: G2.1/G2.5 grade the command cases, G2.4 grades only the
    fault-declaring ones, and G2.2's rule spans the failing ops the fault suite is the only source
    of. Driving ``dev/`` alone leaves G2.4 with no population at all.

    :param gate: the gate whose cases are driven.
    :param run_dir: the run directory the audit log is written beside.
    :param splits: the split directory names under the gate's benchmark dir.
    """
    if gate != "G2":
        return []
    try:
        from benchmarks.g2 import case_run
    except ImportError:
        return []
    resolver = _command_resolver()
    if resolver is None:
        return [
            case_run.CaseOutcome(
                case_id=case.get("id", "?"),
                op_type=case.get("op_type", "?"),
                status=case_run.UNRESOLVED,
                error=(
                    "no command resolver: translating a natural-language command into a tool "
                    "call needs the MCP-client actor (operator ceremony, decisions 010/011)"
                ),
                fault_kind=_declared_fault_kind(case),
            )
            for split in splits
            for case in _load_g2_cases(gate, split)
        ]
    audit_sink = _audit_sink_for(run_dir)
    outcomes: list = []
    for split in splits:
        outcomes.extend(
            case_run.run_split(
                BENCHMARKS_ROOT / KNOWN_GATES[gate] / split,
                resolver,
                repeats=_G2_DEV_REPEATS,
                audit_sink=audit_sink,
            )
        )
    return outcomes


def _declared_fault_kind(case: dict) -> str | None:
    """The case's declared ``fault.kind``, or ``None`` when it is a command case."""
    fault = case.get("fault")
    return fault.get("kind") if isinstance(fault, dict) else None


def _load_g2_cases(gate: str, split: str) -> list[dict]:
    """Load the gate's split cases without needing FreeCAD (for the unresolved-outcome list).

    Recursive to match ``case_run.load_cases``: a fault split nests its cases one level deeper
    than ``dev/``, and a one-level glob would report zero cases for it.
    """
    split_dir = BENCHMARKS_ROOT / KNOWN_GATES[gate] / split
    cases: list[dict] = []
    for case_yaml in sorted(split_dir.rglob("case.yaml")):
        try:
            data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            cases.append(data)
    return cases


def _command_resolver():
    """The callable translating a case's command into a tool call, or ``None`` when unwired.

    A G2 case carries a natural-language ``spec`` and its geometry assertions, never a tool name
    or arguments — translating one into a call is the copilot under test doing its job. Wiring a
    scripted resolver here would grade a lookup table instead of the actor, so the offline runner
    has none and reports the criteria uncollected.
    """
    return None


def _audit_sink_for(run_dir: Path):
    """An ``AuditSink`` writing beside the run, so mutation lines carry real fingerprints."""
    try:
        from freecad_buddy.adapters.audit_log import AuditSink
    except ImportError:
        return None
    return AuditSink(run_dir / "audit.jsonl", actor="benchmark")


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

    if (run_dir / "dev_rate.json").is_file():
        return _exit_verdict_command(gate, run_id, gate_def, run_dir)

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


def _exit_verdict_command(gate: str, run_id: str, gate_def: dict, run_dir: Path) -> int:
    """Re-derive the exit verdict (leg-a per case + leg-c) from the stored exit reports.

    An exit run stores per-case reports keyed by case id (not the G1.1-G1.6 criteria the standard
    loader expects), so it is verdicted over the stored reports directly — pure over stored files,
    re-runnable by an auditor.
    """
    reports = _load_exit_reports(run_dir)
    if not reports:
        raise UsageError(f"exit run '{run_id}' has no stored reports: {run_dir / 'reports'}")
    failures = _exit_verdict_failures(gate_def, run_dir, reports)
    print(f"verdict {gate} --run {run_id} (exit):")
    for failure in failures:
        print(f"  FAILURE {failure}")
    print(f"gate {gate} exit: {'PASS' if not failures else 'FAIL'}")
    return _EXIT_OK if not failures else _EXIT_FAIL


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

    if (run_dir / "dev_rate.json").is_file():
        reports = _load_exit_reports(run_dir)
        if not reports:
            raise UsageError(f"exit run '{run_id}' has no stored reports: {run_dir / 'reports'}")
    else:
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


def faults_command(gate: str, frames_evidence: str | None = None) -> int:
    """Route ``faults <gate>`` to the gate's fault scorer as a subprocess; forward its exit code.

    G1's ``score_grader.py`` grades the planted suite with the independent validator, computes
    sensitivity/FA + Wilson CI, and merge-writes the validator block.

    G2's suite plants each fault by running its ``planted_op`` through the production mutation
    path, which needs a live FreeCAD document. The runner is FreeCAD-free, so the process it
    starts here checks the suite's structure and refuses to score it, naming the in-FreeCAD
    scorer (``score_g2_infc.py``) that produces the rates. That scorer is run by the operator
    under ``FreeCADCmd``, the same way G0's ``score_verify_shape.py`` is — the runner never
    spawns a FreeCAD interpreter.

    G3's ``score_g3_validators.py`` checks the suite's structure and computes G3.E.3 and G3.E.4
    from committed evidence. ``frames_evidence`` names the directory holding the leg's
    ``G3.E.3.1.1.x.json`` file and is forwarded to it; it is a usage error for any other gate.

    An unknown gate or a gate with no scorer is a clean usage error (exit 2), never a traceback.
    """
    if gate not in KNOWN_GATES:
        raise UsageError(f"unknown gate '{gate}' (known: {', '.join(sorted(KNOWN_GATES))})")
    scorer = _FAULT_SCORERS.get(gate)
    if scorer is None:
        raise UsageError(f"no fault scorer wired for gate '{gate}'")
    scorer_path = _REPO_ROOT / scorer
    if not scorer_path.is_file():
        raise UsageError(f"fault scorer not found: {scorer_path}")
    # NFR1: never score the grader while it collides with the actor — the identity guard applies
    # to the fault-scoring path too, not only the stub run.
    _preflight_actor_grader(gate)
    command = [sys.executable, str(scorer_path)]
    if frames_evidence is not None:
        if gate != "G3":
            raise UsageError("--frames-evidence applies to gate G3 only")
        command += ["--frames-evidence", frames_evidence]
    completed = subprocess.run(command)
    return completed.returncode


def _heldout_dir(gate: str) -> Path:
    return BENCHMARKS_ROOT / KNOWN_GATES[gate] / "heldout"


def _require_unseal_key() -> str:
    key = os.environ.get(_UNSEAL_KEY_ENV)
    if not key:
        raise UsageError(
            f"{_UNSEAL_KEY_ENV} is not set — the held-out set is operator-key-gated; "
            f"set {_UNSEAL_KEY_ENV} to seal or run --exit (no offline fallback)"
        )
    return key


def _git_sha() -> str:
    """The current commit sha for the unseal event, or ``"unknown"`` if git is unavailable."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    sha = completed.stdout.strip()
    return sha if completed.returncode == 0 and sha else "unknown"


def seal_command(gate: str) -> int:
    """Seal ``gate``'s held-out split into ``SEAL.json`` + ``heldout.tar.enc`` (key-gated)."""
    if gate not in _SEALABLE_GATES:
        raise UsageError(
            f"seal is only defined for gates {', '.join(sorted(_SEALABLE_GATES))}, got {gate!r}"
        )
    _load_gate(gate)
    key = _require_unseal_key()
    from benchmarks.harness import seal

    manifest = seal.seal_heldout(
        _heldout_dir(gate),
        sealed_by=os.environ.get("USER") or os.environ.get("USERNAME") or "operator",
        sealed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        key=key,
        gate=gate,
    )
    print(
        f"seal {gate}: wrote {seal.MANIFEST_NAME} + {seal.ARCHIVE_NAME} "
        f"(case_count={manifest['case_count']}, archive_sha256={manifest['archive_sha256']})"
    )
    return _EXIT_OK


def _exit_case_reports(result, tier) -> list[dict]:
    """One stored report PER CASE carrying the case's majority-of-R verdict + the tier Wilson CI.

    Emits exactly one report per graded case (not one per repeat): its ``checks`` are a repeat whose
    derived verdict matches the case's majority outcome, so leg-a re-derives the majority-of-R
    verdict from stored files (not an arbitrary single repeat), and the majority tally
    (``passes``/``repeats``) is recorded in the check detail. The banner ``wilson_ci`` is the tier
    CI the exit is measured on, so leg-c reads the R>=10 evidence off each report. A same-cased set
    of repeat reports would otherwise collapse to one arbitrary survivor on disk.
    """
    stamped: list[dict] = []
    for case in tier.cases:
        representative = _majority_report(case)
        report = json.loads(json.dumps(representative))
        report["banner"]["wilson_ci"] = tier.wilson_ci
        passes = sum(1 for p in case.repeat_passes if p)
        for check in report["checks"]:
            check.setdefault("detail", {})
            check["detail"]["majority"] = {"passes": passes, "repeats": len(case.repeat_passes)}
        require_wilson_ci_for_rates(report)
        stamped.append(report)
    return stamped


def _majority_report(case) -> dict:
    """The repeat report whose derived verdict matches the case's majority (``case.passed``).

    Falls back to the first repeat report if none matches (cannot happen for a well-formed case,
    but keeps the exit a labelled dry-run rather than an ``IndexError`` on a degenerate empty set).
    """
    from freecad_buddy.contracts.report import derive_verdict

    want_ok = case.passed
    for report in case.reports:
        if (derive_verdict(report) == "OK") == want_ok:
            return report
    return case.reports[0]


def _g1_exit_eval(extract_dir: Path, run_dir: Path):  # noqa: ARG001 - the seam's fixed signature
    """Run G1's held-out eval; return (per-case reports, dev rate, tier).

    Offline this replays the scripted plans at R>=10, which is a labelled machinery dry-run
    and never the operator pass-rate.
    """
    from benchmarks.g1.actor_run import _load_broken_cases, run_actor_eval
    from benchmarks.harness.actor import Actor
    from benchmarks.harness.scripted_backend import ScriptedBackend

    plans = {case["id"]: _scripted_plan_for(case) for case in _load_broken_cases()}
    backend = ScriptedBackend(plans)
    actor = Actor(_offline_profile_registry())
    result = run_actor_eval(actor, backend, repeats=_EXIT_REPEATS)
    tier = result.n30 if result.escalated else result.n10
    dev_rate = result.n10.passed_count / len(result.n10.cases)
    return _exit_case_reports(result, tier), dev_rate, tier


def _g2_exit_eval(extract_dir: Path, run_dir: Path):
    """Run G2's held-out eval over the unsealed set; return (per-case reports, dev rate, tier).

    Driving a held-out command needs the MCP-client actor that translates it into a tool call, so
    without a wired resolver this produces no case reports and the caller fails the exit honestly
    rather than scoring an undriven set. The unsealed case content is never read here beyond the
    driver's own use of it.
    """
    raise UsageError("G2 exit evaluation is not reachable without a command resolver")


def _g2_exit_precondition() -> None:
    """Refuse a G2 exit that cannot be evaluated, before anything unseals the held-out set.

    Gating this on the resolver alone would still spend an unseal once a resolver is wired but
    the evaluator is not, so the evaluator's own reachability is checked here too: whatever makes
    ``_g2_exit_eval`` raise must refuse before the set is decrypted, never after.

    :raises UsageError: when no command resolver is wired, or when the eval is still the stub.
    """
    if _command_resolver() is None:
        raise UsageError(
            "G2 --exit needs the MCP-client actor to translate each held-out command into a "
            "tool call; no command resolver is wired (operator ceremony, decisions 010/011)"
        )
    if _EXIT_EVALUATORS.get("G2") is _g2_exit_eval:
        raise UsageError(
            "G2 --exit has a command resolver but no held-out evaluator: _g2_exit_eval is the "
            "unimplemented stub, so the set would be unsealed for a run that measures nothing"
        )


def _g3_exit_eval(extract_dir: Path, run_dir: Path):
    """Run G3's held-out eval; unreachable until the external agent harness actor lands.

    Driving a held-out spec needs the actor the runner spawns (Story 4.5), so this stub only
    raises. ``_g3_exit_precondition`` refuses first, so the set is never unsealed to reach it.
    """
    raise UsageError("G3 exit evaluation is not reachable without the external agent harness")


def _g3_exit_precondition() -> None:
    """Refuse every G3 exit before the unseal while ``_g3_exit_eval`` is the stub.

    :raises UsageError: while the held-out evaluator is unimplemented.
    """
    if _EXIT_EVALUATORS.get("G3") is _g3_exit_eval:
        raise UsageError(
            "G3 --exit has no held-out evaluator: _g3_exit_eval is the unimplemented stub, so "
            "the set would be unsealed for a run that measures nothing"
        )


_EXIT_EVALUATORS = {"G1": _g1_exit_eval, "G2": _g2_exit_eval, "G3": _g3_exit_eval}

# Checked before the unseal: an exit that cannot be evaluated must not spend an unseal event.
_EXIT_PRECONDITIONS = {"G2": _g2_exit_precondition, "G3": _g3_exit_precondition}


def run_exit_command(gate: str, run_id: str) -> int:
    """Unseal the held-out set, run the R>=10 eval, verdict it (leg-c), burn on FAIL.

    Key-gated (exit-2 without ``FREECAD_BUDDY_UNSEAL_KEY``). Verifies ``archive_sha256`` before
    extracting to a temp dir, runs the actor eval at R>=10 over the unsealed set, writes per-case
    reports + ``dev_rate.json``, computes the verdict (including leg-c), burns the set on FAIL, and
    always deletes the temp extraction. Offline this is a labelled machinery dry-run over the
    scripted double, NOT the operator pass-rate (decision 010).
    """
    gate_def = _load_gate_def(gate)
    if gate_def.get("verdict", {}).get("heldout") != "sealed":
        raise UsageError(
            f"--exit is only defined for a gate declaring verdict.heldout: sealed, "
            f"got {gate!r}"
        )
    evaluate = _EXIT_EVALUATORS.get(gate)
    if evaluate is None:
        raise UsageError(f"no exit evaluator wired for gate {gate!r}")
    _preflight_actor_grader(gate)
    key = _require_unseal_key()
    precondition = _EXIT_PRECONDITIONS.get(gate)
    if precondition is not None:
        precondition()
    _refuse_reused_run_dir(gate, run_id)

    import shutil

    from benchmarks.harness import seal

    try:
        extract_dir = seal.unseal_heldout(
            _heldout_dir(gate),
            key=key,
            run_id=run_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            git_sha=_git_sha(),
        )
    except seal.SealError as exc:
        raise UsageError(str(exc)) from exc

    try:
        print(
            f"run {gate} --exit: unsealed held-out set (machinery dry-run at "
            f"R={_EXIT_REPEATS}; NOT the operator pass-rate — decisions 010/011)"
        )
        run_dir = _run_dir(gate, run_id)
        reports, dev_rate, tier = evaluate(extract_dir, run_dir)
        for report in reports:
            case_id = report["subject"].get("case", report["subject"]["criterion"])
            _atomic_write_json(run_dir / "reports" / f"{case_id}.json", report)
        _atomic_write_json(run_dir / "dev_rate.json", {"dev_rate": dev_rate})

        from freecad_buddy.contracts.report import derive_verdict

        exit_reports = _load_exit_reports(run_dir)
        if not exit_reports:
            raise UsageError(f"exit run '{run_id}' produced no case reports: {run_dir / 'reports'}")
        heldout_rate = sum(1 for r in exit_reports if derive_verdict(r) == "OK") / len(exit_reports)
        # The `--exit` run's own verdict + burn key off the substantive eval legs (a/c) only; the
        # human tokens (leg-d) and validator currency (leg-b) are attested/re-checked at the later
        # `verdict --run` step, so a not-yet-attested token must not burn the set (spec I/O matrix).
        failures = _exit_eval_failures(gate_def, run_dir, exit_reports)
        passed = not failures
        _print_exit_summary(gate, run_id, tier, dev_rate, heldout_rate, failures)
        if not passed:
            seal.burn_seal(
                _heldout_dir(gate),
                run_id=run_id,
                reason="; ".join(failures)[:200],
            )
        return _EXIT_OK if passed else _EXIT_FAIL
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def _refuse_reused_run_dir(gate: str, run_id: str) -> None:
    """Refuse an exit run whose run dir already holds criterion reports from a dev run.

    ``_load_exit_reports`` globs every ``reports/*.json``, so a dev run's per-criterion reports
    left in the same run dir would join the held-out case reports and be scored as held-out
    evidence — polluting the gap math and burning the set over contamination.

    The glob matches what ``_load_exit_reports`` reads — every ``*.json``, not just the
    criterion-shaped names — because any stored report it would fold into the gap math is
    contamination, whatever it is called.

    :raises UsageError: when the run dir already holds any stored report.
    """
    reports_dir = _run_dir(gate, run_id) / "reports"
    existing = sorted(p.name for p in reports_dir.glob("*.json"))
    if existing:
        raise UsageError(
            f"run id {run_id!r} already holds reports ({', '.join(existing)}); "
            f"use a fresh run id for the exit ceremony"
        )


def _refuse_exit_run_dir(gate: str, run_id: str) -> None:
    """Refuse a dev run whose run dir belongs to a completed exit ceremony.

    The contamination runs both ways. ``_refuse_reused_run_dir`` stops an exit ceremony from
    reusing a dev run's id; this stops the reverse — a dev ``run`` writing its six criterion
    reports into an exit run dir, where ``dev_rate.json`` routes ``verdict``/``attest`` through
    ``_load_exit_reports``, which globs every stored report and would fold the dev criteria into
    the held-out gap math.

    :raises UsageError: when the run dir already holds an exit run's ``dev_rate.json``.
    """
    if (_run_dir(gate, run_id) / "dev_rate.json").is_file():
        raise UsageError(
            f"run id {run_id!r} belongs to an exit ceremony (dev_rate.json present); "
            f"use a fresh run id for a dev run"
        )


def _load_exit_reports(run_dir: Path) -> list[dict]:
    """Read every stored exit report as a mapping; a parse/shape error is an exit-2 UsageError.

    Mirrors ``load_reports``' contract: a malformed, non-mapping, or empty/non-list-``checks``
    stored report is a clean loader error, never a raw traceback and never vacuous-OK on the
    auditor ``verdict --run`` path (``derive_verdict`` returns ``OK`` for a non-list ``checks``,
    so an unvalidated report with its ``checks`` stripped would launder a FAIL into a PASS).
    """
    reports: list[dict] = []
    for path in sorted((run_dir / "reports").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UsageError(
                f"malformed exit report reports/{path.name} ({exc.__class__.__name__})"
            ) from exc
        if not isinstance(data, dict):
            raise UsageError(f"malformed exit report reports/{path.name}: not a mapping")
        checks = data.get("checks")
        if not isinstance(checks, list) or not checks:
            raise UsageError(f"malformed exit report reports/{path.name}: empty/non-list checks")
        reports.append(data)
    return reports


def _case_of(report: dict) -> str:
    subject = report.get("subject")
    return subject.get("case", "?") if isinstance(subject, dict) else "?"


def _exit_verdict_failures(gate_def: dict, run_dir: Path, reports: list[dict]) -> list[str]:
    """Legs a/b/c/d for the exit run (per-case re-derived leg-a, not the criteria-keyed loader).

    Leg-a RE-DERIVES each case verdict via ``derive_verdict`` (the stored ``verdict`` field is
    never trusted — AD-13); leg-b re-checks cited-validator currency; leg-c enforces the R>=10
    banners + dev/held-out gap; leg-d requires the gate's human tokens bound to this exit run.
    """
    from freecad_buddy.contracts.report import derive_verdict

    from benchmarks.harness.verdict import (
        check_exit_run,
        check_token,
        check_validator_currency,
    )

    failures: list[str] = []
    for report in reports:
        verdict = derive_verdict(report)
        if verdict != "OK":
            failures.append(f"leg-a: {_case_of(report)} verdict {verdict}")
    for name in check_validator_currency(gate_def, _load_validators(), _validator_src_hasher):
        failures.append(f"leg-b: validator {name}")
    for failure in check_exit_run(run_dir, gate_def, reports):
        failures.append(f"leg-c: {failure}")
    required_tokens = gate_def.get("required_tokens", []) or []
    for failure in check_token(run_dir, reports, required_tokens):
        failures.append(f"leg-d: {failure}")
    return failures


def _exit_eval_failures(gate_def: dict, run_dir: Path, reports: list[dict]) -> list[str]:
    """The substantive held-out failures (leg-a per-case + leg-c) that a `--exit` run burns on.

    Per the spec I/O matrix the burn trigger is "exit reports fail a rule OR gap >15pp" — the
    eval's own verdict. The human tokens (leg-d) and validator currency (leg-b) are attested and
    re-checked at the later `verdict --run` step, so a not-yet-attested token must NOT burn the
    set before the operator can bind it.
    """
    from freecad_buddy.contracts.report import derive_verdict

    from benchmarks.harness.verdict import check_exit_run

    failures: list[str] = []
    for report in reports:
        verdict = derive_verdict(report)
        if verdict != "OK":
            failures.append(f"leg-a: {_case_of(report)} verdict {verdict}")
    for failure in check_exit_run(run_dir, gate_def, reports):
        failures.append(f"leg-c: {failure}")
    return failures


def _print_exit_summary(
    gate: str, run_id: str, tier, dev_rate: float, heldout_rate: float, failures: list[str]
) -> None:
    print(
        f"run {gate} --exit {run_id}: held-out {heldout_rate:.3f} vs dev {dev_rate:.3f} "
        f"(tier r={tier.wilson_ci['r']}/n={tier.wilson_ci['n']})"
    )
    for failure in failures:
        print(f"  FAILURE {failure}")
    print(f"gate {gate} exit: {'PASS' if not failures else 'FAIL (set burned)'}")


def _offline_profile_registry():
    """Build the read-only profile registry for the offline actor-run (no FreeCAD).

    The offline run never opens a real document, so each read-only tool is a stub handler; the
    registry's tool NAMES are the true read-only allow-list, so the actor drives the identical
    surface and its recorded calls are asserted against it. A live actor-run (operator-gated) would
    instead build the real profile via ``build_readonly_profile`` over a live document registry.
    """
    from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
    from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE

    registry = MethodRegistry()
    for name in sorted(READ_ONLY_PROFILE):
        registry.register(
            RpcMethod(
                name=name,
                handler=lambda **_kwargs: {
                    "schema": "fcb.result-envelope/1",
                    "status": "INVALID_INPUT",
                    "detail": {"code": "invalid_input.offline_actor_run", "message": "offline"},
                    "structured_content": {},
                    "text": "",
                },
            )
        )
    return registry


def _scripted_plan_for(case: dict):
    """The recorded plan for one broken-doc case: two read-only calls, then the answer.

    ``query_tree_summary`` then ``verify_recompute``, followed by an answer naming the expected
    object and a matching cause keyword, so the deterministic grader PASSES every case. The offline
    run exercises escalation + report build + Wilson CI end-to-end, never model quality — the >=80 %
    figure is a measured operator run and is never asserted by this deterministic double.
    """
    expected = case.get("expected", {})
    obj = expected.get("object", "")
    keywords = expected.get("cause_keywords") or []
    keyword = keywords[0] if keywords else ""
    steps = [
        ("query_tree_summary", {"doc": "d"}),
        ("verify_recompute", {"doc": "d"}),
    ]
    return steps, f"{obj} is in error: {keyword}."


def actor_run_command(gate: str) -> int:
    """Run the G1 actor-run over the read-only profile; grade + escalate.

    Offline (no operator backend): replays the scripted plans over the stub
    profile registry, runs the tiered n10->n30 escalation via ``actor_run.run_actor_eval``, prints
    the per-tier summary + Wilson CI, and exits 0 when the scripted answers pass. A live backend
    (any ``FREECAD_BUDDY_G1_ACTOR_BACKEND`` value other than ``offline``) is operator-only and NOT
    wired here — it is skipped in CI so no key/secret ever enters the pipeline.
    """
    if gate != "G1":
        raise UsageError(f"--actor-run is only defined for gate G1, got {gate!r}")
    _load_gate(gate)
    _preflight_actor_grader(gate)

    backend_choice = (os.environ.get(_ACTOR_BACKEND_ENV) or "").strip().lower()
    if backend_choice and backend_choice != "offline":
        # Any non-empty value that is not the explicit "offline" opt-in is treated as a live
        # request (including "live", "1", "true"): the live backend is operator-gated and never
        # wired in CI, so it hard-fails rather than silently running the offline scripted double.
        raise UsageError(
            f"actor-run backend {backend_choice!r} is operator-gated and not wired in this "
            "harness; unset the env var for the offline run, or run the live eval via an "
            "OpenAI-compatible endpoint (llama.cpp/Qwen) per docs/decisions/011"
        )

    from benchmarks.g1.actor_run import _load_broken_cases, run_actor_eval
    from benchmarks.harness.actor import Actor
    from benchmarks.harness.scripted_backend import ScriptedBackend

    print(
        f"actor-run {gate}: no operator backend; replaying scripted plans over the read-only "
        f"surface (live eval skipped)"
    )
    plans = {case["id"]: _scripted_plan_for(case) for case in _load_broken_cases()}
    backend = ScriptedBackend(plans)
    actor = Actor(_offline_profile_registry())
    result = run_actor_eval(actor, backend, repeats=3)

    _print_actor_run_summary(gate, result)
    # The run PASSES on the tier verdict (decision 008): the escalated n=30 tier when it escalated,
    # else the n=10 tier (>=8/10). A per-report all-OK check would report an honest 8/10 tier pass
    # as a failure — the exit code follows the tier threshold, not every individual case.
    tier = result.n30 if result.escalated else result.n10
    return _EXIT_OK if tier.passed else _EXIT_FAIL


def _print_actor_run_summary(gate: str, result) -> None:
    n10 = result.n10
    ci = n10.wilson_ci
    print(
        f"actor-run {gate}: n10 {n10.passed_count}/{len(n10.cases)} passed "
        f"(Wilson CI [{ci['low']:.3f}, {ci['high']:.3f}])"
    )
    n10_verdict = "PASS" if n10.passed else "FAIL"
    print(f"actor-run {gate}: n10 tier {n10_verdict} (>=8/10)")
    if result.escalated:
        n30 = result.n30
        ci30 = n30.wilson_ci
        n30_verdict = "PASS" if n30.passed else "FAIL"
        print(
            f"actor-run {gate}: 10/10 -> escalated to n=30: {n30.passed_count}/{len(n30.cases)} "
            f"passed {n30_verdict} (>=80%) (Wilson CI [{ci30['low']:.3f}, {ci30['high']:.3f}])"
        )
    else:
        print(f"actor-run {gate}: n10 below 10/10 -> no escalation (decision 008)")
    print(f"actor-run {gate}: emitted {len(result.reports)} case reports")


def _filter_criteria(criteria: list[dict], criterion_id: str | None) -> list[dict]:
    if criterion_id is None:
        return criteria
    selected = [c for c in criteria if c.get("id") == criterion_id]
    if not selected:
        raise UsageError(f"--criterion '{criterion_id}' matched no criterion")
    return selected


def _actor_descriptors(data: dict) -> list[tuple[str, dict]]:
    """Every actor descriptor in a gate mapping: each ``actor*`` key + each ``actors:`` list entry.

    A gate may declare a single ``actor:`` block, additional ``actor_local:`` (and any other
    ``actor*``) blocks for extra backends, and/or an ``actors:`` list of blocks. All are collected
    so the NFR1 preflight checks the grader against every backend, not just ``actor:``.
    """
    descriptors: list[tuple[str, dict]] = []
    for key, value in data.items():
        if key == "actors":
            if not isinstance(value, list):
                raise UsageError(f"gate.yaml 'actors' must be a list, got {type(value).__name__}")
            for i, entry in enumerate(value):
                if not isinstance(entry, dict):
                    raise UsageError(f"gate.yaml actors[{i}] must be a mapping, not a scalar")
                descriptors.append((f"actors[{i}]", entry))
        elif isinstance(key, str) and key.startswith("actor"):
            if not isinstance(value, dict):
                raise UsageError(f"gate.yaml '{key}' must be a mapping, not a scalar")
            descriptors.append((key, value))
    return descriptors


def _preflight_actor_grader(gate: str) -> None:
    """Hard-fail INVALID_INPUT if any actor descriptor and the ``grader:`` resolve to one model.

    NFR1 / harness §8: the actor never grades itself. The check spans EVERY actor descriptor — the
    ``actor:`` key, any additional ``actor*`` key (e.g. ``actor_local:``), and any ``actors:`` list
    entry — so a second backend cannot slip an actor==grader collision past the guard. Same model
    id is the collision; a different ``context`` string does not make the same underlying model an
    independent grader. Raises ``UsageError`` (exit-2, clean message, never a traceback). Gates
    without a grader block or without any actor block (e.g. G0's deterministic-tool gate) are inert.
    """
    gate_file = BENCHMARKS_ROOT / KNOWN_GATES[gate] / "gate.yaml"
    try:
        data = yaml.safe_load(gate_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UsageError(f"unreadable gate.yaml ({gate_file}): {exc.__class__.__name__}") from exc
    if not isinstance(data, dict):
        return
    grader = data.get("grader")
    if not isinstance(grader, dict):
        return
    grader_model = grader.get("model")
    if grader_model is None:
        return
    for key, actor in _actor_descriptors(data):
        if actor.get("model") == grader_model:
            raise UsageError(
                f"{key}==grader identity collision in {gate_file}: both resolve to model "
                f"{grader_model!r} (NFR1: the actor must never grade itself — the grader must "
                f"be a different model)"
            )


def run_gate(gate: str, criterion_id: str | None = None) -> tuple[list[dict], int]:
    """Run ``gate`` against the stub; return (reports, exit_code). Never raises UsageError:
    it is converted to an exit-2 signal by ``main`` — but here we let it propagate so callers
    (tests) can assert on it. The stub run itself never raises."""
    # Validate the gate (known id + parseable gate.yaml) first, then run the actor==grader
    # identity preflight BEFORE the --criterion filter so a non-matching --criterion cannot skip
    # the NFR1 identity check.
    all_criteria = _load_gate(gate)
    _preflight_actor_grader(gate)
    criteria = _filter_criteria(all_criteria, criterion_id)
    bridge = StubBridge()
    reports: list[dict] = []
    for criterion in criteria:
        outcome = bridge.call(f"criterion:{criterion['id']}")
        criterion = {**criterion, "gate": criterion.get("gate", gate)}
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
    parser.add_argument(
        "--actor-run",
        dest="actor_run",
        action="store_true",
        help="run the G1 actor-run (offline scripted backend; live eval operator-gated)",
    )
    parser.add_argument("--criterion", help="run a single criterion id, e.g. G0.3")
    # --case was accepted-but-ignored previously; reject it explicitly in stub mode.
    parser.add_argument("--case", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _parse_subcommand(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="runner.py", description="G0 gate runner.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("gate", help="gate id, e.g. G0")
    run_parser.add_argument("--run", dest="run_id", required=True, help="run id")
    run_parser.add_argument(
        "--exit",
        dest="is_exit",
        action="store_true",
        help="G1 gate exit: unseal the held-out set, run the R>=10 eval, burn on FAIL",
    )
    verdict_parser = sub.add_parser("verdict")
    verdict_parser.add_argument("gate", help="gate id, e.g. G0")
    verdict_parser.add_argument("--run", dest="run_id", required=True, help="run id")
    attest = sub.add_parser("attest")
    attest.add_argument("gate", help="gate id, e.g. G0")
    attest.add_argument("--run", dest="run_id", required=True, help="run id")
    attest.add_argument("--type", dest="token_type", required=True, help="token type")
    attest.add_argument("--outcome", default="PASS", help="token outcome (PASS/FAIL)")
    faults = sub.add_parser("faults")
    faults.add_argument("gate", help="gate id, e.g. G1")
    faults.add_argument(
        "--frames-evidence",
        dest="frames_evidence",
        help="G3 only: directory holding the G3.E.3.1.1.x.json frame evidence",
    )
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("gate", help="gate id, e.g. G1")
    return parser.parse_args(argv)


def _run_subcommand(argv: list[str]) -> int:
    try:
        args = _parse_subcommand(argv)
    except SystemExit:
        return _EXIT_USAGE
    try:
        if args.command == "run":
            if args.is_exit:
                return run_exit_command(args.gate, args.run_id)
            return run_command(args.gate, args.run_id)
        if args.command == "verdict":
            return verdict_command(args.gate, args.run_id)
        if args.command == "faults":
            return faults_command(args.gate, args.frames_evidence)
        if args.command == "seal":
            return seal_command(args.gate)
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
        if args.actor_run:
            if args.stub:
                raise UsageError("--actor-run and --stub are mutually exclusive")
            return actor_run_command(args.gate)
        # --stub is the stub-bridge mode; --actor-run is the live/scripted actor path.
        # Require one explicitly so the flag is meaningful, not a silent no-op.
        if not args.stub:
            raise UsageError("pass --stub (stub bridge) or --actor-run (G1 actor-run)")
        reports, exit_code = run_gate(args.gate, args.criterion)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_USAGE

    _print_summary(args.gate, reports)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
