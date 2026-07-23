"""Deterministic FreeCADCmd generator for the G0 export-fault + clean-control fixtures.

Run under FreeCADCmd (``FreeCADCmd build_export_fault_fixtures.py``). Each case writes a real
exported file carrying a planted defect (or a clean control) next to a ``case.yaml`` recording
the targeted verifier, the format, the DETECT/PASS_CLEAN expectation, and the reference facts
the verifier compares against. The oracle-side scorer and ``tests/external`` re-read these
committed files without FreeCAD; the FreeCAD self-read/STEP legs re-open them via the registry.

Defects are planted at the FILE level where a clean writer would not produce them: an STL with
a facet removed (hole), an STL with flipped winding, an STL with a non-manifold extra facet, a
3MF re-tagged with a lying unit or a non-manifold mesh, a truncated 3MF container, a STEP whose
source dropped a solid, and a STEP whose source is 1/10 scale (unit lie).
"""

from __future__ import annotations

import shutil
import struct
import zipfile
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent

LINEAR = 0.1
ANGULAR = 0.5


def _box_shape():
    return Part.makeBox(10, 20, 30)


def _mesh(shape):
    return MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=LINEAR, AngularDeflection=ANGULAR, Relative=False
    )


def _source_facts(shape):
    bb = shape.BoundBox
    return {
        "volume": float(shape.Volume),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "solids": len(shape.Solids),
        "bbox": [bb.XLength, bb.YLength, bb.ZLength],
    }


def _write_binary_stl(path: Path, facets: list[tuple]) -> None:
    """Write ``facets`` (each ``(normal, v0, v1, v2)``) as a binary STL to ``path``."""
    with open(path, "wb") as handle:
        handle.write(b"FCB export-fault fixture".ljust(80, b" "))
        handle.write(struct.pack("<I", len(facets)))
        for normal, v0, v1, v2 in facets:
            handle.write(struct.pack("<3f", *normal))
            for vertex in (v0, v1, v2):
                handle.write(struct.pack("<3f", *vertex))
            handle.write(struct.pack("<H", 0))


def _read_binary_stl(path: Path) -> list[tuple]:
    with open(path, "rb") as handle:
        data = handle.read()
    count = struct.unpack_from("<I", data, 80)[0]
    facets = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12f", data, offset)
        facets.append((values[0:3], values[3:6], values[6:9], values[9:12]))
        offset += 50
    return facets


def _clean_stl(case_dir: Path) -> Path:
    mesh = _mesh(_box_shape())
    target = case_dir / "export.stl"
    mesh.write(str(target))
    return target


def _clean_3mf(case_dir: Path) -> Path:
    mesh = _mesh(_box_shape())
    target = case_dir / "export.3mf"
    mesh.write(str(target))
    return target


def _stl_hole(case_dir: Path) -> Path:
    """Clean STL with one facet removed — an open, non-watertight surface."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    _write_binary_stl(src, facets[:-1])
    return src


def _stl_flipped_normals(case_dir: Path) -> Path:
    """Clean STL with every facet's winding reversed — inconsistent orientation."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    flipped = [(normal, v0, v2, v1) for normal, v0, v1, v2 in facets]
    _write_binary_stl(src, flipped)
    return src


def _stl_non_manifold(case_dir: Path) -> Path:
    """Clean STL with one duplicated facet — an edge shared by three facets (non-manifold)."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    facets.append(facets[0])
    _write_binary_stl(src, facets)
    return src


def _3mf_type_model_lie(case_dir: Path) -> Path:
    """3MF whose mesh is an open surface but declared as a solid model object."""
    open_shape = Part.Shell([_box_shape().Faces[0]])
    mesh = _mesh(open_shape)
    target = case_dir / "export.3mf"
    mesh.write(str(target))
    return target


def _3mf_unit_lie(case_dir: Path) -> Path:
    """3MF re-tagged from millimetre to metre — the writer's hardcoded-mm unit lie."""
    src = _clean_3mf(case_dir)
    tmp = case_dir / "_tmp_unit"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    with zipfile.ZipFile(src, "r") as archive:
        archive.extractall(tmp)
    model_path = tmp / "3D" / "3dmodel.model"
    text = model_path.read_text(encoding="utf-8")
    text = text.replace('unit="millimeter"', 'unit="meter"')
    model_path.write_text(text, encoding="utf-8")
    src.unlink()
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(tmp.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(tmp).as_posix())
    shutil.rmtree(tmp)
    return src


