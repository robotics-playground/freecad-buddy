"""External-process structural checker for the G3 entry gate (run under uv).

Checks the spec set and the fault suite without scoring them: that there are 20 dev specs, each
declaring a closed-set anchor frame and only the eleven closed §7.2 assertion functions, with no
sub-element index selector and no feature-metadata verdict; that every corrupted plan names a dev
spec and a check in that spec, carries a plan whose every step is a catalogued MCP tool called
with arguments its input schema accepts, and marks exactly one planted step when it is a defect
and none when it is a control; that at least ten planted plans exist beside clean controls; and
that each of the four G3 threats is countered by a planted case that exists.

It does NOT produce sensitivity or false-alarm numbers and never writes ``validators.yaml``.
Planting a corrupted plan means replaying it through the MCP mutation tools against a live
FreeCAD document and grading the part with the spec's assertions, which lands in Story 4.2. A rate
reported from here would be a number no run produced.

Exits 0 when the suite is structurally sound, 1 when it is not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
G3_ROOT = HERE.parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# verification-design.md §7.2. A G3 spec grades a finished part against written text, which is
# what this vocabulary was designed for, so G3 declares no extension (unlike G2).
CLOSED_FNS = frozenset(
    {
        "is_valid_solid",
        "count_cylindrical_holes",
        "hole_diameter",
        "hole_position",
        "hole_spacing",
        "hole_through",
        "distance_between",
        "angle_between",
        "expect_bbox",
        "expect_extent",
        "expect_volume",
    }
)
ANCHOR_KINDS = frozenset({"named_datum", "base_sketch_plane", "largest_planar_face"})
# verification-design §7.2 signs these with two selectors; without both the check is unevaluable.
TWO_SELECTOR_FNS = frozenset({"distance_between", "angle_between"})
G3_THREATS = frozenset(
    {
        "plan_looks_professional_part_deviates",
        "agent_stopped_from_lack_of_patience",
        "part_never_looked_at",
        "rate_cited_for_wrong_actor",
    }
)
EXPECTED_DEV_SPECS = 20
MIN_PLANTED_PLANS = 10
TARGET_VALIDATOR = "assertions@harness.assertions.evaluate"
OWNER_OF_THIS_SUITE = "4.1"
# The entry item that claims the spec set fails honestly against a stub.
STUB_ENTRY_ITEM = "G3.E.1"

# AD-13 bans both in a spec: an index names a sub-element that renumbers under any upstream
# edit, and a FreeCAD TypeId (``PartDesign::Hole``) marks a verdict read off feature metadata.
_INDEX_SELECTOR = re.compile(r"\b(?:Face|Edge|Vertex)\d+\b")
_FEATURE_METADATA = re.compile(r"\b\w+::\w+")


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: must be a mapping, got {type(data).__name__}")
    data["_dir"] = path.parent
    return data


def _case_files(root: Path) -> list[Path]:
    """Every ``case.yaml`` under ``root``, by exact name so a miscased file is not picked up."""
    return sorted(p for p in root.rglob("case.yaml") if p.name == "case.yaml")


def load_suite(g3_root: Path = G3_ROOT) -> dict:
    """Load the gate definition, the dev specs and both fault suites under ``g3_root``."""
    specs = []
    for path in _case_files(g3_root / "dev"):
        spec = _load_yaml(path)
        spec["_text"] = path.read_text(encoding="utf-8")
        specs.append(spec)
    faults = g3_root / "fault-injection"
    return {
        "gate": _load_yaml(g3_root / "gate.yaml"),
        "specs": specs,
        "plans": [_load_yaml(p) for p in _case_files(faults / "corrupted-plan")],
        "threat_cases": [_load_yaml(p) for p in _case_files(faults / "threat-counters")],
        "benchmarks_root": g3_root.parent,
        "reuse_survey": g3_root / "reuse-survey.md",
    }


def tool_schemas() -> dict[str, dict]:
    """The input schema of every catalogued MCP tool, keyed by tool name."""
    from freecad_buddy.hosts.tool_catalog import tool_specs

    return {spec.name: spec.input_schema for spec in tool_specs()}


def _is_planted(case: dict) -> bool:
    return (case.get("fault") or {}).get("expectation") == "DETECT"


def _check_spec_count(suite: dict) -> list[str]:
    count = len(suite["specs"])
    if count != EXPECTED_DEV_SPECS:
        return [f"dev/: {count} specs, expected {EXPECTED_DEV_SPECS}"]
    return []


def _check_spec_vocabulary(suite: dict) -> list[str]:
    problems = []
    for spec in suite["specs"]:
        assertions = spec.get("assertions") or {}
        kind = (assertions.get("anchor_frame") or {}).get("kind")
        if kind not in ANCHOR_KINDS:
            problems.append(f"{spec.get('id')}: anchor_frame.kind {kind!r} not in closed set")
        checks = assertions.get("checks") or []
        if not checks:
            problems.append(f"{spec.get('id')}: declares no checks")
        for check in checks:
            fn = check.get("fn") if isinstance(check, dict) else None
            if fn not in CLOSED_FNS:
                problems.append(f"{spec.get('id')}: fn {fn!r} is not a closed §7.2 primitive")
            elif fn in TWO_SELECTOR_FNS and not {"select_a", "select_b"} <= set(check):
                problems.append(f"{spec.get('id')}: {fn} needs both select_a and select_b")
    return problems


def _check_spec_selectors(suite: dict) -> list[str]:
    problems = []
    for spec in suite["specs"]:
        text = repr(spec.get("assertions"))
        for match in _INDEX_SELECTOR.findall(text):
            problems.append(f"{spec.get('id')}: sub-element index selector {match!r}")
        for match in _FEATURE_METADATA.findall(text):
            problems.append(f"{spec.get('id')}: feature-metadata reference {match!r}")
    return problems


def _check_spec_derivations(suite: dict) -> list[str]:
    """Every spec carries its expected values' derivation inline, from the spec prose."""
    return [
        f"{spec.get('id')}: no inline 'Derivations:' comment"
        for spec in suite["specs"]
        if "Derivations:" not in spec["_text"]
    ]


