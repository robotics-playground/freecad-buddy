"""``view_fit_viewport`` tests: the live-camera fit and its audit line (no FreeCAD).

Covers every story 8.3 I/O matrix row against a scripted fake view and a recording audit sink.
The fake view records each ``fitAll`` call, so "no fit occurred" is asserted on the recording
rather than inferred from the envelope, and the sink keeps whole records, so ``camera_before``
can be checked to be present **and** absent from ``params_digest`` at the same time.
"""

from __future__ import annotations

import ast
import inspect
import json
import math

import pytest

from freecad_buddy.adapters.audit_log import AuditSink, _digest
from freecad_buddy.usecases import view_fit
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.view_fit import view_fit_viewport

HANDLE = "fcb-doc:fake"
CAMERA = "#Inventor V2.1 ascii\nOrthographicCamera { position 0 0 87 height 52 }\n"

# ---- fakes -----------------------------------------------------------------------------------


class _FakeDocument:
    def __init__(self, name="Part"):
        self.Name = name


class _FakeGuiDocument:
    """The ``View3DInventor.Document`` hop: a Gui document wrapping its App document."""

    def __init__(self, document):
        self.Document = document


class _FakeView:
    """A live 3D view whose camera string and ``fitAll`` outcome are scripted per test.

    ``fit_calls`` counts the fits that actually reached the view, which is how the wrong-document
    and unavailable rows prove no camera moved.
    """

    def __init__(self, document=None, camera=CAMERA, raises=None):
        self._camera = camera
        self._raises = raises
        self.fit_calls = 0
        if document is not None:
            self.Document = _FakeGuiDocument(document)

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "getCamera":
            raise RuntimeError("no camera node on this view")
        return self._camera

    def fitAll(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "fitAll":
            raise RuntimeError("the scene graph is empty")
        self.fit_calls += 1


class _FakeViewportPort:
    def __init__(self, view, available=True, reason=None):
        self._view = view
        self._available = available
        self._reason = reason

    def available(self, document):  # noqa: ARG002 - the fake answers the same for any document
        return (self._available, self._reason)

    def view(self, document):  # noqa: ARG002 - the fake holds one view
        return self._view


class _FakeRegistry:
    """Minimal ``with_document`` stand-in that binds one handle to one document."""

    def __init__(self, document, handle=HANDLE):
        self._document = document
        self._handle = handle

    def with_document(self, doc, fn):
        if not doc:
            raise ValidationError("missing required 'doc' handle")
        if doc != self._handle:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(self._handle, self._document)


class _RecordingSink:
    """An audit sink keeping whole records, so a field's presence and absence are both checkable."""

    def __init__(self):
        self.records = []

    def camera(self, tool, doc, params, camera_before):
        self.records.append(
            {
                "tool": tool,
                "doc": doc,
                "params": dict(params),
                "camera_before": camera_before,
            }
        )


@pytest.fixture(autouse=True)
def _no_host_sink():
    """Keep a host-installed sink from leaking between tests; every test passes its own."""
    previous = view_fit.set_audit_sink(None)
    yield
    view_fit.set_audit_sink(previous)


# ---- successful fit --------------------------------------------------------------------------


def test_should_fit_the_view_and_audit_the_prior_camera_when_the_document_has_a_live_view():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document)
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert view.fit_calls == 1
    assert sink.records[0]["camera_before"] == CAMERA
    assert sink.records[0]["tool"] == "view_fit_viewport"
    assert sink.records[0]["doc"] == HANDLE


def test_should_write_through_the_host_installed_sink_when_the_caller_passes_none():
    # Arrange
    document = _FakeDocument("Part")
    sink = _RecordingSink()
    view_fit.set_audit_sink(sink)

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(_FakeView(document)), HANDLE)

    # Assert
    assert sink.records[0]["camera_before"] == CAMERA


def test_should_not_abort_the_fit_when_the_audit_sink_cannot_write():
    # Arrange
    class _BrokenSink:
        def camera(self, *_args):
            raise OSError("no space left on device")

    document = _FakeDocument("Part")
    view = _FakeView(document)

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(document), _FakeViewportPort(view), HANDLE, _BrokenSink()
    )

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1


# ---- the camera never enters the digest ------------------------------------------------------


def test_should_keep_the_camera_out_of_params_digest_when_the_real_sink_writes_the_record(tmp_path):
    """AD-31: ``camera_before`` rides its own field, never the irreversible argument digest.

    Checked against the real ``AuditSink`` rather than a fake, because the field placement that
    keeps the camera out of the digest is the sink's own, and the digest of the tool arguments
    alone is what an auditor joins this line to the dispatch bracket's lines with.
    """
    # Arrange
    path = tmp_path / "audit.jsonl"
    document = _FakeDocument("Part")
    params = {"doc": HANDLE}

    # Act
    view_fit_viewport(
        _FakeRegistry(document),
        _FakeViewportPort(_FakeView(document)),
        HANDLE,
        AuditSink(path, actor="test"),
    )
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    # Assert
    assert record["camera_before"] == CAMERA
    assert record["params_digest"] == _digest(params)
    assert CAMERA not in json.dumps({k: v for k, v in record.items() if k != "camera_before"})


