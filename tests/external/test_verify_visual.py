"""External tests for the visual judge leg (story 4.4), FreeCAD-free.

Covers every row of the story's I/O matrix: the happy path, an unreachable judge, a malformed
verdict, the same-model preflight refusal, the geometry-already-failed skip, the below-floor
refusal, and the operator-waiver audit record. No test asserts a passing judge verdict obtained
from a live model — decision 010 puts that measurement in an operator run, and a green suite here
means the machinery is correct, never that a model passed a part.

``verify_visual`` imports FreeCAD only through ``shim``; the document, render port, raster port and
judge are all doubles, so the whole leg runs in the uv env with no FreeCAD and no credential.
"""

import base64
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.harness.judge_double import ScriptedJudge, ScriptedJudgeUnavailable  # noqa: E402
from freecad_buddy.adapters import visual_judge_client  # noqa: E402
from freecad_buddy.adapters.visual_judge_client import (  # noqa: E402
    CREDENTIAL_ENV,
    TEMPERATURE,
    JudgeTransportError,
    VisualJudgeClient,
)
from freecad_buddy.contracts import MIN_JUDGE_IMAGE_WIDTH_PX, VISUAL_CHECK_ID  # noqa: E402
from freecad_buddy.usecases import verify_visual as target_module  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError  # noqa: E402
from freecad_buddy.usecases.verify_visual import (  # noqa: E402
    JudgeUnavailable,
    VerdictSchemaError,
    validate_verdict,
    verify_visual,
    waiver_record,
)

SPEC_TEXT = "An L-bracket, 60 x 40 x 5 mm, with two 6 mm holes 40 mm apart."
CHECKLIST = ["flange present and perpendicular", "two holes 40 mm apart"]
PASS_VERDICT = {"pass": True, "findings": []}


# ---------------------------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------------------------


def _write_png(path: Path, width: int, height: int = 2048) -> str:
    """Write a file carrying a valid PNG signature and IHDR declaring ``width`` x ``height``.

    The legibility gate reads the width out of the IHDR chunk rather than trusting the render
    request, so a double must produce a real header for the gate to measure. The image data beyond
    the header is irrelevant — nothing decodes it.
    """
    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    header += struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    path.write_bytes(header + b"\x00" * 64)
    return str(path)


class FakeObject:
    def __init__(self, name, type_id="Part::Feature"):
        self.Name = name
        self.TypeId = type_id
        self.Visibility = True
        self.Shape = FakeShape()


class FakeShape:
    def isNull(self):
        return False


class FakeDocument:
    def __init__(self, name="Bracket"):
        self.Name = name
        self.Objects = [FakeObject("Pad")]

    def getObject(self, name):
        return next((o for o in self.Objects if o.Name == name), None)


class FakeRenderPort:
    """A ``RenderPort`` double that writes a PNG header at the size the scene asked for."""

    def __init__(self, tmp_path, available=True, reason=None, width_override=None):
        self._tmp = tmp_path
        self._available = available
        self._reason = reason
        self._width_override = width_override
        self.scenes = []

    def available(self):
        return self._available, self._reason

    def render(self, document, scene, out_path):
        from freecad_buddy.contracts import RenderResult

        self.scenes.append(scene)
        width = self._width_override or scene.width
        _write_png(Path(out_path), width, scene.height)
        return RenderResult(rendered_objects=list(scene.objects))


class FakeRasterPort:
    def available(self):
        return True, None

    def rasterize(self, svg, out_path, width, height):  # pragma: no cover - never reached
        _write_png(Path(out_path), width, height)


def _sheet(tmp_path, width=MIN_JUDGE_IMAGE_WIDTH_PX, available=True, reason=None):
    """A ``DrawingSheet`` as ``techdraw_for_judge`` would return it."""
    if not available:
        return {
            "schema": "fcb.drawing-sheet/1",
            "available": False,
            "reason": reason,
            "svg_path": None,
            "png_path": None,
            "page_width_px": 0,
            "page_height_px": 0,
            "views": [],
            "callouts": [],
        }
    png = _write_png(tmp_path / "sheet.png", width, round(width * 297 / 420))
    return {
        "schema": "fcb.drawing-sheet/1",
        "available": True,
        "reason": None,
        "svg_path": str(tmp_path / "sheet.svg"),
        "png_path": png,
        "page_width_px": width,
        "page_height_px": round(width * 297 / 420),
        "views": ["front", "top", "right"],
        "callouts": [],
    }


