"""Deterministic FreeCADCmd generator for the G0 export-fault + clean-control fixtures.

Run under FreeCADCmd (``FreeCADCmd build_export_fault_fixtures.py``). Each case writes a real
exported file carrying a planted defect (or a clean control) next to a ``case.yaml`` recording
the targeted verifier, the format, the DETECT/PASS_CLEAN expectation, and the reference facts
the verifier compares against. The oracle-side scorer and ``tests/external`` re-read these
committed files without FreeCAD; the FreeCAD self-read/STEP legs re-open them via the registry.

Defects are planted at the FILE level where a clean writer would not produce them: STLs with a
facet removed, flipped winding, extra/degenerate facets, a doubled shell, a scaled or dented
mesh, or truncated coordinates; 3MFs with a lying unit, a truncated or model-less container, a
syntactically malformed transform, a removed/duplicated/out-of-range triangle, a moved vertex,
or a second non-manifold mesh object; STEPs whose source dropped a solid, is scaled, is a bare
shell, carries an unrefined fuse or CompSolid, or gained a notch, an overlap, or a loose face.
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


def _cylinder_shape():
    return Part.makeCylinder(10, 30)


def _mesh(shape):
    return MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=LINEAR, AngularDeflection=ANGULAR, Relative=False
    )


def _source_facts(shape):
    bb = shape.BoundBox
    return {
        "volume": float(shape.Volume),
        "area": float(shape.Area),
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


def _stl_duplicated_shell(case_dir: Path) -> Path:
    """Clean STL with every facet emitted twice — a doubled, self-coincident shell."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    _write_binary_stl(src, facets + facets)
    return src


def _stl_scaled_mesh(case_dir: Path) -> Path:
    """Clean STL scaled to 0.9 — a mesh whose volume is 0.729x the reference solid's."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    scaled = [
        (normal, *(tuple(c * 0.9 for c in vertex) for vertex in (v0, v1, v2)))
        for normal, v0, v1, v2 in facets
    ]
    _write_binary_stl(src, scaled)
    return src


def _stl_missing_face(case_dir: Path) -> Path:
    """Clean STL with the whole top face removed — a box open across one full side."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    kept = [facet for facet in facets if not all(abs(v[2] - 30.0) < 1e-6 for v in facet[1:])]
    _write_binary_stl(src, kept)
    return src


def _stl_shifted_vertex(case_dir: Path) -> Path:
    """Clean STL with one facet's first vertex displaced 1 mm — a torn corner."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    normal, v0, v1, v2 = facets[0]
    facets[0] = (normal, (v0[0] + 1.0, v0[1], v0[2]), v1, v2)
    _write_binary_stl(src, facets)
    return src


def _stl_appended_degenerate(case_dir: Path) -> Path:
    """Clean STL with a zero-area facet appended — three identical vertices."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    normal, v0, _v1, _v2 = facets[0]
    facets.append((normal, v0, v0, v0))
    _write_binary_stl(src, facets)
    return src


def _stl_collapsed_facet(case_dir: Path) -> Path:
    """Clean STL with one facet collapsed in place onto a single vertex — a hole plus zero area."""
    src = _clean_stl(case_dir)
    facets = _read_binary_stl(src)
    normal, v0, _v1, _v2 = facets[0]
    facets[0] = (normal, v0, v0, v0)
    _write_binary_stl(src, facets)
    return src


def _stl_truncated_coordinates(case_dir: Path) -> Path:
    """STL of the cylinder reference with every coordinate rounded to whole millimetres.

    Truncation must be applied to a CURVED source: the box mesh's vertices are all integer-valued,
    so rounding it is a bitwise no-op. Rounding the cylinder collapses facets to zero area.
    """
    mesh = _mesh(_cylinder_shape())
    target = case_dir / "export.stl"
    mesh.write(str(target))
    facets = _read_binary_stl(target)
    truncated = [
        (normal, *(tuple(round(c) for c in vertex) for vertex in (v0, v1, v2)))
        for normal, v0, v1, v2 in facets
    ]
    _write_binary_stl(target, truncated)
    return target


