"""Pure unit tests for per-tool summary builders (no FreeCAD required)."""

from freecad_buddy.usecases.queries import summarize_tree, summarize_mass_properties
from freecad_buddy.usecases.screenshot import summarize_screenshot
from freecad_buddy.usecases.verify import summarize_recompute, summarize_shape


def test_summarize_tree_reports_counts_and_errors():
    sc = {
        "total_objects": 201,
        "returned_nodes": 14,
        "tree": [
            {
                "name": "Assembly",
                "label": "h96max-mainboard",
                "type": "Assembly::AssemblyObject",
                "visibility": True,
                "links_count": 11,
                "children_count": 2,
                "children": [
                    {
                        "name": "Joint002",
                        "label": "x",
                        "type": "App::FeaturePython",
                        "visibility": True,
                        "error": "Broken link in: Reference1",
                    }
                ],
            },
        ],
    }
    out = summarize_tree(sc)
    assert "201 objects" in out
    assert "14" in out
    assert "Joint002" in out and "Broken link" in out


def test_summarize_tree_clean_no_error_suffix():
    sc = {
        "total_objects": 5,
        "returned_nodes": 3,
        "tree": [
            {"name": "Body", "label": "Body", "type": "PartDesign::Body", "visibility": True}
        ],
    }
    out = summarize_tree(sc)
    assert "5 objects" in out
    assert "3" in out
    assert "Errors" not in out
    assert out.endswith(".")


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
        "render": {"available": True, "dirty_document": False, "resource_link": "/tmp/x.png", "reason": None},
        "scene": {"rendered_objects": ["Body", "Pad", "Fillet"], "focused_on": None},
    }
    out = summarize_screenshot(sc)
    assert "3" in out
    assert "Rendered" in out
    assert "dirty" not in out.lower()


def test_summarize_screenshot_dirty_document():
    sc = {
        "render": {"available": True, "dirty_document": True, "resource_link": "/tmp/x.png", "reason": None},
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
                "detail": {"code": "recompute.error", "message": "Pad: Invalid", "objects": ["Pad"]},
            },
            {
                "id": "recompute.object",
                "measured": "Error",
                "expected": None,
                "passed": False,
                "detail": {"code": "recompute.error", "message": "Fillet: Error", "objects": ["Fillet"]},
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
            {"id": "shape.volume", "measured": 1000.0, "expected": 1000.0, "passed": True, "detail": {"message": "ok"}},
            {"id": "shape.valid", "measured": True, "expected": True, "passed": True, "detail": {"message": "ok"}},
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
