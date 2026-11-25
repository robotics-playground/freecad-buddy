# Verifier r3 probes: real geometry through query_interference on the code under test; prints a verdict per case.
import sys, os, time
SRC = os.environ["FCB_SRC"]; sys.path.insert(0, SRC)
import FreeCAD as App, Part
from freecad_buddy.usecases import queries
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.fingerprint import fingerprint
assert queries.__file__.replace("\\", "/").startswith(SRC.replace("\\", "/")), queries.__file__
print("code under test:", queries.__file__, "has _boundaries_meet:", hasattr(queries, "_boundaries_meet"), flush=True)
V = App.Vector; box = Part.makeBox; sph = Part.makeSphere; cyl = Part.makeCylinder
ONLY = os.environ.get("FCB_ONLY", "")
def run(label, a, b, check, tol=None):
    if ONLY and ONLY not in label:
        return
    if tol is not None:
        a.fixTolerance(tol); b.fixTolerance(tol)
    true = a.distToShape(b)[0]
    reg = DocumentRegistry(); h = reg.document_create("p")["structured_content"]["doc"]
    _, doc = reg.with_document(h, lambda x, d: (x, d))
    for n, s in (("A", a), ("B", b)):
        o = doc.addObject("Part::Feature", n); o.Shape = s
    doc.recompute(); fp = fingerprint(doc, fresh=True)["digest"]
    t = time.perf_counter(); env = queries.query_interference(reg, doc=h, pairs=[["A", "B"]]); dt = time.perf_counter() - t
    if env["status"] != "OK":
        print(f"{label}: status={env['status']} detail={env.get('detail')} time={dt:.2f}s -> FAIL", flush=True); App.closeDocument(doc.Name); return
    r = env["structured_content"]["pairs"][0]
    cv = r["common_volume"] and r["common_volume"]["value"]; md = r["min_distance"] and r["min_distance"]["value"]; bf = r["boolean_failed"]
    ok = check(cv, md, bf, true) and fingerprint(doc, fresh=True)["digest"] == fp
    print(f"{label}: distToShape={true:.4g} -> common_volume={cv} min_distance={md} boolean_failed={bf} time={dt:.2f}s -> {'PASS' if ok else 'FAIL'}", flush=True)
    App.closeDocument(doc.Name)
gap = lambda cv, md, bf, t: cv == 0.0 and bf is False and md is not None and md > 1e-7 and abs(md - t) <= 1e-3 * t
touch = lambda cv, md, bf, t: cv == 0.0 and md == 0.0 and bf is False
failed = lambda cv, md, bf, t: cv is None and bf is True
run("gap edge 1.5e-7 (default tol)", box(10,10,10), box(10,10,10,V(10+1.5e-7,10+1.5e-7,0)), gap)
run("gap sphere-sphere 2e-7 (default tol)", sph(5), sph(5,V(10+2e-7,0,0)), gap)
run("gap sphere-box 1.5e-7 (default tol)", box(10,10,10), sph(5,V(5,5,15+1.5e-7)), gap)
run("gap vertex 1.5e-7 (default tol)", box(10,10,10), box(10,10,10,V(10+1.5e-7,10+1.5e-7,10+1.5e-7)), gap)
run("gap face 1.5e-7 (default tol)", box(10,10,10), box(10,10,10,V(10+1.5e-7,0,0)), gap)
for g in (1e-3, 5e-3, 2e-2):
    run(f"tol1e-2 gap edge {g}", box(10,10,10), box(10,10,10,V(10+g,10+g,0)), gap, 1e-2)
    run(f"tol1e-2 gap vertex {g}", box(10,10,10), box(10,10,10,V(10+g,10+g,10+g)), gap, 1e-2)
    run(f"tol1e-2 gap sphere-sphere {g}", sph(5), sph(5,V(10+g,0,0)), gap, 1e-2)
    run(f"tol1e-2 gap face {g}", box(10,10,10), box(10,10,10,V(10+g,0,0)), gap, 1e-2)
run("nested sphere r10", sph(10), sph(10+1e-6, V(1e-6,0,0)), failed)
run("nested sphere r100", sph(100), sph(100+5e-7, V(5e-7,0,0)), failed)
run("touch face", box(10,10,10), box(10,10,10,V(10,0,0)), touch)
run("touch edge", box(10,10,10), box(10,10,10,V(10,10,0)), touch)
run("touch vertex", box(10,10,10), box(10,10,10,V(10,10,10)), touch)
run("touch sphere on box", box(10,10,10), sph(5,V(5,5,15)), touch)
run("touch cylinder line on box", box(10,10,10), cyl(5,10,V(0,5,15),V(1,0,0)), touch)
run("overlap 1e-7 depth 100 mm boxes (common empty)", box(100,100,100), box(100,100,100,V(100-1e-7,0,0)), failed)
run("box 5 inside box 10, shared faces", box(10,10,10), box(5,5,5), lambda cv, md, bf, t: cv is not None and abs(cv - 125) < 1e-6 and md == 0.0 and bf is False)
for n in (100, 200):
    run(f"rt5 lid x{n}", box(n,1,1,V(0,0,1)), Part.makeCompound([box(1,1,1,V(i,0,0)) for i in range(n)]), touch)