def _3mf_type_model_lie(case_dir: Path) -> Path:
    """3MF whose mesh is an open surface but declared as a solid model object."""
    open_shape = Part.Shell([_box_shape().Faces[0]])
    mesh = _mesh(open_shape)
    target = case_dir / "export.3mf"
    mesh.write(str(target))
    return target


def _rewrite_3mf_model(src: Path, transform) -> Path:
    """Rebuild the 3MF at ``src`` with ``3D/3dmodel.model`` replaced by ``transform(text)``.

    ``transform`` receives the model XML as text and returns the replacement text; returning
    ``None`` drops the part from the rebuilt container. Every other zip entry is copied verbatim.
    """
    tmp = src.parent / "_tmp_3mf"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    with zipfile.ZipFile(src, "r") as archive:
        archive.extractall(tmp)
    model_path = tmp / "3D" / "3dmodel.model"
    replacement = transform(model_path.read_text(encoding="utf-8"))
    if replacement is None:
        model_path.unlink()
    else:
        model_path.write_text(replacement, encoding="utf-8")
    src.unlink()
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(tmp.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(tmp).as_posix())
    shutil.rmtree(tmp)
    return src


def _3mf_unit_lie(case_dir: Path) -> Path:
    """3MF re-tagged from millimetre to metre — the writer's hardcoded-mm unit lie."""
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace('unit="millimeter"', 'unit="meter"'),
    )


def _3mf_corrupt_container(case_dir: Path) -> Path:
    """3MF whose zip container is truncated — lib3mf cannot parse it."""
    src = _clean_3mf(case_dir)
    data = src.read_bytes()
    src.write_bytes(data[: len(data) // 2])
    return src


def _3mf_missing_model_part(case_dir: Path) -> Path:
    """3MF rebuilt without its ``3D/3dmodel.model`` part — the OPC package has no model."""
    return _rewrite_3mf_model(_clean_3mf(case_dir), lambda _text: None)


def _3mf_malformed_transform(case_dir: Path) -> Path:
    """3MF whose build item carries a non-numeric token in its transform matrix.

    Only a SYNTACTICALLY malformed matrix is detectable: the oracle reads mesh vertex/triangle
    arrays and never applies build-item transforms, so a well-formed but absurd matrix passes.
    """
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace(
            'transform="1 0 0 0 1 0 0 0 1 0 0 0"', 'transform="1 0 0 0 1 0 0 0 1 0 0 BOGUS"'
        ),
    )


def _3mf_missing_triangle(case_dir: Path) -> Path:
    """3MF with one ``<triangle>`` element deleted — an open, non-manifold mesh."""
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace('     <triangle v1="0" v2="1" v3="2" />\n', "", 1),
    )


def _3mf_corrupt_vertex(case_dir: Path) -> Path:
    """3MF with one vertex pulled from x=10 to x=5 — a dented box under the reference volume."""
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace(
            '<vertex x="10" y="0" z="30" />', '<vertex x="5" y="0" z="30" />'
        ),
    )


def _3mf_duplicated_triangle(case_dir: Path) -> Path:
    """3MF with one ``<triangle>`` repeated — edges shared by three triangles (non-manifold)."""
    triangle = '     <triangle v1="0" v2="1" v3="2" />\n'
    return _rewrite_3mf_model(
        _clean_3mf(case_dir), lambda text: text.replace(triangle, triangle * 2, 1)
    )


def _3mf_vertex_index_out_of_range(case_dir: Path) -> Path:
    """3MF whose first triangle references a vertex index past the end of the vertex array."""
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace(
            '<triangle v1="0" v2="1" v3="2" />', '<triangle v1="0" v2="1" v3="99" />', 1
        ),
    )


