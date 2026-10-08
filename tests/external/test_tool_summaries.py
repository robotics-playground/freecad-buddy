"""Pure unit tests for per-tool summary builders (no FreeCAD required)."""

import pytest

from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import summarize_document_list
from freecad_buddy.usecases.exports import summarize_export
from freecad_buddy.usecases.preview import summarize_preview
from freecad_buddy.usecases.queries import (
    _json_safe,
    summarize_dependencies,
    summarize_mass_properties,
    summarize_placement,
    summarize_sketch_info,
    summarize_tree,
)
from freecad_buddy.usecases.screenshot import summarize_screenshot
from freecad_buddy.usecases.verify import summarize_recompute, summarize_shape


def test_should_report_objects_and_shown_when_the_tree_fits():
    # Arrange
    sc = {"doc": "fcb-doc:D", "total_objects": 5, "shown": 3, "truncated": False}

    # Act
    out = summarize_tree(sc)

    # Assert
    assert out == "5 objects, 3 shown."


def test_should_say_truncated_when_the_cap_cut_the_tree():
    # Arrange
    sc = {"doc": "fcb-doc:D", "total_objects": 900, "shown": 200, "truncated": True}

    # Act
    out = summarize_tree(sc)

    # Assert
    assert out == "900 objects, 200 shown, truncated."


def test_should_count_the_matches_when_filters_revealed_them():
    # Arrange
    sc = {"doc": "fcb-doc:D", "total_objects": 184, "shown": 59, "truncated": False, "matches": 51}

    # Act
    out = summarize_tree(sc)

    # Assert
    assert out == "184 objects, 59 shown, 51 matches."


def test_should_name_every_error_when_objects_in_the_start_subtree_failed():
    # Arrange
    sc = {"doc": "fcb-doc:D", "total_objects": 9, "shown": 2, "truncated": False}
    errors = ["Pad: Invalid", "Sketch: Broken link in: Support"]

    # Act
    out = summarize_tree(sc, errors)

    # Assert
    assert out == "9 objects, 2 shown. Errors: Pad: Invalid; Sketch: Broken link in: Support"


def test_summarize_mass_properties_headlines_volume():
    sc = {
        "name": "Body",
        "solid": True,
        "volume": {"value": 8642.85, "unit": "mm^3"},
        "counts": {"faces": 15, "edges": 39, "solids": 1},
    }
    out = summarize_mass_properties(sc)
    assert "8642.85" in out and "mm^3" in out
    assert "15 faces" in out


def test_summarize_mass_properties_non_solid():
    sc = {
        "name": "Shell",
        "solid": False,
        "volume": None,
        "counts": {"faces": 4, "edges": 8, "solids": 0},
    }
    out = summarize_mass_properties(sc)
    assert "non-solid" in out
    assert "n/a" in out
    assert "4 faces" in out


def test_summarize_screenshot_renders_count():
    sc = {
        "render": {
            "available": True,
            "dirty_document": False,
            "resource_link": "/tmp/x.png",
            "reason": None,
        },
        "scene": {"rendered_objects": ["Body", "Pad", "Fillet"], "focused_on": None},
    }
    out = summarize_screenshot(sc)
    assert "3" in out
    assert "Rendered" in out
    assert "dirty" not in out.lower()


def test_summarize_screenshot_dirty_document():
    sc = {
        "render": {
            "available": True,
            "dirty_document": True,
            "resource_link": "/tmp/x.png",
            "reason": None,
        },
        "scene": {"rendered_objects": ["Body"], "focused_on": None},
    }
    out = summarize_screenshot(sc)
    assert "dirty" in out.lower() or "dirty" in out


def test_summarize_screenshot_unavailable():
    sc = {
        "render": {"available": False, "reason": "no GUI"},
        "scene": {"rendered_objects": [], "focused_on": None},
    }
    out = summarize_screenshot(sc)
    assert "unavailable" in out.lower() or "Render" in out
    assert "no GUI" in out


def test_summarize_recompute_clean():
    report = {
        "schema": "fcb.validation-report/1",
        "verdict": "OK",
        "subject": {"failing_objects": []},
        "checks": [
            {
                "id": "recompute.clean",
                "measured": 0,
                "expected": 0,
                "passed": True,
                "detail": {"message": "no object left in an error state"},
            }
        ],
        "banner": {"freecad_version": "1.0", "element_map_version": 1},
    }
    out = summarize_recompute(report)
    assert "clean" in out.lower() or "OK" in out or "0" in out


