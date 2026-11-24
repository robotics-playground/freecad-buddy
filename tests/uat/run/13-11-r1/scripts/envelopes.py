import json, os, sys
sys.path.insert(0, os.environ["FCB_SRC"])
import FreeCAD as App, Part, Sketcher
from freecad_buddy.usecases import confirm, features, sketches
from freecad_buddy.usecases.documents import DocumentRegistry

out = {}
import traceback
try:
    confirm.set_auto_approve(True)
    reg = DocumentRegistry()
    h = reg.document_create("envcmp")["structured_content"]["doc"]
    d = reg.with_document(h, lambda hh, dd: dd)
    body = d.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Rect")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3] if False else [f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane"][0], "")]
    sk.MapMode = "FlatFace"
    pts = [(0, 0), (16, 0), (16, 8), (0, 8)]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        sk.addGeometry(Part.LineSegment(App.Vector(*a, 0), App.Vector(*b, 0)), False)
    for args in (("Coincident", 0, 2, 1, 1), ("Coincident", 1, 2, 2, 1), ("Coincident", 2, 2, 3, 1),
                 ("Coincident", 3, 2, 0, 1), ("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1),
                 ("Vertical", 3), ("Coincident", 0, 1, -1, 1)):
        sk.addConstraint(Sketcher.Constraint(*args))
    d.recompute()
    def c(t, g1, p1, g2, p2, v):
        return {"type": t, "first": g1, "first_pos": p1, "second": g2, "second_pos": p2,
                "value": {"value": v, "unit": "mm"}}
    out["sketch_add_constraint"] = sketches.sketch_add_constraint(
        reg, doc=h, sketch="Rect", constraints=[c("DistanceX", 0, 1, 0, 2, 16.0), c("DistanceY", 1, 1, 1, 2, 8.0)])
    out["feature_pad"] = features.feature_pad(reg, doc=h, body="Body", profile="Rect", name="Block",
                                              length={"value": 5.0, "unit": "mm"})
    out["feature_set_parameters"] = features.feature_set_parameters(
        reg, doc=h, feature="Block", parameters={"Length": {"value": 9.0, "unit": "mm"}})
    out["document_undo"] = reg.document_undo(doc=h)
    out["feature_set_parameters_rollback"] = features.feature_set_parameters(reg, doc=h, feature="Block", parameters={"Length": {"value": 0.0, "unit": "mm"}})
    out["feature_pad_bad"] = features.feature_pad(reg, doc=h, body="Body", profile="Rect", name="Block2", length={"value": 5.0, "unit": "mm"}, up_to="Nope") if False else None
    open(os.environ["FCB_OUT"], "w").write(json.dumps(out, indent=1, sort_keys=True, default=str))
except Exception:
    open(os.environ['FCB_OUT']+'.err','w').write(traceback.format_exc())
