"""In-FreeCAD export writers and their FreeCAD-side verification legs.

``export_step``/``export_stl``/``export_3mf`` write a document's shape to disk and always
report ``verified: false`` — an export is done only once its paired ``verify_export_*`` passes
(AD-9). STL and 3MF share a single ``MeshPart.meshFromShape`` tessellation (linear AND angular
deflection, #25311) so the two formats can never diverge. Each writer mints an ``export_id``
and records the path, source document handle, format, tessellation parameters, and source shape
facts in the ``ExportRegistry`` so the paired verifier can compare the re-read file against the
recorded source.

``verify_export_step`` re-imports the written STEP into a fresh ``FCB_TMP_`` document and grades
volume (±0.1 %), ``isValid``, and face/edge/solid counts against the recorded source, closing
the temp document in a ``finally``. It also reads the written header's ``FILE_SCHEMA`` against
the recorded application protocol. ``export_self_read_stl``/``export_self_read_3mf`` re-read a
written mesh and return facet/vertex/bbox facts with no verdict — the third-party oracle legs
and verdict assembly live in ``adapters`` and are merged by the host handler.

Stdlib + FreeCAD App modules only.
"""

from __future__ import annotations

import math
import os
import re
import secrets
import zipfile
from xml.sax.saxutils import escape

from freecad_buddy.contracts import (
    ResultEnvelope,
    derive_verdict,
    displayed_deviation,
    summary_text,
)
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_STEP_VOLUME_REL = 0.001
_STEP_VOLUME_ABS_FLOOR = 1e-6
_DEFAULT_LINEAR = 0.1
_DEFAULT_ANGULAR = 0.5
_MIN_DEFLECTION = 1e-4
_MESH_BAND_ABS_FLOOR = 1e-6
_STEP_FILE_SCHEMAS = {
    "AP242": "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF",
    "AP214": "AUTOMOTIVE_DESIGN",
    "AP203": "CONFIG_CONTROL_DESIGN",
}
_FILE_SCHEMA_IDENTIFIER = re.compile(r"FILE_SCHEMA\s*\(\s*\(\s*'\s*([A-Za-z0-9_]+)")
_3MF_MODEL_PART = "3D/3dmodel.model"
_3MF_CONTENT_TYPES_PART = "[Content_Types].xml"
_3MF_OBJECT_TAG = re.compile(r'<object id="(\d+)" type="(model|surface)">')
_LINK_PROPERTY_TYPES = frozenset(
    {
        "App::PropertyLink",
        "App::PropertyLinkList",
        "App::PropertyLinkSub",
        "App::PropertyLinkSubList",
    }
)
# Input links whose result contains the target: a boolean's operands, the sections of a loft or
# sweep, an extrusion's base, a Body's or Part's members.
_CONSUMING_LINKS = frozenset(
    {"Base", "Tool", "Shapes", "Sections", "Spine", "Group", "BaseFeature"}
)
_ATTRIBUTE_ESCAPES = {'"': "&quot;"}
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f]")
_CONTENT_TYPE_DEFAULT = re.compile(
    r"[ \t]*<Default\b[^>]*?\bExtension=\"([^\"]*)\"[^>]*/>[ \t]*\r?\n?"
)
_STEP_PRODUCT = re.compile(r"PRODUCT\('(?:[^']|'')*','((?:[^']|'')*)'")


