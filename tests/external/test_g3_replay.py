"""The G3 corrupted-plan replay scorer and the G3.E.3 / G3.E.4 entry items, with no FreeCAD.

Covers every I/O matrix row of Story 4.2b. The replay rows drive ``score_g3_replay`` against a
fake MCP session that answers each tool call from a script, so classification is tested on the
envelope shapes the H1 host returns without a FreeCAD process. The live builds are the
operator-run scorer's job.
"""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
FAULT_DIR = BENCHMARKS / "g3" / "fault-injection"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(FAULT_DIR))

import score_g3_replay as replay  # noqa: E402
import score_g3_validators as checker  # noqa: E402

from benchmarks import runner  # noqa: E402

INVALID_CODE = "invalid_input.unsupported_assertion"
SPEC = {"assertions": {"anchor_frame": {"kind": "base_sketch_plane", "ref": "XY_Plane"}}}
SPEC["assertions"]["checks"] = [{"fn": "hole_diameter", "expect": 5.5}]
XY_FRAME = {
    "kind": "base_sketch_plane",
    "ref": "XY_Plane",
    "entity": "XY_Plane",
    "origin": [0.0, 0.0, 0.0],
    "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    "units": "mm",
}


def _check(fn: str, passed: bool, code: str | None = None) -> dict:
    return {
        "id": f"assert.{fn}",
        "passed": passed,
        "measured": None if code else 1.0,
        "detail": {"code": code} if code else {"message": ""},
    }


def _verified(status: str, checks: list[dict], frame: dict | None = None) -> dict:
    banner = {"anchor_frame": frame or XY_FRAME, "freecad_version": "1.1.0"}
    return {"status": status, "structured_content": {"checks": checks, "banner": banner}}


class FakeSession:
    """Answers MCP tool calls from a script, the way the H1 host's envelopes look.

    ``verify`` holds the ``verify_shape`` envelopes in call order; ``failing_tool`` names a
    mutation tool whose confirmed call returns ``SPEC_FAILED``.
    """

    def __init__(self, verify: list[dict], failing_tool: str | None = None):
        self.verify = list(verify)
        self.failing_tool = failing_tool
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool: str, args: dict):
        self.calls.append((tool, args))
        if tool == "document_create":
            envelope = {"status": "OK", "structured_content": {"doc": "doc-1"}}
        elif tool == "preview_dry_run":
            envelope = {"status": "OK", "structured_content": {"preview_id": "p-1"}}
        elif tool == "verify_shape":
            envelope = self.verify.pop(0)
        elif tool == self.failing_tool:
            envelope = {"status": "SPEC_FAILED", "detail": {"message": "post-verify failed"}}
        else:
            envelope = {"status": "OK", "structured_content": {}}
        return SimpleNamespace(structuredContent=envelope, content=[])


def _plan(diameter: float) -> list[dict]:
    return [
        {"tool": "document_create", "args": {"label": "case"}},
        {
            "tool": "feature_hole",
            "args": {"doc": "$doc", "name": "Holes", "diameter": {"value": diameter}},
        },
    ]


def _planted_case() -> dict:
    return {
        "id": "g3-fault-plan-wrong-hole-diameter",
        "spec_ref": "g3-dev-001-mounting-plate",
        "targets_validator": "spec_assertions@usecases.assertions.evaluate_checks",
        "fault": {"kind": "planted_defect", "expectation": "DETECT"},
        "detected_by": "hole_diameter",
        "planted_step": 1,
        "plan": _plan(8.0),
        "faithful_args": {"doc": "$doc", "name": "Holes", "diameter": {"value": 5.5}},
    }


def _control_case() -> dict:
    return {
        "id": "g3-fault-plan-control-faithful-mounting-plate",
        "spec_ref": "g3-dev-001-mounting-plate",
        "targets_validator": "spec_assertions@usecases.assertions.evaluate_checks",
        "fault": {"kind": "clean_control", "expectation": "PASS_CLEAN"},
        "plan": _plan(5.5),
    }


