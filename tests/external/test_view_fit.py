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
from freecad_buddy.usecases import framing, view_fit
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.view_fit import view_fit_viewport

HANDLE = "fcb-doc:fake"
CAMERA = "#Inventor V2.1 ascii\nOrthographicCamera { position 0 0 87 height 52 }\n"

# The fraction of the viewport `_FakeView` projects the model onto. It equals the fit's own target,
# so the correction factor comes out 1.0 and these rows measure the behaviour they name rather than
# the zoom arithmetic, which the simulator section covers.
_FILLED = view_fit._FILL_FRACTION

# ---- fakes -----------------------------------------------------------------------------------


class _FakeBoundBox:
    def __init__(self, bounds):
        (self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax) = bounds


class _FakeShape:
    def __init__(self, bounds):
        self.BoundBox = _FakeBoundBox(bounds)

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False


class _FakeObject:
    """A visible shape-bearing object, the set ``is_default_renderable`` selects."""

    def __init__(self, name, bounds):
        self.Name = name
        self.TypeId = "Part::Feature"
        self.Visibility = True
        self.Shape = _FakeShape(bounds)


class _FakeDocument:
    """A document carrying one measurable object, so the post-fit verdict has something to grade."""

    def __init__(self, name="Part", bounds=(-10, -10, -10, 10, 10, 10)):
        self.Name = name
        self.Objects = [_FakeObject("Pad", bounds)]


class _FakeView:
    """A live 3D view whose camera string and ``fitAll`` outcome are scripted per test.

    ``fit_calls`` counts the camera moves that actually reached the view — each ``fitAll`` and each
    ``boxZoom`` — which is how the wrong-document and unavailable rows prove no camera moved.
    ``zoom_boxes`` records each ``boxZoom`` argument.

    It projects the model onto a centred rectangle already filling the target fraction of an
    800x600 viewport, so the post-fit verdict is ``fits: True`` and these rows exercise the
    behaviour they are about — the audit line, the camera field, the handle errors — rather than
    tripping over an unmeasurable view.
    """

    def __init__(self, camera=CAMERA, raises=None):
        self._camera = camera
        self._raises = raises
        self.fit_calls = 0
        self.zoom_boxes = []

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "getCamera":
            raise RuntimeError("no camera node on this view")
        return self._camera

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return (800, 600)

    def getPointOnViewport(self, x, y, _z):  # noqa: N802 - FreeCAD API name
        half_width, half_height = 800 * _FILLED / 2, 600 * _FILLED / 2
        return (
            400.0 + (half_width if x > 0 else -half_width),
            300.0 + (half_height if y > 0 else -half_height),
        )

    def fitAll(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "fitAll":
            raise RuntimeError("the scene graph is empty")
        self.fit_calls += 1

    def boxZoom(self, xmin, ymin, xmax, ymax):  # noqa: N802 - FreeCAD API name
        self.zoom_boxes.append((xmin, ymin, xmax, ymax))
        self.fit_calls += 1


class _FakeViewportPort:
    """One view plus the session-wide on-screen name the wrong-document guard reads.

    ``showing`` defaults to ``None`` — "the on-screen name could not be read" — so every row that
    is not about the guard proceeds without naming a document, which is the shipped behaviour for
    a host that cannot read it.
    """

    def __init__(self, view, available=True, reason=None, showing=None):
        self._view = view
        self._available = available
        self._reason = reason
        self._showing = showing

    def available(self, document):  # noqa: ARG002 - the fake answers the same for any document
        return (self._available, self._reason)

    def view(self, document):  # noqa: ARG002 - the fake holds one view
        return self._view

    def showing_document_name(self):
        return self._showing


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
    view = _FakeView()
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert view.fit_calls == 2, "one known-state fit, then one correction pass"
    assert sink.records[0]["camera_before"] == CAMERA
    assert sink.records[0]["tool"] == "view_fit_viewport"
    assert sink.records[0]["doc"] == HANDLE


def test_should_write_through_the_host_installed_sink_when_the_caller_passes_none():
    # Arrange
    document = _FakeDocument("Part")
    sink = _RecordingSink()
    view_fit.set_audit_sink(sink)

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(_FakeView()), HANDLE)

    # Assert
    assert sink.records[0]["camera_before"] == CAMERA


