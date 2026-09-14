"""Structural self-check for the G3 entry gate (story 4.1).

Pins the invariants the entry gate is accountable for: every assertion ``fn`` is a closed §7.2
primitive, every case declares an anchor frame from the closed derivation set, every dev spec
names a provenance manifest, ``heldout/`` holds only the sealed pair, the fault suites measure
both bars, and every criterion still fails honestly against the absent Phase 3 implementation.

A test here that started passing for the wrong reason would let the entry gate rot: the whole
point of landing the measures first is that nothing can quietly change them afterwards.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
G3 = REPO_ROOT / "benchmarks" / "g3"
PROVENANCE = REPO_ROOT / "benchmarks" / "_registry" / "provenance"

EXPECTED_DEV_CASES = 20
EXPECTED_HELDOUT_CASES = 7
EXPECTED_CRITERIA = ["G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7"]

# The closed assertion vocabulary (verification-design.md §7.2). G3 declares NO extension: a case
# naming anything else has forked the vocabulary rather than grown it.
VOCABULARY_FNS = frozenset(
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

# The closed anchor-frame derivation set (verification-design.md §7.1).
ANCHOR_FRAME_KINDS = frozenset({"named_datum", "base_sketch_plane", "largest_planar_face"})

# The corrupted-plan taxonomy defined in benchmarks/g3/README.md.
CORRUPTION_CLASSES = frozenset(
    {"value", "topology", "omission", "insertion", "ordering", "frame", "none"}
)

FAULT_SUITES = frozenset({"corrupted-plan", "visual-judge", "assertions", "recompute"})

# The suites whose cases grade a part against a written spec, so every case must name the dev spec
# it deviates from. ``recompute`` is absent on purpose: ``verify_recompute`` grades DOCUMENT STATE,
# not geometry, so there is no spec to violate and a ``spec_ref`` on one of its cases would name a
# contract the case never measures against.
SPEC_BOUND_FAULT_SUITES = frozenset({"corrupted-plan", "visual-judge", "assertions"})
EXPECTED_CORRUPTED_PLAN_DEFECTS = 10

# AD-13's floor for a fault suite: at least ten planted defects plus discriminating controls.
EXPECTED_RECOMPUTE_DEFECTS = 10

# The failure modes a recompute fault can take, spanning both criteria that cite the validator:
# an object the dependency graph never resolved, a dependency resolved in the wrong order, an
# expression binding that cannot resolve, a feature that errors whenever it rebuilds, and a sketch
# the solver cannot converge.
RECOMPUTE_FAULT_CLASSES = frozenset(
    {"silent_skip", "dependency_order", "broken_expression", "rebuild_error", "sketch_solve"}
)

# The distinguishing phrase each honest-failure message must carry, so a reader of a failing
# report can tell WHICH absent actor blocks that criterion. Keywords rather than whole strings:
# the wording may be improved, but a criterion that stops naming its blocker must fail.
_MISSING_ACTOR_KEYWORD = {
    "G3.1": "designer actor",
    "G3.2": "generated part",
    # G3.3 has a real collector since story 4.6, but it still reports an absent actor rather than a
    # measurement: the probe changes a parameter on a part that PASSED G3.1, and G3.1 has no
    # planner. The keyword therefore names the run that has not happened, not a missing facade.
    "G3.3": "no editability run has been driven",
    "G3.4": "designer loop",
    "G3.5": "run to time",
    "G3.6": "ablation",
    "G3.7": "visual verdict",
}

# The criteria that have a real collector and report a MEASUREMENT rather than a missing actor.
# G3.4 joined this set when story 4.5 landed the designer loop that drives its corrupted-plan
# cases. Listed explicitly so a criterion that quietly loses its collector fails this file rather
# than reverting to an uncollected report nobody notices.
COLLECTED_CRITERIA = frozenset({"G3.4"})


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


DEV_CASES = sorted((G3 / "dev").glob("*/case.yaml"))
FAULT_CASES = sorted((G3 / "fault-injection").glob("*/*/case.yaml"))


def _fault_cases_in(suite: str) -> list[Path]:
    return [case for case in FAULT_CASES if case.parent.parent.name == suite]


# --- gate.yaml -------------------------------------------------------------------------------


def test_Should_mirror_the_seven_g3_criteria_When_gate_yaml_is_loaded():
    # Arrange
    target = G3 / "gate.yaml"

    # Act
    gate = _load(target)

    # Assert
    assert gate["gate"] == "G3"
    assert [criterion["id"] for criterion in gate["criteria"]] == EXPECTED_CRITERIA
    assert gate["verdict"]["heldout"] == "sealed"
    assert gate["required_tokens"] == ["spot_audit"]
    for criterion in gate["criteria"]:
        assert criterion["text"].strip()
        assert criterion["pass_rule"].strip()


def test_Should_declare_a_judge_distinct_from_the_actor_When_gate_yaml_is_loaded():
    """AD-21: the acting agent may never be the visual judge, enforced at preflight."""
    # Arrange
    gate = _load(G3 / "gate.yaml")

    # Act
    actor_model = gate["actor"]["model"]
    judge_model = gate["visual_judge"]["model"]
    grader_model = gate["grader"]["model"]

    # Assert
    assert judge_model != actor_model
    assert grader_model != actor_model
    assert gate["visual_judge"]["temperature"] == 0
    assert gate["visual_judge"]["check_id"] == "visual.judge"


# --- dev split -------------------------------------------------------------------------------


def test_Should_hold_twenty_specs_When_the_dev_split_is_counted():
    # Arrange
    cases = DEV_CASES

    # Act
    count = len(cases)

    # Assert
    assert count == EXPECTED_DEV_CASES


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
def test_Should_be_well_formed_When_a_dev_case_is_loaded(case: Path):
    # Arrange
    data = _load(case)

    # Act
    checks = data["assertions"]["checks"]

    # Assert
    assert data["gate"] == "g3"
    assert data["criterion"] == "G3.1"
    assert data["spec"].strip(), "a spec case must carry the written requirement"
    assert checks, "a spec case with no checks cannot grade anything"
    for check in checks:
        assert check["fn"].strip()
        assert "expect" in check


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
def test_Should_declare_a_closed_anchor_frame_When_a_dev_case_is_loaded(case: Path):
    """An undeclared or invented frame makes every in-frame measurement meaningless (§7.1)."""
    # Arrange
    frame = _load(case)["assertions"]["anchor_frame"]

    # Act
    kind = frame["kind"]

    # Assert
    assert kind in ANCHOR_FRAME_KINDS
    if kind == "named_datum":
        assert frame["ref"], "a named_datum frame that names no datum resolves to nothing"


def test_Should_use_only_closed_vocabulary_primitives_When_every_dev_check_is_collected():
    """G3 declares no vocabulary extension, so a fn outside §7.2 is a fork, not a case."""
    # Arrange
    cases = DEV_CASES

    # Act
    used = {check["fn"] for case in cases for check in _load(case)["assertions"]["checks"]}

    # Assert
    assert used <= VOCABULARY_FNS, f"outside the closed vocabulary: {sorted(used - VOCABULARY_FNS)}"


def test_Should_exercise_every_closed_primitive_When_the_dev_split_is_taken_as_a_whole():
    """A primitive no spec exercises is a primitive story 4.2 could omit unnoticed."""
    # Arrange
    cases = DEV_CASES

    # Act
    used = {check["fn"] for case in cases for check in _load(case)["assertions"]["checks"]}

    # Assert
    assert VOCABULARY_FNS - used == set(), f"never exercised: {sorted(VOCABULARY_FNS - used)}"


def test_Should_cover_every_anchor_frame_kind_When_the_dev_split_is_taken_as_a_whole():
    """A derivation no spec declares is one the shared resolver could get wrong unnoticed."""
    # Arrange
    cases = DEV_CASES

    # Act
    declared = {_load(case)["assertions"]["anchor_frame"]["kind"] for case in cases}

    # Assert
    assert declared == ANCHOR_FRAME_KINDS


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
def test_Should_name_a_real_provenance_manifest_When_a_dev_case_is_loaded(case: Path):
    """AD-16: every shipped spec derives from a documented real part."""
    # Arrange
    data = _load(case)

    # Act
    manifest_path = (case.parent / data["provenance"]).resolve()

    # Assert
    assert manifest_path.is_file()
    manifest = _load(manifest_path)
    assert manifest["kind"] == "part-spec"
    assert manifest["source"]["kind"] == "hand-authored"
    assert manifest["real_world_basis"].strip()


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
def test_Should_carry_its_derivation_When_a_dev_case_is_read_as_text(case: Path):
    """An `expect` with no derivation cannot be distinguished from a captured value (AD-13)."""
    # Arrange
    text = case.read_text(encoding="utf-8")

    # Act
    comment_lines = [line for line in text.splitlines() if line.startswith("#")]

    # Assert
    assert any("=" in line for line in comment_lines), (
        "no derivation comment: an assertion read off an implementation cannot falsify it"
    )


def test_Should_ship_no_banned_dataset_lineage_When_every_spec_basis_is_read():
    """The frozen boundary bans DeepCAD / ABC / Text2CAD / Fusion 360 Gallery lineage."""
    # Arrange
    banned = ("deepcad", "abc dataset", "text2cad", "fusion 360 gallery")

    # Act
    bases = {
        case.parent.name: _load((case.parent / _load(case)["provenance"]).resolve())[
            "real_world_basis"
        ].lower()
        for case in DEV_CASES
    }

    # Assert
    for case_id, basis in bases.items():
        for name in banned:
            assert name not in basis, f"{case_id} cites banned lineage {name!r}"


# --- held-out split --------------------------------------------------------------------------


def test_Should_hold_only_the_sealed_pair_When_heldout_is_listed():
    """DW-99: a readable held-out case is the failure the seal exists to prevent."""
    # Arrange
    heldout = G3 / "heldout"

    # Act
    present = sorted(path.name for path in heldout.iterdir())

    # Assert
    assert present == ["SEAL.json", "heldout.tar.enc"]


def test_Should_attest_the_case_count_When_the_seal_manifest_is_read():
    # Arrange
    manifest_path = G3 / "heldout" / "SEAL.json"

    # Act
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Assert
    assert manifest["gate"] == "G3"
    assert manifest["case_count"] == EXPECTED_HELDOUT_CASES
    assert manifest["archive_sha256"]
    assert manifest.get("burned") is None


def test_Should_be_opaque_When_the_sealed_archive_is_scanned_for_case_text():
    """An archive that still spelled its cases in the clear would seal nothing."""
    # Arrange
    archive = G3 / "heldout" / "heldout.tar.enc"

    # Act
    blob = archive.read_bytes()

    # Assert
    for needle in (b"g3-heldout", b"anchor_frame", b"expect_volume", b"spec:"):
        assert needle not in blob, f"{needle!r} is readable in the sealed archive"


def test_Should_show_no_plaintext_case_When_the_heldout_git_history_is_read():
    """The DW-99 trap: G2's split was burned by a plaintext commit that stays in history."""
    # Arrange
    command = ["git", "log", "-p", "--", "benchmarks/g3/heldout/"]

    # Act
    completed = subprocess.run(
        command, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60
    )

    # Assert
    assert completed.returncode == 0, completed.stderr
    assert "anchor_frame" not in completed.stdout
    assert "g3-heldout-" not in completed.stdout