def _score(cases: list[dict], session: FakeSession, monkeypatch) -> tuple[list[dict], dict]:
    monkeypatch.setattr(replay, "load_spec", lambda _ref: SPEC)
    return asyncio.run(replay.score_suite(session, cases))


# --------------------------------------------------------------------------- #
# I/O matrix: classification
# --------------------------------------------------------------------------- #


def test_should_detect_the_case_when_the_detected_by_check_fails_with_a_measured_value(
    monkeypatch,
):
    # Arrange
    session = FakeSession(
        [
            _verified("SPEC_FAILED", [_check("hole_diameter", False)]),
            _verified("OK", [_check("hole_diameter", True)]),
        ]
    )

    # Act
    rows, _ = _score([_planted_case()], session, monkeypatch)

    # Assert
    assert rows[0]["outcome"] == replay.DETECTED
    assert rows[0]["clean"] == replay.PASS_CLEAN
    totals = replay.tally(rows)
    assert (totals["planted"], totals["detected"], totals["controls"]) == (1, 1, 1)
    assert replay.bars_met(totals)


def test_should_count_a_miss_and_list_it_when_only_invalid_input_checks_fail(monkeypatch):
    # Arrange: the detected_by check fails through an empty match, not a measurement.
    session = FakeSession(
        [
            _verified("INVALID_INPUT", [_check("hole_diameter", False, INVALID_CODE)]),
            _verified("OK", [_check("hole_diameter", True)]),
        ]
    )

    # Act
    rows, _ = _score([_planted_case()], session, monkeypatch)

    # Assert
    totals = replay.tally(rows)
    assert rows[0]["outcome"] == replay.MISSED
    assert totals["missed"] == ["g3-fault-plan-wrong-hole-diameter"]
    assert totals["sensitivity"] == 0.0
    assert not replay.bars_met(totals)


def test_should_count_a_miss_when_another_check_fails_but_not_the_detected_by_one(monkeypatch):
    # Arrange
    session = FakeSession(
        [
            _verified(
                "SPEC_FAILED",
                [_check("hole_diameter", True), _check("expect_volume", False)],
            ),
            _verified("OK", [_check("hole_diameter", True), _check("expect_volume", True)]),
        ]
    )

    # Act
    rows, _ = _score([_planted_case()], session, monkeypatch)

    # Assert
    assert rows[0]["outcome"] == replay.MISSED


def test_should_make_the_case_invalid_input_when_the_reverted_build_is_not_clean(monkeypatch):
    # Arrange
    session = FakeSession(
        [
            _verified("SPEC_FAILED", [_check("hole_diameter", False)]),
            _verified("SPEC_FAILED", [_check("hole_diameter", False)]),
        ]
    )

    # Act
    rows, frames = _score([_planted_case()], session, monkeypatch)

    # Assert
    totals = replay.tally(rows)
    assert rows[0]["outcome"] == replay.INVALID_INPUT
    assert "reverted build is SPEC_FAILED" in rows[0]["reason"]
    assert totals["invalid"] == ["g3-fault-plan-wrong-hole-diameter"]
    assert (totals["planted"], totals["controls"]) == (0, 0)
    assert not replay.bars_met(totals)
    assert "g3-fault-plan-wrong-hole-diameter#reverted" in frames


def test_should_count_a_false_alarm_when_a_control_verdict_is_not_ok(monkeypatch):
    # Arrange
    session = FakeSession([_verified("SPEC_FAILED", [_check("hole_diameter", False)])])

    # Act
    rows, _ = _score([_control_case()], session, monkeypatch)

    # Assert
    totals = replay.tally(rows)
    assert rows[0]["outcome"] == replay.FALSE_ALARM
    assert totals["false_alarms"] == ["g3-fault-plan-control-faithful-mounting-plate"]
    assert totals["false_alarm"] == 1.0
    assert not replay.bars_met(totals)


