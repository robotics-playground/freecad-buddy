"""K-1 probe: single-object export + verify results and files, for the src tree in FCB_SRC.

Writes <FCB_OUT>/k1.json and the exported files into <FCB_OUT>/files/. Run under freecadcmd.
"""
import hashlib, json, os, re, sys

SRC = os.environ["FCB_SRC"]
OUT = os.environ["FCB_OUT"]
sys.path.insert(0, SRC)
import FreeCAD as App  # noqa: E402
import freecad_buddy  # noqa: E402
from freecad_buddy.usecases import exports  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402
from freecad_buddy.usecases.exports import ExportRegistry  # noqa: E402

os.makedirs(os.path.join(OUT, "files"), exist_ok=True)
result = {"module": freecad_buddy.__file__, "cases": {}}


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in ("export_id", "path", "doc", "subject")}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"fcb-exp:[A-Za-z0-9_-]+", "<id>", value.replace(OUT.replace("\\", "/"), "<out>").replace(OUT, "<out>"))
    return value


def file_digest(path):
    data = open(path, "rb").read()
    if path.endswith(".step"):
        # FILE_NAME carries the write time; drop the header before hashing.
        text = data.decode("latin-1")
        text = re.sub(r"FILE_NAME\([^;]*;", "FILE_NAME(<scrubbed>);", text, flags=re.S)
        data = text.encode("latin-1")
        colours = len(re.findall(r"COLOUR_RGB|STYLED_ITEM", text))
    else:
        colours = None
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "step_colour_entities": colours}


def build(case, doc):
    if case == "cylinder":
        doc.addObject("Part::Cylinder", "Cyl")
    elif case == "body":
        body = doc.addObject("PartDesign::Body", "Body")
        body.newObject("PartDesign::AdditiveBox", "Box")
    elif case == "hidden_sphere":
        doc.addObject("Part::Sphere", "Sph").Visibility = False
    elif case == "box_named":
        doc.addObject("Part::Box", "BoxA").Label = "Alpha"
        other = doc.addObject("Part::Sphere", "Other")
        other.Placement.Base = App.Vector(50, 0, 0)
    doc.recompute()


for case in ("cylinder", "body", "hidden_sphere", "box_named"):
    registry, export_registry = DocumentRegistry(), ExportRegistry()
    handle = registry.document_create(case)["structured_content"]["doc"]
    _, doc = registry.with_document(handle, lambda h, d: (h, d))
    build(case, doc)
    objects = {"box_named": ["BoxA"], "body": ["Body"]}.get(case)
    record = {}
    for fmt in ("step", "stl", "3mf"):
        path = os.path.join(OUT, "files", f"{case}.{fmt}")
        kwargs = {"doc": handle, "path": path}
        if objects:
            kwargs["objects"] = objects
        written = getattr(exports, f"export_{fmt}")(registry, export_registry, **kwargs)
        export_id = written["structured_content"]["export_id"]
        if fmt == "step":
            verified = exports.verify_export_step(registry, export_registry, doc=handle, export_id=export_id)
        else:
            verified = getattr(exports, f"export_self_read_{fmt}")(registry, export_registry, doc=handle, export_id=export_id)
        verified["structured_content"].pop("banner", None)
        record[fmt] = {"export": scrub(written), "verify": scrub(verified), "file": file_digest(path)}
    result["cases"][case] = record
    for name in list(App.listDocuments().keys()):
        App.closeDocument(name)

json.dump(result, open(os.path.join(OUT, "k1.json"), "w"), indent=1, sort_keys=True, default=str)
print("K1_DONE", result["module"])
