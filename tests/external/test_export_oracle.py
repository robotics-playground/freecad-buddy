"""FreeCAD-free tests for the export oracles and verdict assembly (trimesh + lib3mf).

Runs in the uv leg over the committed export-fault fixtures. Golden expectations are analytic
(a box 10x20x30 is watertight, volume 6000, Euler 2), never captured from the implementation.
Covers trimesh + stdlib STL oracles on clean vs holed/flipped/non-manifold meshes, the lib3mf
3MF oracle on unit-lie / type-model-lie / corrupt-container, and that a cross-oracle
disagreement forces FAIL in ``assemble_export_verdict``.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

from freecad_buddy.adapters import export_oracle, export_verdict
from freecad_buddy.usecases import exports

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"

BOX_VOLUME = 6000.0
BOX_BBOX = [10.0, 20.0, 30.0]
BOX_AREA = 2200.0
BAND = exports.mesh_volume_band(0.1, BOX_AREA)


def _stl(case: str) -> str:
    return str(SUITE / case / "export.stl")


def _3mf(case: str) -> str:
    return str(SUITE / case / "export.3mf")


def _facts(path: str) -> dict:
    return {
        "self_read": {"facets": 0, "vertices": 0, "bbox": BOX_BBOX},
        "recorded": {"facets": 0, "vertices": 0},
        "path": path,
        "volume_band": BAND,
        "tess": {"linear": 0.1, "angular": 0.5},
    }


def test_trimesh_stl_oracle_passes_clean_box():
    result = export_oracle.stl_oracle(_stl("stl-clean-control"), BOX_VOLUME, BAND)
    assert result["ok"] is True


def test_trimesh_stl_oracle_flags_hole_and_non_manifold():
    assert export_oracle.stl_oracle(_stl("stl-hole"), BOX_VOLUME, BAND)["ok"] is False
    assert export_oracle.stl_oracle(_stl("stl-non-manifold"), BOX_VOLUME, BAND)["ok"] is False


def test_stdlib_stl_oracle_agrees_on_clean_flags_defects():
    oracle = export_oracle.StdlibStlOracle()
    assert oracle.check(_stl("stl-clean-control"))["ok"] is True
    assert oracle.check(_stl("stl-hole"))["ok"] is False
    assert oracle.check(_stl("stl-non-manifold"))["ok"] is False


def test_mesh3mf_oracle_passes_clean_and_catches_lies():
    assert export_oracle.mesh3mf_oracle(_3mf("3mf-clean-control"), True, BOX_VOLUME, BAND)["ok"]
    assert not export_oracle.mesh3mf_oracle(_3mf("3mf-unit-lie"), True, BOX_VOLUME, BAND)["ok"]
    assert not export_oracle.mesh3mf_oracle(_3mf("3mf-type-model-lie"), True, BOX_VOLUME, BAND)[
        "ok"
    ]
    assert not export_oracle.mesh3mf_oracle(_3mf("3mf-corrupt-container"), True, BOX_VOLUME, BAND)[
        "ok"
    ]


def test_mesh3mf_unit_lie_fails_even_when_geometry_is_sound():
    result = export_oracle.mesh3mf_oracle(_3mf("3mf-unit-lie"), True, BOX_VOLUME, BAND)
    unit_check = next(c for c in result["checks"] if c["id"] == "lib3mf.unit_millimeter")
    assert unit_check["passed"] is False


def test_assemble_verdict_ok_when_all_oracles_agree_pass():
    path = _stl("stl-clean-control")
    legs = [
        export_oracle.stl_oracle(path, BOX_VOLUME, BAND),
        export_oracle.StdlibStlOracle().check(path),
    ]
    envelope = export_verdict.assemble_export_verdict(legs, _facts(path), banner={"v": 1})
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["verdict"] == "OK"


def test_assemble_verdict_fails_on_cross_oracle_disagreement():
    # flipped normals: trimesh flags a non-volume mesh, the stdlib edge-pairing check passes.
    path = _stl("stl-flipped-normals")
    trimesh_leg = export_oracle.stl_oracle(path, BOX_VOLUME, BAND)
    stdlib_leg = export_oracle.StdlibStlOracle().check(path)
    assert trimesh_leg["ok"] != stdlib_leg["ok"], "fixture must produce a disagreement"
    envelope = export_verdict.assemble_export_verdict(
        [trimesh_leg, stdlib_leg], _facts(path), banner={}
    )
    assert envelope["status"] != "OK"
    agreement = next(
        c for c in envelope["structured_content"]["checks"] if c["id"] == "oracle.agreement"
    )
    assert agreement["passed"] is False


def test_mesh_volume_band_is_not_step_tolerance():
    band = exports.mesh_volume_band(0.1, BOX_AREA)
    step_band = BOX_VOLUME * 0.001
    assert band != step_band
    assert band > 0


def test_safe_oracle_turns_missing_file_into_failed_leg():
    missing = str(SUITE / "does-not-exist" / "export.stl")
    leg = export_oracle.safe_oracle(
        "trimesh_stl", lambda: export_oracle.stl_oracle(missing, BOX_VOLUME, BAND)
    )
    assert leg["ok"] is False
    assert leg["checks"][0]["id"] == "trimesh_stl.readable"


def test_safe_oracle_failed_leg_forces_fail_verdict():
    missing = str(SUITE / "does-not-exist" / "export.stl")
    legs = [
        export_oracle.safe_oracle(
            "trimesh_stl", lambda: export_oracle.stl_oracle(missing, BOX_VOLUME, BAND)
        ),
        export_oracle.safe_oracle(
            "stdlib_stl", lambda: export_oracle.StdlibStlOracle().check(missing)
        ),
    ]
    envelope = export_verdict.assemble_export_verdict(legs, _facts(missing), banner={})
    assert envelope["status"] != "OK"


def test_unreadable_self_read_leg_forces_fail_verdict():
    # A self-read leg whose file could not be re-read (missing/corrupt) must FAIL closed, not
    # be treated as passing — mirrors safe_oracle for the FreeCAD self-read leg.
    path = _stl("stl-clean-control")
    facts = _facts(path)
    facts["self_read"] = {"readable": False, "error": "file not found"}
    legs = [
        export_oracle.stl_oracle(path, BOX_VOLUME, BAND),
        export_oracle.StdlibStlOracle().check(path),
    ]
    envelope = export_verdict.assemble_export_verdict(legs, facts, banner={})
    assert envelope["status"] != "OK"
    readable = next(
        c for c in envelope["structured_content"]["checks"] if c["id"] == "self_read.readable"
    )
    assert readable["passed"] is False


class _StubMesh:
    """A sound closed mesh whose volume is set directly, for the volume-band verdict alone."""

    is_watertight = True
    is_winding_consistent = True
    is_volume = True
    euler_number = 2

    def __init__(self, volume: float) -> None:
        self.volume = volume


@pytest.mark.parametrize(("decimals", "passed"), [(2, True), (4, False)])
def test_should_compare_the_displayed_deviation_when_the_volume_sits_at_the_band_edge(
    decimals, passed
):
    # Arrange: |6.054 - 6.0| shows as 0.05 at 2 places (within 0.05) and 0.054 at 4 (outside).
    mesh = _StubMesh(6.054)

    # Act
    result = export_oracle._trimesh_checks(mesh, 6.0, 0.05, "trimesh_stl", decimals)

    # Assert
    volume_check = next(c for c in result["checks"] if c["id"] == "trimesh_stl.volume_band")
    assert volume_check["passed"] is passed


_BOX_TRIANGLES = [
    (0, 2, 1),
    (0, 3, 2),
    (4, 5, 6),
    (4, 6, 7),
    (0, 1, 5),
    (0, 5, 4),
    (1, 2, 6),
    (1, 6, 5),
    (2, 3, 7),
    (2, 7, 6),
    (3, 0, 4),
    (3, 4, 7),
]


def _write_named_boxes(path: Path, boxes: list[tuple[str, float, float, float, float]]) -> None:
    """Write a 3MF with one named box mesh per ``(name, x_offset, dx, dy, dz)``."""
    import lib3mf

    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)
    for name, x0, dx, dy, dz in boxes:
        corners = [
            (x0, 0, 0),
            (x0 + dx, 0, 0),
            (x0 + dx, dy, 0),
            (x0, dy, 0),
            (x0, 0, dz),
            (x0 + dx, 0, dz),
            (x0 + dx, dy, dz),
            (x0, dy, dz),
        ]
        mesh = model.AddMeshObject()
        mesh.SetName(name)
        mesh.SetGeometry(
            [lib3mf.Position(tuple(float(c) for c in corner)) for corner in corners],
            [lib3mf.Triangle((ctypes.c_uint * 3)(*triangle)) for triangle in _BOX_TRIANGLES],
        )
        model.AddBuildItem(mesh, wrapper.GetIdentityTransform())
    model.QueryWriter("3mf").WriteToFile(str(path))


def _object_entries(boxes: list[tuple[str, float, float, float, float]]) -> list[dict]:
    return [
        {"name": name, "label": name, "volume": dx * dy * dz, "band": BAND}
        for name, _x0, dx, dy, dz in boxes
    ]


THREE_BOXES = [
    ("Alpha", 0.0, 10.0, 20.0, 30.0),
    ("Beta", 20.0, 5.0, 5.0, 5.0),
    ("Gamma", 40.0, 2.0, 3.0, 4.0),
]


def _check_by_id(result: dict) -> dict:
    return {check["id"]: check for check in result["checks"]}


def test_Should_pass_every_object_check_When_a_multi_object_3mf_matches_its_objects(tmp_path):
    # Arrange
    path = tmp_path / "three.3mf"
    _write_named_boxes(path, THREE_BOXES)
    total = sum(entry["volume"] for entry in _object_entries(THREE_BOXES))

    # Act
    target = export_oracle.mesh3mf_oracle(
        str(path), True, total, BAND, None, _object_entries(THREE_BOXES)
    )

    # Assert
    checks = _check_by_id(target)
    assert target["ok"] is True
    assert checks["lib3mf.object_count"]["measured"] == 3
    assert checks["lib3mf.object_names"]["measured"] == ["Alpha", "Beta", "Gamma"]
    for name in ("Alpha", "Beta", "Gamma"):
        assert checks[f"trimesh_3mf.object_volume:{name}"]["passed"] is True


def test_Should_fail_and_name_the_object_When_one_object_volume_is_wrong(tmp_path):
    # Arrange
    path = tmp_path / "three.3mf"
    _write_named_boxes(path, THREE_BOXES)
    objects = _object_entries(THREE_BOXES)
    objects[1]["volume"] = 500.0
    total = sum(entry["volume"] for entry in _object_entries(THREE_BOXES))

    # Act
    target = export_oracle.mesh3mf_oracle(str(path), True, total, BAND, None, objects)

    # Assert
    checks = _check_by_id(target)
    assert target["ok"] is False
    assert checks["trimesh_3mf.object_volume:Beta"]["passed"] is False
    assert checks["trimesh_3mf.object_volume:Alpha"]["passed"] is True


def test_Should_fail_the_name_check_When_a_mesh_object_carries_another_name(tmp_path):
    # Arrange
    path = tmp_path / "three.3mf"
    _write_named_boxes(path, [("Alpha", 0.0, 10.0, 20.0, 30.0), ("Other", 20.0, 5.0, 5.0, 5.0)])
    objects = _object_entries(THREE_BOXES[:2])
    total = sum(entry["volume"] for entry in objects)

    # Act
    target = export_oracle.mesh3mf_oracle(str(path), True, total, BAND, None, objects)

    # Assert
    assert _check_by_id(target)["lib3mf.object_names"]["passed"] is False


def test_Should_fail_the_count_check_When_the_file_holds_fewer_meshes_than_objects(tmp_path):
    # Arrange
    path = tmp_path / "two.3mf"
    _write_named_boxes(path, THREE_BOXES[:2])
    objects = _object_entries(THREE_BOXES)
    total = sum(entry["volume"] for entry in objects)

    # Act
    target = export_oracle.mesh3mf_oracle(str(path), True, total, BAND, None, objects)

    # Assert
    assert target["ok"] is False
    assert _check_by_id(target)["lib3mf.object_count"]["passed"] is False


def _box_facets(x0: float, size: float) -> list[tuple]:
    corners = [
        (x0, 0, 0),
        (x0 + size, 0, 0),
        (x0 + size, size, 0),
        (x0, size, 0),
        (x0, 0, size),
        (x0 + size, 0, size),
        (x0 + size, size, size),
        (x0, size, size),
    ]
    return [tuple(corners[i] for i in triangle) for triangle in _BOX_TRIANGLES]


def _write_binary_stl(path: Path, facets: list[tuple]) -> None:
    import struct

    data = bytearray(b"\0" * 80 + struct.pack("<I", len(facets)))
    for v0, v1, v2 in facets:
        edge_a = [v1[i] - v0[i] for i in range(3)]
        edge_b = [v2[i] - v0[i] for i in range(3)]
        normal = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        data += struct.pack("<12fH", *normal, *v0, *v1, *v2, 0)
    path.write_bytes(bytes(data))


TOUCHING_BOXES_VOLUME = 2000.0


def test_Should_fail_When_two_boxes_sharing_a_face_are_graded_as_one_mesh(tmp_path):
    # Arrange
    path = tmp_path / "touching.stl"
    _write_binary_stl(path, _box_facets(0.0, 10.0) + _box_facets(10.0, 10.0))

    # Act
    trimesh_leg = export_oracle.stl_oracle(str(path), TOUCHING_BOXES_VOLUME, BAND)
    stdlib_leg = export_oracle.StdlibStlOracle().check(str(path))

    # Assert
    assert trimesh_leg["ok"] is False
    assert stdlib_leg["ok"] is False


def test_Should_pass_both_oracles_When_touching_boxes_are_graded_per_object(tmp_path):
    # Arrange
    path = tmp_path / "touching.stl"
    _write_binary_stl(path, _box_facets(0.0, 10.0) + _box_facets(10.0, 10.0))
    facet_counts = [12, 12]

    # Act
    trimesh_leg = export_oracle.stl_oracle(
        str(path), TOUCHING_BOXES_VOLUME, BAND, None, facet_counts
    )
    stdlib_leg = export_oracle.StdlibStlOracle().check(str(path), facet_counts)

    # Assert
    assert trimesh_leg["ok"] is True
    assert stdlib_leg["ok"] is True
    volume_check = _check_by_id(trimesh_leg)["trimesh_stl.volume_band"]
    assert volume_check["measured"] == pytest.approx(TOUCHING_BOXES_VOLUME)


def test_Should_still_fail_per_object_When_one_object_has_a_hole(tmp_path):
    # Arrange
    path = tmp_path / "holed.stl"
    holed = _box_facets(10.0, 10.0)[:-1]
    _write_binary_stl(path, _box_facets(0.0, 10.0) + holed)
    facet_counts = [12, 11]

    # Act
    trimesh_leg = export_oracle.stl_oracle(str(path), 1900.0, BAND, None, facet_counts)
    stdlib_leg = export_oracle.StdlibStlOracle().check(str(path), facet_counts)

    # Assert
    assert trimesh_leg["ok"] is False
    assert stdlib_leg["ok"] is False


def test_Should_grade_the_whole_mesh_When_the_facet_counts_do_not_match_the_file(tmp_path):
    # Arrange
    path = tmp_path / "one.stl"
    _write_binary_stl(path, _box_facets(0.0, 10.0))

    # Act
    trimesh_leg = export_oracle.stl_oracle(str(path), 1000.0, BAND, None, [5, 5])
    stdlib_leg = export_oracle.StdlibStlOracle().check(str(path), [5, 5])

    # Assert
    assert trimesh_leg["ok"] is True
    assert stdlib_leg["ok"] is True