# ---- wrong document --------------------------------------------------------------------------


def test_should_refuse_naming_both_documents_when_the_viewport_shows_another_document():
    # Arrange
    target = _FakeDocument("DocA")
    view = _FakeView(_FakeDocument("DocB"))
    sink = _RecordingSink()

    # Act
    def act():
        return view_fit_viewport(_FakeRegistry(target), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    with pytest.raises(ValidationError) as caught:
        act()
    message = str(caught.value)
    assert "DocA" in message
    assert "DocB" in message
    assert view.fit_calls == 0
    assert sink.records == []


def test_should_fit_when_the_view_reports_no_document_of_its_own():
    """An unreadable view document is not evidence of a mismatch, so it must not refuse.

    The port already resolved the view through ``getDocument(<Name>)``, so the view belongs to the
    targeted document; refusing on a missing attribute would make the tool unusable against any
    build whose view does not expose one.
    """
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document=None)

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1


# ---- handle errors ---------------------------------------------------------------------------


def test_should_raise_naming_the_handle_when_the_handle_is_unknown():
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))
    port = _FakeViewportPort(_FakeView())

    # Act
    def act():
        return view_fit_viewport(registry, port, "fcb-doc:stale")

    # Assert
    with pytest.raises(ValidationError, match="fcb-doc:stale"):
        act()


def test_should_raise_when_the_handle_is_missing():
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))
    port = _FakeViewportPort(_FakeView())

    # Act
    def act():
        return view_fit_viewport(registry, port)

    # Assert
    with pytest.raises(ValidationError, match="doc"):
        act()


def test_should_resolve_the_handle_before_the_port_when_the_host_has_no_viewport():
    """A stale handle on a headless host is still INVALID_INPUT, not "no viewport"."""
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))

    # Act
    def act():
        return view_fit_viewport(registry, None, "fcb-doc:stale")

    # Assert
    with pytest.raises(ValidationError, match="fcb-doc:stale"):
        act()


# ---- no viewport -----------------------------------------------------------------------------


def test_should_degrade_honestly_when_no_viewport_port_is_injected():
    # Arrange
    document = _FakeDocument("Part")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), None, HANDLE, sink)

    # Assert
    assert envelope["status"] != "OK"
    assert envelope["structured_content"]["fitted"] is False
    assert "no live viewport" in envelope["detail"]["message"]
    assert sink.records == []


def test_should_name_the_missing_view_when_the_port_reports_unavailable():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document)
    port = _FakeViewportPort(view, available=False, reason="document 'Part' has no open 3D view")

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), port, HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert "no open 3D view" in envelope["detail"]["message"]
    assert view.fit_calls == 0


def test_should_degrade_honestly_when_the_port_reports_available_but_hands_back_no_view():
    # Arrange
    document = _FakeDocument("Part")

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(None), HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert "Part" in envelope["detail"]["message"]


# ---- degraded camera and fit -----------------------------------------------------------------


def test_should_fit_and_omit_the_camera_when_getcamera_is_unavailable():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="getCamera")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1
    assert sink.records[0]["camera_before"] is None
    assert envelope["structured_content"]["camera_recorded"] is False


def test_should_omit_the_camera_field_entirely_when_the_camera_was_unreadable(tmp_path):
    """An unreadable camera omits the field rather than persisting a fabricated null string."""
    # Arrange
    path = tmp_path / "audit.jsonl"
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="getCamera")

    # Act
    view_fit_viewport(
        _FakeRegistry(document), _FakeViewportPort(view), HANDLE, AuditSink(path, actor="test")
    )
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    # Assert
    assert "camera_before" not in record


def test_should_report_a_non_ok_status_naming_the_failure_when_fitall_raises():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="fitAll")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] != "OK"
    assert "RuntimeError" in envelope["detail"]["message"]
    assert view.fit_calls == 0
    assert sink.records == []


def test_should_ignore_a_camera_that_is_not_a_string():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, camera=object())
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert sink.records[0]["camera_before"] is None


# ---- AD-31: Gui-free, gate-free --------------------------------------------------------------


def test_should_import_no_gui_qt_or_pivy_module():
    """The view arrives as an opaque object from the port; ``usecases/`` stays Gui-free."""
    # Arrange
    tree = ast.parse(inspect.getsource(view_fit))
    banned = {"FreeCADGui", "PySide", "PySide2", "PySide6", "PyQt5", "PyQt6", "pivy"}

    # Act
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    # Assert
    assert imported & banned == set()


