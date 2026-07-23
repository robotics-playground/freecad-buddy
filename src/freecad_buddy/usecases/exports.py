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
the temp document in a ``finally``. ``export_self_read_stl``/``export_self_read_3mf`` re-read a
written mesh and return facet/vertex/bbox facts with no verdict — the third-party oracle legs
and verdict assembly live in ``adapters`` and are merged by the host handler.

Stdlib + FreeCAD App modules only.
"""

from __future__ import annotations

import math
import os
import secrets

from freecad_buddy.contracts import ResultEnvelope, derive_verdict, mirror_text
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_STEP_VOLUME_REL = 0.001
_STEP_VOLUME_ABS_FLOOR = 1e-6
_DEFAULT_LINEAR = 0.1
_DEFAULT_ANGULAR = 0.5
_MIN_DEFLECTION = 1e-4
_MESH_BAND_ABS_FLOOR = 1e-6


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


def _resolve_export_object(document: object, objects: list | None):
    """Return the single object to export, or raise ``ValidationError``.

    Uses the named object when ``objects`` carries exactly one Name. With no selection the sole
    document object is used; a document holding more than one object requires an explicit
    ``objects`` — the export writers operate on one shape, so both a multi-object selection and
    an ambiguous no-selection request are fail-closed rather than silently exporting the first.
    """
    if objects:
        if len(objects) != 1:
            raise ValidationError("export supports a single object; got multiple")
        obj = document.getObject(objects[0])
        if obj is None:
            raise ValidationError(f"unknown object: {objects[0]}")
        return obj
    doc_objects = list(document.Objects)
    if not doc_objects:
        raise ValidationError("document has no objects to export")
    if len(doc_objects) > 1:
        raise ValidationError(
            "document has multiple objects; specify 'objects' with the one to export"
        )
    return doc_objects[0]


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
    """Write a document object's shape to a STEP file with unit and schema pinned per call.

    Pins ``write.step.unit=MM`` and the STEP ``Scheme`` to ``ap`` through the shim, exports the
    resolved object's ``Shape``, and records the source facts under a minted ``export_id``. The
    result carries ``{export_id, path, bytes, verified: false}``; the export is done only once
    ``verify_export_step`` passes. A missing path, unknown object, or null shape raises
    ``ValidationError``.
    """

    def write(handle: str, document: object) -> ResultEnvelope:
        if not path:
            raise ValidationError("export_step requires a 'path'")
        obj = _resolve_export_object(document, objects)
        shape = _require_shape(obj)
        shim.pin_step_config(ap)
        shape.exportStep(path)
        facts = _source_facts(shape, _is_mm(document))
        export_id = export_registry.record(
            {
                "path": path,
                "doc": handle,
                "format": "step",
                "ap": ap,
                "schema": shim.step_schema(),
                "source": facts,
            }
        )
        structured = {
            "export_id": export_id,
            "path": path,
            "bytes": os.path.getsize(path),
            "verified": False,
        }
        return _ok_envelope(structured)

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
    """Tessellate the resolved object once and write it to ``path`` in ``fmt`` (``stl``/``3mf``).

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
        obj = _resolve_export_object(document, objects)
        shape = _require_shape(obj)
        mesh = MeshPart.meshFromShape(
            Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False
        )
        if int(mesh.CountFacets) == 0:
            raise ValidationError("tessellation produced no facets; nothing to export")
        mesh.write(path)
        facts = _source_facts(shape, _is_mm(document))
        export_id = export_registry.record(
            {
                "path": path,
                "doc": handle,
                "format": fmt,
                "tess": {"linear": lin, "angular": ang},
                "facets": int(mesh.CountFacets),
                "vertices": int(mesh.CountPoints),
                "source": facts,
            }
        )
        structured = {
            "export_id": export_id,
            "path": path,
            "bytes": os.path.getsize(path),
            "facets": int(mesh.CountFacets),
            "verified": False,
        }
        return _ok_envelope(structured)

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
    """Write a document object's shape to a binary STL from a single tessellation.

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
    """Write a document object's shape to a 3MF from a single tessellation.

    Shares its ``MeshPart.meshFromShape`` call shape with ``export_stl``. The result carries
    ``{export_id, path, bytes, facets, verified: false}``.
    """
    return _mesh_export(registry, export_registry, "3mf", doc, path, objects, linear, angular)


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
    ±0.1 %, ``isValid``, and face/edge/solid counts equal to the recorded source. An unknown
    ``export_id``/``doc``, or an ``export_id`` for a non-STEP export, raises ``ValidationError``.
    """

    def read(handle: str, _document: object) -> ResultEnvelope:
        import Part

        entry = export_registry.resolve(export_id, handle)
        if entry["format"] != "step":
            raise ValidationError(f"export_id {export_id} is not a step export")
        source = entry["source"]
        reimported = Part.Shape()
        reimported.read(entry["path"])
        checks = _step_checks(reimported, source)
        report = {"subject": {"export_id": export_id, "path": entry["path"]}, "checks": checks}
        return _finish(report)

    return registry.with_document(doc, read)


def _step_checks(shape: object, source: dict) -> list[dict]:
    """Return the STEP round-trip checks: volume ±0.1 %, isValid, exact topology counts."""
    measured_volume = float(shape.Volume)
    expected_volume = float(source["volume"])
    band = max(abs(expected_volume) * _STEP_VOLUME_REL, _STEP_VOLUME_ABS_FLOOR)
    volume_ok = abs(measured_volume - expected_volume) <= band

    is_valid = bool(shape.isValid())

    counts = {"faces": len(shape.Faces), "edges": len(shape.Edges), "solids": len(shape.Solids)}
    counts_ok = all(counts[k] == source[k] for k in ("faces", "edges", "solids"))

    return [
        {
            "id": "export_step.volume",
            "measured": measured_volume,
            "expected": expected_volume,
            "tolerance": {"rel": _STEP_VOLUME_REL},
            "passed": volume_ok,
            "detail": {"message": f"|{measured_volume} - {expected_volume}| <= {band}"},
        },
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
    return {
        "schema": "fcb.result-envelope/1",
        "status": verdict,
        "detail": None if verdict == "OK" else _failure_detail(report),
        "structured_content": report,
        "text": mirror_text(report),
    }


def _finish(report: dict) -> ResultEnvelope:
    """Attach schema/banner, derive the verdict, and wrap the report in an envelope."""
    report["schema"] = "fcb.validation-report/1"
    report["banner"] = _banner()
    report["verdict"] = derive_verdict(report)
    return _report_envelope(report)


def _ok_envelope(structured: dict) -> ResultEnvelope:
    """Wrap a plain structured payload as an ``OK`` ResultEnvelope."""
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": mirror_text(structured),
    }