def _check_provenance(suite: dict) -> list[str]:
    """Every spec and fault case names a manifest that binds back to that case file."""
    root = suite["benchmarks_root"]
    problems = []
    for case in suite["specs"] + suite["plans"] + suite["threat_cases"]:
        declared = case.get("provenance")
        if not isinstance(declared, str) or not declared:
            problems.append(f"{case.get('id')}: names no provenance manifest")
            continue
        manifest_path = (case["_dir"] / declared).resolve()
        if not manifest_path.is_file():
            problems.append(f"{case.get('id')}: provenance manifest {declared} is missing")
            continue
        artifact = yaml.safe_load(manifest_path.read_text(encoding="utf-8")).get("artifact")
        expected = (case["_dir"] / "case").relative_to(root).as_posix()
        if artifact != expected:
            problems.append(f"{case.get('id')}: manifest binds {artifact!r}, not {expected!r}")
    return problems


def _check_fault_shape(suite: dict) -> list[str]:
    criteria = {c.get("id") for c in suite["gate"].get("criteria", [])}
    controls = {c.get("id") for c in suite["plans"] if not _is_planted(c)}
    problems = []
    for case in suite["plans"] + suite["threat_cases"]:
        case_id = case.get("id")
        fault = case.get("fault") or {}
        kind, expectation = fault.get("kind"), fault.get("expectation")
        if (kind, expectation) not in {
            ("planted_defect", "DETECT"),
            ("clean_control", "PASS_CLEAN"),
        }:
            problems.append(f"{case_id}: fault.kind {kind!r} disagrees with {expectation!r}")
        if case.get("criterion") not in criteria:
            problems.append(f"{case_id}: criterion {case.get('criterion')!r} is not a G3 criterion")
        if case.get("fixture") != "pending":
            problems.append(f"{case_id}: fixture is {case.get('fixture')!r}, expected 'pending'")
    for case in suite["plans"]:
        if case.get("targets_validator") != TARGET_VALIDATOR:
            problems.append(f"{case.get('id')}: targets_validator is not {TARGET_VALIDATOR}")
    for case in suite["threat_cases"]:
        if not _is_planted(case):
            problems.append(f"{case.get('id')}: a threat counter must be a planted defect")
        if case.get("plan_ref") not in controls:
            problems.append(f"{case.get('id')}: plan_ref names no corrupted-plan clean control")
        if not isinstance(case.get("planted_evidence"), dict) or not case["planted_evidence"]:
            problems.append(f"{case.get('id')}: declares no planted_evidence")
    return problems