def _3mf_second_non_manifold_object(case_dir: Path) -> Path:
    """3MF carrying a second mesh object that is a single loose triangle — non-manifold."""
    extra_object = (
        '  <object id="2" type="model">\n'
        "   <mesh>\n"
        "    <vertices>\n"
        '     <vertex x="50" y="0" z="0" />\n'
        '     <vertex x="60" y="0" z="0" />\n'
        '     <vertex x="50" y="10" z="0" />\n'
        "    </vertices>\n"
        "    <triangles>\n"
        '     <triangle v1="0" v2="1" v3="2" />\n'
        "    </triangles>\n"
        "   </mesh>\n"
        "  </object>\n"
        " </resources>\n"
    )
    return _rewrite_3mf_model(
        _clean_3mf(case_dir),
        lambda text: text.replace(" </resources>\n", extra_object, 1).replace(
            " </build>\n",
            '  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n </build>\n',
        ),
    )


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


def _export_step(case_dir: Path, shape) -> Path:
    Part.setStaticValue("write.step.unit", "MM")
    target = case_dir / "export.step"
    shape.exportStep(str(target))
    return target


def _stacked_halves():
    """The two box-10-20-15 halves that stack into the box-10-20-30 reference."""
    return (
        Part.makeBox(10, 20, 15),
        Part.makeBox(10, 20, 15, App.Vector(0, 0, 15)),
    )


def _step_shell_no_solid(case_dir: Path) -> Path:
    """STEP of the box's closed shell with no solid built from it — solids 0 where 1 is expected.

    Volume and ``isValid`` both still pass, so this case isolates ``topology_counts`` on ``solids``.
    """
    return _export_step(case_dir, Part.Shell(_box_shape().Faces))


def _step_unrefined_fuse(case_dir: Path) -> Path:
    """STEP of the two stacked halves fused without refinement — the shared face is left in.

    The fused volume is exactly 6000 and it is a single solid, so this case isolates
    ``topology_counts`` on ``faces``/``edges`` (10/20 where 6/12 is expected).
    """
    lower, upper = _stacked_halves()
    return _export_step(case_dir, lower.fuse(upper))


def _step_cut_notch(case_dir: Path) -> Path:
    """STEP of the box with a 2x2x2 corner notch cut out — under-volume plus extra faces/edges."""
    return _export_step(case_dir, _box_shape().cut(Part.makeBox(2, 2, 2)))


def _step_fused_overlap(case_dir: Path) -> Path:
    """STEP of the box fused with a 5x5x5 block on its +X face — over-volume plus extra topology."""
    return _export_step(case_dir, _box_shape().fuse(Part.makeBox(5, 5, 5, App.Vector(10, 0, 0))))


def _step_compsolid(case_dir: Path) -> Path:
    """STEP of the two stacked halves as a CompSolid — two solids where the box is one.

    The CompSolid's volume is exactly 6000, so this case isolates ``topology_counts``.
    """
    lower, upper = _stacked_halves()
    return _export_step(
        case_dir,
        Part.CompSolid([Part.Solid(lower.Shells[0]), Part.Solid(upper.Shells[0])]),
    )


def _step_loose_face(case_dir: Path) -> Path:
    """STEP of the box compounded with a stray plane far off the part — an extra loose face.

    The re-imported volume is bounding-box driven (6607), so both volume and topology deviate.
    """
    return _export_step(
        case_dir,
        Part.makeCompound([_box_shape(), Part.makePlane(5, 5, App.Vector(100, 100, 100))]),
    )


def _step_open_shell(case_dir: Path) -> Path:
    """STEP of the box's shell with the top face dropped — an open 5-face surface, no solid."""
    return _export_step(case_dir, Part.Shell(_box_shape().Faces[:-1]))