def test_should_not_abort_the_fit_when_the_audit_sink_cannot_write():
    # Arrange
    class _BrokenSink:
        def camera(self, *_args):
            raise OSError("no space left on device")

    document = _FakeDocument("Part")
    view = _FakeView()

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(document), _FakeViewportPort(view), HANDLE, _BrokenSink()
    )

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2, "one known-state fit, then one correction pass"


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
        _FakeViewportPort(_FakeView()),
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
    """R2-02's reproduction: DocB is on screen and the fit targets DocA.

    The port's on-screen name is session-wide, so it disagrees with the target even though the
    view was resolved from the target's own handle. The shipped guard compared the target against
    a view resolved from that same target, which is a name against itself, and let this through
    with ``fitted: true`` after rewriting DocB's camera.
    """
    # Arrange
    target = _FakeDocument("DocA")
    view = _FakeView()
    sink = _RecordingSink()
    port = _FakeViewportPort(view, showing="DocB")

    # Act
    def act():
        return view_fit_viewport(_FakeRegistry(target), port, HANDLE, sink)

    # Assert
    with pytest.raises(ValidationError) as caught:
        act()
    message = str(caught.value)
    assert "DocA" in message
    assert "DocB" in message
    assert view.fit_calls == 0
    assert sink.records == []


def test_should_fit_when_the_viewport_is_showing_the_targeted_document():
    # Arrange
    document = _FakeDocument("DocA")
    view = _FakeView()
    port = _FakeViewportPort(view, showing="DocA")

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), port, HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2, "one known-state fit, then one correction pass"


def test_should_fit_when_the_on_screen_document_name_cannot_be_read():
    """An unreadable on-screen name is not evidence of a mismatch, so it must not refuse.

    ``showing_document_name`` returns ``None`` for a host with no viewport and for a focused
    sub-window that is not a 3D view alike, with no reason string. Refusing on it would make the
    tool unusable wherever the name cannot be read.
    """
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView()
    port = _FakeViewportPort(view, showing=None)

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), port, HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2, "one known-state fit, then one correction pass"
    assert "reason" not in envelope["structured_content"]


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
    view = _FakeView()
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
    view = _FakeView(raises="getCamera")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2, "one known-state fit, then one correction pass"
    assert sink.records[0]["camera_before"] is None
    assert envelope["structured_content"]["camera_recorded"] is False


def test_should_omit_the_camera_field_entirely_when_the_camera_was_unreadable(tmp_path):
    """An unreadable camera omits the field rather than persisting a fabricated null string."""
    # Arrange
    path = tmp_path / "audit.jsonl"
    document = _FakeDocument("Part")
    view = _FakeView(raises="getCamera")

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
    view = _FakeView(raises="fitAll")
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
    view = _FakeView(camera=object())
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


# ---- measured framing --------------------------------------------------------------------------


class _ProjectingDocument:
    def __init__(self, objects, name="Part"):
        self.Name = name
        self.Objects = objects


class _ProjectingView(_FakeView):
    """A view that projects world corners through a caller-supplied function.

    The projection may be swapped per pass: ``project`` is re-read on every corner, so a test can
    hand a different function to passes 1 and 3 and make the two measurements distinguishable.
    ``factors`` records the ``fitAll`` argument of each call; ``zoom_boxes`` (inherited) records
    each ``boxZoom``. The projection ignores both, so a test controls exactly what each pass reads.
    """

    def __init__(self, project, size=(800, 600)):
        super().__init__()
        self.project = project
        self._size = size
        self.factors = []
        self.isometric_calls = 0

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return self._size

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        return self.project(x, y, z)

    def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
        self.factors.append(factor)
        self.fit_calls += 1

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