def test_summarize_recompute_with_failures():
    report = {
        "schema": "fcb.validation-report/1",
        "verdict": "RECOMPUTE_ERROR",
        "subject": {"failing_objects": ["Pad", "Fillet"]},
        "checks": [
            {
                "id": "recompute.object",
                "measured": "Invalid",
                "expected": None,
                "passed": False,
                "detail": {
                    "code": "recompute.error",
                    "message": "Pad: Invalid",
                    "objects": ["Pad"],
                },
            },
            {
                "id": "recompute.object",
                "measured": "Error",
                "expected": None,
                "passed": False,
                "detail": {
                    "code": "recompute.error",
                    "message": "Fillet: Error",
                    "objects": ["Fillet"],
                },
            },
        ],
        "banner": {"freecad_version": "1.0", "element_map_version": 1},
    }
    out = summarize_recompute(report)
    assert "Pad" in out or "Fillet" in out
    assert "2" in out or "fail" in out.lower() or "error" in out.lower()


def test_summarize_shape_ok():
    report = {
        "schema": "fcb.validation-report/1",
        "verdict": "OK",
        "subject": {"object": "Body"},
        "checks": [
            {
                "id": "shape.volume",
                "measured": 1000.0,
                "expected": 1000.0,
                "passed": True,
                "detail": {"message": "ok"},
            },
            {
                "id": "shape.valid",
                "measured": True,
                "expected": True,
                "passed": True,
                "detail": {"message": "ok"},
            },
        ],
        "banner": {"freecad_version": "1.0", "element_map_version": 1},
    }
    out = summarize_shape(report)
    assert "Body" in out or "OK" in out or "pass" in out.lower()


def test_summarize_shape_fail():
    report = {
        "schema": "fcb.validation-report/1",
        "verdict": "SHAPE_MISMATCH",
        "subject": {"object": "Pocket"},
        "checks": [
            {
                "id": "shape.volume",
                "measured": 500.0,
                "expected": 1000.0,
                "passed": False,
                "detail": {"message": "|500.0 - 1000.0| = 500.0 <= 10.0"},
                "tolerance": {"rel": 0.01},
            }
        ],
        "banner": {"freecad_version": "1.0", "element_map_version": 1},
    }
    out = summarize_shape(report)
    assert "Pocket" in out or "shape.volume" in out
    assert "fail" in out.lower() or "SHAPE_MISMATCH" in out or "500" in out


# --- Task 6: documents, exports, sketch, placement, dependencies ---


def test_summarize_document_list_counts_docs():
    sc = {"documents": [{"label": "a"}, {"label": "b"}]}
    assert "2" in summarize_document_list(sc)


def test_summarize_document_list_empty():
    sc = {"documents": []}
    out = summarize_document_list(sc)
    assert "0" in out


def test_summarize_document_list_names_docs():
    sc = {"documents": [{"label": "Part1"}, {"label": "Assembly"}]}
    out = summarize_document_list(sc)
    assert "Part1" in out and "Assembly" in out


def test_summarize_export_reports_verdict():
    sc = {"format": "STEP", "verdict": "OK", "path": "/tmp/x.step"}
    out = summarize_export(sc)
    assert "STEP" in out and "OK" in out


def test_summarize_export_missing_fields_safe():
    out = summarize_export({})
    assert isinstance(out, str) and len(out) > 0


def test_summarize_export_fail_verdict():
    sc = {"format": "STL", "verdict": "MESH_MISMATCH", "path": "/tmp/x.stl"}
    out = summarize_export(sc)
    assert "STL" in out and "MESH_MISMATCH" in out


def test_summarize_sketch_info_dof():
    sc = {
        "sketch": "Sketch",
        "geometry": [{"index": 0, "type": "LineSegment", "construction": False}],
        "constraints": [
            {"id": 1, "type": "Coincident", "name": "", "driving": True},
            {"id": 2, "type": "Distance", "name": "w", "driving": True},
        ],
    }
    out = summarize_sketch_info(sc)
    assert "Sketch" in out
    assert "1 geo" in out or "geometry" in out.lower() or "1" in out
    assert "2 constraint" in out or "2" in out


def test_summarize_sketch_info_empty():
    sc = {"sketch": "Sk", "geometry": [], "constraints": []}
    out = summarize_sketch_info(sc)
    assert "Sk" in out
    assert "0" in out