class ExportRegistry:
    """Maps a minted ``export_id`` to the record its paired ``verify_export_*`` looks up.

    Each record carries the written path, the source document handle, the format, the
    tessellation parameters, and the source shape facts. An unknown ``export_id`` raises
    ``ValidationError`` so the dispatch boundary maps it to ``INVALID_INPUT``.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}

    def _mint_id(self) -> str:
        return f"fcb-export:{secrets.token_urlsafe(16)}"

    def record(self, entry: dict) -> str:
        """Store ``entry`` under a freshly minted ``export_id`` and return that id."""
        export_id = self._mint_id()
        self._by_id[export_id] = entry
        return export_id

    def resolve(self, export_id: str | None, doc: str | None) -> dict:
        """Return the record for ``export_id``, checking it belongs to ``doc``, or raise."""
        if not export_id:
            raise ValidationError("missing required 'export_id'")
        entry = self._by_id.get(export_id)
        if entry is None:
            raise ValidationError(f"unknown or stale export_id: {export_id}")
        if doc is not None and entry["doc"] != doc:
            raise ValidationError(f"export_id {export_id} does not belong to document {doc}")
        return entry


def _resolve_export_objects(document: object, objects: list | None) -> list:
    """Return the objects to export, or raise ``ValidationError``.

    Named ``objects`` resolve in order with repeated names collapsed. With no selection the
    export covers every visible solid object that no other such object consumes: the inputs of a
    boolean and the features of a Body are covered by the boolean and the Body that use them. An
    object is visible when it and every Body or Part that holds it is visible, because hiding a
    group in the GUI leaves its children's own flag set. A document that holds exactly one object
    exports it whatever its visibility.
    """
    if objects:
        resolved = []
        for name in dict.fromkeys(objects):
            obj = document.getObject(name)
            if obj is None:
                raise ValidationError(f"unknown object: {name}")
            resolved.append(obj)
        return resolved
    if not document.Objects:
        raise ValidationError("document has no objects to export")
    if len(document.Objects) == 1:
        return list(document.Objects)
    candidates = [obj for obj in document.Objects if _is_visible_solid(obj)]
    consumed = {inner.Name for obj in candidates for inner in _shape_inputs(obj)}
    exported = [obj for obj in candidates if obj.Name not in consumed]
    if not exported:
        raise ValidationError("document has no visible solid objects to export")
    return exported


def _shape_inputs(obj: object) -> list:
    """Return the objects ``obj`` contains: the targets of its input link properties.

    Only the links that name an input the result contains count (see ``_CONSUMING_LINKS``). An
    attachment target, an expression reference and the ``Source`` of a mirror are not inputs: the
    object they point at still exports on its own.
    """
    inputs: list = []
    for name in obj.PropertiesList:
        if name in _CONSUMING_LINKS and obj.getTypeIdOfProperty(name) in _LINK_PROPERTY_TYPES:
            inputs.extend(_linked_objects(getattr(obj, name)))
    return inputs


def _linked_objects(value: object) -> list:
    """Flatten a link property value (object, list, or ``(object, subnames)`` pair) to objects."""
    if isinstance(value, (list, tuple)):
        return [obj for item in value for obj in _linked_objects(item)]
    return [value] if hasattr(value, "TypeId") else []


def _is_visible_solid(obj: object) -> bool:
    """Whether ``obj`` is shown, with every group above it, and its shape holds a solid."""
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull() or not _is_shown(obj):
        return False
    return len(shape.Solids) > 0


def _is_shown(obj: object) -> bool:
    """Whether ``obj`` and every Body or Part that holds it have ``Visibility`` set."""
    if not getattr(obj, "Visibility", True):
        return False
    group = obj.getParentGeoFeatureGroup()
    while group is not None:
        if not group.Visibility:
            return False
        group = group.getParentGeoFeatureGroup()
    return True


def _require_shape(obj: object):
    """Return ``obj.Shape`` or raise ``ValidationError`` when it is null/absent."""
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        raise ValidationError(f"object has no shape: {obj.Name}")
    return shape


def _source_facts(shape: object, is_mm: bool) -> dict:
    """Return the recorded source shape facts a verifier compares the re-read file against."""
    bb = shape.BoundBox
    return {
        "volume": float(shape.Volume),
        "area": float(shape.Area),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "solids": len(shape.Solids),
        "bbox": [bb.XLength, bb.YLength, bb.ZLength],
        "is_mm": is_mm,
    }


def _selected_shapes(objs: list) -> list:
    """Return the shape of each object to write.

    One object keeps its shape. With several objects each object needs a solid, and the shape to
    write is its solids alone: a loose face or wire would become a product with no solid, and
    the recorded facts and every written file then describe the same geometry.
    """
    shapes = [_require_shape(obj) for obj in objs]
    if len(objs) == 1:
        return shapes
    solid_shapes = []
    for obj, shape in zip(objs, shapes):
        solids = shape.Solids
        if not solids:
            raise ValidationError(f"object has no solid: {obj.Name}")
        solid_shapes.append(solids[0] if len(solids) == 1 else _one_shape(solids))
    return solid_shapes


def _one_shape(shapes: list):
    """Return the only shape, or a compound of all of them."""
    if len(shapes) == 1:
        return shapes[0]
    import Part

    return Part.makeCompound(shapes)


def _selection_facts(objs: list, shapes: list, is_mm: bool) -> dict:
    """Return the source facts of the selection: the shape's facts, plus ``objects`` for several.

    Several objects are one compound for the totals, and each object also keeps its own facts so
    a verifier can grade it alone. A one-object selection has the facts it always had.
    """
    facts = _source_facts(_one_shape(shapes), is_mm)
    if len(shapes) == 1:
        return facts
    facts["objects"] = [
        {"name": obj.Name, "label": obj.Label, **_source_facts(shape, is_mm)}
        for obj, shape in zip(objs, shapes)
    ]
    # A compound counts a sub-shape two selected objects share once, but each re-imported product
    # holds its own copy, so the totals a verifier compares are the sums over the objects.
    for key in ("faces", "edges", "solids"):
        facts[key] = sum(entry[key] for entry in facts["objects"])
    return facts


def _is_mm(document: object) -> bool:
    """Whether the document's length unit schema is millimetres (internal unit, default True).

    FreeCAD stores geometry in millimetres internally; only the display schema differs. The
    bridge always writes millimetres, so this records that the source is mm for the unit-lie
    guard rather than inferring from a display preference.
    """
    return True


def export_step(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    path: str | None = None,
    objects: list | None = None,
    ap: str = "AP242",
) -> ResultEnvelope:
    """Write document objects to a STEP file with unit and schema pinned per call.

    Pins ``write.step.unit=MM`` and ``write.step.schema`` to ``ap`` through the shim, exports the
    resolved objects (one object through its ``Shape``, several as one product per object named
    by its ``Label``; no selection means every visible solid), restores both statics whether or
    not the write raised, and records the source facts under a minted ``export_id``.
    The result carries ``{export_id, path, bytes, verified: false, objects}``; the export is done
    only once ``verify_export_step`` passes. A missing path, unknown object, or null shape raises
    ``ValidationError``.
    """

    def write(handle: str, document: object) -> ResultEnvelope:
        if not path:
            raise ValidationError("export_step requires a 'path'")
        objs = _resolve_export_objects(document, objects)
        shapes = _selected_shapes(objs)
        previous_unit = shim.pin_step_config(ap)
        try:
            if len(objs) == 1:
                shapes[0].exportStep(path)
            else:
                step_names = shim.export_step_objects(
                    [(obj.Label, shape) for obj, shape in zip(objs, shapes)], path
                )
        finally:
            shim.restore_step_config(previous_unit)
        facts = _selection_facts(objs, shapes, _is_mm(document))
        if len(objs) > 1:
            for entry, name in zip(facts["objects"], step_names):
                entry["step_name"] = name
        export_id = export_registry.record(
            {
                "path": path,
                "doc": handle,
                "format": "step",
                "ap": ap,
                "source": facts,
            }
        )
        structured = {
            "export_id": export_id,
            "path": path,
            "bytes": os.path.getsize(path),
            "verified": False,
            "objects": [obj.Name for obj in objs],
        }
        return _ok_envelope(
            structured, summarize_export({"format": "STEP", "verdict": "written", "path": path})
        )

    return registry.with_document(doc, write)


def _mesh_export(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    fmt: str,
    doc: str | None,
    path: str | None,
    objects: list | None,
    linear: float | None,
    angular: float | None,
) -> ResultEnvelope:
    """Tessellate the resolved objects once and write them to ``path`` in ``fmt`` (``stl``/``3mf``).

    A single ``MeshPart.meshFromShape`` (linear AND angular deflection) is the one tessellation
    source; the ``Mesh.MeshObject`` is written with its extension driving the format. Records the
    tessellation parameters and source facts under a minted ``export_id``.
    """
    lin = _DEFAULT_LINEAR if linear is None else float(linear)
    ang = _DEFAULT_ANGULAR if angular is None else float(angular)
    if not math.isfinite(lin) or not math.isfinite(ang) or lin < _MIN_DEFLECTION or ang <= 0.0:
        raise ValidationError(
            f"deflection out of range: finite linear>={_MIN_DEFLECTION} and finite angular>0 "
            f"required, got linear={lin}, angular={ang}"
        )

    def write(handle: str, document: object) -> ResultEnvelope:
        import MeshPart

        if not path:
            raise ValidationError(f"export_{fmt} requires a 'path'")
        objs = _resolve_export_objects(document, objects)
        shapes = _selected_shapes(objs)
        # STL merges the selection into one mesh; 3MF keeps one mesh object per input object.
        per_object = fmt == "3mf" and len(objs) > 1
        pieces = shapes if per_object else [_one_shape(shapes)]

        def tessellate(piece: object):
            return MeshPart.meshFromShape(
                Shape=piece, LinearDeflection=lin, AngularDeflection=ang, Relative=False
            )

        meshes = [tessellate(piece) for piece in pieces]
        if any(int(mesh.CountFacets) == 0 for mesh in meshes):
            raise ValidationError("tessellation produced no facets; nothing to export")
        facets = sum(int(mesh.CountFacets) for mesh in meshes)
        vertices = sum(int(mesh.CountPoints) for mesh in meshes)
        if per_object:
            shim.export_meshes(meshes, path)
            try:
                _name_3mf_objects(path, [obj.Label for obj in objs])
            except Exception:
                os.remove(path)
                raise
        else:
            meshes[0].write(path)
        facet_counts = None
        if fmt == "stl" and len(objs) > 1:
            # The STL holds no object boundaries. The per-object facet counts let a verifier
            # weld vertices inside one object only: objects that touch share positions, and a
            # weld across them reads as a non-manifold edge. Counts that do not add up to the
            # written mesh are not usable and are not recorded.
            counts = [int(tessellate(shape).CountFacets) for shape in shapes]
            facet_counts = counts if sum(counts) == facets else None
        facts = _selection_facts(objs, shapes, _is_mm(document))
        export_id = export_registry.record(
            {
                "path": path,
                "doc": handle,
                "format": fmt,
                "tess": {"linear": lin, "angular": ang},
                "facets": facets,
                "vertices": vertices,
                "facet_counts": facet_counts,
                "source": facts,
            }
        )
        structured = {
            "export_id": export_id,
            "path": path,
            "bytes": os.path.getsize(path),
            "facets": facets,
            "verified": False,
            "objects": [obj.Name for obj in objs],
        }
        return _ok_envelope(
            structured,
            summarize_export({"format": fmt.upper(), "verdict": "written", "path": path}),
        )

    return registry.with_document(doc, write)


def export_stl(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    path: str | None = None,
    objects: list | None = None,
    linear: float | None = None,
    angular: float | None = None,
) -> ResultEnvelope:
    """Write document objects to a binary STL, merged into one mesh, from a single tessellation.

    Shares its ``MeshPart.meshFromShape`` call shape with ``export_3mf`` so the two formats
    never diverge. The result carries ``{export_id, path, bytes, facets, verified: false}``.
    """
    return _mesh_export(registry, export_registry, "stl", doc, path, objects, linear, angular)


def export_3mf(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    path: str | None = None,
    objects: list | None = None,
    linear: float | None = None,
    angular: float | None = None,
) -> ResultEnvelope:
    """Write document objects to a 3MF, one mesh object per object, from a single tessellation.

    Shares its ``MeshPart.meshFromShape`` call shape with ``export_stl``. The result carries
    ``{export_id, path, bytes, facets, verified: false}``.
    """
    return _mesh_export(registry, export_registry, "3mf", doc, path, objects, linear, angular)


def _name_3mf_objects(path: str, labels: list[str]) -> None:
    """Add ``name="<label>"`` to each ``<object>`` of a written 3MF, in order.

    FreeCAD's 3MF writer ignores object names (``Exporter3MF::addMesh`` discards them), so the
    names are added to the model part after the write. Every other archive part is copied
    unchanged, except that repeated ``Default`` content types are reduced to one per extension.
    Raises ``RuntimeError`` when the file has no model part or its object count
    differs from ``labels``: the file is then not what the writer was expected to produce.
    """
    with zipfile.ZipFile(path) as archive:
        parts = [(info, archive.read(info.filename)) for info in archive.infolist()]
    if all(info.filename != _3MF_MODEL_PART for info, _data in parts):
        raise RuntimeError(f"3MF has no {_3MF_MODEL_PART} part")
    rewritten = f"{path}.named"
    try:
        with zipfile.ZipFile(rewritten, "w") as target:
            for info, data in parts:
                if info.filename == _3MF_MODEL_PART:
                    data = _name_model_objects(data.decode("utf-8"), labels).encode("utf-8")
                elif info.filename == _3MF_CONTENT_TYPES_PART:
                    data = _unique_content_types(data.decode("utf-8")).encode("utf-8")
                target.writestr(info, data, compress_type=info.compress_type)
        os.replace(rewritten, path)
    finally:
        if os.path.exists(rewritten):
            os.remove(rewritten)


def _unique_content_types(content_types_xml: str) -> str:
    """Return ``content_types_xml`` with one ``Default`` entry per file extension.

    The GUI writer adds a thumbnail per mesh and writes one ``Default Extension="png"`` entry per
    thumbnail, and lib3mf refuses a file that declares a content type twice. The first entry of
    an extension stays.
    """
    seen: set[str] = set()

    def keep(match: re.Match) -> str:
        extension = match.group(1).lower()
        if extension in seen:
            return ""
        seen.add(extension)
        return match.group(0)

    return _CONTENT_TYPE_DEFAULT.sub(keep, content_types_xml)


def three_mf_object_name(label: str) -> str:
    """Return the object name written to a 3MF for ``label``.

    XML cannot carry a control character in a name, and lib3mf refuses every numeric character
    reference, so each control character (tab and newline included) becomes a space.
    """
    return _CONTROL_CHARACTERS.sub(" ", label)


def _attribute(text: str) -> str:
    """Return ``text`` escaped for a double-quoted XML attribute value."""
    return escape(three_mf_object_name(text), _ATTRIBUTE_ESCAPES)


def _name_model_objects(model_xml: str, labels: list[str]) -> str:
    """Return ``model_xml`` with the ``i``-th ``<object>`` tag named ``labels[i]``."""
    found = _3MF_OBJECT_TAG.findall(model_xml)
    if len(found) != len(labels):
        raise RuntimeError(f"3MF holds {len(found)} objects for {len(labels)} selected")
    names = iter(labels)
    return _3MF_OBJECT_TAG.sub(
        lambda match: (
            f'<object id="{match.group(1)}" type="{match.group(2)}" '
            f'name="{_attribute(next(names))}">'
        ),
        model_xml,
    )


def mesh_volume_band(linear: float, area: float) -> float:
    """Return the absolute mesh-volume tolerance derived from the tessellation deflection.

    Chordal tessellation replaces curved faces with flat facets that sit at most ``linear`` below
    the true surface; averaged over a chord the sag is ``(2/3) * linear``, so the volume the
    facets enclose falls short of the solid by at most ``(2/3) * linear * area``. This bounds the
    deficit for doubly-curved surfaces (spheres) that a bbox-relative band underestimates, while
    staying far tighter than the STEP ±0.1 %. A small absolute floor keeps a zero-area edge case
    non-degenerate.
    """
    return max((2.0 / 3.0) * abs(float(linear)) * abs(float(area)), _MESH_BAND_ABS_FLOOR)


def verify_export_step(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    export_id: str | None = None,
) -> ResultEnvelope:
    """Re-import a written STEP with a fresh reader and grade it against the recorded source.

    Reads the file into a fresh ``Part.Shape`` (independent reader state), checks volume within
    ±0.1 %, ``isValid``, and face/edge/solid counts equal to the recorded source, and checks the
    file's ``FILE_SCHEMA`` names the recorded application protocol. An unknown
    ``export_id``/``doc``, or an ``export_id`` for a non-STEP export, raises ``ValidationError``.
    """

    def read(handle: str, _document: object) -> ResultEnvelope:
        import Part

        entry = export_registry.resolve(export_id, handle)
        if entry["format"] != "step":
            raise ValidationError(f"export_id {export_id} is not a step export")
        source = entry["source"]
        if "objects" in source:
            leaves = shim.read_step_leaves(entry["path"])
            checks = _grade_step_measure(_leaf_measure(leaves), source)
            checks.extend(_object_volume_checks(leaves, source["objects"]))
            checks.append(_object_names_check(entry["path"], source["objects"]))
        else:
            reimported = Part.Shape()
            reimported.read(entry["path"])
            checks = _step_checks(reimported, source)
        checks.append(_schema_check(entry["path"], entry["ap"]))
        report = {
            "subject": {"export_id": export_id, "path": entry["path"]},
            "checks": checks,
            "format": "step",
        }
        return _finish(report)

    return registry.with_document(doc, read)


def _shape_measure(shape: object) -> dict:
    """Return the measurements ``_step_checks`` grades, taken from one re-imported shape."""
    return {
        "volume": float(shape.Volume),
        "valid": bool(shape.isValid()),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "solids": len(shape.Solids),
    }


def _leaf_measure(leaves: list[dict]) -> dict:
    """Return the same measurements summed over the products of a multi-object re-import."""
    return {
        "volume": sum(leaf["volume"] for leaf in leaves),
        "valid": all(leaf["valid"] for leaf in leaves),
        "faces": sum(leaf["faces"] for leaf in leaves),
        "edges": sum(leaf["edges"] for leaf in leaves),
        "solids": sum(leaf["solids"] for leaf in leaves),
    }


def _volume_check(check_id: str, measured_volume: float, expected_volume: float) -> dict:
    """Return the check that ``measured_volume`` is within ±0.1 % of ``expected_volume``."""
    band = max(abs(expected_volume) * _STEP_VOLUME_REL, _STEP_VOLUME_ABS_FLOOR)
    deviation = displayed_deviation(measured_volume, expected_volume, shim.display_decimals())
    return {
        "id": check_id,
        "measured": measured_volume,
        "expected": expected_volume,
        "tolerance": {"rel": _STEP_VOLUME_REL},
        "passed": deviation <= band,
        "detail": {
            "message": (
                f"|{shim.displayed(measured_volume)} - {shim.displayed(expected_volume)}| "
                f"= {deviation} <= {band:g}"
            )
        },
    }


def _object_volume_checks(leaves: list[dict], objects: list[dict]) -> list[dict]:
    """Return one volume check per source object, matched to the re-imported products in order.

    FreeCAD splits an object that holds several solids into one product per solid, so each
    object takes products in file order until their solid count reaches the recorded count. An
    object the products cannot fill, or products left over, fail ``export_step.objects_matched``.
    """
    checks = []
    cursor = 0
    all_matched = True
    for entry in objects:
        solids = 0
        volume = 0.0
        while solids < entry["solids"] and cursor < len(leaves):
            solids += leaves[cursor]["solids"]
            volume += leaves[cursor]["volume"]
            cursor += 1
        matched = solids == entry["solids"]
        all_matched = all_matched and matched
        check = _volume_check(f"export_step.object_volume:{entry['name']}", volume, entry["volume"])
        check["passed"] = check["passed"] and matched
        check["detail"]["message"] = f"{entry['label']}: {check['detail']['message']}"
        checks.append(check)
    all_matched = all_matched and cursor == len(leaves)
    checks.append(
        {
            "id": "export_step.objects_matched",
            "measured": len(leaves),
            "expected": sum(entry["solids"] for entry in objects),
            "tolerance": None,
            "passed": all_matched,
            "detail": {"message": f"{len(leaves)} products for {len(objects)} objects"},
        }
    )
    return checks


def _object_names_check(path: str, objects: list[dict]) -> dict:
    """Return the check that the file names a product after every object's ``Label``.

    The names come from the written file, never from the writer's return value. The file may hold
    more products than objects (a multi-solid object, the root of the scratch document).
    """
    with open(path, encoding="utf-8", errors="replace") as handle:
        written = {
            match.replace("''", "'").replace("\\\\", "\\")
            for match in _STEP_PRODUCT.findall(handle.read())
        }
    expected = [entry["step_name"] for entry in objects]
    missing = [name for name in expected if name not in written]
    return {
        "id": "export_step.object_names",
        "measured": sorted(written),
        "expected": expected,
        "tolerance": None,
        "passed": not missing,
        "detail": {"message": f"missing product names: {missing}" if missing else "all named"},
    }


def _step_checks(shape: object, source: dict) -> list[dict]:
    """Return the STEP round-trip checks of one re-imported shape against ``source``."""
    return _grade_step_measure(_shape_measure(shape), source)


def _grade_step_measure(measured: dict, source: dict) -> list[dict]:
    """Return the STEP round-trip checks: volume ±0.1 %, isValid, exact topology counts."""
    is_valid = measured["valid"]
    counts = {k: measured[k] for k in ("faces", "edges", "solids")}
    counts_ok = all(counts[k] == source[k] for k in ("faces", "edges", "solids"))

    return [
        _volume_check("export_step.volume", measured["volume"], float(source["volume"])),
        {
            "id": "export_step.valid",
            "measured": is_valid,
            "expected": True,
            "tolerance": None,
            "passed": is_valid,
            "detail": {"message": f"isValid() {is_valid}"},
        },
        {
            "id": "export_step.topology_counts",
            "measured": counts,
            "expected": {k: source[k] for k in ("faces", "edges", "solids")},
            "tolerance": None,
            "passed": counts_ok,
            "detail": {
                "message": (
                    f"faces {counts['faces']} vs {source['faces']}, "
                    f"edges {counts['edges']} vs {source['edges']}, "
                    f"solids {counts['solids']} vs {source['solids']}"
                )
            },
        },
    ]


def _read_file_schema(path: str) -> str | None:
    """Return the first identifier of the STEP header's ``FILE_SCHEMA``, or ``None`` when absent.

    Only the header is read: the text before ``DATA;``. The entry may span several lines.
    """
    header: list[str] = []
    with open(path, encoding="ascii", errors="replace") as handle:
        for line in handle:
            before, data_found, _ = line.partition("DATA;")
            header.append(before)
            if data_found:
                break
    match = _FILE_SCHEMA_IDENTIFIER.search("".join(header))
    return match.group(1) if match else None


def _schema_check(path: str, ap: str) -> dict:
    """Return the check that the written file's ``FILE_SCHEMA`` names the schema of ``ap``."""
    measured = _read_file_schema(path)
    expected = _STEP_FILE_SCHEMAS[ap]
    return {
        "id": "export_step.schema",
        "measured": measured,
        "expected": expected,
        "tolerance": None,
        "passed": measured == expected,
        "detail": {"message": f"FILE_SCHEMA {measured} vs {expected} for {ap}"},
    }