def test_should_make_the_case_invalid_input_and_close_the_document_when_a_step_errors(
    monkeypatch,
):
    # Arrange
    session = FakeSession([], failing_tool="feature_hole")

    # Act
    rows, frames = _score([_control_case()], session, monkeypatch)

    # Assert
    assert rows[0]["outcome"] == replay.INVALID_INPUT
    assert "step 1 feature_hole: SPEC_FAILED" in rows[0]["reason"]
    assert replay.tally(rows)["invalid"] == ["g3-fault-plan-control-faithful-mounting-plate"]
    assert frames == {}
    assert ("document_close", {"doc": "doc-1"}) in session.calls


def test_should_preview_then_confirm_each_mutation_with_the_bound_document_handle(monkeypatch):
    # Arrange
    session = FakeSession([_verified("OK", [_check("hole_diameter", True)])])

    # Act
    _score([_control_case()], session, monkeypatch)

    # Assert
    tools = [tool for tool, _ in session.calls]
    assert tools == [
        "document_create",
        "preview_dry_run",
        "feature_hole",
        "verify_shape",
        "document_close",
    ]
    preview_args, hole_args, verify_args = (session.calls[i][1] for i in (1, 2, 3))
    assert preview_args["operation"]["tool"] == "feature_hole"
    assert hole_args["doc"] == "doc-1"
    assert hole_args["confirm"] == {"preview_id": "p-1", "elicitation_action": "accept"}
    assert verify_args["object"] == "Holes"
    assert verify_args["anchor_frame"] == SPEC["assertions"]["anchor_frame"]


def test_should_replace_only_the_planted_step_args_when_the_plan_is_reverted():
    # Arrange
    case = _planted_case()

    # Act
    reverted = replay.reverted_plan(case)

    # Assert
    assert reverted[0] == case["plan"][0]
    assert reverted[1]["tool"] == "feature_hole"
    assert reverted[1]["args"]["diameter"] == {"value": 5.5}
    assert case["plan"][1]["args"]["diameter"] == {"value": 8.0}


# --------------------------------------------------------------------------- #
# I/O matrix: frames
# --------------------------------------------------------------------------- #


def test_should_name_the_case_and_field_when_a_leg_frame_drifts():
    # Arrange
    reference = {"g3-fault-plan-control-faithful-mounting-plate": XY_FRAME}
    drifted = copy.deepcopy(XY_FRAME)
    drifted["origin"] = [0.0, 0.0, 6.0]

    # Act
    drifts = replay.compare_frames(
        reference, {"g3-fault-plan-control-faithful-mounting-plate": drifted}
    )

    # Assert
    assert len(drifts) == 1
    assert drifts[0].startswith("g3-fault-plan-control-faithful-mounting-plate: origin")


def test_should_ignore_the_largest_face_entity_and_float_noise_when_frames_are_compared():
    # Arrange
    face = {
        "kind": "largest_planar_face",
        "ref": None,
        "entity": "#32:1;:H138f,F",
        "origin": [0.0, 0.0, -25.0],
        "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    }
    other_session = copy.deepcopy(face)
    other_session["entity"] = "#32:1;:H1011,F"
    other_session["origin"] = [1e-9, -0.0, -25.000000001]

    # Act
    drifts = replay.compare_frames({"case": face}, {"case": other_session})

    # Assert
    assert drifts == []


def test_should_compare_the_entity_when_the_frame_kind_names_an_object():
    # Arrange
    renamed = copy.deepcopy(XY_FRAME)
    renamed["entity"] = "XY_Plane001"

    # Act
    drifts = replay.compare_frames({"case": XY_FRAME}, {"case": renamed})

    # Assert
    assert drifts == ["case: entity 'XY_Plane001' != 'XY_Plane'"]


def test_should_report_a_build_missing_on_one_side_when_frames_are_compared():
    # Arrange
    reference = {"a": XY_FRAME, "b": XY_FRAME}

    # Act
    drifts = replay.compare_frames(reference, {"a": XY_FRAME, "c": XY_FRAME})

    # Assert
    assert drifts == ["b: no frame in this run", "c: not in the reference"]


def _evidence_dir(tmp_path: Path, frames: dict) -> Path:
    for leg in replay.LEGS:
        evidence = {"leg": leg, "freecad_version": leg.replace("x", "0"), "frames": frames}
        (tmp_path / f"G3.E.3.{leg}.json").write_text(json.dumps(evidence), encoding="utf-8")
    return tmp_path


def test_should_report_invalid_input_when_the_frames_reference_is_missing(tmp_path):
    # Arrange
    evidence = _evidence_dir(tmp_path, {"case": XY_FRAME})

    # Act
    status = checker.frames_status(evidence, tmp_path / "no-reference.json")

    # Assert
    assert status.startswith("INVALID_INPUT (no frames reference")


def test_should_report_invalid_input_when_the_leg_evidence_file_is_absent(tmp_path):
    # Arrange
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"frames": {"case": XY_FRAME}}), encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    # Act
    status = checker.frames_status(evidence, reference)

    # Assert
    assert status == "INVALID_INPUT (leg 1.1.x evidence absent: G3.E.3.1.1.x.json)"