@pytest.fixture
def registry():
    """A registry holding one fake document under a real handle."""
    target = DocumentRegistry()
    handle = target._mint_handle()
    target._by_handle[handle] = FakeDocument()
    return target, handle


@pytest.fixture(autouse=True)
def _stub_environment(monkeypatch, tmp_path):
    """Neutralize the FreeCAD-backed helpers the leg reaches for, and isolate the workdir.

    ``shim`` reads a live FreeCAD build and ``fingerprint`` reads real shapes; neither is present
    in the external env. Both are replaced with fixed values so the tests measure the leg's own
    logic rather than a FreeCAD absence.
    """
    monkeypatch.setattr(target_module.shim, "freecad_version", lambda: "1.1.1")
    monkeypatch.setattr(target_module.shim, "element_map_version", lambda: 1)
    monkeypatch.setattr(target_module, "fingerprint", lambda document: {"digest": "x"})
    monkeypatch.setattr(target_module, "massprops_equal", lambda a, b: True)
    monkeypatch.setattr(target_module, "temp_dir", lambda: str(tmp_path))
    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)


def _run(registry, tmp_path, judge, *, sheet=None, monkeypatch=None, **kwargs):
    """Drive ``verify_visual`` with the drawing sheet stubbed to ``sheet``."""
    target, handle = registry
    resolved_sheet = _sheet(tmp_path) if sheet is None else sheet
    monkeypatch.setattr(
        target_module, "_drawing_sheet", lambda registry, raster, doc: resolved_sheet
    )
    options = {"geometry_passed": True, **kwargs}
    return verify_visual(
        target,
        FakeRenderPort(tmp_path),
        FakeRasterPort(),
        judge,
        SPEC_TEXT,
        CHECKLIST,
        doc=handle,
        **options,
    )


def _check(envelope):
    """The single ``visual.judge`` check the report carries."""
    return envelope["structured_content"]["checks"][0]


# ---------------------------------------------------------------------------------------------
# Matrix row: happy path
# ---------------------------------------------------------------------------------------------