# --- fault suites ----------------------------------------------------------------------------


def test_Should_present_every_suite_When_the_fault_tree_is_walked():
    # Arrange
    cases = FAULT_CASES

    # Act
    suites = {case.parent.parent.name for case in cases}

    # Assert
    assert suites == FAULT_SUITES


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_Should_be_well_formed_When_a_fault_case_is_loaded(case: Path):
    # Arrange
    data = _load(case)

    # Act
    fault = data["fault"]

    # Assert
    assert data["gate"] == "g3"
    assert fault["kind"] in {"planted_defect", "clean_control"}
    assert fault["description"].strip()
    expected = "DETECT" if fault["kind"] == "planted_defect" else "PASS_CLEAN"
    assert fault["expectation"] == expected
    assert str(data.get("targets_validator") or "").strip()
    if case.parent.parent.name in SPEC_BOUND_FAULT_SUITES:
        assert data["spec_ref"].strip()


def test_Should_plant_ten_corrupted_plans_When_the_corrupted_plan_suite_is_counted():
    """G3.4 scores >=9/10, so exactly ten planted corrupted plans must exist."""
    # Arrange
    cases = _fault_cases_in("corrupted-plan")

    # Act
    planted = [c for c in cases if _load(c)["fault"]["kind"] == "planted_defect"]

    # Assert
    assert len(planted) == EXPECTED_CORRUPTED_PLAN_DEFECTS


