import json, os, re, sys
ROOT = os.environ["FCB_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "src"))
import FreeCAD as App, Part, Sketcher
import freecad_buddy
from freecad_buddy.hosts import tool_catalog
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.capabilities import Capabilities
reg = DocumentRegistry()
methods = tool_catalog.build_inline_handlers(reg, tool_catalog.ExportRegistry(), Capabilities(script_exec=True, auto_approve=True), None, render_port=object())
h = reg.document_create("envdiff")["structured_content"]["doc"]
d = reg.with_document(h, lambda _h, doc: doc)
body = d.addObject("PartDesign::Body", "Body")
sk = body.newObject("Sketcher::SketchObject", "Profile")
sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
sk.MapMode = "FlatFace"
pts = [App.Vector(0,0,0), App.Vector(8,0,0), App.Vector(8,16,0), App.Vector(0,16,0)]
for i in range(4):
    sk.addGeometry(Part.LineSegment(pts[i], pts[(i+1)%4]))
for i in range(4):
    sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i+1)%4, 1))
sk.addConstraint(Sketcher.Constraint("Horizontal", 0)); sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
sk.addConstraint(Sketcher.Constraint("Vertical", 1)); sk.addConstraint(Sketcher.Constraint("Vertical", 3))
sk.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 8.0))
sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 16.0))
d.recompute()
MASK = re.compile(r"(time|duration|elapsed|_ms$|session|token|snapshot|path|traceback|ts$|timestamp|digest_at|id$)", re.I)
def norm(o, k=""):
    if isinstance(o, dict):
        return {kk: ("<masked>" if MASK.search(kk) else norm(v, kk)) for kk, v in o.items()}
    if isinstance(o, list):
        return [norm(v, k) for v in o]
    if isinstance(o, float):
        return round(o, 6)
    return o
calls = [
    ("feature_pad", {"doc": h, "body": "Body", "profile": "Profile", "name": "Block", "length": {"value": 5, "unit": "mm"}}),
    ("feature_set_parameters", {"doc": h, "feature": "Block", "parameters": {"Length": {"value": 7, "unit": "mm"}}}),
    ("feature_set_parameters", {"doc": h, "feature": "Block", "parameters": {"Nope": 1}}),
    ("feature_pad", {"doc": h, "body": "Body", "profile": "Profile", "name": "Bad", "length": {"value": -3, "unit": "mm"}}),
    ("feature_fillet", {"doc": h, "body": "Body", "base": "Block", "name": "F", "edges": ["Edge999"], "radius": {"value": 1, "unit": "mm"}}),
    ("query_object", {"doc": h, "object": "Missing"}),
    ("query_tree_summary", {"doc": h}),
    ("query_parameters", {"doc": h}),
    ("document_undo", {"doc": h}),
    ("query_mass_properties", {"doc": h, "object": "Block"}),
    ("script_exec", {"doc": h, "code": "raise ValueError('boom')"}),
    ("no_such_tool", {}),
    ("feature_parameters_define", {"doc": h, "varset": "P", "parameters": [{"name": "W", "type": "float", "value": 1}]}),
]
out = []
for name, params in calls:
    env = methods.dispatch(name, params)
    out.append({"call": name, "params": params, "envelope": norm(env)})
with open(os.environ["FCB_OUT"], "w") as f:
    json.dump(out, f, indent=1, sort_keys=True, default=str)
sys.stderr.write("PKG %s DONE\n" % freecad_buddy.__file__)
