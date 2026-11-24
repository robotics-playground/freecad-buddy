import os, sys, traceback, json
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-11\src")
import FreeCAD as App
from freecad_buddy.usecases import confirm, features
from freecad_buddy.usecases.documents import DocumentRegistry
out = []
confirm.set_auto_approve(True)
def case(label, build, target, **kw):
    try:
        reg = DocumentRegistry()
        h = reg.document_create("gp")["structured_content"]["doc"]
        d = reg.with_document(h, lambda hh, dd: dd)
        info = build(d)
        d.recompute()
        env = features.document_object_delete(reg, doc=h, objects=[target], **kw)
        sc = env.get("structured_content") or {}
        out.append({"case": label, "status": env["status"], "code": (env.get("detail") or {}).get("code"),
                    "message": (env.get("detail") or {}).get("message"), "deleted": sc.get("deleted"),
                    "after": info(d) if callable(info) else None})
    except Exception:
        out.append({"case": label, "error": traceback.format_exc()[-800:]})
    for n in list(App.listDocuments()):
        App.closeDocument(n)

def box(d, n="Box"):
    b = d.addObject("Part::Box", n); return b

def b_grouppython(d):
    g = d.addObject("App::DocumentObjectGroupPython", "G"); g.addObject(box(d))
    return lambda d: {"G.Group": [o.Name for o in d.getObject("G").Group]}
case("DocumentObjectGroupPython member", b_grouppython, "Box")

def b_fem(d):
    import Fem  # noqa
    a = d.addObject("Fem::FemAnalysis", "Analysis"); a.addObject(box(d))
    return lambda d: {"Analysis.Group": [o.Name for o in d.getObject("Analysis").Group]}
case("Fem::FemAnalysis member", b_fem, "Box")

def b_assembly(d):
    try:
        import Assembly  # noqa
    except Exception:
        pass
    a = d.addObject("Assembly::AssemblyObject", "Assembly"); a.addObject(box(d))
    return lambda d: {"Assembly.Group": [o.Name for o in d.getObject("Assembly").Group], "ext": d.getObject("Assembly").hasExtension("App::GroupExtension")}
case("Assembly::AssemblyObject member", b_assembly, "Box")

def b_linkholder(d):
    h = d.addObject("App::FeaturePython", "Holder")
    h.addExtension("App::GroupExtensionPython")
    h.addProperty("App::PropertyLink", "Source", "Base")
    b = box(d); h.addObject(b); h.Source = b
    return lambda d: {"Holder.Source": getattr(d.getObject("Holder").Source, "Name", None), "Holder.Group": [o.Name for o in d.getObject("Holder").Group]}
case("GroupExtensionPython holder with PropertyLink to its member", b_linkholder, "Box")

def b_pipeline(d):
    import Fem  # noqa
    p = d.addObject("Fem::FemPostPipeline", "Pipeline")
    f = d.addObject("Fem::FemPostClipFilter", "Clip"); p.addObject(f)
    return lambda d: {"Pipeline.Group": [o.Name for o in d.getObject("Pipeline").Group], "hasGroupExt": d.getObject("Pipeline").hasExtension("App::GroupExtension")}
case("Fem::FemPostPipeline filter member", b_pipeline, "Clip")

open(r"%s/groupprobe.json" % os.environ["S"], "w").write(json.dumps(out, indent=1, default=str))