def test_Should_span_the_whole_taxonomy_When_the_corrupted_plan_classes_are_collected():
    """Ten spellings of one failure mode would pass the count and measure one thing."""
    # Arrange
    cases = _fault_cases_in("corrupted-plan")

    # Act
    classes = {
        _load(case)["corruption_class"]
        for case in cases
        if _load(case)["fault"]["kind"] == "planted_defect"
    }

    # Assert
    assert classes <= CORRUPTION_CLASSES
    assert classes == CORRUPTION_CLASSES - {"none"}


def test_Should_mix_defects_with_controls_When_each_fault_suite_is_partitioned():
    """Controls measure false alarms; defects measure sensitivity. A suite needs both."""
    # Arrange
    by_suite: dict[str, list[str]] = {}

    # Act
    for case in FAULT_CASES:
        by_suite.setdefault(case.parent.parent.name, []).append(_load(case)["fault"]["kind"])

    # Assert
    for suite, kinds in by_suite.items():
        assert "planted_defect" in kinds, f"{suite} measures no sensitivity"
        assert "clean_control" in kinds, f"{suite} measures no false alarm"


def test_Should_plant_the_four_named_assertion_faults_When_the_assertion_suite_is_read():
    """verification-design.md §9 names these four explicitly."""
    # Arrange
    cases = _fault_cases_in("assertions")

    # Act
    ids = {case.parent.name for case in cases}

    # Assert
    for required in (
        "g3-fault-assert-missing-hole",
        "g3-fault-assert-wrong-diameter",
        "g3-fault-assert-mirrored-pattern",
        "g3-fault-assert-spacing-error-0p5mm",
    ):
        assert required in ids


