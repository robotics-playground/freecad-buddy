"""Framing read tests: the exact projection test (no FreeCAD).

Covers every story 8.2 I/O matrix row against a scripted fake view. The fake's
``getPointOnViewport`` returns whatever the test maps each world corner to, so containment,
the ``short``-wrap discard rule, the hull ratio and every no-verdict state are driven exactly
rather than inferred from a real camera. AD-30 binds the measured object set to the render's own
``is_default_renderable``, so one test changes only ``Visibility`` and watches the verdict move.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from freecad_buddy.usecases import framing, screenshot
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.screenshot import is_default_renderable

# ---- fakes -----------------------------------------------------------------------------------


class _FakeBoundBox:
    def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
        self.XMin, self.YMin, self.ZMin = xmin, ymin, zmin
        self.XMax, self.YMax, self.ZMax = xmax, ymax, zmax


class _FakeShape:
    def __init__(self, bbox=None):
        self.BoundBox = bbox if bbox is not None else _FakeBoundBox(0, 0, 0, 10, 10, 10)

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False


class _FakeObject:
    """An App object carrying only what the predicate and the union read."""

    def __init__(self, name, shape=None, visibility=True, type_id="Part::Feature"):
        self.Name = name
        self.TypeId = type_id
        self.Visibility = visibility
        if shape is not None:
            self.Shape = shape


class _FakeDocument:
    def __init__(self, objects, name="Part"):
        self.Name = name
        self._objects = list(objects)

    @property
    def Objects(self):  # noqa: N802 - FreeCAD API name
        return list(self._objects)


class _FakeRegistry:
    """Minimal ``with_document`` stand-in that binds a handle to a fixed document."""

    def __init__(self, document, handle="fcb-doc:fake"):
        self._document = document
        self._handle = handle

    def with_document(self, doc, fn):
        if doc != self._handle:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(self._handle, self._document)


class _FakeView:
    """A live 3D view whose projection and size are scripted per test.

    ``points`` maps a world ``(x, y, z)`` corner to the viewport coordinate it projects to; a
    corner absent from the map falls back to ``default``. Setting ``raises`` makes the named
    method throw, which is how the projection-failure rows are driven.
    """

    def __init__(self, size=(800, 600), points=None, default=(400.0, 300.0), raises=None):
        self._size = size
        self._points = points or {}
        self._default = default
        self._raises = raises
        self.projected_corners = []

    def getSize(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "getSize":
            raise RuntimeError("view widget is gone")
        return self._size

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        if self._raises == "getPointOnViewport":
            raise RuntimeError("no render manager")
        self.projected_corners.append((x, y, z))
        return self._points.get((x, y, z), self._default)


class _FakeViewportPort:
    """A ``ViewportPort`` whose availability and view handle are scripted."""

    def __init__(self, view, available=True, reason=None):
        self._view = view
        self._available = available
        self._reason = reason
        self.asked_documents = []

    def available(self, document):
        self.asked_documents.append(document)
        return (self._available, self._reason)

    def view(self, document):
        return self._view


def _box_object(name, bounds, **kwargs):
    return _FakeObject(name, shape=_FakeShape(_FakeBoundBox(*bounds)), **kwargs)


def _corner_map(bounds, coordinate):
    """Map every corner of ``bounds`` to one viewport ``coordinate``."""
    return {corner: coordinate for corner in framing.corners(bounds)}


def _read(document, view, available=True):
    port = _FakeViewportPort(view, available=available)
    return framing.read_framing(_FakeRegistry(document), port, "fcb-doc:fake")


# ---- union_bbox (pure) -----------------------------------------------------------------------


def test_should_fold_two_boxes_into_their_union_when_both_are_readable():
    # Arrange
    objects = [
        _box_object("A", (0, 0, 0, 10, 10, 10)),
        _box_object("B", (-5, 2, 1, 4, 20, 3)),
    ]

    # Act
    result = framing.union_bbox(objects)

    # Assert
    assert result == (-5.0, 0.0, 0.0, 10.0, 20.0, 10.0)


def test_should_return_none_when_no_object_carries_a_readable_box():
    # Arrange
    objects = [_FakeObject("NoShape")]

    # Act
    result = framing.union_bbox(objects)

    # Assert
    assert result is None


def test_should_skip_a_non_finite_box_rather_than_poison_the_union():
    # Arrange
    objects = [
        _box_object("Bad", (float("nan"), 0, 0, 1, 1, 1)),
        _box_object("Good", (0, 0, 0, 10, 10, 10)),
    ]

    # Act
    result = framing.union_bbox(objects)

    # Assert
    assert result == (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)


def test_should_emit_eight_distinct_corners_when_the_box_is_non_degenerate():
    # Arrange
    box = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)

    # Act
    result = framing.corners(box)

    # Assert
    assert len(result) == 8
    assert len(set(result)) == 8
    assert (0.0, 1.0, 2.0) in result
    assert (3.0, 4.0, 5.0) in result


# ---- containment + ratio (pure) ---------------------------------------------------------------


def test_should_report_fits_when_every_corner_is_within_the_rectangle():
    # Arrange
    projected = [(100.0, 100.0), (700.0, 500.0)]

    # Act
    fits, kept, discarded = framing.containment(projected, (800, 600))

    # Assert
    assert fits is True
    assert kept == projected
    assert discarded == 0


def test_should_treat_a_corner_exactly_on_the_boundary_as_inside():
    # Arrange
    projected = [(0.0, 0.0), (800.0, 600.0)]

    # Act
    fits, _kept, discarded = framing.containment(projected, (800, 600))

    # Assert
    assert fits is True
    assert discarded == 0


def test_should_report_not_fits_when_one_corner_is_one_pixel_outside():
    # Arrange
    projected = [(100.0, 100.0), (801.0, 300.0)]

    # Act
    fits, kept, discarded = framing.containment(projected, (800, 600))

    # Assert
    assert fits is False
    assert discarded == 0
    assert (801.0, 300.0) in kept


def test_should_discard_a_coordinate_beyond_four_times_the_viewport_dimension():
    # Arrange: 3201 exceeds 4 x 800; 3200 exactly does not.
    projected = [(3200.0, 100.0), (3201.0, 100.0)]

    # Act
    fits, kept, discarded = framing.containment(projected, (800, 600))

    # Assert
    assert fits is False
    assert discarded == 1
    assert kept == [(3200.0, 100.0)]


def test_should_discard_a_sign_wrapped_negative_coordinate():
    # Arrange: the short() cast wraps a distant corner to a large negative value.
    projected = [(-32000.0, 100.0)]

    # Act
    fits, kept, discarded = framing.containment(projected, (800, 600))

    # Assert
    assert fits is False
    assert kept == []
    assert discarded == 1


def test_should_compute_the_ratio_from_the_binding_axis_when_nothing_was_discarded():
    # Arrange: x spans 400/800 = 0.5, y spans 450/600 = 0.75; y binds.
    kept = [(200.0, 75.0), (600.0, 525.0)]

    # Act
    result = framing.hull_ratio(kept, 0, (800, 600))

    # Assert
    assert result == pytest.approx(0.75)


def test_should_return_a_ratio_above_one_when_the_hull_overflows_the_viewport():
    # Arrange
    kept = [(-400.0, 100.0), (1200.0, 200.0)]

    # Act
    result = framing.hull_ratio(kept, 0, (800, 600))

    # Assert
    assert result == pytest.approx(2.0)


def test_should_return_no_ratio_when_any_coordinate_was_discarded():
    # Arrange
    kept = [(200.0, 75.0), (600.0, 525.0)]

    # Act
    result = framing.hull_ratio(kept, 1, (800, 600))

    # Assert
    assert result is None


# ---- read_framing: the verdict ---------------------------------------------------------------


def test_should_report_fits_true_and_computed_when_the_model_is_fully_inside():
    # Arrange
    bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    document = _FakeDocument([_box_object("Box", bounds)])
    view = _FakeView(size=(800, 600), points=_corner_map(bounds, (400.0, 300.0)))

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is True
    assert verdict["checked"] == "computed"
    assert verdict["stale_reason"] is None
    assert verdict["ratio"] < 1.0


def test_should_report_fits_false_and_a_ratio_above_one_when_one_corner_overflows():
    # Arrange
    bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    all_corners = framing.corners(bounds)
    points = dict.fromkeys(all_corners, (100.0, 300.0))
    points[all_corners[-1]] = (1700.0, 300.0)
    document = _FakeDocument([_box_object("Box", bounds)])
    view = _FakeView(size=(800, 600), points=points)

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is False
    assert verdict["checked"] == "computed"
    assert verdict["ratio"] == pytest.approx(2.0)


def test_should_report_no_ratio_when_a_corner_wrapped_past_four_times_the_viewport():
    # Arrange
    bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    all_corners = framing.corners(bounds)
    points = dict.fromkeys(all_corners, (400.0, 300.0))
    points[all_corners[0]] = (-32000.0, 300.0)
    document = _FakeDocument([_box_object("Box", bounds)])
    view = _FakeView(size=(800, 600), points=points)

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is False
    assert verdict["ratio"] is None
    assert verdict["checked"] == "computed"


def test_should_report_unavailable_when_every_corner_is_implausible():
    # Arrange
    bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    document = _FakeDocument([_box_object("Box", bounds)])
    view = _FakeView(size=(800, 600), points=_corner_map(bounds, (-32000.0, -32000.0)))

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"
    assert "implausible" in verdict["stale_reason"]


def test_should_report_unavailable_naming_the_failure_when_the_projection_raises():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    view = _FakeView(raises="getPointOnViewport")

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"
    assert "projection failed" in verdict["stale_reason"]
    assert "RuntimeError" in verdict["stale_reason"]


def test_should_report_unavailable_naming_the_failure_when_get_size_raises():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    view = _FakeView(raises="getSize")

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"
    assert "viewport size unreadable" in verdict["stale_reason"]


def test_should_report_unavailable_rather_than_divide_when_the_viewport_has_a_zero_dimension():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    view = _FakeView(size=(800, 0))

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"
    assert "zero" in verdict["stale_reason"]


def test_should_report_unavailable_and_never_fits_true_when_the_document_is_empty():
    # Arrange
    document = _FakeDocument([])
    view = _FakeView()

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"
    assert "no visible shape-bearing objects" in verdict["stale_reason"]


def test_should_report_unavailable_when_every_object_is_hidden():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10), visibility=False)])
    view = _FakeView()

    # Act
    verdict = _read(document, view)

    # Assert
    assert verdict["fits"] is None
    assert verdict["checked"] == "unavailable"


# ---- read_framing: the omitted-block states ---------------------------------------------------


def test_should_return_none_when_no_viewport_port_is_injected():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    registry = _FakeRegistry(document)

    # Act
    verdict = framing.read_framing(registry, None, "fcb-doc:fake")

    # Assert
    assert verdict is None


def test_should_return_none_when_the_port_reports_the_document_unavailable():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    view = _FakeView()

    # Act
    verdict = _read(document, view, available=False)

    # Assert
    assert verdict is None


def test_should_return_none_when_the_port_reports_available_but_hands_back_no_view():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    port = _FakeViewportPort(None, available=True)

    # Act
    verdict = framing.read_framing(_FakeRegistry(document), port, "fcb-doc:fake")

    # Assert
    assert verdict is None


def test_should_ask_the_port_about_the_resolved_document_the_call_targeted():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))], name="Target")
    port = _FakeViewportPort(_FakeView())

    # Act
    framing.read_framing(_FakeRegistry(document), port, "fcb-doc:fake")

    # Assert
    assert port.asked_documents == [document]


def test_should_raise_validation_error_when_the_handle_is_unknown():
    # Arrange
    document = _FakeDocument([_box_object("Box", (0, 0, 0, 10, 10, 10))])
    port = _FakeViewportPort(_FakeView())

    # Act
    act = lambda: framing.read_framing(_FakeRegistry(document), port, "fcb-doc:stale")  # noqa: E731

    # Assert
    with pytest.raises(ValidationError):
        act()


# ---- AD-30: the measured set is the render's own predicate ------------------------------------


def test_should_drop_an_object_from_the_union_when_only_its_visibility_changes():
    """Render and framing warning must describe one scene, so the predicate is shared.

    Only ``Visibility`` differs between the two reads. The hidden object's box would move the
    union (and with it the corner the view projects), so a re-derived filter that ignored
    ``Visibility`` would leave both verdicts identical.
    """
    # Arrange
    visible_bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    wide_bounds = (0.0, 0.0, 0.0, 1000.0, 10.0, 10.0)
    far = _box_object("Far", wide_bounds, visibility=True)
    near = _box_object("Near", visible_bounds)
    # Corners of the visible-only union project inside; the wider union's far corner does not.
    points = dict.fromkeys(framing.corners(visible_bounds), (400.0, 300.0))
    points.update(dict.fromkeys(framing.corners(wide_bounds), (400.0, 300.0)))
    points[(1000.0, 10.0, 10.0)] = (5000.0, 300.0)
    view_with = _FakeView(size=(800, 600), points=points)
    view_without = _FakeView(size=(800, 600), points=points)

    # Act
    with_far = _read(_FakeDocument([near, far]), view_with)
    far.Visibility = False
    without_far = _read(_FakeDocument([near, far]), view_without)

    # Assert
    assert with_far["fits"] is False
    assert without_far["fits"] is True
    assert (1000.0, 10.0, 10.0) in view_with.projected_corners
    assert (1000.0, 10.0, 10.0) not in view_without.projected_corners


@pytest.mark.parametrize(
    "type_id",
    ["PartDesign::Body", "Sketcher::SketchObject", "App::Origin", "App::Plane"],
)
def test_should_exclude_the_render_predicates_non_renderable_types_from_the_union(type_id):
    # Arrange
    obj = _box_object("Excluded", (0, 0, 0, 10, 10, 10), type_id=type_id)

    # Act
    result = framing.union_bbox([o for o in [obj] if is_default_renderable(o)])

    # Assert
    assert result is None


def test_should_measure_exactly_the_render_predicates_set_by_importing_it_not_redefining_it():
    """The module must call the render's predicate object, not carry an equivalent copy.

    Identity, not a source grep: ``framing.is_default_renderable`` must be the very function
    ``screenshot`` exports, so a re-derived filter with the same behavior today still fails.
    """
    # Act
    bound = framing.is_default_renderable

    # Assert
    assert bound is screenshot.is_default_renderable
    assert "is_default_renderable" in screenshot.__all__


# ---- AD-30: no DPI correction, no Gui import --------------------------------------------------


def test_should_call_no_device_pixel_ratio_or_to_q_point_method():
    """No DPI divide: ``getSize()`` and the projection share one render-manager pixel space."""
    # Arrange
    tree = ast.parse(inspect.getsource(framing))
    banned = {"devicePixelRatio", "toQPoint", "devicePixelRatioF"}

    # Act
    called = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in banned
    }

    # Assert
    assert called == set()


def test_should_import_no_gui_qt_or_pivy_module():
    # Arrange
    tree = ast.parse(inspect.getsource(framing))
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


def test_should_report_the_same_verdict_on_a_hidpi_viewport_as_on_its_logical_twin():
    # Arrange: the same projected coordinates against a 2x viewport must not be DPI-corrected.
    bounds = (0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    document = _FakeDocument([_box_object("Box", bounds)])
    points = _corner_map(bounds, (900.0, 300.0))
    logical = _FakeView(size=(800, 600), points=points)
    hidpi = _FakeView(size=(1600, 1200), points=points)

    # Act
    logical_verdict = _read(document, logical)
    hidpi_verdict = _read(document, hidpi)

    # Assert
    assert logical_verdict["fits"] is False
    assert hidpi_verdict["fits"] is True