def _3mf_corrupt_container(case_dir: Path) -> Path:
    """3MF whose zip container is truncated — lib3mf cannot parse it."""
    src = _clean_3mf(case_dir)
    data = src.read_bytes()
    src.write_bytes(data[: len(data) // 2])
    return src


def _step_dropped_solid(case_dir: Path) -> Path:
    """STEP of a single box where the recorded source is a two-solid compound."""
    Part.setStaticValue("write.step.unit", "MM")
    target = case_dir / "export.step"
    _box_shape().exportStep(str(target))
    return target


def _step_unit_lie(case_dir: Path) -> Path:
    """STEP of a 1/10-scale box mislabelled as the full-scale mm reference.

    A ``write.step.unit=M`` "unit lie" is NOT usable as a volume fault: the STEP unit is a
    file-unit annotation, so a mm box written in metres re-imports back to the same mm volume
    (round-trip-neutral, verified empirically). The detectable unit fault is therefore a genuine
    geometry-scale mismatch — a 1/10-scale box referenced against the full-scale facts.
    """
    Part.setStaticValue("write.step.unit", "MM")
    target = case_dir / "export.step"
    Part.makeBox(1, 2, 3).exportStep(str(target))
    return target


def _clean_step(case_dir: Path) -> Path:
    Part.setStaticValue("write.step.unit", "MM")
    target = case_dir / "export.step"
    _box_shape().exportStep(str(target))
    return target


# id -> (validator, format, expectation, builder)
CASES = {
    "stl-hole": ("verify_export_stl", "stl", "DETECT", _stl_hole),
    "stl-flipped-normals": ("verify_export_stl", "stl", "DETECT", _stl_flipped_normals),
    "stl-non-manifold": ("verify_export_stl", "stl", "DETECT", _stl_non_manifold),
    "stl-clean-control": ("verify_export_stl", "stl", "PASS_CLEAN", _clean_stl),
    "3mf-type-model-lie": ("verify_export_3mf", "3mf", "DETECT", _3mf_type_model_lie),
    "3mf-unit-lie": ("verify_export_3mf", "3mf", "DETECT", _3mf_unit_lie),
    "3mf-corrupt-container": ("verify_export_3mf", "3mf", "DETECT", _3mf_corrupt_container),
    "3mf-clean-control": ("verify_export_3mf", "3mf", "PASS_CLEAN", _clean_3mf),
    "step-dropped-solid": ("verify_export_step", "step", "DETECT", _step_dropped_solid),
    "step-unit-lie": ("verify_export_step", "step", "DETECT", _step_unit_lie),
    "step-clean-control": ("verify_export_step", "step", "PASS_CLEAN", _clean_step),
}


def _reference_source(case_id: str) -> dict:
    """Return the reference (correct-shape) source facts a verifier compares the file against.

    The reference is what a CORRECT export of the intended part yields; the fixture deviates
    from it. ``step-dropped-solid`` intends a two-solid compound; ``step-unit-lie`` intends the
    full-scale box; every other case intends the clean box-10-20-30.
    """
    if case_id == "step-dropped-solid":
        compound = Part.makeCompound(
            [Part.makeBox(10, 20, 30), Part.makeBox(10, 20, 30, App.Vector(20, 0, 0))]
        )
        return _source_facts(compound)
    return _source_facts(_box_shape())


def _write_case_yaml(case_dir: Path, case_id: str) -> None:
    validator, fmt, expectation, _ = CASES[case_id]
    source = _reference_source(case_id)
    bbox = ", ".join(str(v) for v in source["bbox"])
    case_dir.joinpath("case.yaml").write_text(
        f"id: g0-export-{case_id}\n"
        "gate: g0\n"
        f"targets_validator: {validator}\n"
        f"format: {fmt}\n"
        f"expectation: {expectation}\n"
        f"export_file: export.{fmt}\n"
        "source:\n"
        f"  volume: {source['volume']}\n"
        f"  faces: {source['faces']}\n"
        f"  edges: {source['edges']}\n"
        f"  solids: {source['solids']}\n"
        f"  bbox: [{bbox}]\n"
        "  is_mm: true\n"
        "tess:\n"
        f"  linear: {LINEAR}\n"
        f"  angular: {ANGULAR}\n",
        encoding="utf-8",
    )


def build_all(base_dir: Path | None = None) -> list[Path]:
    base_dir = base_dir or HERE
    written = []
    for case_id, (_validator, _fmt, _expectation, builder) in CASES.items():
        case_dir = base_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        target = builder(case_dir)
        _write_case_yaml(case_dir, case_id)
        written.append(target)
    return written


def _is_top_level_script() -> bool:
    """Whether this file is the script FreeCADCmd (or python) was launched with.

    FreeCADCmd runs a script with ``__name__`` set to the file stem rather than ``"__main__"``,
    so the standard guard alone never fires; this also matches ``__file__`` against ``argv[1]``.
    """
    import sys

    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
    return False


if _is_top_level_script():
    for path in build_all():
        print(f"wrote {path}")