def test_Should_plant_at_least_ten_defects_When_the_recompute_suite_is_counted():
    """AD-13 sets the floor at ten planted defects; a thinner suite measures a narrower claim."""
    # Arrange
    cases = _fault_cases_in("recompute")

    # Act
    planted = [c for c in cases if _load(c)["fault"]["kind"] == "planted_defect"]

    # Assert
    assert len(planted) >= EXPECTED_RECOMPUTE_DEFECTS


def test_Should_span_every_recompute_class_When_the_recompute_classes_are_collected():
    """Twelve spellings of one failure mode would pass the count and measure one thing.

    ``verify_recompute`` is cited for two different criteria — G3.2's recompute-clean hygiene and
    G3.3's recompute-after-an-edit — so a suite covering only one failure mode would leave the
    other criterion citing a number measured over a population it does not describe.
    """
    # Arrange
    cases = _fault_cases_in("recompute")

    # Act
    classes = {
        _load(case)["fault_class"]
        for case in cases
        if _load(case)["fault"]["kind"] == "planted_defect"
    }

    # Assert
    assert classes == RECOMPUTE_FAULT_CLASSES


def test_Should_carry_the_discriminating_controls_When_the_recompute_suite_is_read():
    """Three controls a naive implementation would flag, without which the false-alarm arm is weak.

    Every planted case in this suite freezes recomputes to survive the mutation bracket, so
    ``control-frozen-but-clean`` is what stops a validator keying off that flag from scoring a
    perfect sensitivity while measuring the planting mechanism. The other two separate document
    state from run history: an object that was touched and has since resolved, and a document whose
    mutation failed but whose rollback restored it.
    """
    # Arrange
    cases = _fault_cases_in("recompute")

    # Act
    ids = {case.parent.name for case in cases}

    # Assert
    for required in (
        "g3-fault-recompute-control-frozen-but-clean",
        "g3-fault-recompute-control-touched-then-cleared",
        "g3-fault-recompute-control-rollback-clean",
    ):
        assert required in ids


def test_Should_resolve_every_planted_op_When_the_recompute_registry_is_read():
    """An unresolved ``planted_op`` left the whole G2 suite unscoreable for months (DW-73).

    The names are checked against the registry rather than the ops being run, so the structural
    half is caught here without FreeCAD. Each op must also declare the fixture its case builds
    from, or the driver has no document to plant into.
    """
    # Arrange
    sys.path.insert(0, str(G3 / "fault-injection"))
    import planted_recomputes

    cases = _fault_cases_in("recompute")

    # Act
    ops = {case.parent.name: _load(case)["planted_op"] for case in cases}

    # Assert
    for case_id, op in ops.items():
        assert op in planted_recomputes.REGISTRY, f"{case_id}: {op} resolves to no callable"
        assert op in planted_recomputes.FIXTURES, f"{case_id}: {op} declares no fixture"


def test_Should_name_a_measurement_When_a_recompute_op_is_undriveable():
    """An undriveable op must carry the measurement that established it, never a bare claim.

    This is the rule that keeps a skipped case from becoming a quiet way to drop a defect the
    validator misses. Every exclusion states the FreeCAD version it was measured on and the
    document state it produced, so a reader can re-run it rather than trust it.
    """
    # Arrange
    sys.path.insert(0, str(G3 / "fault-injection"))
    import planted_recomputes

    # Act
    undriveable = planted_recomputes.UNDRIVEABLE

    # Assert
    for op, reason in undriveable.items():
        assert op in planted_recomputes.REGISTRY, f"{op} is excluded but resolves to no callable"
        assert "Measured on" in reason, f"{op} claims undriveable without a measurement"