def test_summarize_placement_position():
    sc = {
        "object": "Body",
        "local": {
            "position": {
                "x": {"value": 10.0, "unit": "mm"},
                "y": {"value": 0.0, "unit": "mm"},
                "z": {"value": 5.5, "unit": "mm"},
            },
            "axis": {"x": 0.0, "y": 0.0, "z": 1.0},
            "angle": {"value": 45.0, "unit": "deg"},
        },
        "global": {
            "position": {
                "x": {"value": 10.0, "unit": "mm"},
                "y": {"value": 0.0, "unit": "mm"},
                "z": {"value": 5.5, "unit": "mm"},
            },
            "axis": {"x": 0.0, "y": 0.0, "z": 1.0},
            "angle": {"value": 45.0, "unit": "deg"},
        },
    }
    out = summarize_placement(sc)
    assert "Body" in out
    assert "10" in out or "mm" in out


def test_summarize_dependencies_edge_count():
    sc = {"edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]}
    out = summarize_dependencies(sc)
    assert "2" in out


def test_summarize_dependencies_single_object():
    sc = {"object": "Pad", "in_list": ["Sketch"], "out_list": []}
    out = summarize_dependencies(sc)
    assert "Pad" in out


def test_summarize_dependencies_truncated():
    sc = {
        "edges": [{"from": "A", "to": "B"}],
        "total_edges": 5,
        "returned_edges": 1,
        "truncated": True,
    }
    out = summarize_dependencies(sc)
    assert out == "1 dependency edge(s) (truncated from 5)."


@pytest.fixture
def two_decimals(monkeypatch):
    monkeypatch.setattr(shim, "display_decimals", lambda: 2)


def test_should_print_displayed_numbers_when_the_placement_carries_noise(two_decimals):
    # Arrange
    sc = {
        "object": "Pad",
        "local": {
            "position": {
                "x": {"value": 5.999999998, "unit": "mm"},
                "y": {"value": -4.281973375071899e-16, "unit": "mm"},
                "z": {"value": 1234.5678, "unit": "mm"},
            },
            "angle": {"value": 45.0000001, "unit": "deg"},
        },
    }

    # Act
    out = summarize_placement(sc)

    # Assert
    assert out == "Pad at (6.0, 0.0, 1234.57) mm, rotated 45.0 deg."


def test_should_print_the_displayed_volume_when_mass_properties_carry_noise(two_decimals):
    # Arrange
    sc = {
        "name": "Body",
        "solid": True,
        "volume": {"value": 5999.999999998, "unit": "mm^3"},
        "counts": {"faces": 6, "edges": 12},
    }

    # Act
    out = summarize_mass_properties(sc)

    # Assert
    assert out == "Body: volume 6000.0 mm^3 (solid), 6 faces, 12 edges."


@pytest.mark.parametrize(
    ("delta", "shown"),
    [(-4.281973375071899e-16, "+0.0"), (1234.5678, "+1234.57"), (-3.3e-8, "-3.3e-08")],
    ids=["noise-at-zero", "real-value", "tiny-real"],
)
def test_should_print_the_displayed_volume_delta_when_a_preview_is_summarized(
    two_decimals, delta, shown
):
    # Arrange
    sc = {
        "diff": {
            "deltas": {"volume": {"delta": delta}},
            "counts": {"faces": {"delta": 0}},
            "validity": {"is_valid": True},
            "tnp_precheck": {"status": "OK"},
        }
    }

    # Act
    out = summarize_preview(sc)

    # Assert
    assert out == f"Preview: volume {shown} mm^3, faces +0, valid=True, tnp=OK."


class Quantity:
    """Stands in for ``Base.Quantity``: ``str`` is the full-length float, then the unit text."""

    def __init__(self, value: float, unit: str) -> None:
        self.Value = value
        self.unit = unit

    def __str__(self) -> str:
        return f"{self.Value!r} {self.unit}" if self.unit else repr(self.Value)


class Vector:
    """Stands in for ``Base.Vector``."""

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = x, y, z

    def __str__(self) -> str:
        return f"Vector ({self.x!r}, {self.y!r}, {self.z!r})"


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (Quantity(3.33333, "mm"), "3.33 mm"),
        (Quantity(5.999999998, "mm^2"), "6.0 mm^2"),
        (Quantity(0.123456, ""), "0.12"),
        (Vector(5.999999998, -0.0, 1234.5678), "Vector (6.0, 0.0, 1234.57)"),
    ],
    ids=["length", "area", "dimensionless", "vector"],
)
def test_should_render_displayed_numbers_when_a_property_is_a_quantity_or_vector(
    two_decimals, value, shown
):
    # Arrange
    target = _json_safe

    # Act
    out = target(value)

    # Assert
    assert out == shown