def _check_fault_mapping(suite: dict) -> list[str]:
    """Every fault case names a dev spec, and a planted plan names a check that spec declares."""
    fns_by_spec = {
        spec.get("id"): {c.get("fn") for c in (spec.get("assertions") or {}).get("checks") or []}
        for spec in suite["specs"]
    }
    problems = [
        f"{case.get('id')}: spec_ref {case.get('spec_ref')!r} names no dev spec"
        for case in suite["plans"] + suite["threat_cases"]
        if case.get("spec_ref") not in fns_by_spec
    ]
    for case in suite["plans"]:
        spec_ref, detected_by = case.get("spec_ref"), case.get("detected_by")
        if (
            _is_planted(case)
            and spec_ref in fns_by_spec
            and detected_by not in fns_by_spec[spec_ref]
        ):
            problems.append(
                f"{case.get('id')}: detected_by {detected_by!r} names no check in {spec_ref}"
            )
    return problems


def _check_plan_steps(suite: dict, tools: dict[str, dict]) -> list[str]:
    """Every plan step calls a catalogued tool with arguments that tool's input schema accepts."""
    from jsonschema.validators import validator_for

    problems = []
    for case in suite["plans"]:
        plan = case.get("plan")
        if not isinstance(plan, list) or not plan:
            problems.append(f"{case.get('id')}: carries no plan")
            continue
        for index, step in enumerate(plan):
            where = f"{case.get('id')}: step {index}"
            if not isinstance(step, dict) or set(step) != {"tool", "args"}:
                problems.append(f"{where}: must be exactly {{tool, args}}")
                continue
            schema = tools.get(step["tool"])
            if schema is None:
                problems.append(f"{where}: tool {step['tool']!r} is not in tool_specs()")
                continue
            validator = validator_for(schema)(schema)
            for error in validator.iter_errors(step["args"]):
                problems.append(
                    f"{where}: args fail the {step['tool']} input schema: {error.message}"
                )
    return problems


def _check_planted_steps(suite: dict) -> list[str]:
    problems = []
    for case in suite["plans"]:
        marked = case.get("planted_step")
        if not _is_planted(case):
            if marked is not None:
                problems.append(f"{case.get('id')}: a clean control marks planted_step {marked}")
            continue
        steps = case.get("plan") if isinstance(case.get("plan"), list) else []
        if type(marked) is not int or not 0 <= marked < len(steps):
            problems.append(f"{case.get('id')}: planted case marks no valid planted_step")
    return problems


def _check_fault_counts(suite: dict) -> list[str]:
    planted = sum(1 for case in suite["plans"] if _is_planted(case))
    controls = len(suite["plans"]) - planted
    problems = []
    if planted < MIN_PLANTED_PLANS:
        problems.append(f"corrupted-plan/: {planted} planted plans, need >= {MIN_PLANTED_PLANS}")
    if controls < 1:
        problems.append("corrupted-plan/: no clean control, so false alarm is unmeasurable")
    return problems


def _check_threat_coverage(suite: dict) -> list[str]:
    """Each of the four G3 threats names a planted counter case that exists in the suite."""
    planted = {
        case.get("id") for case in suite["plans"] + suite["threat_cases"] if _is_planted(case)
    }
    threats = {t.get("id"): t for t in suite["gate"].get("threats") or [] if isinstance(t, dict)}
    problems = [
        f"threat {name!r}: not declared in gate.yaml" for name in sorted(G3_THREATS - set(threats))
    ]
    for name, threat in sorted(threats.items()):
        if name not in G3_THREATS:
            problems.append(f"threat {name!r}: not one of the four G3 threats")
            continue
        listed = threat.get("counter_cases") or []
        for case_id in listed:
            if case_id not in planted:
                problems.append(f"threat {name!r}: counter case {case_id!r} is not a planted case")
        if not any(case_id in planted for case_id in listed):
            problems.append(f"threat {name!r}: no planted counter case exists")
    return problems