def test_should_fail_naming_the_leg_case_and_field_when_a_leg_frame_drifts(tmp_path):
    # Arrange
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"frames": {"case": XY_FRAME}}), encoding="utf-8")
    drifted = copy.deepcopy(XY_FRAME)
    drifted["axes"] = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    (tmp_path / "evidence").mkdir()
    evidence = _evidence_dir(tmp_path / "evidence", {"case": drifted})

    # Act
    status = checker.frames_status(evidence, reference)

    # Assert
    assert status.startswith("FAIL (leg 1.1.x: case: axes")


def test_should_fail_naming_the_file_when_a_leg_was_measured_on_another_freecad(tmp_path):
    # Arrange
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"frames": {"case": XY_FRAME}}), encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    evidence = _evidence_dir(tmp_path / "evidence", {"case": XY_FRAME})
    relabelled = {"leg": "1.1.x", "freecad_version": "1.2.0", "frames": {"case": XY_FRAME}}
    (evidence / "G3.E.3.1.1.x.json").write_text(json.dumps(relabelled), encoding="utf-8")

    # Act
    status = checker.frames_status(evidence, reference)

    # Assert
    assert status == "FAIL (G3.E.3.1.1.x.json was measured on FreeCAD 1.2.0, not leg 1.1.x)"


def test_should_report_ok_when_the_leg_equals_the_reference(tmp_path):
    # Arrange
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"frames": {"case": XY_FRAME}}), encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    evidence = _evidence_dir(tmp_path / "evidence", {"case": XY_FRAME})

    # Act
    status = checker.frames_status(evidence, reference)

    # Assert
    assert status.startswith("OK (1 built parts")


# --------------------------------------------------------------------------- #
# I/O matrix: score currency
# --------------------------------------------------------------------------- #


def _registry(tmp_path: Path, sha: str, sensitivity: float = 1.0, false_alarm: float = 0.0) -> Path:
    path = tmp_path / "validators.yaml"
    block = {
        "spec_assertions": {
            "validator_sha": sha,
            "last_run": {"sensitivity": sensitivity, "false_alarm": false_alarm},
        }
    }
    path.write_text(yaml.safe_dump(block), encoding="utf-8")
    return path


def test_should_fail_stale_when_the_registry_sha_differs_from_the_hashed_sources(tmp_path):
    # Arrange
    registry = _registry(tmp_path, "0" * 64)

    # Act
    status = checker.score_status(registry)

    # Assert
    assert status.startswith("FAIL (stale")


def test_should_fail_when_a_current_score_misses_the_sensitivity_bar(tmp_path):
    # Arrange
    registry = _registry(tmp_path, replay.validator_sha(), sensitivity=0.9)

    # Act
    status = checker.score_status(registry)

    # Assert
    assert status.startswith("FAIL (sensitivity 0.9")


def test_should_fail_when_a_current_score_misses_the_false_alarm_bar(tmp_path):
    # Arrange
    registry = _registry(tmp_path, replay.validator_sha(), false_alarm=0.1)

    # Act
    status = checker.score_status(registry)

    # Assert
    assert status.startswith("FAIL (sensitivity 1.0 / false alarm 0.1")


