import sys

import FreeCAD as App  # noqa: F401
import Part

COPY = "D:/Work/Personal/Sources/fcb-verify-13-8"
sys.path.insert(0, COPY + "/src")
for name in [m for m in sys.modules if m == "freecad_buddy" or m.startswith("freecad_buddy.")]:
    del sys.modules[name]
from freecad_buddy.usecases import queries  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402
from freecad_buddy.usecases.fingerprint import fingerprint  # noqa: E402

assert queries.__file__.replace("\\", "/").startswith(COPY)
mode = sys.argv[-1]
if mode == "nocopy":
    queries._copied_queryable_shape = queries._named_shape
registry = DocumentRegistry()
handle = registry.document_create("probe")["structured_content"]["doc"]
_, document = registry.with_document(handle, lambda h, d: (h, d))
feature_box = document.addObject("Part::Box", "FeatureBox")
plain = document.addObject("Part::Feature", "PlainBox")
plain.Shape = Part.makeBox(10, 20, 30)
cyl = document.addObject("Part::Cylinder", "Cyl")
document.recompute()
for index, n in enumerate(("A", "B", "C")):
    b = document.addObject("Part::Box", n); b.Placement.Base = App.Vector(index * 30, 0, 0)
document.recompute()
before = fingerprint(document, fresh=True)["digest"]
queries.query_interference(registry, doc=handle, objects=["A", "B", "C"])
sys.stderr.write(f"PROBE mode={mode} interference equal={before == fingerprint(document, fresh=True)['digest']}\n")
for name in ("FeatureBox", "PlainBox", "Cyl"):
    before = fingerprint(document, fresh=True)["digest"]
    envelope = queries.query_section(
        registry, doc=handle, object=name,
        plane={"normal": "z", "offset": {"value": 5, "unit": "mm"}},
        points={"deflection": {"value": 0.1, "unit": "mm"}},
    )
    after = fingerprint(document, fresh=True)["digest"]
    sys.stderr.write(f"PROBE mode={mode} {name} status={envelope['status']} equal={before == after}\n")