def _check_reuse_survey(suite: dict) -> list[str]:
    """The entry gate carries its recorded reuse survey (phase-gates.md:3)."""
    if not suite["reuse_survey"].is_file():
        return [f"{suite['reuse_survey'].name}: the recorded reuse survey is missing"]
    return []


def check_suite(suite: dict, tools: dict[str, dict] | None = None) -> dict[str, list[str]]:
    """Run every structural check; return ``{check name: [problem, ...]}``.

    ``tools`` maps tool name to input schema and defaults to the live catalog.
    """
    tools = tool_schemas() if tools is None else tools
    return {
        "spec_count": _check_spec_count(suite),
        "spec_vocabulary": _check_spec_vocabulary(suite),
        "spec_selectors": _check_spec_selectors(suite),
        "spec_derivations": _check_spec_derivations(suite),
        "provenance": _check_provenance(suite),
        "fault_shape": _check_fault_shape(suite),
        "fault_mapping": _check_fault_mapping(suite),
        "plan_steps": _check_plan_steps(suite, tools),
        "planted_steps": _check_planted_steps(suite),
        "fault_counts": _check_fault_counts(suite),
        "threat_coverage": _check_threat_coverage(suite),
        "reuse_survey": _check_reuse_survey(suite),
    }


def entry_status(gate: dict, sound: bool) -> list[tuple[str, str, str]]:
    """``(id, owner, status)`` per G3.E item.

    The items this suite owns read the structural result only. That the stub run fails honestly
    is not checked here: the CI G3 stub step and ``test_should_fail_all_six_criteria_with_invalid_
    input_when_run_against_the_stub`` check it. Every other item reports ``INVALID_INPUT`` until
    its owning story lands, so G3.E stays open.
    """
    rows = []
    for item in gate.get("entry") or []:
        owner = str(item.get("owner"))
        if owner == OWNER_OF_THIS_SUITE:
            status = f"{'OK' if sound else 'FAIL'} (structural check only"
            if item.get("id") == STUB_ENTRY_ITEM:
                status += (
                    "; the honest stub failure is checked by the CI G3 stub step and "
                    "test_should_fail_all_six_criteria_with_invalid_input_when_run_against_the_stub"
                )
            status += ")"
        else:
            status = f"INVALID_INPUT (owned by Story {owner}, not landed)"
        rows.append((item.get("id"), owner, status))
    return rows


def main(argv: list[str] | None = None) -> int:
    """Check the G3 entry gate's structure, print the G3.E items, and refuse to score."""
    suite = load_suite()
    results = check_suite(suite)
    planted = sum(1 for case in suite["plans"] if _is_planted(case))
    print(
        f"g3: {len(suite['specs'])} dev specs, {planted} planted plans + "
        f"{len(suite['plans']) - planted} controls, {len(suite['threat_cases'])} threat counters"
    )
    for name, problems in results.items():
        print(f"  {name:18s} {'OK' if not problems else 'FAIL'}")
        for problem in problems:
            print(f"  {'':18s} {problem}")
    sound = not any(results.values())
    print("G3.E entry items:")
    for item_id, owner, status in entry_status(suite["gate"], sound):
        print(f"  {item_id} [{owner}] {status}")
    print(
        "\n  NOT SCORED HERE: planting a corrupted plan means replaying it through the MCP "
        "mutation\n  tools and grading the part, which lands in Story 4.2. No sensitivity, "
        "false_alarm or\n  validator_sha is computed and validators.yaml is not written."
    )
    return 0 if sound else 1


if __name__ == "__main__":
    sys.exit(main())