def test_should_name_neither_preview_id_nor_run_mutation():
    """The camera move must not route through the confirm gate or the mutation bracket.

    Both would demand a ``preview_id`` for an operation that has no geometry to preview, which is
    exactly the failure AD-31 spells the tool's own literal spec out to avoid.
    """
    # Arrange
    source = inspect.getsource(view_fit)
    banned = ("preview_id", "run_mutation", "gate_mutation")

    # Act
    present = [name for name in banned if name in source]

    # Assert
    assert present == []


# ---- the calibrated fit margin ------------------------------------------------------------------


class _FactorRecordingView:
    """A view whose ``fitAll`` accepts the optional factor, as the real ``View3DInventor`` does."""

    def __init__(self, document):
        self.Document = _FakeGuiDocument(document)
        self.factors = []

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        return CAMERA

    def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
        self.factors.append(factor)




def test_should_fall_back_to_the_bare_call_for_a_view_whose_fitAll_takes_no_factor():
    """The view is duck-typed, so an older or stubbed one may accept no argument. At factor 1.0
    the two calls frame identically, so the fallback loses nothing."""
    # Arrange
    document = _FakeDocument()
    view = _FakeView(document)  # its fitAll takes no argument at all
    registry = _FakeRegistry(document)

    # Act
    envelope = view_fit_viewport(registry, _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1


# ---- silhouette framing ----------------------------------------------------------------------


class _FakeShape:
    def __init__(self, bounds):
        self.BoundBox = _FakeBoundBox(bounds)

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False


class _FakeBoundBox:
    def __init__(self, bounds):
        (self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax) = bounds


class _FakeObject:
    """A visible shape-bearing object, the set ``is_default_renderable`` selects."""

    def __init__(self, name, bounds):
        self.Name = name
        self.TypeId = "Part::Feature"
        self.Visibility = True
        self.Shape = _FakeShape(bounds)


class _ProjectingDocument:
    def __init__(self, objects, name="Part"):
        self.Name = name
        self.Objects = objects


class _ProjectingView(_FakeView):
    """A view that projects world corners through a caller-supplied function.

    ``boxZoom`` calls are recorded verbatim so the rectangle handed to FreeCAD can be asserted
    rather than inferred from a camera the fake does not really own.
    """

    def __init__(self, project, size=(800, 600), document=None):
        super().__init__(document=document)
        self._project = project
        self._size = size
        self.box_zooms = []
        self.isometric_calls = 0

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return self._size

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        return self._project(x, y, z)

    def boxZoom(self, xmin, ymin, xmax, ymax):  # noqa: N802 - FreeCAD API name
        self.box_zooms.append((xmin, ymin, xmax, ymax))

    def viewIsometric(self):  # noqa: N802 - FreeCAD API name
        self.isometric_calls += 1


def _centred_box(half_w, half_h, size=(800, 600)):
    """Project every corner onto a centred rectangle of the given half-extents."""
    cx, cy = size[0] / 2, size[1] / 2

    def project(x, y, _z):
        return (cx + (half_w if x > 0 else -half_w), cy + (half_h if y > 0 else -half_h))

    return project





def test_should_reorient_to_isometric_when_the_model_is_edge_on():
    # Arrange: a silhouette filling 2% of the viewport — a tall bar seen down its own axis.
    view = _ProjectingView(_centred_box(8, 6))
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.isometric_calls == 1


def test_should_orient_isometrically_on_every_fit():
    # Arrange: the isometric corner view shows all three dimensions, which is what a fit is for.
    # A top view down a tall bar shows only its end face however well it is zoomed.
    view = _ProjectingView(_centred_box(200, 100))
    document = _ProjectingDocument([_FakeObject("Pad", (-10, -10, -10, 10, 10, 10))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.isometric_calls == 1


def test_should_fall_back_to_fit_all_when_every_corner_is_implausible():
    # Arrange: corners far beyond the viewport wrap through short() and carry no usable value.
    view = _ProjectingView(lambda _x, _y, _z: (99999.0, 99999.0))
    document = _ProjectingDocument([_FakeObject("Pad", (-10, -10, -10, 10, 10, 10))])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.box_zooms == []
    assert view.fit_calls >= 1


def test_should_still_fit_when_the_camera_starts_pointed_away_from_the_model():
    # Arrange: the live failure this guards. A camera not looking at the model projects every
    # corner to an implausible magnitude, so the silhouette cannot be measured. fitAll must still
    # run, or the one call an agent makes to recover a lost model does nothing.
    view = _ProjectingView(lambda _x, _y, _z: (99999.0, 99999.0))
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls >= 1, "an unmeasurable silhouette must not leave the camera untouched"




# ---- geometry-computed framing ---------------------------------------------------------------


class _FactorView(_FakeView):
    """A view recording the ``fitAll`` factor it was handed."""

    def __init__(self, document=None):
        super().__init__(document=document)
        self.factors = []
        self.isometric_calls = 0

    def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
        self.factors.append(factor)
        self.fit_calls += 1

    def viewIsometric(self):  # noqa: N802 - FreeCAD API name
        self.isometric_calls += 1


def _resulting_fill(bounds, factor):
    """What fraction of the viewport the model occupies after ``fitAll(factor)``.

    ``fitAll`` frames the scene box's space diagonal, so the model lands at
    ``silhouette / (diagonal * factor)``. This mirrors the shipped arithmetic rather than
    re-deriving it, so the assertions below are about the *result* the human sees.
    """
    dx, dy, dz = bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2]
    diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)
    silhouette = max(
        math.sqrt(dx * dx + dy * dy),
        math.sqrt(dy * dy + dz * dz),
        math.sqrt(dx * dx + dz * dz),
    )
    return silhouette / (diagonal * factor)


@pytest.mark.parametrize(
    "bounds",
    [
        (-20, -20, 0, 20, 20, 800),  # 20:1 bar — the shape fitAll alone frames at 5%
        (-20, -20, -20, 20, 20, 20),  # cube
        (0, 0, 0, 40, 25, 15),  # plate
    ],
)
def test_should_fill_the_viewport_to_the_configured_fraction_whatever_the_aspect(bounds):
    # Arrange
    view = _FactorView()
    document = _ProjectingDocument([_FakeObject("Part", bounds)])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert _resulting_fill(bounds, view.factors[-1]) == pytest.approx(
        view_fit._FILL_FRACTION, abs=0.001
    )


def test_should_not_read_the_camera_back_while_it_holds_the_qt_thread():
    # Arrange: the fit runs on the Qt main thread inside the marshal, so viewIsometric's
    # NavigationAnimation and viewBoundBox's own animation cannot land until the call returns.
    # A projection taken here would read the PRE-fit camera, which is how a measure-then-correct
    # loop converged on the wrong framing and still reported success. The framing must therefore
    # come from geometry alone.
    view = _FactorView()
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.fit_calls == 1, "one deterministic camera write, no correction passes"
    assert not hasattr(view, "projections"), "the fit must not project through the live camera"


def test_should_fall_back_to_a_plain_fit_when_the_geometry_cannot_be_measured():
    # Arrange: an unreadable document still gets framed rather than refused.
    view = _FactorView()

    class _Opaque:
        Name = "Part"

    # Act
    view_fit_viewport(_FakeRegistry(_Opaque()), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors == [1.0]


def test_should_never_pass_a_factor_viewall_would_refuse():
    # Arrange: viewAll returns early for factor <= 0 (View3DInventorViewer.cpp:4463), so a
    # degenerate box must not silently skip the fit.
    view = _FactorView()
    document = _ProjectingDocument([_FakeObject("Flat", (0, 0, 0, 0, 0, 0))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors[-1] > 0.0


class _AnimationView(_FactorView):
    """A view recording the order of animation toggles and camera writes."""

    def __init__(self, animation_enabled=True):
        super().__init__()
        self._animation_enabled = animation_enabled
        self.events = []

    def isAnimationEnabled(self):  # noqa: N802 - FreeCAD API name
        return self._animation_enabled

    def setAnimationEnabled(self, enabled):  # noqa: N802 - FreeCAD API name
        self._animation_enabled = enabled
        self.events.append(f"animation={enabled}")

    def viewIsometric(self):  # noqa: N802 - FreeCAD API name
        super().viewIsometric()
        self.events.append("isometric")

    def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
        super().fitAll(factor)
        self.events.append("fitAll")


def test_should_write_the_camera_with_animation_off_so_the_fit_lands_in_this_call():
    # Arrange: both camera writes animate by default, and an animation advances on the Qt event
    # loop this code blocks while it runs inside the marshal. Animated, the fit would land only
    # after the call returned — the defect that made a single call frame the model wrongly.
    view = _AnimationView(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.events == ["animation=False", "isometric", "fitAll", "animation=True"]


def test_should_restore_the_humans_animation_setting_when_the_fit_raises():
    # Arrange: this is the human's viewer; a failed fit must not leave animation switched off.
    class _Raising(_AnimationView):
        def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
            raise RuntimeError("the scene graph is empty")

    view = _Raising(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert view.isAnimationEnabled() is True


def test_should_leave_animation_off_when_the_human_already_had_it_off():
    # Arrange
    view = _AnimationView(animation_enabled=False)
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.isAnimationEnabled() is False


def test_should_still_fit_a_view_that_has_no_animation_toggle():
    # Arrange: the toggle is a nicety; a view without it still gets framed.
    view = _FactorView()
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1