def test_should_fall_back_to_a_plain_fit_when_every_corner_is_implausible():
    # Arrange: corners far beyond the viewport wrap through short() and carry no usable value, so
    # no correction factor can be derived. The plain fitAll(1.0) must still run — a lost model has
    # to be recoverable by the one call an agent makes.
    view = _ProjectingView(lambda _x, _y, _z: (99999.0, 99999.0))
    document = _ProjectingDocument([_FakeObject("Pad", (-10, -10, -10, 10, 10, 10))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors == [1.0], "no measurable ratio means no correction pass, but still a fit"


def test_should_still_fit_when_the_camera_starts_pointed_away_from_the_model():
    # Arrange: the live failure this guards. A camera not looking at the model projects every
    # corner to an implausible magnitude, so the extent cannot be measured. fitAll must still run,
    # or the one call an agent makes to recover a lost model does nothing.
    view = _ProjectingView(lambda _x, _y, _z: (99999.0, 99999.0))
    document = _ProjectingDocument([_FakeObject("Bar", (-20, -20, 0, 20, 20, 800))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.fit_calls >= 1, "an unmeasurable extent must not leave the camera untouched"


def test_should_report_the_honest_failure_when_pass_three_cannot_measure_the_model():
    # Arrange: the fit ran and the model is still not demonstrably framed. AD-31 makes
    # `fitted: true` a measurement, so an unverifiable fit is a failure, not a silent success.
    # Every corner is implausible, so nothing was measured — the code names that, not an overflow.
    view = _ProjectingView(lambda _x, _y, _z: (99999.0, 99999.0))
    document = _ProjectingDocument([_FakeObject("Pad", (-10, -10, -10, 10, 10, 10))])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "SPEC_FAILED"
    assert envelope["structured_content"]["fitted"] is False
    assert envelope["detail"]["code"] == "view_fit.unverified"




# ---- measured framing: the fit verifies its own result ----------------------------------------


class _SimulatingView(_FakeView):
    """A view that models FreeCAD's real camera moves, so the fit's own measurement can be graded.

    ``fitAll(f)`` in FreeCAD scales the **scene** box about its centre by ``f`` and frames the
    result through ``SoCamera::viewBoundingBox``, which surrounds the box with a **sphere**
    (``View3DInventorViewer.cpp:4456-4492, 4840``). The on-screen scale is therefore
    ``min(width, height) / (space_diagonal * f)`` pixels per world unit, centred on the scene box.
    The scene box is ``scene_bounds``: everything Coin draws, a datum plane included, which can be
    larger than and off-centre from the measured model.

    ``boxZoom(XMin, YMin, XMax, YMax)`` follows ``NavigationStyle.cpp:584-620``: the box is Y-down,
    its integer midpoint is normalised by ``size - 1``, the camera pans so that point becomes the
    view centre, and the camera height scales by the larger of ``size_x / width`` and
    ``size_y / height``. A 0x0 box moves nothing.

    ``getPointOnViewport`` projects through the target and scale the last move set, Y-up, so every
    pass measures the camera it follows. Before any move the scale is the ``initial_scale`` the
    test supplies, standing in for whatever camera the human left behind.
    """

    _ISO = (
        (0.7071067811865476, -0.7071067811865476, 0.0),
        (0.4082482904638631, 0.4082482904638631, -0.8164965809277261),
    )

    def __init__(self, bounds, size=(800, 600), initial_scale=1.0, scene_bounds=None):
        super().__init__()
        self._scene = scene_bounds if scene_bounds is not None else bounds
        self._size = size
        self._scale = initial_scale
        self._target = _box_centre(self._scene)
        self.factors = []
        self.isometric_calls = 0

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return self._size

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        offset = (x - self._target[0], y - self._target[1], z - self._target[2])
        screen = [sum(axis[i] * offset[i] for i in range(3)) for axis in self._ISO]
        return (
            self._size[0] / 2.0 + screen[0] * self._scale,
            self._size[1] / 2.0 + screen[1] * self._scale,
        )

    def viewIsometric(self):  # noqa: N802 - FreeCAD API name
        self.isometric_calls += 1

    def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
        self.factors.append(factor)
        self.fit_calls += 1
        dx, dy, dz = (self._scene[i + 3] - self._scene[i] for i in range(3))
        diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)
        if diagonal <= 0.0 or not factor:
            return
        self._target = _box_centre(self._scene)
        self._scale = min(self._size) / (diagonal * factor)

    def boxZoom(self, xmin, ymin, xmax, ymax):  # noqa: N802 - FreeCAD API name
        super().boxZoom(xmin, ymin, xmax, ymax)
        width, height = self._size
        size_x, size_y = xmax - xmin, ymax - ymin
        if size_x == 0 and size_y == 0:
            return
        centre_x = int((xmin + xmax) / 2) / max(width - 1, 1)
        centre_y = (height - int((ymin + ymax) / 2)) / max(height - 1, 1)
        pan_x = (centre_x - 0.5) * width / self._scale
        pan_y = (centre_y - 0.5) * height / self._scale
        self._target = tuple(
            self._target[i] + self._ISO[0][i] * pan_x + self._ISO[1][i] * pan_y for i in range(3)
        )
        self._scale /= max(size_x / width, size_y / height)


def _box_centre(bounds):
    return tuple((bounds[i] + bounds[i + 3]) / 2.0 for i in range(3))


def _hull_centre(view, bounds):
    """The centre of ``bounds``' projected hull through ``view``'s camera now, Y-up pixels."""
    projected = [view.getPointOnViewport(*corner) for corner in framing.corners(bounds)]
    xs = [x for x, _ in projected]
    ys = [y for _, y in projected]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _binding_ratio(view, bounds):
    """The ratio the framing verdict would report for ``bounds`` through ``view``'s camera now.

    Measured with the same projection the production code measures with, so this asserts the
    result the human sees rather than re-deriving a second model of it.
    """
    projected = [view.getPointOnViewport(*corner) for corner in framing.corners(bounds)]
    _fits, kept, discarded = framing.containment(projected, view.getSize())
    return framing.hull_ratio(kept, discarded, view.getSize())


def test_should_fall_back_to_the_bare_call_for_a_view_whose_fitAll_takes_no_factor():
    """The view is duck-typed, so an older or stubbed one may accept no argument.

    Both passes must still reach the view: the bare call frames the model with FreeCAD's own
    sphere margin instead of the requested one, which is worse framing but never a failed fit.
    """

    # Arrange
    class _NoFactor(_SimulatingView):
        def fitAll(self):  # noqa: N802 - FreeCAD API name; this view takes no factor at all
            super().fitAll(1.0)

    bounds = (-20, -20, -20, 20, 20, 20)
    view = _NoFactor(bounds)
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2, "the arity fallback must not swallow a pass"


def test_should_zoom_in_when_the_model_measures_as_a_sub_pixel_dot():
    """A measured ``0.0`` is a measurement, not a failure to measure.

    Treating it as unusable skipped the correction pass entirely and left the dot on screen while
    reporting ``fitted: true`` — the same contradiction this story removes, in the opposite
    direction. The floor keeps the box one ``boxZoom`` will act on.
    """
    # Arrange: every corner lands on one pixel in the middle of the viewport.
    view = _ProjectingView(lambda _x, _y, _z: (400.0, 300.0))
    document = _ProjectingDocument([_FakeObject("Dot", (-10, -10, -10, 10, 10, 10))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors == [1.0]
    assert view.zoom_boxes == [(396, 297, 404, 303)], "a zero ratio must still be zoomed, floored"


def test_should_restore_animation_when_the_previous_setting_could_not_be_read():
    """This is the human's viewer. An unreadable current setting is no reason to leave their
    navigation animation switched off after the fit."""

    # Arrange
    class _UnreadableSetting(_SimulatingView):
        def __init__(self, bounds):
            super().__init__(bounds)
            self.enabled = None

        def isAnimationEnabled(self):  # noqa: N802 - FreeCAD API name
            raise RuntimeError("the navigation style has no animation node")

        def setAnimationEnabled(self, enabled):  # noqa: N802 - FreeCAD API name
            self.enabled = enabled

    bounds = (-20, -20, -20, 20, 20, 20)
    view = _UnreadableSetting(bounds)
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.enabled is True, "the fit must not leave animation switched off"


def test_should_name_the_measurement_failure_rather_than_claim_an_overflow():
    """Nothing was measured, so "the model does not fit" would name a cause the verdict does not
    support. The unreadable document is the failure, and the block is where it is named."""
    # Arrange
    view = _ProjectingView(_centred_box(100, 80))

    class _Opaque:
        Name = "Part"

    # Act
    envelope = view_fit_viewport(_FakeRegistry(_Opaque()), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["detail"]["code"] == "view_fit.unverified"
    assert "document" in envelope["framing"]["stale_reason"]
    assert "view" not in envelope["framing"]["stale_reason"]


# ``boxZoom`` takes whole pixels, so each side of the zoom box is up to one pixel off the exact
# expanded hull. On these models' ~400-600 px boxes that moves the landed ratio by under 0.003.
_PIXEL_TOLERANCE = 0.003

_ASPECT_SWEEP = [
    pytest.param((-20, -20, -20, 20, 20, 20), id="40mm-cube"),
    pytest.param((0, 0, 0, 20, 20, 30), id="20x20x30-box"),
    pytest.param((0, 0, 0, 40, 40, 80), id="40x40x80-bar"),
    pytest.param((0, 0, 0, 40, 25, 15), id="40x25x15-plate"),
    pytest.param((-20, -20, 0, 20, 20, 800), id="40x40x800-bar"),
]


@pytest.mark.parametrize("bounds", _ASPECT_SWEEP)
def test_should_fill_the_viewport_to_the_configured_fraction_whatever_the_aspect(bounds):
    """One call, any aspect. The cube and the 20x20x30 box are the two the shipped analytic
    estimate never sampled, and the two it clipped: it underestimated the projected extent by
    1.155x and 1.132x, so the fit zoomed past the edge and still reported success."""
    # Arrange
    view = _SimulatingView(bounds)
    document = _ProjectingDocument([_FakeObject("Part", bounds)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert _binding_ratio(view, bounds) == pytest.approx(
        view_fit._FILL_FRACTION, abs=_PIXEL_TOLERANCE
    )


@pytest.mark.parametrize("bounds", _ASPECT_SWEEP)
def test_should_leave_a_stable_ratio_in_the_band_when_the_same_model_is_fitted_twice(bounds):
    """Non-convergence was the shipped symptom: two fits in a row both left the model 7.5% too
    large, because a factor derived from geometry cannot improve by repetition."""
    # Arrange
    view = _SimulatingView(bounds)
    handler = _FakeViewportPort(view)
    document = _ProjectingDocument([_FakeObject("Part", bounds)])

    # Act
    view_fit_viewport(_FakeRegistry(document), handler, doc=HANDLE)
    first_ratio = _binding_ratio(view, bounds)
    second = view_fit_viewport(_FakeRegistry(document), handler, doc=HANDLE)

    # Assert
    assert second["status"] == "OK"
    assert _binding_ratio(view, bounds) == pytest.approx(first_ratio, abs=0.001)


def test_should_converge_in_one_call_from_any_starting_camera():
    # Arrange: the pre-fit camera is not fitAll(1.0)'s camera, so a factor derived from the pre-fit
    # ratio alone would be wrong. The fit zooms to a known state before it measures.
    bounds = (-20, -20, -20, 20, 20, 20)
    view = _SimulatingView(bounds, initial_scale=0.3)
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert _binding_ratio(view, bounds) == pytest.approx(
        view_fit._FILL_FRACTION, abs=_PIXEL_TOLERANCE
    )


def test_should_measure_the_model_through_the_camera_it_wrote():
    # Arrange: the three passes. A fit that measured only before its own zoom could not tell
    # whether the zoom worked, which is the whole defect: `fitted: true` meant "the call ran".
    bounds = (-20, -20, -20, 20, 20, 20)
    view = _SimulatingView(bounds)
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors == [1.0], "pass 1 zooms to a known camera before it measures"
    assert len(view.zoom_boxes) == 1, "one centring zoom, never a retry loop"


def test_should_report_spec_failed_carrying_the_framing_block_when_the_fit_contradicts_itself():
    """AD-32's single carve-out: the verdict is freshly computed and is the *cause* of the status,
    and ``ratio`` lives nowhere else in the contract."""
    # Arrange: a view whose projection jumps outside the viewport after the correction pass.
    bounds = (-20, -20, -20, 20, 20, 20)
    view = _ProjectingView(_centred_box(100, 80))
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    def overflow_after_the_correction(x, y, _z):
        if view.zoom_boxes:
            return (900.0 if x > 0 else -100.0, 700.0 if y > 0 else -100.0)
        return _centred_box(100, 80)(x, y, _z)

    view.project = overflow_after_the_correction

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "SPEC_FAILED"
    assert envelope["structured_content"]["fitted"] is False
    assert envelope["detail"]["code"] == "view_fit.not_framed"
    assert envelope["framing"]["fits"] is False
    assert envelope["framing"]["checked"] == "computed"
    assert envelope["framing"]["ratio"] > 1.0


def test_should_keep_the_ratio_out_of_the_prose_when_the_fit_contradicts_itself():
    """The number reaches the caller through the ``framing`` block only. A hand-written copy in
    ``text`` is a second place for it to drift from the measurement."""
    # Arrange
    bounds = (-20, -20, -20, 20, 20, 20)
    def overflowing(x, y, _z):
        return (900.0 if x > 0 else -100.0, 700.0 if y > 0 else -100.0)

    view = _ProjectingView(overflowing)
    document = _ProjectingDocument([_FakeObject("Cube", bounds)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    ratio = envelope["framing"]["ratio"]
    assert str(ratio) not in envelope["text"]
    assert str(ratio) not in envelope["detail"]["message"]


def test_should_fall_back_to_a_plain_fit_when_the_geometry_cannot_be_measured():
    # Arrange: an unreadable document still gets framed rather than refused.
    view = _ProjectingView(_centred_box(100, 80))

    class _Opaque:
        Name = "Part"

    # Act
    view_fit_viewport(_FakeRegistry(_Opaque()), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.factors == [1.0]


def test_should_never_pass_a_box_boxzoom_would_ignore():
    # Arrange: boxZoom returns early for a 0x0 box (NavigationStyle.cpp:599), so a degenerate
    # measurement must not silently skip the zoom.
    view = _ProjectingView(lambda _x, _y, _z: (400.0, 300.0))
    document = _ProjectingDocument([_FakeObject("Edge", (0, 0, 0, 10, 0, 0))])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.zoom_boxes, "the zoom pass must run"
    assert all(xmax > xmin and ymax > ymin for xmin, ymin, xmax, ymax in view.zoom_boxes)


_BAR = (-20, -20, 0, 20, 20, 800)


class _AnimationView(_SimulatingView):
    """A view recording the order of animation toggles and camera writes."""

    def __init__(self, animation_enabled=True, bounds=_BAR):
        super().__init__(bounds)
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

    def boxZoom(self, xmin, ymin, xmax, ymax):  # noqa: N802 - FreeCAD API name
        super().boxZoom(xmin, ymin, xmax, ymax)
        self.events.append("boxZoom")


def test_should_write_the_camera_with_animation_off_so_the_fit_lands_in_this_call():
    # Arrange: both camera writes animate by default, and an animation advances on the Qt event
    # loop this code blocks while it runs inside the marshal. Animated, the fit would land only
    # after the call returned — and pass 3 would then re-project through the PRE-fit camera and
    # grade a fit that had not happened yet.
    view = _AnimationView(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.events == [
        "animation=False",
        "isometric",
        "fitAll",
        "boxZoom",
        "animation=True",
    ]


def test_should_refuse_the_fit_when_the_view_has_a_toggle_that_will_not_suspend_animation():
    """Suspension is a precondition, not best-effort. With animation on, pass 3 re-reads the
    pre-fit camera and restores exactly the defect this story removes — so a toggle that exists
    and fails is a refusal, and no camera is touched."""

    # Arrange
    class _Refusing(_AnimationView):
        def setAnimationEnabled(self, enabled):  # noqa: N802 - FreeCAD API name
            raise RuntimeError("the navigation style is mid-gesture")

    view = _Refusing(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "SPEC_FAILED"
    assert envelope["detail"]["code"] == "view_fit.animation"
    assert "animation" in envelope["detail"]["message"]
    assert view.fit_calls == 0, "a fit that cannot verify itself must not move the camera"


def test_should_carry_no_framing_block_when_animation_could_not_be_suspended():
    # Arrange: nothing was measured, so there is no verdict to report. The carve-out covers the
    # post-fit contradiction only.
    class _Refusing(_AnimationView):
        def setAnimationEnabled(self, enabled):  # noqa: N802 - FreeCAD API name
            raise RuntimeError("the navigation style is mid-gesture")

    view = _Refusing(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert "framing" not in envelope


def test_should_restore_the_humans_animation_setting_when_the_fit_raises():
    # Arrange: this is the human's viewer; a failed fit must not leave animation switched off.
    class _Raising(_AnimationView):
        def fitAll(self, factor=None):  # noqa: N802 - FreeCAD API name
            raise RuntimeError("the scene graph is empty")

    view = _Raising(animation_enabled=True)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert view.isAnimationEnabled() is True


def test_should_leave_animation_off_when_the_human_already_had_it_off():
    # Arrange
    view = _AnimationView(animation_enabled=False)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert view.isAnimationEnabled() is False


def test_should_still_fit_a_view_that_has_no_animation_toggle():
    # Arrange: a view with no toggle at all is animating nothing, so there is nothing to suspend
    # and the fit proceeds. Only a toggle that exists and refuses is a refusal.
    view = _SimulatingView(_BAR)
    document = _ProjectingDocument([_FakeObject("Bar", _BAR)])

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 2


# ---- F-28: what the fit measures --------------------------------------------------------------


class _TypedObject(_FakeObject):
    """A visible object of a named type, optionally a datum by derivation."""

    def __init__(self, name, bounds, type_id, base=None):
        super().__init__(name, bounds)
        self.TypeId = type_id
        self._base = base

    def isDerivedFrom(self, type_name):  # noqa: N802 - FreeCAD API name
        return type_name == self._base


class _FakeMeshObject:
    """A ``Mesh::Feature``: no ``Shape`` at all, its geometry is the ``Mesh`` property."""

    def __init__(self, name, bounds):
        self.Name = name
        self.TypeId = "Mesh::Feature"
        self.Visibility = True
        self.Mesh = _FakeShape(bounds)
        self.Mesh.CountFacets = 12


_SKETCH = (0, 0, 0, 40, 25, 0)
_INFINITE_PLANE = (-1e100, -1e100, 0, 1e100, 1e100, 0)


def test_should_fit_a_sketch_when_it_is_the_only_visible_object():
    # Arrange
    view = _SimulatingView(_SKETCH)
    sketch = _TypedObject("Sketch", _SKETCH, "Sketcher::SketchObject")

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(_ProjectingDocument([sketch])), _FakeViewportPort(view), doc=HANDLE
    )

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert 0.0 < _binding_ratio(view, _SKETCH) <= 1.0


def test_should_fit_a_mesh_when_it_is_the_only_object():
    # Arrange
    bounds = (-5, -5, -5, 5, 5, 5)
    view = _SimulatingView(bounds)
    mesh = _FakeMeshObject("Mesh", bounds)

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(_ProjectingDocument([mesh])), _FakeViewportPort(view), doc=HANDLE
    )

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert 0.0 < _binding_ratio(view, bounds) <= 1.0


# The S4 pad and the Coin scene box FreeCAD drew around it in UAT run 2026-10-05-01: the drawn
# datum plane widens the scene box to the left and below, so its centre is far from the pad's.
_S4_PAD = (0, 0, 0, 20, 30, 10)
_S4_SCENE = (-30.2, -30.2, 0, 30.2, 35.2, 10)


def test_should_frame_the_pad_alone_when_a_datum_plane_shares_the_body():
    # Arrange: the plane's ±1e100 box once shrank the pad to a dot and the fit reported OK beside
    # a ratio of 0.0.
    pad_bounds = (0, 0, 0, 10, 10, 5)
    view = _SimulatingView(pad_bounds)
    document = _ProjectingDocument(
        [
            _TypedObject("Pad", pad_bounds, "PartDesign::Pad"),
            _TypedObject("DatumPlane", _INFINITE_PLANE, "PartDesign::Plane", base="Part::Datum"),
        ]
    )

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert _binding_ratio(view, pad_bounds) == pytest.approx(
        view_fit._FILL_FRACTION, abs=_PIXEL_TOLERANCE
    )


def test_should_centre_the_pad_when_the_drawn_scene_box_is_larger_and_off_centre():
    """``fitAll`` centres on the scene box, which includes the drawn datum plane; the measurement
    grades only the pad. Zooming about the scene centre to 95 % left the pad off-centre and over
    the edge, and the fit returned ``SPEC_FAILED view_fit.not_framed``."""
    # Arrange
    view = _SimulatingView(_S4_PAD, scene_bounds=_S4_SCENE)
    document = _ProjectingDocument(
        [
            _TypedObject("Pad", _S4_PAD, "PartDesign::Pad"),
            _TypedObject("DatumPlane", _INFINITE_PLANE, "PartDesign::Plane", base="Part::Datum"),
        ]
    )

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), doc=HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert 0.0 < _binding_ratio(view, _S4_PAD) <= 1.0
    # boxZoom normalises the box's integer midpoint by ``size - 1``, about a pixel off before the
    # zoom magnifies it; 1 % of the view is that error with margin. The scene-box fit missed by
    # ~180 px.
    centre_x, centre_y = _hull_centre(view, _S4_PAD)
    assert centre_x == pytest.approx(400.0, abs=8.0)
    assert centre_y == pytest.approx(300.0, abs=6.0)


def test_should_refuse_before_any_camera_move_when_the_model_has_zero_size_on_every_axis():
    # Arrange: a visible sketch holding one point projects to one pixel; fitting it reported OK
    # beside a ratio of 0.0.
    view = _AnimationView(animation_enabled=True, bounds=(5, 5, 0, 5, 5, 0))
    point = _TypedObject("Sketch", (5, 5, 0, 5, 5, 0), "Sketcher::SketchObject")

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(_ProjectingDocument([point])), _FakeViewportPort(view), doc=HANDLE
    )

    # Assert
    assert envelope["status"] == "SPEC_FAILED"
    assert envelope["detail"]["code"] == "view_fit.nothing_to_frame"
    assert "framing" not in envelope
    assert view.events == [], "no animation toggle, no reorientation, no fit"


def test_should_refuse_before_any_camera_move_when_only_a_datum_plane_is_visible():
    # Arrange
    view = _AnimationView(animation_enabled=True, bounds=_INFINITE_PLANE)
    plane = _TypedObject("DatumPlane", _INFINITE_PLANE, "PartDesign::Plane", base="Part::Datum")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(_ProjectingDocument([plane])), _FakeViewportPort(view), HANDLE, sink
    )

    # Assert
    assert envelope["status"] == "SPEC_FAILED"
    assert envelope["detail"]["code"] == "view_fit.nothing_to_frame"
    assert envelope["detail"]["message"] == (
        "no visible object to frame; datum planes are infinite and are not measured"
    )
    assert "framing" not in envelope
    assert view.events == [], "no animation toggle, no reorientation, no fit"
    assert sink.records == [], "no camera moved, so there is no camera move to audit"