def test_Should_plant_the_five_named_visual_faults_When_the_judge_suite_is_read():
    """AD-21 names mirrored, missing flange, wrong face, wrong proportions, wrong callout."""
    # Arrange
    cases = _fault_cases_in("visual-judge")

    # Act
    ids = {case.parent.name for case in cases}

    # Assert
    for required in (
        "g3-fault-visual-mirrored-part",
        "g3-fault-visual-missing-flange",
        "g3-fault-visual-feature-on-wrong-face",
        "g3-fault-visual-wrong-proportions",
        "g3-fault-visual-wrong-dimension-callout",
    ):
        assert required in ids


def test_Should_pin_the_geometry_leg_When_a_judge_only_fault_declares_what_must_miss_it():
    """A visual suite every geometry assertion also catches proves nothing about the judge."""
    # Arrange
    cases = _fault_cases_in("visual-judge")

    # Act
    pinned = {
        case.parent.name: _load(case)["must_not_be_caught_by"]
        for case in cases
        if "must_not_be_caught_by" in _load(case)
    }

    # Assert
    assert pinned, "no visual fault pins the geometry leg, so the visual leg is decorative"
    assert set(pinned.values()) == {"geometry_assertions_pass"}


def test_Should_declare_its_fixture_state_explicitly_When_a_fault_case_is_authored():
    """The exemption check_provenance grants requires the fixture state to be explicit.

    Three states are legal. A case the designer loop can plant declares
    ``driven-by-designer-loop`` — the plan IS the fixture. A case planted straight through the
    production mutation bracket declares ``driven-by-mutation-bracket`` — the document that bracket
    leaves behind IS the fixture, which is the shape a document-state validator is graded over. Both
    driven states must also name the ``planted_op`` that resolves them, and neither ships a
    ``.FCStd``. A case that still cannot be driven declares ``pending``. A fourth value, or a driven
    case naming no op, is a case that would be silently skipped by the provenance check.
    """
    # Arrange
    cases = FAULT_CASES
    driven = ("driven-by-designer-loop", "driven-by-mutation-bracket")

    # Act
    fixtures = {case.parent.name: _load(case) for case in cases}

    # Assert
    for name, case in fixtures.items():
        assert case.get("fixture") in (*driven, "pending"), name
        if case.get("fixture") in driven:
            assert case.get("planted_op"), f"{name} claims to be driven but names no planted_op"


def test_Should_leave_no_fault_case_pending_When_every_suite_names_a_driver():
    """Every fault suite now plants its own fixture, the visual-judge suite included.

    That suite's geometry is built by ``render_visual_judge.py`` and its standard visual set is
    rendered to ``visual-judge/<case-id>/render/``. Grading those images is inspection by a
    vision-capable judge, which needs no API client and no credential — so decision 017, which
    governs the automatic IN-LOOP judge, does not keep this suite pending. What is still absent is
    a VERDICT, and that is recorded by ``visual_judge`` staying ``not_scored`` in the registry
    rather than by a fixture claiming nothing can build it.
    """
    # Arrange
    cases = FAULT_CASES

    # Act
    pending = {case.parent.parent.name for case in cases if _load(case).get("fixture") == "pending"}

    # Assert
    assert pending == set()


def test_Should_reference_no_heldout_spec_When_every_fault_case_names_its_spec():
    """A fault case naming a held-out spec would leak the sealed set's contents.

    Only the spec-bound suites are read. A ``recompute`` case grades document state and names no
    spec, so it can leak nothing, and requiring a ``spec_ref`` from it would invent a reference
    the case does not have.
    """
    # Arrange
    dev_ids = {case.parent.name for case in DEV_CASES}

    # Act
    referenced = {
        _load(case)["spec_ref"]
        for case in FAULT_CASES
        if case.parent.parent.name in SPEC_BOUND_FAULT_SUITES
    }

    # Assert
    assert referenced <= dev_ids, f"outside the dev split: {sorted(referenced - dev_ids)}"


# --- the judge seam --------------------------------------------------------------------------


def test_Should_return_a_failing_schema_valid_verdict_When_the_stub_judge_is_called():
    """Fail-closed (AD-21): no vision backend means the part is not done, never a pass."""
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.g3 import judge

    target = judge.StubJudge()

    # Act
    verdict = target.judge_or_unavailable(images=[], spec_text="", checklist=[])

    # Assert
    assert verdict["pass"] is False
    assert judge.UNAVAILABLE_CODE in verdict["findings"][0]["observation"]
    assert verdict["findings"][0]["severity"] == "blocking"
    assert judge.validate_verdict(verdict) is verdict


def test_Should_raise_When_a_verdict_omits_its_pass_field():
    """Model output is untrusted: a caller doing verdict.get('pass') would read None as a fail
    for the right reason but a missing findings list as an empty one for the wrong reason."""
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.g3 import judge

    malformed = {"findings": []}

    # Act
    act = lambda: judge.validate_verdict(malformed)  # noqa: E731

    # Assert
    with pytest.raises(judge.VerdictSchemaError, match="pass"):
        act()


