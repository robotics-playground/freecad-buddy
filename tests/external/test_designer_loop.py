"""External tests for the designer loop's control flow (story 4.5), FreeCAD-free.

Every decision the loop makes is proven here against a scripted backend: a stub registry, a
scripted grader that replays a fixed sequence of check lists, a scripted visual leg and a scripted
repairer. Nothing here builds geometry, so the whole control flow is provable without a live model
and without FreeCAD — which is what lets the convergence rule, the cap-is-failure rule and the
repair-input rule be asserted rather than assumed.

The last section goes further and drives the loop through the REAL ``verify_visual`` with story
4.4's ``ScriptedJudge`` behind it. The scripted ``VisualLeg`` used everywhere above proves the
loop's own branching; only that section proves the loop's seam actually binds to the shipped visual
leg, which is where a conjunction could silently come apart — a loop wired to a leg it never
exercises would pass every test above while converging on nothing.

What is deliberately NOT here: any claim that a model passed a part. ``ScriptedJudge`` replays
whatever verdict its script carries, so a green run means "the machinery is correct", never "the
judge approved the geometry" (decision 010/017). The real G3.1 rate is an operator run.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freecad_buddy.contracts import (  # noqa: E402
    CONVERGENCE_RULE,
    MAX_REPAIRS,
    VISUAL_CHECK_ID,
    converged,
)
from freecad_buddy.usecases.designer_loop import (  # noqa: E402
    PlanRefused,
    detect_spec_violation,
    discrepancy_vector,
    run_designer_loop,
    summarize_run,
)

SPEC_ID = "g3-dev-001-mounting-plate"
CHECKS = [{"fn": "hole_diameter", "expect": 5.5, "tol": {"abs": 0.05}}]


# ---------------------------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------------------------


class StubDocument:
    """The minimum a document needs to be resolvable and identifiable by the loop."""

    def __init__(self, name: str = "Doc") -> None:
        self.Name = name


class StubRegistry:
    """A ``DocumentRegistry``-shaped double recording every rebind the loop performed.

    ``rebinds`` is what the document-rebind test reads: the loop must rebind after every mutation,
    because the snapshot-restore path closes and reopens the document (DW-71).
    """

    def __init__(self, document: object | None = None) -> None:
        self.document = document if document is not None else StubDocument()
        self.rebinds: list[object] = []

    def with_document(self, _doc, fn):
        return fn("fcb-doc:stub", self.document)

    def rebind(self, _doc, document) -> None:
        self.rebinds.append(document)
        self.document = document


class ScriptedTool:
    """A plan-step tool returning a scripted envelope and optionally swapping the document.

    ``swaps_document`` reproduces the snapshot-restore path: the tool leaves a DIFFERENT document
    object bound, which is exactly the state a loop that kept its own reference would get wrong.
    """

    def __init__(self, status: str = "OK", swaps_document: object | None = None) -> None:
        self.status = status
        self.swaps_document = swaps_document
        self.calls: list[dict] = []

    def __call__(self, registry, doc=None, confirm=None, audit_sink=None, **args):
        self.calls.append({"doc": doc, "confirm": confirm, "args": args})
        if self.swaps_document is not None:
            registry.document = self.swaps_document
        return {
            "status": self.status,
            "detail": None if self.status == "OK" else {"message": "scripted failure"},
            "structured_content": {},
        }


class ScriptedGrader:
    """Replays one check list per call; repeats the last once the script is exhausted."""

    def __init__(self, script: list[list[dict]]) -> None:
        self.script = script
        self.calls = 0

    def __call__(self, document, checks, anchor_frame=None):
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        return self.script[index]


class ScriptedVisual:
    """Replays one ``visual.judge`` check per call, recording the ``geometry_passed`` it was given.

    ``geometry_passed_calls`` is what the judge-cadence test reads: the judge must not be called
    with a failing geometry leg doing real work, and the loop must pass the real value through.
    """

    def __init__(self, script: list[bool]) -> None:
        self.script = script
        self.calls = 0
        self.geometry_passed_calls: list[bool] = []

    def __call__(self, doc, geometry_passed):
        self.geometry_passed_calls.append(geometry_passed)
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        passed = self.script[index] and geometry_passed
        return {
            "id": VISUAL_CHECK_ID,
            "measured": []
            if passed
            else [{"view": "iso", "observation": "off", "severity": "blocking"}],
            "measured_kind": "text",
            "expected": True,
            "tolerance": None,
            "passed": passed,
            "detail": None if passed else {"code": "visual.judge_failed", "message": "off"},
        }


class RecordingRepairer:
    """Returns the same plan back, recording exactly what repair input it was handed."""

    def __init__(self, plan: dict | None = None) -> None:
        self.plan = plan
        self.inputs: list[tuple] = []

    def __call__(self, plan, discrepancy, judge_findings):
        self.inputs.append((plan, discrepancy, judge_findings))
        return self.plan if self.plan is not None else plan


def passing_check(check_id: str = "assert.hole_diameter") -> dict:
    return {
        "id": check_id,
        "measured": 5.5,
        "expected": 5.5,
        "tolerance": {"abs": 0.05},
        "passed": True,
        "detail": {"message": "within band"},
    }


def failing_check(check_id: str = "assert.hole_diameter", measured=8.0) -> dict:
    return {
        "id": check_id,
        "measured": measured,
        "expected": 5.5,
        "tolerance": {"abs": 0.05},
        "passed": False,
        "detail": {"message": f"diameters [{measured}] vs 5.5 +/- 0.05 mm"},
    }


def approved_plan(steps: list[dict] | None = None) -> dict:
    return {
        "schema": "fcb.design-plan/1",
        "spec_id": SPEC_ID,
        "spec_text": "A rectangular mounting plate with four 5.5 mm holes.",
        "steps": steps if steps is not None else [{"tool": "feature_pad", "args": {}}],
        "approved": True,
        "approved_by": "operator",
    }


@pytest.fixture()
def workdir(tmp_path, monkeypatch):
    """Point the session workdir at a temp dir so run artifacts land somewhere inspectable."""
    monkeypatch.setenv("FREECAD_BUDDY_WORKDIR", str(tmp_path))
    return tmp_path


def drive(registry, grader, visual, **kwargs):
    """Run the loop with the scripted doubles, defaulting the plan and the tool table."""
    tool = kwargs.pop("tool", ScriptedTool())
    plan = kwargs.pop("plan", approved_plan())
    return run_designer_loop(
        registry,
        plan,
        CHECKS,
        grader,
        visual,
        doc="fcb-doc:stub",
        extra_tools={"feature_pad": tool},
        **kwargs,
    )


# ---------------------------------------------------------------------------------------------
# Convergence is the verdict, never the count
# ---------------------------------------------------------------------------------------------


def test_Should_report_converged_When_geometry_and_visual_both_pass(workdir):
    # Arrange
    registry = StubRegistry()
    grader = ScriptedGrader([[passing_check()]])
    visual = ScriptedVisual([True])

    # Act
    record = drive(registry, grader, visual, run_id="converge-first-try")

    # Assert
    assert record["status"] == "CONVERGED"
    assert record["converged"] is True
    assert record["repairs_used"] == 0
    assert record["convergence_rule"] == CONVERGENCE_RULE
    assert record["iterations"][-1]["geometry_pass"] is True
    assert record["iterations"][-1]["visual_pass"] is True


def test_Should_report_failure_When_the_cap_is_exhausted(workdir):
    # Arrange: a part that never satisfies the spec, and a repairer that keeps proposing.
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()]])
    visual = ScriptedVisual([False])
    repairer = RecordingRepairer()

    # Act
    record = drive(registry, grader, visual, repairer=repairer, run_id="cap-exhausted")

    # Assert: the cap is a FAILURE, never a finish.
    assert record["status"] == "CAP_EXHAUSTED"
    assert record["converged"] is False
    assert record["repairs_used"] == MAX_REPAIRS
    assert len(record["iterations"]) == MAX_REPAIRS + 1
    assert "FAILURE, not a finish" in record["detail"]
    assert "did NOT converge" in summarize_run(record)


def test_Should_not_converge_When_geometry_passes_but_the_judge_does_not(workdir):
    # Arrange: the conjunction's second leg fails on every iteration.
    registry = StubRegistry()
    grader = ScriptedGrader([[passing_check()]])
    visual = ScriptedVisual([False])
    repairer = RecordingRepairer()

    # Act
    record = drive(registry, grader, visual, repairer=repairer, run_id="visual-blocks")

    # Assert
    assert record["converged"] is False
    assert record["status"] == "CAP_EXHAUSTED"
    assert all(iteration["geometry_pass"] is True for iteration in record["iterations"])
    assert all(iteration["visual_pass"] is False for iteration in record["iterations"])


def test_Should_converge_After_a_repair_fixes_the_discrepancy(workdir):
    # Arrange: the first attempt misses a dimension; the repair lands it.
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()], [passing_check()]])
    visual = ScriptedVisual([False, True])
    repairer = RecordingRepairer()

    # Act
    record = drive(registry, grader, visual, repairer=repairer, run_id="converge-after-repair")

    # Assert
    assert record["status"] == "CONVERGED"
    assert record["repairs_used"] == 1
    assert record["repairs_used"] <= MAX_REPAIRS


def test_Should_read_convergence_from_the_two_legs_only():
    # Arrange: the four combinations of the conjunctive rule.
    legs = [(True, True), (True, False), (False, True), (False, False)]

    # Act
    verdicts = [converged(geometry, visual) for geometry, visual in legs]

    # Assert: only the conjunction is done; no iteration count enters the rule.
    assert verdicts == [True, False, False, False]


# ---------------------------------------------------------------------------------------------
# The discrepancy vector is the repair input
# ---------------------------------------------------------------------------------------------


def test_Should_carry_measured_and_expected_When_building_the_discrepancy_vector():
    # Arrange
    results = [passing_check("assert.expect_bbox"), failing_check("assert.hole_diameter", 8.0)]

    # Act
    vector = discrepancy_vector(results)

    # Assert: only the failing check, carrying the pair a repair can act on.
    assert len(vector) == 1
    assert vector[0]["check_id"] == "assert.hole_diameter"
    assert vector[0]["measured"] == 8.0
    assert vector[0]["expected"] == 5.5
    assert vector[0]["tolerance"] == {"abs": 0.05}


def test_Should_hand_the_repairer_the_vector_and_the_findings_never_the_plan_text(workdir):
    # Arrange
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()], [passing_check()]])
    visual = ScriptedVisual([False, True])
    repairer = RecordingRepairer()

    # Act
    drive(registry, grader, visual, repairer=repairer, run_id="repair-input")

    # Assert: the repairer saw the measured-vs-expected pair, not an error string.
    _plan, discrepancy, findings = repairer.inputs[0]
    assert discrepancy[0]["measured"] == 8.0
    assert discrepancy[0]["expected"] == 5.5
    assert isinstance(findings, list)


def test_Should_record_the_repair_decision_On_the_repaired_iteration(workdir):
    # Arrange
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()], [passing_check()]])
    visual = ScriptedVisual([False, True])
    repairer = RecordingRepairer()

    # Act
    record = drive(registry, grader, visual, repairer=repairer, run_id="repair-decision")

    # Assert
    repair = record["iterations"][1]["repair"]
    assert repair["for_iteration"] == 0
    assert repair["addressed"] == ["assert.hole_diameter"]


# ---------------------------------------------------------------------------------------------
# Detection measures the artifact, never the plan
# ---------------------------------------------------------------------------------------------


def test_Should_detect_a_spec_violation_From_a_failing_measurement():
    # Arrange
    results = [passing_check("assert.is_valid_solid"), failing_check("assert.hole_diameter")]

    # Act
    violation = detect_spec_violation(results)

    # Assert
    assert violation is not None
    assert violation["check_id"] == "assert.hole_diameter"


def test_Should_detect_no_violation_When_every_measurement_passes():
    # Arrange
    results = [passing_check("assert.is_valid_solid"), passing_check("assert.hole_diameter")]

    # Act
    violation = detect_spec_violation(results)

    # Assert
    assert violation is None


def test_Should_detect_nothing_From_a_corrupt_plan_whose_part_measures_correct():
    # Arrange: a plan the suite calls corrupt, whose produced part nonetheless satisfies every
    # assertion. Detection reads the artifact, so there is nothing to report — which is exactly
    # what makes a geometry-preserving reorder a clean control rather than a defect.
    corrupt_looking_plan = approved_plan(
        [{"tool": "feature_pocket", "args": {}}, {"tool": "feature_pad", "args": {}}]
    )

    # Act
    violation = detect_spec_violation([passing_check()])

    # Assert
    assert violation is None
    assert corrupt_looking_plan["steps"][0]["tool"] == "feature_pocket"


# ---------------------------------------------------------------------------------------------
# The document rebind (DW-71)
# ---------------------------------------------------------------------------------------------


def test_Should_rebind_the_document_After_a_step_swaps_it(workdir):
    # Arrange: the tool leaves a different document bound, as the snapshot restore does.
    reopened = StubDocument("Reopened")
    registry = StubRegistry()
    tool = ScriptedTool(swaps_document=reopened)
    grader = ScriptedGrader([[passing_check()]])
    visual = ScriptedVisual([True])

    # Act
    drive(registry, grader, visual, tool=tool, run_id="rebind")

    # Assert: the loop holds the reopened document, never the closed original.
    assert registry.document is reopened
    assert registry.rebinds[-1] is reopened


def test_Should_measure_the_rebound_document_Not_the_original(workdir):
    # Arrange
    reopened = StubDocument("Reopened")
    registry = StubRegistry()
    tool = ScriptedTool(swaps_document=reopened)
    seen: list[object] = []

    def grader(document, checks, anchor_frame=None):
        seen.append(document)
        return [passing_check()]

    # Act
    drive(registry, grader, ScriptedVisual([True]), tool=tool, run_id="measure-rebound")

    # Assert
    assert seen == [reopened]


# ---------------------------------------------------------------------------------------------
# Plan refusal and step failure
# ---------------------------------------------------------------------------------------------


def test_Should_refuse_An_unapproved_plan(workdir):
    # Arrange
    plan = approved_plan()
    plan["approved"] = False
    registry = StubRegistry()

    # Act
    def act():
        return drive(
            registry, ScriptedGrader([[passing_check()]]), ScriptedVisual([True]), plan=plan
        )

    # Assert
    with pytest.raises(PlanRefused, match="not approved"):
        act()


def test_Should_refuse_A_plan_naming_a_tool_outside_the_surface(workdir):
    # Arrange
    plan = approved_plan([{"tool": "os_system", "args": {}}])
    registry = StubRegistry()

    # Act
    def act():
        return drive(
            registry, ScriptedGrader([[passing_check()]]), ScriptedVisual([True]), plan=plan
        )

    # Assert
    with pytest.raises(PlanRefused, match="outside the Phase-2 tool surface"):
        act()


def test_Should_still_measure_the_artifact_When_a_step_failed(workdir):
    # Arrange: a step that never applied leaves a part the assertions still measure.
    registry = StubRegistry()
    tool = ScriptedTool(status="SPEC_FAILED")
    grader = ScriptedGrader([[failing_check()]])
    visual = ScriptedVisual([True])

    # Act
    record = drive(registry, grader, visual, tool=tool, run_id="step-failed")

    # Assert: the failure is recorded beside the measurement, never in place of it.
    iteration = record["iterations"][0]
    assert "SPEC_FAILED" in iteration["step_failure"]
    assert iteration["geometry_pass"] is False
    assert iteration["discrepancy"][0]["check_id"] == "assert.hole_diameter"


def test_Should_fail_the_iteration_When_the_grader_raises(workdir):
    # Arrange
    registry = StubRegistry()

    def grader(document, checks, anchor_frame=None):
        raise RuntimeError("the shape could not be read")

    # Act
    record = drive(registry, grader, ScriptedVisual([True]), run_id="grader-raised")

    # Assert: an ungradable artifact is a failure, never a pass.
    assert record["converged"] is False
    assert record["iterations"][0]["geometry_pass"] is False
    assert "the shape could not be read" in record["iterations"][0]["discrepancy"][0]["message"]


def test_Should_stop_at_the_first_failing_step(workdir):
    # Arrange: the second step must not run on geometry the first did not produce.
    registry = StubRegistry()
    first = ScriptedTool(status="SPEC_FAILED")
    second = ScriptedTool()
    plan = approved_plan(
        [{"tool": "feature_pad", "args": {}}, {"tool": "feature_pocket", "args": {}}]
    )

    # Act
    run_designer_loop(
        registry,
        plan,
        CHECKS,
        ScriptedGrader([[failing_check()]]),
        ScriptedVisual([False]),
        doc="fcb-doc:stub",
        run_id="stop-at-failure",
        extra_tools={"feature_pad": first, "feature_pocket": second},
    )

    # Assert
    assert len(first.calls) == 1
    assert second.calls == []


# ---------------------------------------------------------------------------------------------
# Run artifacts: a failed run is reconstructable from its workdir alone
# ---------------------------------------------------------------------------------------------


def test_Should_write_the_plan_every_vector_and_every_repair_To_the_workdir(workdir):
    # Arrange
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()]])
    visual = ScriptedVisual([False])
    repairer = RecordingRepairer()

    # Act
    record = drive(registry, grader, visual, repairer=repairer, run_id="artifacts")

    # Assert
    run_dir = Path(record["workdir"])
    written = sorted(path.name for path in run_dir.iterdir())
    assert "plan.json" in written
    assert "run.json" in written
    assert sum(1 for name in written if name.startswith("iteration-")) == MAX_REPAIRS + 1
    assert sum(1 for name in written if name.startswith("repair-")) == MAX_REPAIRS


def test_Should_record_the_discrepancy_and_the_judge_detail_In_each_iteration_artifact(workdir):
    # Arrange
    registry = StubRegistry()
    grader = ScriptedGrader([[failing_check()]])
    visual = ScriptedVisual([False])

    # Act
    record = drive(registry, grader, visual, run_id="artifact-content")

    # Assert
    stored = json.loads((Path(record["workdir"]) / "iteration-00.json").read_text(encoding="utf-8"))
    assert stored["discrepancy"][0]["measured"] == 8.0
    assert stored["discrepancy"][0]["expected"] == 5.5
    assert stored["visual_detail"]["code"] == "visual.judge_failed"


def test_Should_report_the_elapsed_time_Even_when_the_run_failed(workdir):
    # Arrange
    registry = StubRegistry()

    # Act
    record = drive(
        registry, ScriptedGrader([[failing_check()]]), ScriptedVisual([False]), run_id="timing"
    )

    # Assert: timing is always reported; the gate judges it, the loop does not hide it.
    assert record["elapsed_s"] >= 0.0
    assert record["iterations"][0]["elapsed_s"] >= 0.0


def test_Should_end_the_run_When_no_repairer_is_supplied(workdir):
    # Arrange
    registry = StubRegistry()

    # Act
    record = drive(
        registry, ScriptedGrader([[failing_check()]]), ScriptedVisual([False]), run_id="no-repairer"
    )

    # Assert: honest "no repairer was supplied", never a pass and never a silent cap spend.
    assert record["status"] == "CAP_EXHAUSTED"
    assert record["repairs_used"] == 0
    assert "no repairer was supplied" in record["detail"]


def test_Should_pass_the_geometry_verdict_Into_the_visual_leg(workdir):
    # Arrange: the judge cadence is the loop's to enforce; the leg is told the real verdict so it
    # can skip its own call on an iteration geometry already failed.
    registry = StubRegistry()
    visual = ScriptedVisual([True])

    # Act
    drive(registry, ScriptedGrader([[failing_check()]]), visual, run_id="judge-cadence")

    # Assert
    assert visual.geometry_passed_calls == [False]


# ---------------------------------------------------------------------------------------------
# The loop composed with the REAL visual leg
#
# Everything above scripts the `VisualLeg` directly, which proves the loop's branching but not that
# the seam binds to the shipped `verify_visual`. These drive the real use case with story 4.4's
# `ScriptedJudge` and its port doubles behind it, so the conjunction is proven end to end offline.
# No credential is involved and none is needed: the judge replays a recorded verdict.
# ---------------------------------------------------------------------------------------------


def _write_png(path: Path, width: int, height: int) -> str:
    """A file carrying a valid PNG signature and an IHDR declaring ``width`` x ``height``.

    The legibility gate reads the width out of the IHDR rather than trusting the render request, so
    a double must write a real header for the gate to measure anything.
    """
    import struct

    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    header += struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    path.write_bytes(header + b"\x00" * 64)
    return str(path)


@pytest.fixture()
def visual_environment(monkeypatch, tmp_path):
    """Neutralize the FreeCAD-backed helpers ``verify_visual`` reaches for, as 4.4's suite does.

    ``shim`` reads a live build and ``fingerprint`` reads real shapes; neither exists in the uv env.
    The drawing sheet is stubbed at the same seam 4.4 stubs it, because composing a real TechDraw
    page needs FreeCAD — what is under test here is the loop-to-leg binding, not the sheet builder.
    """
    from freecad_buddy.contracts import MIN_JUDGE_IMAGE_WIDTH_PX
    from freecad_buddy.usecases import verify_visual as leg_module

    monkeypatch.setattr(leg_module.shim, "freecad_version", lambda: "1.1.1")
    monkeypatch.setattr(leg_module.shim, "element_map_version", lambda: 1)
    monkeypatch.setattr(leg_module, "fingerprint", lambda document: {"digest": "x"})
    monkeypatch.setattr(leg_module, "massprops_equal", lambda a, b: True)
    monkeypatch.setattr(leg_module, "temp_dir", lambda: str(tmp_path))

    width = MIN_JUDGE_IMAGE_WIDTH_PX
    height = round(width * 297 / 420)
    sheet = {
        "schema": "fcb.drawing-sheet/1",
        "available": True,
        "reason": None,
        "svg_path": str(tmp_path / "sheet.svg"),
        "png_path": _write_png(tmp_path / "sheet.png", width, height),
        "page_width_px": width,
        "page_height_px": height,
        "views": ["front", "top", "right"],
        "callouts": [],
    }
    monkeypatch.setattr(leg_module, "_drawing_sheet", lambda registry, raster, doc: sheet)
    return tmp_path


class RenderingDouble:
    """A ``RenderPort`` double writing a PNG header at the size the scene asked for."""

    def __init__(self, tmp_path):
        self._tmp = tmp_path
        self.scenes = []

    def available(self):
        return True, None

    def render(self, document, scene, out_path):
        from freecad_buddy.contracts import RenderResult

        self.scenes.append(scene)
        _write_png(Path(out_path), scene.width, scene.height)
        return RenderResult(rendered_objects=list(scene.objects))


class RasterDouble:
    """An ``SvgRasterPort`` double; never reached, because the sheet itself is stubbed."""

    def available(self):
        return True, None

    def rasterize(self, svg, out_path, width, height):  # pragma: no cover - sheet is stubbed
        _write_png(Path(out_path), width, height)


class RenderableDocument:
    """The least a document needs for the real visual leg to find drawable geometry."""

    def __init__(self, name="Plate"):
        self.Name = name
        self.Objects = [_RenderableObject("Pad")]

    def getObject(self, name):
        return next((obj for obj in self.Objects if obj.Name == name), None)


class _RenderableObject:
    def __init__(self, name):
        self.Name = name
        self.TypeId = "Part::Feature"
        self.Visibility = True
        self.Shape = _NonNullShape()


class _NonNullShape:
    def isNull(self):
        return False


CHECKLIST = ["four 5.5 mm holes, one at each corner"]
SPEC_TEXT = "A mounting plate with four 5.5 mm corner holes."


def _real_visual_leg(registry, judge, tmp_path):
    """Bind the shipped ``verify_visual`` into the loop's ``VisualLeg`` shape.

    This IS the production wiring a caller performs: the ports and the judge are bound once, and
    the loop supplies only what varies per iteration. Returning the ``visual.judge`` check off the
    report is what the loop reads.
    """
    from freecad_buddy.usecases.verify_visual import verify_visual

    def leg(doc, geometry_passed):
        envelope = verify_visual(
            registry,
            RenderingDouble(tmp_path),
            RasterDouble(),
            judge,
            SPEC_TEXT,
            CHECKLIST,
            doc=doc,
            geometry_passed=geometry_passed,
        )
        return envelope["structured_content"]["checks"][0]

    return leg


def _registry_with(document):
    """A real ``DocumentRegistry`` holding ``document`` under a real minted handle."""
    from freecad_buddy.usecases.documents import DocumentRegistry

    registry = DocumentRegistry()
    handle = registry._mint_handle()
    registry._by_handle[handle] = document
    return registry, handle


def _drive_with_real_leg(registry, handle, judge, tmp_path, grader, **kwargs):
    """Run the loop with the shipped visual leg bound behind it."""
    return run_designer_loop(
        registry,
        approved_plan(),
        CHECKS,
        grader,
        _real_visual_leg(registry, judge, tmp_path),
        doc=handle,
        extra_tools={"feature_pad": ScriptedTool()},
        **kwargs,
    )


def test_Should_converge_When_the_real_visual_leg_returns_a_passing_verdict(
    workdir, visual_environment
):
    # Arrange: a recorded PASS verdict, replayed. This asserts the WIRING, never model quality.
    from benchmarks.harness.judge_double import ScriptedJudge

    registry, handle = _registry_with(RenderableDocument())
    judge = ScriptedJudge({CHECKLIST[0]: {"pass": True, "findings": []}})

    # Act
    record = _drive_with_real_leg(
        registry,
        handle,
        judge,
        visual_environment,
        ScriptedGrader([[passing_check()]]),
        run_id="real-leg-pass",
    )

    # Assert: the loop reached done THROUGH the shipped leg, and the judge really was called.
    assert record["status"] == "CONVERGED"
    assert record["converged"] is True
    assert len(judge.calls) == 1


def test_Should_not_converge_When_the_real_judge_is_unreachable(workdir, visual_environment):
    # Arrange: an empty script, so the judge raises its unreachable-judge failure. Geometry PASSES.
    from benchmarks.harness.judge_double import ScriptedJudge

    registry, handle = _registry_with(RenderableDocument())
    judge = ScriptedJudge({})

    # Act
    record = _drive_with_real_leg(
        registry,
        handle,
        judge,
        visual_environment,
        ScriptedGrader([[passing_check()]]),
        run_id="real-leg-unreachable",
    )

    # Assert: this is the conjunction's whole point — a part whose geometry is right is NOT done
    # when no verdict was obtained. A loop that weakened the rule to make runs pass would converge
    # here, which is the defect the story's Never list forbids.
    iteration = record["iterations"][0]
    assert iteration["geometry_pass"] is True
    assert iteration["visual_pass"] is False
    assert record["converged"] is False
    assert iteration["visual_detail"]["code"] == "visual.unavailable"


def test_Should_not_converge_When_no_vision_backend_is_available(workdir, visual_environment):
    # Arrange: the no-credential posture this machine is actually in — the client reports
    # unavailable rather than raising, which is the branch a missing key takes in production.
    from benchmarks.harness.judge_double import ScriptedJudge

    registry, handle = _registry_with(RenderableDocument())
    judge = ScriptedJudge({}, available_reason="no credential in the environment")

    # Act
    record = _drive_with_real_leg(
        registry,
        handle,
        judge,
        visual_environment,
        ScriptedGrader([[passing_check()]]),
        run_id="real-leg-no-credential",
    )

    # Assert
    assert record["converged"] is False
    assert record["iterations"][0]["visual_detail"]["code"] == "visual.unavailable"
    assert "no credential" in record["iterations"][0]["visual_detail"]["message"]
    assert judge.calls == [], "an unavailable judge must never be handed a visual set"


def test_Should_skip_the_judge_call_When_geometry_failed_on_that_iteration(
    workdir, visual_environment
):
    """AD-21 cadence: the judge never runs on an iteration geometry already failed.

    Conjunctive, so the verdict could not change — and a call would spend one of only three repair
    iterations for no information. Proven against the real leg rather than the double, because the
    skip is the leg's decision and the loop only supplies the flag.
    """
    # Arrange
    from benchmarks.harness.judge_double import ScriptedJudge

    registry, handle = _registry_with(RenderableDocument())
    judge = ScriptedJudge({CHECKLIST[0]: {"pass": True, "findings": []}})

    # Act
    record = _drive_with_real_leg(
        registry,
        handle,
        judge,
        visual_environment,
        ScriptedGrader([[failing_check()]]),
        run_id="real-leg-geometry-failed",
    )

    # Assert
    assert judge.calls == [], "the judge was called on an iteration geometry had already failed"
    assert record["iterations"][0]["visual_detail"]["code"] == "visual.not_run"
    assert record["converged"] is False


def test_Should_carry_the_judges_findings_Into_the_repair_input(workdir, visual_environment):
    """The findings the repair reads must come from the real leg, not only from a double.

    The loop's repair input is the discrepancy vector PLUS the judge's findings. Geometry passes
    here, so the vector is empty and the findings are the whole input — which makes this the case
    that proves they survive the trip from the judge through the leg into the repairer.
    """
    # Arrange
    from benchmarks.harness.judge_double import ScriptedJudge

    registry, handle = _registry_with(RenderableDocument())
    verdict = {
        "pass": False,
        "findings": [
            {
                "view": "front",
                "observation": "the flange faces the wrong way",
                "severity": "blocking",
            }
        ],
    }
    judge = ScriptedJudge({CHECKLIST[0]: verdict})
    repairer = RecordingRepairer()

    # Act
    _drive_with_real_leg(
        registry,
        handle,
        judge,
        visual_environment,
        ScriptedGrader([[passing_check()]]),
        repairer=repairer,
        run_id="real-leg-findings",
    )

    # Assert
    _plan, discrepancy, findings = repairer.inputs[0]
    assert discrepancy == [], "geometry passed, so the vector is empty by construction"
    assert findings[0]["view"] == "front"
    assert findings[0]["observation"] == "the flange faces the wrong way"