def test_should_report_invalid_input_when_no_spec_assertions_score_is_recorded(tmp_path):
    # Arrange
    registry = tmp_path / "validators.yaml"
    registry.write_text("assertions: {validator_sha: x}\n", encoding="utf-8")

    # Act
    status = checker.score_status(registry)

    # Assert
    assert status.startswith("INVALID_INPUT (no spec_assertions score")


def test_should_hash_spec_assertions_like_its_scorer_and_the_registry_when_currency_is_read():
    # Arrange
    committed = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )

    # Act
    mirrored = runner._validator_src_hasher("spec_assertions")

    # Assert
    assert mirrored == replay.validator_sha()
    assert mirrored == committed["spec_assertions"]["validator_sha"]
    assert runner._VALIDATOR_SOURCES["spec_assertions"] == replay.VALIDATOR_SOURCES
    assert FAULT_DIR / "score_g3_replay.py" in replay.VALIDATOR_SOURCES
    suite = runner._targeted_suite_sources("spec_assertions")
    folded = {identity.decode() for identity, _ in runner._g3_dev_spec_sources(suite)}
    assert folded == {f"dev/{case['spec_ref']}/case.yaml" for case in replay.load_cases()}


def test_should_stale_the_sha_when_a_referenced_dev_spec_is_edited(tmp_path):
    # Arrange
    dev = tmp_path / "dev"
    shutil.copytree(replay.DEV_ROOT, dev)
    before = replay.validator_sha(replay.SUITE_ROOT, dev)
    spec_yaml = dev / "g3-dev-007-jig-block-blind-bore" / "case.yaml"

    # Act
    spec_yaml.write_text(spec_yaml.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")

    # Assert
    assert replay.validator_sha(replay.SUITE_ROOT, dev) != before
    assert replay.validator_sha() == before


def test_should_keep_the_sha_when_a_dev_spec_no_case_names_is_edited(tmp_path):
    # Arrange
    dev = tmp_path / "dev"
    shutil.copytree(replay.DEV_ROOT, dev)
    before = replay.validator_sha(replay.SUITE_ROOT, dev)
    spec_yaml = dev / "g3-dev-002-l-bracket" / "case.yaml"

    # Act
    spec_yaml.write_text(spec_yaml.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")

    # Assert
    assert replay.validator_sha(replay.SUITE_ROOT, dev) == before


def test_should_stale_the_sha_when_a_corrupted_plan_case_is_edited(tmp_path):
    # Arrange
    suite = tmp_path / "corrupted-plan"
    shutil.copytree(replay.SUITE_ROOT, suite)
    before = replay.validator_sha(suite)
    case_yaml = suite / "g3-fault-plan-wrong-hole-diameter" / "case.yaml"

    # Act
    case_yaml.write_text(case_yaml.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")

    # Assert
    assert replay.validator_sha(suite) != before
    assert replay.validator_sha() == before


# --------------------------------------------------------------------------- #
# Entry items and the runner route
# --------------------------------------------------------------------------- #


def test_should_compute_g3e3_and_g3e4_when_the_committed_evidence_is_read():
    # Arrange
    suite = checker.load_suite()

    # Act
    rows = checker.entry_status(suite["gate"], sound=True, frames_evidence=None)

    # Assert
    statuses = {item_id: status for item_id, _, status in rows}
    assert statuses["G3.E.3"] == "INVALID_INPUT (no --frames-evidence directory given)"
    assert statuses["G3.E.4"].startswith("OK (sensitivity 1.0, false alarm 0.0")


def test_should_report_g3e3_ok_when_the_leg_carries_the_reference_frames(tmp_path):
    # Arrange
    reference = json.loads(checker.FRAMES_REFERENCE.read_text(encoding="utf-8"))["frames"]
    evidence = _evidence_dir(tmp_path, reference)
    suite = checker.load_suite()

    # Act
    rows = checker.entry_status(suite["gate"], sound=True, frames_evidence=evidence)

    # Assert
    assert dict((item_id, status) for item_id, _, status in rows)["G3.E.3"].startswith("OK")


def test_should_list_in_gate_yaml_exactly_the_specs_the_reference_proves_on_built_parts():
    # Arrange
    reference = json.loads(checker.FRAMES_REFERENCE.read_text(encoding="utf-8"))["frames"]
    gate = checker.load_suite()["gate"]
    frames_item = next(item for item in gate["entry"] if item["id"] == "G3.E.3")

    # Act
    proven = {frame["spec_ref"] for frame in reference.values()}

    # Assert
    assert set(frames_item["proven_on_built_parts"]) == proven
    all_specs = {spec["id"] for spec in checker.load_suite()["specs"]}
    assert set(frames_item["not_proven_on_built_parts"]) == all_specs - proven


def test_should_hold_a_frame_for_every_control_and_reverted_build_in_the_reference():
    # Arrange
    cases = replay.load_cases()

    # Act
    expected = {c["id"] + ("#reverted" if replay.is_planted(c) else "") for c in cases}

    # Assert
    reference = json.loads(checker.FRAMES_REFERENCE.read_text(encoding="utf-8"))
    assert set(reference["frames"]) == expected
    assert reference["leg"] == "1.1.x"


def test_should_forward_the_frames_evidence_dir_when_runner_faults_g3_runs(monkeypatch, tmp_path):
    # Arrange
    seen = {}

    def fake_run(command):
        seen["command"] = command
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "_preflight_actor_grader", lambda _gate: None)

    # Act
    exit_code = runner.main(["faults", "G3", "--frames-evidence", str(tmp_path)])

    # Assert
    assert exit_code == 0
    assert seen["command"][-2:] == ["--frames-evidence", str(tmp_path)]


def test_should_refuse_frames_evidence_for_a_gate_other_than_g3(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(runner, "_preflight_actor_grader", lambda _gate: None)

    # Act
    exit_code = runner.main(["faults", "G1", "--frames-evidence", str(tmp_path)])

    # Assert
    assert exit_code == 2


def test_should_name_the_case_when_a_planted_case_carries_no_faithful_args():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["id"] == "g3-fault-plan-wrong-hole-diameter")
    del case["faithful_args"]

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["planted_steps"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p for p in problems), problems


def test_should_name_the_case_when_faithful_args_fail_the_planted_tool_schema():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["id"] == "g3-fault-plan-wrong-hole-diameter")
    case["faithful_args"]["no_such_argument"] = 1

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["plan_steps"]

    # Assert
    assert any("faithful_args of step 7" in p for p in problems), problems


def test_should_name_the_case_when_a_control_carries_faithful_args():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["fault"]["expectation"] == "PASS_CLEAN")
    case["faithful_args"] = {}

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["planted_steps"]

    # Assert
    assert any(case["id"] in p and "faithful_args" in p for p in problems), problems