def test_Should_raise_When_a_finding_names_a_view_outside_the_standard_visual_set():
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.g3 import judge

    malformed = {
        "pass": False,
        "findings": [{"view": "back", "observation": "x", "severity": "blocking"}],
    }

    # Act
    act = lambda: judge.validate_verdict(malformed)  # noqa: E731

    # Assert
    with pytest.raises(judge.VerdictSchemaError, match="view"):
        act()


# --- the gate still fails honestly -------------------------------------------------------------


def test_Should_fail_every_criterion_naming_the_missing_actor_When_the_gate_runs():
    """AD-19: the machinery is born graded and must fail against the absent implementation.

    Every criterion still fails, but for two different reasons now, and the report must say which.
    G3.4 is COLLECTED since story 4.5 — the designer loop drives the corrupted-plan cases — so it
    fails on a measured shortfall against its stated bar rather than on an absent actor. Every
    other criterion still reports the actor it is waiting on. Asserting the two shapes separately
    is what keeps a collected criterion from silently regressing to "uncollected" and reading the
    same as one that was never built.

    The run id is fresh per invocation and the run dir is removed afterwards. A reused id would
    let this read reports an earlier run wrote — so the assertions would hold even after the
    collector that writes them was deleted, which is a test that measures its own leftovers.
    """
    # Arrange
    import shutil
    import uuid

    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    run_id = f"g3-honest-fail-{uuid.uuid4().hex[:12]}"
    run_dir = REPO_ROOT / "benchmarks" / "gate-artifacts" / "g3" / run_id
    assert not run_dir.exists(), "a fresh run id must not already hold reports"

    # Act
    try:
        exit_code = runner.run_command("G3", run_id)

        # Assert
        assert exit_code == 1
        for criterion_id in EXPECTED_CRITERIA:
            report = json.loads((run_dir / "reports" / f"{criterion_id}.json").read_text("utf-8"))
            message = report["checks"][0]["detail"]["message"]
            if criterion_id in COLLECTED_CRITERIA:
                # A measured shortfall, not an absent actor: SPEC_FAILED rather than INVALID_INPUT.
                assert report["verdict"] == "SPEC_FAILED", criterion_id
                assert "detected" in message, (
                    f"{criterion_id} is collected but reports no measurement: {message!r}"
                )
                continue
            assert report["verdict"] == "INVALID_INPUT"
            # "no collector for G3.1" also starts with "no", so the assertion names the ACTOR:
            # a reader of a failing report must be able to tell the entry gate's measures from
            # the Phase 3 code they measure without opening the epic.
            assert message != f"no collector for {criterion_id}", (
                f"{criterion_id} falls back to the generic message and names no missing actor"
            )
            assert _MISSING_ACTOR_KEYWORD[criterion_id] in message, (
                f"{criterion_id} message does not name what is missing: {message!r}"
            )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_Should_grade_against_the_authored_defect_count_When_g3_4_is_collected():
    """G3.4's ">=9/10" bar counts AUTHORED defects, never the population that happened to run.

    A criterion that recomputed its bar from its own denominator could never fail: a loop able to
    drive one case and catch it would read 1/1 and clear a rule written for ten. The bar is an
    absolute count, so a run whose population shrank must fail rather than pass on a smaller set.
    """
    # Arrange
    import shutil
    import uuid

    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    run_id = f"g3-bar-{uuid.uuid4().hex[:12]}"
    run_dir = REPO_ROOT / "benchmarks" / "gate-artifacts" / "g3" / run_id

    # Act
    try:
        runner.run_command("G3", run_id)
        report = json.loads((run_dir / "reports" / "G3.4.json").read_text("utf-8"))
        detection = next(c for c in report["checks"] if c["id"] == "G3.4.detection")

        # Assert
        assert detection["expected"] == runner.G3_4_DETECTION_BAR
        assert detection["passed"] == (detection["measured"] >= runner.G3_4_DETECTION_BAR)
        assert "authored" in detection["detail"]["message"]
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_Should_refuse_without_a_key_When_the_exit_run_is_invoked(monkeypatch):
    """The held-out set is key-gated: no key means no unseal, exit 2, seal untouched."""
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    monkeypatch.delenv("FREECAD_BUDDY_UNSEAL_KEY", raising=False)
    before = json.loads((G3 / "heldout" / "SEAL.json").read_text(encoding="utf-8"))

    # Act
    exit_code = runner._run_subcommand(["run", "G3", "--exit", "--run", "g3-exit-nokey-test"])

    # Assert
    assert exit_code == 2
    after = json.loads((G3 / "heldout" / "SEAL.json").read_text(encoding="utf-8"))
    assert after["unseal_events"] == before["unseal_events"]
    assert after.get("burned") is None


