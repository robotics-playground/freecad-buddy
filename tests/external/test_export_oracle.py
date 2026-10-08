"""FreeCAD-free tests for the export oracles and verdict assembly (trimesh + lib3mf).

Runs in the uv leg over the committed export-fault fixtures. Golden expectations are analytic
(a box 10x20x30 is watertight, volume 6000, Euler 2), never captured from the implementation.
Covers trimesh + stdlib STL oracles on clean vs holed/flipped/non-manifold meshes, the lib3mf
3MF oracle on unit-lie / type-model-lie / corrupt-container, and that a cross-oracle
disagreement forces FAIL in ``assemble_export_verdict``.
"""

from __future__ import annotations

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