def test_should_name_the_case_when_a_planted_case_carries_both_faithful_fields():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["id"] == "g3-fault-plan-wrong-hole-diameter")
    case["faithful_steps"] = {7: None}

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["planted_steps"]

    # Assert
    assert any("exactly one of faithful_args, faithful_steps" in p for p in problems), problems


def test_should_name_the_case_when_faithful_steps_names_a_step_outside_the_plan():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["id"] == "g3-fault-plan-extra-unrequested-pocket")
    case["faithful_steps"] = {99: None}

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["planted_steps"]

    # Assert
    assert any("faithful_steps index 99" in p for p in problems), problems


def test_should_replace_and_drop_steps_when_a_plan_is_reverted_through_faithful_steps():
    # Arrange
    case = _planted_case()
    del case["faithful_args"]
    case["plan"].append({"tool": "feature_pocket", "args": {"doc": "$doc", "name": "Extra"}})
    replacement = {"tool": "feature_hole", "args": {"doc": "$doc", "name": "Holes"}}
    case["faithful_steps"] = {1: replacement, 2: None}

    # Act
    reverted = replay.reverted_plan(case)

    # Assert
    assert reverted == [case["plan"][0], replacement]


def test_should_name_the_step_when_a_faithful_steps_entry_fails_its_tool_schema():
    # Arrange
    suite = copy.deepcopy(checker.load_suite())
    case = next(c for c in suite["plans"] if c["id"] == "g3-fault-plan-hole-on-wrong-face")
    case["faithful_steps"][5]["args"]["no_such_argument"] = 1

    # Act
    problems = checker.check_suite(suite, checker.tool_schemas())["plan_steps"]

    # Assert
    assert any(
        "g3-fault-plan-hole-on-wrong-face: faithful_steps[5]" in p and "no_such_argument" in p
        for p in problems
    ), problems