def _self_read(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    fmt: str,
    doc: str | None,
    export_id: str | None,
) -> ResultEnvelope:
    """Re-read a written mesh in FreeCAD and return facet/vertex/bbox facts plus the banner.

    No verdict is derived here — the facts and banner are merged with the third-party oracle
    legs by the host handler. Returns the source facts and tessellation band alongside the
    self-read facts so the verdict assembler needs no FreeCAD import.
    """

    def read(handle: str, _document: object) -> ResultEnvelope:
        import Mesh

        entry = export_registry.resolve(export_id, handle)
        if entry["format"] != fmt:
            raise ValidationError(f"export_id {export_id} is not a {fmt} export")
        source = entry["source"]
        band = mesh_volume_band(entry["tess"]["linear"], source["area"])
        try:
            mesh = Mesh.Mesh(entry["path"])
        except Exception as exc:  # noqa: BLE001 - a missing/corrupt export file is a FAIL, not a crash
            self_read = {"readable": False, "error": str(exc)}
        else:
            bb = mesh.BoundBox
            self_read = {
                "readable": True,
                "facets": int(mesh.CountFacets),
                "vertices": int(mesh.CountPoints),
                "bbox": [bb.XLength, bb.YLength, bb.ZLength],
            }
        structured = {
            "self_read": self_read,
            "recorded": {
                "facets": entry["facets"],
                "vertices": entry["vertices"],
            },
            "source": source,
            "tess": entry["tess"],
            "volume_band": band,
            "path": entry["path"],
            "banner": _banner(),
        }
        if entry.get("facet_counts"):
            structured["facet_counts"] = entry["facet_counts"]
        if fmt == "3mf" and "objects" in source:
            structured["objects"] = [
                {
                    "name": obj["name"],
                    "label": obj["label"],
                    "file_name": three_mf_object_name(obj["label"]),
                    "volume": obj["volume"],
                    "band": mesh_volume_band(entry["tess"]["linear"], obj["area"]),
                }
                for obj in source["objects"]
            ]
        return _ok_envelope(structured)

    return registry.with_document(doc, read)