def test_Should_refuse_before_unsealing_When_an_exit_run_has_no_evaluator(monkeypatch):
    """Holding the RIGHT key is not enough: an unseal must never be spent on an unevaluable run.

    The key must be the real one. A wrong key also exits 2 — the decrypt fails — so a test using a
    dummy key passes whether or not the precondition exists, and measures nothing. Skipped rather
    than faked when the operator key is absent, because a fake key cannot prove this property.
    """
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    key_path = Path.home() / ".freecad-buddy-g3-unseal.key"
    if not key_path.is_file():
        pytest.skip(f"the real unseal key is absent ({key_path}); a dummy key proves nothing")
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", key_path.read_text(encoding="utf-8").strip())
    before = json.loads((G3 / "heldout" / "SEAL.json").read_text(encoding="utf-8"))

    # Act
    exit_code = runner._run_subcommand(["run", "G3", "--exit", "--run", "g3-exit-noeval-test"])

    # Assert
    assert exit_code == 2
    after = json.loads((G3 / "heldout" / "SEAL.json").read_text(encoding="utf-8"))
    assert after["unseal_events"] == before["unseal_events"], "an unseal was spent"
    assert after.get("burned") is None


def test_Should_record_a_not_scored_reason_When_a_g3_validator_has_no_driveable_case():
    """A fabricated 0.0 makes 'never measured' indistinguishable from 'detected nothing'.

    Every cited G3 validator must either carry a rate it actually measured or say in words why it
    did not. This asserts the invariant over all of them rather than naming one: which validator
    happens to be unmeasured changes as suites are authored, and a test pinned to today's laggard
    fails for the wrong reason the moment that one is measured.

    It also pins the shape of a *measured* row. ``visual_judge`` is the case that motivated this:
    its score comes from a judge grading rendered images against ``visual-judge/RUBRIC.md``, which
    may be a vision model over a client or a vision-capable agent reading the PNGs. A row scored
    that way must still declare the ``judge`` that produced it and any confidence caveat, so a
    reader can tell how the number was obtained rather than assuming a credentialed call.
    """
    # Arrange
    registry = _load(REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml")
    gate = _load(G3 / "gate.yaml")
    cited = {name for entry in gate["criteria"] for name in entry.get("cited_validators", [])}

    # Act
    rows = {name: registry[name]["last_run"] for name in cited if name in registry}

    # Assert
    assert rows, "no cited G3 validator has a registry row"
    for name, run in rows.items():
        measured = isinstance(run.get("sensitivity"), (int, float)) and run["sensitivity"] > 0.0
        assert measured or run.get("not_scored"), (
            f"{name} records neither a measured rate nor a reason it was not scored"
        )
        if measured and run.get("graded_by"):
            assert run.get("low_confidence") or run.get("wilson_ci"), (
                f"{name} was graded by a judge but carries no interval or confidence caveat"
            )


def test_Should_record_a_measured_rate_When_a_g3_validator_was_driven():
    """A validator the loop drove carries a real rate, its interval, and any excluded case.

    A driven validator must NOT read ``not_scored`` — that spelling is reserved for an absent
    measurement, and using it for a measured one would hide a real result as effectively as a
    fabricated zero hides an absent one.
    """
    # Arrange
    registry = _load(REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml")
    driven_validators = ("g3_assertions", "corrupted_plan", "verify_recompute")

    # Act
    driven = {name: registry[name]["last_run"] for name in driven_validators}

    # Assert
    for name, run in driven.items():
        assert not run.get("not_scored"), f"{name} was driven but reads as unmeasured"
        assert isinstance(run["sensitivity"], float), name
        assert run["wilson_ci"]["n"] > 0, f"{name} claims a rate over an empty population"


def test_Should_name_every_excluded_case_When_a_population_was_narrowed():
    """A rate measured over a reduced population must name what was left out, and why.

    ``sensitivity: 1.0`` over ``n: 8`` beside ``planted: 10`` is only readable if the two missing
    cases are named. Without this the row is honest about its arithmetic and silent about its
    scope, which is the same defect as a fabricated zero one level up.
    """
    # Arrange
    registry = _load(REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml")
    run = registry["corrupted_plan"]["last_run"]

    # Act
    excluded = run.get("excluded_unscorable") or {}

    # Assert
    assert excluded, "cases were skipped but none is named"
    assert len(excluded) == run["skipped_cases"]
    for case_id, reason in excluded.items():
        assert reason.strip(), f"{case_id} is excluded with no stated reason"


def test_Should_match_the_committed_digest_When_the_runner_hashes_a_g3_validator():
    """A clean working tree must read as CURRENT: a hasher mismatch stales a fresh score."""
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    registry = _load(REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml")

    # Act
    fresh = {name: runner._validator_src_hasher(name) for name in ("g3_assertions", "visual_judge")}

    # Assert
    for name, digest in fresh.items():
        assert registry[name]["validator_sha"] == digest


def test_Should_fail_leg_b_When_a_cited_validator_was_never_measured():
    """An UNMEASURED validator must never read as current, whatever else the gate has measured.

    Before story 4.5 this held for the whole cited set, because nothing had been scored. The loop
    has since measured ``corrupted_plan`` and ``g3_assertions``, so the property that survives — and
    the one ``not_scored`` exists to enforce — is narrower and sharper: a validator carrying a
    ``not_scored`` reason must still fail leg-b. A citation that passed while nothing backed it is
    exactly the failure mode this guards.
    """
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner
    from benchmarks.harness.verdict import check_validator_currency

    gate = runner._load_gate_def("G3")
    registry = runner._load_validators()
    cited = {
        name for criterion in gate["criteria"] for name in (criterion.get("cited_validators") or [])
    }
    assert cited, "the G3 gate cites no validator"

    # The unmeasured row is INJECTED rather than found. Reading the live registry for one made the
    # test self-disabling: every cited G3 validator is now measured, so the search returned empty
    # and the assertion had nothing to run against. The rule under test — an unmeasured validator
    # must fail leg-b — is a property of `check_validator_currency`, not of today's registry, so
    # the fixture supplies the condition instead of depending on a gap that should eventually close.
    victim = sorted(cited)[0]
    doctored = dict(registry)
    doctored[victim] = {
        **registry.get(victim, {}),
        "last_run": {
            **(registry.get(victim, {}).get("last_run") or {}),
            "sensitivity": 0.0,
            "false_alarm": 0.0,
            "not_scored": "injected by this test: no fault case targets this validator",
        },
    }

    # Act
    failures = check_validator_currency(gate, doctored, runner._validator_src_hasher)
    clean = check_validator_currency(gate, registry, runner._validator_src_hasher)

    # Assert
    failing_names = {failure.split(" ", 1)[0] for failure in failures}
    assert victim in failing_names, (
        f"{victim} carries a not_scored reason and a 0.0 rate yet reads as current"
    )
    assert victim not in {failure.split(" ", 1)[0] for failure in clean}, (
        f"{victim} fails leg-b on the real registry too, so the injection proved nothing"
    )


def test_Should_carry_a_registry_row_When_a_validator_is_cited_by_a_criterion():
    """Every cited validator must have a registry row naming the suite it was measured over.

    A cited validator with no row makes `check_validator_currency` report "not in registry" — a
    wiring failure, distinct from an honestly unmeasured validator. `verify_recompute` is the case
    that proves the difference: it was cited by G3.2/G3.3 with no suite targeting it and carried a
    row whose `not_scored` named the absent suite, and authoring `recompute/` discharged exactly
    that reason. The row must now name a real suite rather than the gap.
    """
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner
    from benchmarks.harness.verdict import check_validator_currency

    gate = runner._load_gate_def("G3")
    registry = runner._load_validators()
    cited = {
        name for criterion in gate["criteria"] for name in (criterion.get("cited_validators") or [])
    }

    # Act
    failures = check_validator_currency(gate, registry, runner._validator_src_hasher)

    # Assert
    missing_rows = sorted(name for name in cited if name not in registry)
    assert missing_rows == [], f"cited with no registry row: {missing_rows}"
    assert not any("not in registry" in failure for failure in failures)
    recompute = registry["verify_recompute"]
    assert recompute["suite"] == "g3/fault-injection/recompute/"
    assert not recompute["last_run"].get("not_scored"), (
        "verify_recompute has a fault suite; a not_scored reason would hide a measured rate"
    )


def test_Should_stay_bound_to_the_g2_suite_When_the_shared_assertions_validator_is_hashed():
    """G3 must not stale a G2 score: the two suites bind to separate registry names."""
    # Arrange
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks import runner

    registry = _load(REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml")

    # Act
    g2_digest = runner._validator_src_hasher("assertions")
    g3_digest = runner._validator_src_hasher("g3_assertions")

    # Assert
    assert registry["assertions"]["validator_sha"] == g2_digest
    assert g2_digest != g3_digest, "one digest cannot represent two populations"