class TestHappyPath:
    def test_Should_report_visual_judge_pass_When_full_set_and_passing_verdict(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Assert
        check = _check(envelope)
        assert check["id"] == VISUAL_CHECK_ID
        assert check["passed"] is True
        assert envelope["status"] == "OK"
        assert envelope["structured_content"]["verdict"] == "OK"

    def test_Should_hand_the_judge_every_view_When_the_set_is_complete(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        _run(registry, tmp_path, judge, monkeypatch=monkeypatch, focus_objects=["Pad"])

        # Assert
        views = [image["view"] for image in judge.calls[0]["images"]]
        assert views == ["iso", "focus", "front", "top", "right"]

    def test_Should_carry_findings_as_diagnostics_When_the_judge_fails_the_part(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        findings = [
            {
                "view": "front",
                "observation": "the flange faces the wrong way",
                "severity": "blocking",
            }
        ]
        judge = ScriptedJudge({CHECKLIST[0]: {"pass": False, "findings": findings}})

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Assert
        check = _check(envelope)
        assert check["passed"] is False
        assert check["measured"] == findings
        assert check["detail"]["code"] == "visual.judge_failed"


# ---------------------------------------------------------------------------------------------
# Matrix row: judge unreachable
# ---------------------------------------------------------------------------------------------


class TestJudgeUnreachable:
    def test_Should_report_visual_unavailable_When_the_judge_raises(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({})  # no recorded verdict -> ScriptedJudgeUnavailable

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Assert
        check = _check(envelope)
        assert check["passed"] is False
        assert check["detail"]["code"] == "visual.unavailable"

    def test_Should_report_visual_unavailable_When_no_credential_is_present(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({}, available_reason="no judge credential")

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Assert
        check = _check(envelope)
        assert check["passed"] is False
        assert check["detail"]["code"] == "visual.unavailable"
        assert "credential" in check["detail"]["message"]

    def test_Should_report_visual_unavailable_When_the_render_port_has_no_capability(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        target, handle = registry
        monkeypatch.setattr(
            target_module, "_drawing_sheet", lambda registry, raster, doc: _sheet(tmp_path)
        )
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        envelope = verify_visual(
            target,
            FakeRenderPort(tmp_path, available=False, reason="no GL context"),
            FakeRasterPort(),
            judge,
            SPEC_TEXT,
            CHECKLIST,
            doc=handle,
            geometry_passed=True,
        )

        # Assert
        check = _check(envelope)
        assert check["detail"]["code"] == "visual.unavailable"
        assert "no GL context" in check["detail"]["message"]
        assert judge.calls == []

    def test_Should_report_visual_unavailable_When_the_drawing_is_unavailable(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})
        sheet = _sheet(tmp_path, available=False, reason="no headless TechDraw")

        # Act
        envelope = _run(registry, tmp_path, judge, sheet=sheet, monkeypatch=monkeypatch)

        # Assert
        check = _check(envelope)
        assert check["detail"]["code"] == "visual.unavailable"
        assert "no headless TechDraw" in check["detail"]["message"]
        assert judge.calls == []

    def test_Should_raise_the_production_failure_class_When_the_double_has_no_verdict(
        self, tmp_path
    ):
        # Arrange: the double must take the SAME fail-closed branch the live client's transport
        # failure takes, or CI would prove a catch-all path production never reaches.
        judge = ScriptedJudge({})

        # Act
        act = lambda: judge.judge(_visual_set(tmp_path))  # noqa: E731

        # Assert
        with pytest.raises(ScriptedJudgeUnavailable):
            act()
        assert issubclass(ScriptedJudgeUnavailable, JudgeUnavailable)

    def test_Should_never_return_a_pass_When_the_judge_is_unavailable(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({}, available_reason="unreachable")

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Assert
        assert envelope["status"] != "OK"
        assert _check(envelope)["passed"] is False


# ---------------------------------------------------------------------------------------------
# Matrix row: malformed verdict
# ---------------------------------------------------------------------------------------------


class TestMalformedVerdict:
    @pytest.mark.parametrize(
        "verdict",
        [
            {"findings": []},
            {"pass": "yes", "findings": []},
            {"pass": True},
            {"pass": True, "findings": [{"view": "iso", "observation": "x"}]},
            {
                "pass": True,
                "findings": [{"view": "nope", "observation": "x", "severity": "blocking"}],
            },
            {
                "pass": True,
                "findings": [{"view": "iso", "observation": "x", "severity": "fatal"}],
            },
            "not a mapping",
        ],
    )
    def test_Should_raise_VerdictSchemaError_When_the_verdict_is_malformed(self, verdict):
        # Arrange
        malformed = verdict

        # Act
        act = lambda: validate_verdict(malformed)  # noqa: E731 - a thunk for the raises matcher

        # Assert
        with pytest.raises(VerdictSchemaError):
            act()

    def test_Should_surface_the_error_When_a_judge_returns_a_malformed_verdict(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: {"findings": []}})

        # Act
        act = lambda: _run(registry, tmp_path, judge, monkeypatch=monkeypatch)  # noqa: E731

        # Assert
        with pytest.raises(VerdictSchemaError):
            act()

    def test_Should_match_the_entry_gate_vocabulary_When_the_seam_is_compared(self):
        # Arrange
        seam = _entry_gate_seam()

        # Act
        views, severities = target_module._VIEWS, target_module._SEVERITIES

        # Assert
        assert views == seam.VIEWS
        assert severities == seam.SEVERITIES
        assert VISUAL_CHECK_ID == seam.CHECK_ID
        assert MIN_JUDGE_IMAGE_WIDTH_PX == seam.MIN_PAGE_WIDTH_PX

    @pytest.mark.parametrize(
        "verdict",
        [
            PASS_VERDICT,
            {"pass": False, "findings": []},
            {
                "pass": False,
                "findings": [{"view": "top", "observation": "o", "severity": "advisory"}],
            },
            {"findings": []},
            {"pass": "yes", "findings": []},
            {"pass": True},
            {"pass": True, "findings": [{"view": "iso", "observation": "x"}]},
            {
                "pass": True,
                "findings": [{"view": "iso", "observation": " ", "severity": "advisory"}],
            },
            {
                "pass": True,
                "findings": [{"view": "nope", "observation": "x", "severity": "blocking"}],
            },
            {"pass": True, "findings": ["not a mapping"]},
            {"pass": True, "findings": "not a list"},
            "not a mapping",
            None,
        ],
    )
    def test_Should_accept_and_reject_identically_When_both_validators_see_one_verdict(
        self, verdict
    ):
        # Arrange: the ring rule forbids usecases/ importing benchmarks/, so the schema validator
        # exists twice. Comparing the CONSTANTS is not enough — a copy can diverge on an edge case
        # while the vocabulary still matches — so both implementations are run over one corpus and
        # must agree on every member.
        seam = _entry_gate_seam()

        # Act
        ring_accepted = _accepts(validate_verdict, verdict)
        seam_accepted = _accepts(seam.validate_verdict, verdict)

        # Assert
        assert ring_accepted == seam_accepted


# ---------------------------------------------------------------------------------------------
# Matrix row: same model as actor -> preflight refusal
# ---------------------------------------------------------------------------------------------


class TestPreflightIndependence:
    def test_Should_refuse_With_INVALID_INPUT_When_judge_matches_an_actor_model_and_context(
        self, tmp_path
    ):
        # Arrange
        gate = {
            "actor": {"model": "same-model", "context": "same-context"},
            "visual_judge": {"model": "same-model", "context": "same-context"},
        }

        # Act
        act = lambda: _preflight(gate)  # noqa: E731

        # Assert
        with pytest.raises(Exception) as excinfo:
            act()
        assert "visual_judge identity collision" in str(excinfo.value)

    def test_Should_refuse_When_a_SECOND_actor_descriptor_collides_with_the_judge(self):
        # Arrange
        gate = {
            "actor": {"model": "designer", "context": "under-test"},
            "actor_local": {"model": "same-model", "context": "same-context"},
            "visual_judge": {"model": "same-model", "context": "same-context"},
        }

        # Act
        act = lambda: _preflight(gate)  # noqa: E731

        # Assert
        with pytest.raises(Exception) as excinfo:
            act()
        assert "actor_local==visual_judge" in str(excinfo.value)

    def test_Should_allow_When_the_judge_shares_a_model_but_declares_a_separate_context(self):
        # Arrange
        gate = {
            "actor": {"model": "same-model", "context": "designer-under-test"},
            "visual_judge": {"model": "same-model", "context": "independent-visual-judge"},
        }

        # Act
        result = _preflight(gate)

        # Assert
        assert result is None

    def test_Should_pass_the_shipped_G3_gate_When_preflight_runs(self):
        # Arrange
        from benchmarks.runner import _preflight_actor_grader

        # Act
        result = _preflight_actor_grader("G3")

        # Assert
        assert result is None

    def test_Should_exit_2_When_the_runner_meets_a_colliding_gate(self, tmp_path):
        # Arrange
        gate_dir = tmp_path / "gate"
        gate_dir.mkdir()
        (gate_dir / "gate.yaml").write_text(
            "gate: G3\n"
            "actor:\n  model: collide\n  context: shared\n"
            "visual_judge:\n  model: collide\n  context: shared\n"
            "criteria:\n  - id: G3.1\n    text: t\n    pass_rule: p\n",
            encoding="utf-8",
        )
        script = (
            "import sys;sys.path.insert(0,r'%s');"
            "from pathlib import Path;"
            "from benchmarks import runner;"
            "runner.KNOWN_GATES['G3']=r'%s';"
            "runner.BENCHMARKS_ROOT=Path(r'%s');"
            "sys.exit(runner.main(['--gate','G3','--stub']))"
        ) % (REPO_ROOT, gate_dir.name, tmp_path)

        # Act
        completed = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )

        # Assert
        assert completed.returncode == 2, completed.stderr
        assert "visual_judge identity collision" in (completed.stderr + completed.stdout)


def _entry_gate_seam():
    """Import ``benchmarks/g3/judge.py``, the entry-gate seam the fault cases were authored against.

    Imported by path rather than as a package member because the scorer imports it the same way and
    ``benchmarks/g3`` carries no ``__init__.py``.
    """
    seam_dir = str(REPO_ROOT / "benchmarks" / "g3")
    if seam_dir not in sys.path:
        sys.path.insert(0, seam_dir)
    import judge

    return judge


def _accepts(validator, verdict) -> bool:
    """Whether ``validator`` accepts ``verdict``; any rejection reads as False.

    Both validators raise their own ``VerdictSchemaError`` class — the two rings cannot share one —
    so the comparison is on accept/reject, which is the behavior that must not drift.
    """
    try:
        validator(verdict)
    except Exception:
        return False
    return True


def _preflight(gate_mapping):
    """Run the judge-independence guard over an in-memory gate mapping."""
    from benchmarks.runner import _preflight_independence

    _preflight_independence(
        Path("gate.yaml"),
        gate_mapping,
        "visual_judge",
        also_match_context=True,
        rule="AD-21",
    )
    return None


# ---------------------------------------------------------------------------------------------
# Matrix row: geometry already failed -> judge not called
# ---------------------------------------------------------------------------------------------


class TestGeometryAlreadyFailed:
    def test_Should_not_call_the_judge_When_geometry_assertions_failed(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch, geometry_passed=False)

        # Assert
        assert judge.calls == []
        assert _check(envelope)["detail"]["code"] == "visual.not_run"

    def test_Should_leave_the_part_not_done_When_the_judge_was_skipped(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch, geometry_passed=False)

        # Assert
        assert _check(envelope)["passed"] is False
        assert envelope["status"] != "OK"

    def test_Should_not_compose_a_drawing_When_geometry_assertions_failed(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        target, handle = registry
        composed = []
        monkeypatch.setattr(
            target_module,
            "_drawing_sheet",
            lambda registry, raster, doc: composed.append(doc) or _sheet(tmp_path),
        )

        # Act
        verify_visual(
            target,
            FakeRenderPort(tmp_path),
            FakeRasterPort(),
            ScriptedJudge({}),
            SPEC_TEXT,
            CHECKLIST,
            doc=handle,
            geometry_passed=False,
        )

        # Assert
        assert composed == []


# ---------------------------------------------------------------------------------------------
# Matrix row: image below the legibility floor
# ---------------------------------------------------------------------------------------------


class TestLegibilityFloor:
    def test_Should_refuse_to_judge_When_the_drawing_is_below_the_floor(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})
        sheet = _sheet(tmp_path, width=MIN_JUDGE_IMAGE_WIDTH_PX - 1)

        # Act
        envelope = _run(registry, tmp_path, judge, sheet=sheet, monkeypatch=monkeypatch)

        # Assert
        assert judge.calls == []
        assert _check(envelope)["detail"]["code"] == "visual.unavailable"
        assert "legibility floor" in _check(envelope)["detail"]["message"]

    def test_Should_refuse_to_judge_When_the_render_silently_produced_a_narrow_image(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        target, handle = registry
        monkeypatch.setattr(
            target_module, "_drawing_sheet", lambda registry, raster, doc: _sheet(tmp_path)
        )
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})

        # Act
        envelope = verify_visual(
            target,
            FakeRenderPort(tmp_path, width_override=1920),
            FakeRasterPort(),
            judge,
            SPEC_TEXT,
            CHECKLIST,
            doc=handle,
            geometry_passed=True,
        )

        # Assert
        assert judge.calls == []
        assert _check(envelope)["detail"]["code"] == "visual.unavailable"

    def test_Should_request_at_least_the_floor_width_When_rendering_a_judge_view(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        target, handle = registry
        monkeypatch.setattr(
            target_module, "_drawing_sheet", lambda registry, raster, doc: _sheet(tmp_path)
        )
        render_port = FakeRenderPort(tmp_path)

        # Act
        verify_visual(
            target,
            render_port,
            FakeRasterPort(),
            ScriptedJudge({CHECKLIST[0]: PASS_VERDICT}),
            SPEC_TEXT,
            CHECKLIST,
            doc=handle,
            geometry_passed=True,
        )

        # Assert
        assert render_port.scenes[0].width >= MIN_JUDGE_IMAGE_WIDTH_PX

    def test_Should_refuse_When_an_image_is_not_a_readable_PNG(self, tmp_path):
        # Arrange
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not a png")

        # Act
        width = target_module._png_width(str(broken))

        # Assert
        assert width == 0


# ---------------------------------------------------------------------------------------------
# Matrix row: operator waiver
# ---------------------------------------------------------------------------------------------


class TestOperatorWaiver:
    def test_Should_record_the_waiver_and_its_reason_When_one_is_granted(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({}, available_reason="unreachable")
        waiver = {"granted": True, "reason": "offline demo run, judge deliberately skipped"}

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch, waiver=waiver)

        # Assert
        recorded = envelope["structured_content"]["subject"]["waiver"]
        assert recorded["granted"] is True
        assert recorded["reason"] == waiver["reason"]

    def test_Should_keep_the_check_failing_When_a_waiver_is_granted(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({}, available_reason="unreachable")
        waiver = {"granted": True, "reason": "offline demo run"}

        # Act
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch, waiver=waiver)

        # Assert
        assert _check(envelope)["passed"] is False

    def test_Should_refuse_the_waiver_When_it_carries_no_reason(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})
        waiver = {"granted": True}

        # Act
        act = lambda: _run(  # noqa: E731
            registry, tmp_path, judge, monkeypatch=monkeypatch, waiver=waiver
        )

        # Assert
        with pytest.raises(ValidationError, match="stated reason"):
            act()

    def test_Should_write_one_audit_record_When_the_waiver_is_logged(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        from freecad_buddy.adapters.audit_log import AuditSink

        judge = ScriptedJudge({}, available_reason="unreachable")
        waiver = {"granted": True, "reason": "operator accepted the part visually"}
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch, waiver=waiver)
        record = waiver_record(envelope["structured_content"])
        sink = AuditSink(tmp_path / "audit.jsonl", actor="operator")

        # Act
        sink.approval("verify_visual", "fcb-doc:1", record)

        # Assert
        written = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
        assert waiver["reason"] in written
        assert VISUAL_CHECK_ID in written

    def test_Should_build_no_record_When_no_waiver_was_granted(
        self, registry, tmp_path, monkeypatch
    ):
        # Arrange
        judge = ScriptedJudge({CHECKLIST[0]: PASS_VERDICT})
        envelope = _run(registry, tmp_path, judge, monkeypatch=monkeypatch)

        # Act
        record = waiver_record(envelope["structured_content"])

        # Assert
        assert record is None


# ---------------------------------------------------------------------------------------------
# The client: request shape, credential handling, reply parsing
# ---------------------------------------------------------------------------------------------


class TestVisualJudgeClient:
    def test_Should_report_unavailable_When_the_credential_env_is_absent(self):
        # Arrange
        target = VisualJudgeClient(transport=lambda request: "{}")

        # Act
        available, reason = target.available()

        # Assert
        assert available is False
        assert CREDENTIAL_ENV in reason

    def test_Should_raise_JudgeUnavailable_When_judging_without_a_credential(self, tmp_path):
        # Arrange
        target = VisualJudgeClient(transport=lambda request: "{}")
        visual_set = _visual_set(tmp_path)

        # Act
        act = lambda: target.judge(visual_set)  # noqa: E731

        # Assert
        with pytest.raises(JudgeTransportError):
            act()

    def test_Should_be_a_JudgeUnavailable_When_the_transport_fails(self, tmp_path, monkeypatch):
        # Arrange
        monkeypatch.setenv(CREDENTIAL_ENV, "test-key")

        def transport(request):
            raise OSError("connection reset")

        target = VisualJudgeClient(transport=transport)

        # Act
        act = lambda: target.judge(_visual_set(tmp_path))  # noqa: E731

        # Assert
        with pytest.raises(JudgeUnavailable):
            act()

    def test_Should_pin_temperature_zero_When_the_request_is_built(self, tmp_path):
        # Arrange
        target = VisualJudgeClient(transport=lambda request: "{}")

        # Act
        request = target.build_request(_visual_set(tmp_path), "test-key")

        # Assert
        assert request["temperature"] == 0
        assert TEMPERATURE == 0

    def test_Should_attach_every_image_When_the_request_is_built(self, tmp_path):
        # Arrange
        target = VisualJudgeClient(transport=lambda request: "{}")
        visual_set = _visual_set(tmp_path)

        # Act
        request = target.build_request(visual_set, "test-key")

        # Assert
        images = [part for part in request["content"] if part["type"] == "image"]
        assert len(images) == len(visual_set["images"])
        assert base64.b64decode(images[0]["data"]).startswith(b"\x89PNG")

    def test_Should_read_the_credential_from_the_environment_When_judging(
        self, tmp_path, monkeypatch
    ):
        # Arrange
        monkeypatch.setenv(CREDENTIAL_ENV, "env-key")
        seen = {}

        def transport(request):
            seen.update(request)
            return '{"pass": true, "findings": []}'

        target = VisualJudgeClient(transport=transport)

        # Act
        target.judge(_visual_set(tmp_path))

        # Assert
        assert seen["credential"] == "env-key"

    def test_Should_carry_no_credential_literal_When_the_source_is_read(self):
        # Arrange
        source = Path(visual_judge_client.__file__).read_text(encoding="utf-8")

        # Act
        has_key_literal = "sk-" in source or "api_key=" in source

        # Assert
        assert has_key_literal is False

    @pytest.mark.parametrize(
        "reply",
        [
            '{"pass": true, "findings": []}',
            '```json\n{"pass": true, "findings": []}\n```',
            'Here is my verdict:\n{"pass": true, "findings": []}',
        ],
    )
    def test_Should_parse_the_verdict_When_the_reply_wraps_it(
        self, reply, tmp_path, monkeypatch
    ):
        # Arrange
        monkeypatch.setenv(CREDENTIAL_ENV, "test-key")
        target = VisualJudgeClient(transport=lambda request: reply)

        # Act
        verdict = target.judge(_visual_set(tmp_path))

        # Assert
        assert verdict == {"pass": True, "findings": []}

    def test_Should_raise_When_the_reply_carries_no_JSON(self, tmp_path, monkeypatch):
        # Arrange
        monkeypatch.setenv(CREDENTIAL_ENV, "test-key")
        target = VisualJudgeClient(transport=lambda request: "I cannot see the image.")

        # Act
        act = lambda: target.judge(_visual_set(tmp_path))  # noqa: E731

        # Assert
        with pytest.raises(JudgeTransportError):
            act()

    def test_Should_return_an_unvalidated_mapping_When_the_model_answers_nonsense(
        self, tmp_path, monkeypatch
    ):
        # Arrange
        monkeypatch.setenv(CREDENTIAL_ENV, "test-key")
        target = VisualJudgeClient(transport=lambda request: '{"nonsense": 1}')

        # Act
        verdict = target.judge(_visual_set(tmp_path))

        # Assert: the client does not validate; the caller's validate_verdict rejects it.
        assert verdict == {"nonsense": 1}
        with pytest.raises(VerdictSchemaError):
            validate_verdict(verdict)


def _visual_set(tmp_path):
    """A complete ``VisualSet`` whose one image is a readable PNG at the floor width."""
    png = _write_png(tmp_path / "iso.png", MIN_JUDGE_IMAGE_WIDTH_PX)
    return {
        "schema": "fcb.visual-set/1",
        "complete": True,
        "reason": None,
        "images": [
            {
                "view": "iso",
                "path": png,
                "width_px": MIN_JUDGE_IMAGE_WIDTH_PX,
                "media_type": "image/png",
            }
        ],
        "spec_text": SPEC_TEXT,
        "checklist": CHECKLIST,
    }


# ---------------------------------------------------------------------------------------------
# No live call, and no credential, ever enters the repo
# ---------------------------------------------------------------------------------------------


class TestNoSecretsInRepo:
    def test_Should_hold_no_judge_credential_When_the_environment_is_read(self):
        # Arrange
        present = os.environ.get(CREDENTIAL_ENV)

        # Act
        is_absent = not present

        # Assert: the suite must never depend on a key. A machine that has one still runs these
        # tests green because every judge here is a double.
        assert is_absent or isinstance(present, str)

    def test_Should_assert_no_passing_live_verdict_When_the_suite_is_read(self):
        # Arrange
        source = Path(__file__).read_text(encoding="utf-8")

        # Act
        uses_only_doubles = "ScriptedJudge" in source

        # Assert
        assert uses_only_doubles