def export_self_read_stl(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    export_id: str | None = None,
) -> ResultEnvelope:
    """FreeCAD self-read leg for an STL export: facet/vertex/bbox facts, no verdict."""
    return _self_read(registry, export_registry, "stl", doc, export_id)


def export_self_read_3mf(
    registry: DocumentRegistry,
    export_registry: ExportRegistry,
    doc: str | None = None,
    export_id: str | None = None,
) -> ResultEnvelope:
    """FreeCAD self-read leg for a 3MF export: facet/vertex/bbox facts, no verdict."""
    return _self_read(registry, export_registry, "3mf", doc, export_id)


def _banner() -> dict:
    """Return the report banner: FreeCAD version and element-map version (int or None)."""
    return {
        "freecad_version": shim.freecad_version(),
        "element_map_version": shim.element_map_version(),
    }


def _failure_detail(report: dict) -> dict:
    """Build the envelope ``ErrorDetail`` from the report's failed checks."""
    failed = [c for c in report.get("checks", []) if not c.get("passed")]
    ids = [c.get("id") for c in failed]
    return {
        "code": report["verdict"],
        "message": "; ".join(str(i) for i in ids) or report["verdict"],
        "objects": [],
    }


def _report_envelope(report: dict) -> ResultEnvelope:
    """Wrap a ValidationReport as a ResultEnvelope whose status mirrors the derived verdict."""
    verdict = report["verdict"]
    subject = report.get("subject") or {}
    path = subject.get("path", "?")
    fmt = report.get("format", "export")
    return {
        "schema": "fcb.result-envelope/1",
        "status": verdict,
        "detail": None if verdict == "OK" else _failure_detail(report),
        "structured_content": report,
        "text": summarize_export({"format": fmt.upper(), "verdict": verdict, "path": path}),
    }


def _finish(report: dict) -> ResultEnvelope:
    """Attach schema/banner, derive the verdict, and wrap the report in an envelope."""
    report["schema"] = "fcb.validation-report/1"
    report["banner"] = _banner()
    report["verdict"] = derive_verdict(report)
    return _report_envelope(report)


def summarize_export(sc: dict) -> str:
    """One-line summary of an export write or verify result."""
    fmt = sc.get("format") or sc.get("fmt") or "?"
    verdict = sc.get("verdict", "written")
    path = sc.get("path", "?")
    return f"{fmt} export {verdict} -> {path}."


def _ok_envelope(structured: dict, summary: str | None = None) -> ResultEnvelope:
    """Wrap a plain structured payload as an ``OK`` ResultEnvelope."""
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summary if summary is not None else summary_text(structured),
    }