def _step_scaled_half_box(case_dir: Path) -> Path:
    """STEP of a half-size box (5x10x15, volume 750) sold as the full-scale reference."""
    return _export_step(case_dir, Part.makeBox(5, 10, 15))


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
    "stl-duplicated-shell": ("verify_export_stl", "stl", "DETECT", _stl_duplicated_shell),
    "stl-scaled-mesh": ("verify_export_stl", "stl", "DETECT", _stl_scaled_mesh),
    "stl-missing-face": ("verify_export_stl", "stl", "DETECT", _stl_missing_face),
    "stl-shifted-vertex": ("verify_export_stl", "stl", "DETECT", _stl_shifted_vertex),
    "stl-appended-degenerate": ("verify_export_stl", "stl", "DETECT", _stl_appended_degenerate),
    "stl-collapsed-facet": ("verify_export_stl", "stl", "DETECT", _stl_collapsed_facet),
    "stl-truncated-coordinates": (
        "verify_export_stl",
        "stl",
        "DETECT",
        _stl_truncated_coordinates,
    ),
    "stl-clean-control": ("verify_export_stl", "stl", "PASS_CLEAN", _clean_stl),
    "3mf-type-model-lie": ("verify_export_3mf", "3mf", "DETECT", _3mf_type_model_lie),
    "3mf-unit-lie": ("verify_export_3mf", "3mf", "DETECT", _3mf_unit_lie),
    "3mf-corrupt-container": ("verify_export_3mf", "3mf", "DETECT", _3mf_corrupt_container),
    "3mf-missing-model-part": ("verify_export_3mf", "3mf", "DETECT", _3mf_missing_model_part),
    "3mf-malformed-transform": ("verify_export_3mf", "3mf", "DETECT", _3mf_malformed_transform),
    "3mf-missing-triangle": ("verify_export_3mf", "3mf", "DETECT", _3mf_missing_triangle),
    "3mf-corrupt-vertex": ("verify_export_3mf", "3mf", "DETECT", _3mf_corrupt_vertex),
    "3mf-duplicated-triangle": ("verify_export_3mf", "3mf", "DETECT", _3mf_duplicated_triangle),
    "3mf-vertex-index-out-of-range": (
        "verify_export_3mf",
        "3mf",
        "DETECT",
        _3mf_vertex_index_out_of_range,
    ),
    "3mf-second-non-manifold-object": (
        "verify_export_3mf",
        "3mf",
        "DETECT",
        _3mf_second_non_manifold_object,
    ),
    "3mf-clean-control": ("verify_export_3mf", "3mf", "PASS_CLEAN", _clean_3mf),
    "step-dropped-solid": ("verify_export_step", "step", "DETECT", _step_dropped_solid),
    "step-unit-lie": ("verify_export_step", "step", "DETECT", _step_unit_lie),
    "step-shell-no-solid": ("verify_export_step", "step", "DETECT", _step_shell_no_solid),
    "step-unrefined-fuse": ("verify_export_step", "step", "DETECT", _step_unrefined_fuse),
    "step-cut-notch": ("verify_export_step", "step", "DETECT", _step_cut_notch),
    "step-fused-overlap": ("verify_export_step", "step", "DETECT", _step_fused_overlap),
    "step-compsolid": ("verify_export_step", "step", "DETECT", _step_compsolid),
    "step-loose-face": ("verify_export_step", "step", "DETECT", _step_loose_face),
    "step-open-shell": ("verify_export_step", "step", "DETECT", _step_open_shell),
    "step-scaled-half-box": ("verify_export_step", "step", "DETECT", _step_scaled_half_box),
    "step-clean-control": ("verify_export_step", "step", "PASS_CLEAN", _clean_step),
}


def _reference_source(case_id: str) -> dict:
    """Return the reference (correct-shape) source facts a verifier compares the file against.

    The reference is what a CORRECT export of the intended part yields; the fixture deviates
    from it. ``step-dropped-solid`` intends a two-solid compound; ``stl-truncated-coordinates``
    intends the cylinder; every other case intends the clean box-10-20-30 (``step-unit-lie`` and
    ``step-scaled-half-box`` both intend it at full scale).
    """
    if case_id == "step-dropped-solid":
        compound = Part.makeCompound(
            [Part.makeBox(10, 20, 30), Part.makeBox(10, 20, 30, App.Vector(20, 0, 0))]
        )
        return _source_facts(compound)
    if case_id == "stl-truncated-coordinates":
        return _source_facts(_cylinder_shape())
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
        f"  area: {source['area']}\n"
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