def test_should_exit_one_when_a_computed_entry_item_fails_on_a_sound_suite(monkeypatch):
    # Arrange
    monkeypatch.setattr(checker, "score_status", lambda: "FAIL (stale: test)")

    # Act
    exit_code = checker.main([])

    # Assert
    assert exit_code == 1


# --------------------------------------------------------------------------- #
# replay.main exit codes and writes
# --------------------------------------------------------------------------- #


def _clean_rows(planted_outcome: str = replay.DETECTED, clean: str = replay.PASS_CLEAN) -> list:
    planted = {
        "case": "p",
        "spec_ref": "s",
        "planted": planted_outcome,
        "clean": clean,
        "outcome": planted_outcome,
        "builds": {"planted": None, "clean": {"freecad_version": "1.1.0"}},
    }
    control = {
        "case": "c",
        "spec_ref": "s",
        "planted": None,
        "clean": clean,
        "outcome": clean,
        "builds": {"planted": None, "clean": {"freecad_version": "1.1.0"}},
    }
    return [planted, control]


def _main(monkeypatch, tmp_path: Path, rows: list, argv: list[str]) -> tuple[int, Path]:
    registry = tmp_path / "validators.yaml"
    registry.write_text("# header\n\nassertions:\n  suite: g2/\n", encoding="utf-8")
    monkeypatch.setattr(replay, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(replay, "VALIDATORS_YAML", registry)

    async def fake_run(_run_dir, _cases):
        return rows, {"c": XY_FRAME}

    monkeypatch.setattr(replay, "_run", fake_run)
    return replay.main(["--leg", "1.1.x", "--run", "t", *argv]), registry


def test_should_exit_zero_and_write_the_block_when_the_run_is_clean(monkeypatch, tmp_path):
    # Arrange
    rows = _clean_rows()

    # Act
    exit_code, registry = _main(monkeypatch, tmp_path, rows, [])

    # Assert
    assert exit_code == 0
    assert "spec_assertions:" in registry.read_text(encoding="utf-8")
    assert (tmp_path / "artifacts" / "t" / "G3.E.3.1.1.x.json").is_file()


def test_should_exit_one_when_a_frame_drifts_from_the_reference(monkeypatch, tmp_path):
    # Arrange
    drifted = copy.deepcopy(XY_FRAME)
    drifted["origin"] = [1.0, 0.0, 0.0]
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"frames": {"c": drifted}}), encoding="utf-8")

    # Act
    exit_code, _ = _main(
        monkeypatch, tmp_path, _clean_rows(), ["--check", "--frames-check", str(reference)]
    )

    # Assert
    assert exit_code == 1


def test_should_exit_one_when_a_bar_is_missed(monkeypatch, tmp_path):
    # Arrange
    rows = _clean_rows(planted_outcome=replay.MISSED)

    # Act
    exit_code, _ = _main(monkeypatch, tmp_path, rows, ["--check"])

    # Assert
    assert exit_code == 1


def test_should_write_nothing_to_the_registry_when_check_is_passed(monkeypatch, tmp_path):
    # Arrange
    rows = _clean_rows()

    # Act
    exit_code, registry = _main(monkeypatch, tmp_path, rows, ["--check"])

    # Assert
    assert exit_code == 0
    assert "spec_assertions" not in registry.read_text(encoding="utf-8")


def test_should_write_nothing_to_the_registry_when_a_case_is_invalid_input(monkeypatch, tmp_path):
    # Arrange
    rows = _clean_rows()
    rows[0]["outcome"] = replay.INVALID_INPUT

    # Act
    exit_code, registry = _main(monkeypatch, tmp_path, rows, [])

    # Assert
    assert exit_code == 1
    assert "spec_assertions" not in registry.read_text(encoding="utf-8")
