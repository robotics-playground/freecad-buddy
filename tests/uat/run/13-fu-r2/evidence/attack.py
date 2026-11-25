# Verifier r2 probes: real geometry through query_interference on the code under test.
import sys, os, time
SRC = os.environ["FCB_SRC"]; sys.path.insert(0, SRC)
import FreeCAD as App, Part
from freecad_buddy.usecases import queries
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.fingerprint import fingerprint
assert queries.__file__.replace("\\", "/").startswith(SRC.replace("\\", "/")), queries.__file__
print("code under test:", queries.__file__, flush=True)
V = App.Vector
ONLY = os.environ.get("FCB_ONLY", "")

def run(label, a, b, tol=None, expect=""):
    if ONLY and ONLY not in label:
        return
    reg = DocumentRegistry(); h = reg.document_create("p")["structured_content"]["doc"]
    _, doc = reg.with_document(h, lambda x, d: (x, d))
    if tol is not None:
        a.fixTolerance(tol); b.fixTolerance(tol)
    for n, s in (("A", a), ("B", b)):
        o = doc.addObject("Part::Feature", n); o.Shape = s
    doc.recompute()
    fp = fingerprint(doc, fresh=True)["digest"]
    t = time.perf_counter()
    env = queries.query_interference(reg, doc=h, pairs=[["A", "B"]])
    dt = time.perf_counter() - t
    r = (env["structured_content"] or {}).get("pairs", [{}])[0] if env["status"] == "OK" else env.get("detail")
    cv = r.get("common_volume") if isinstance(r, dict) else None
    md = r.get("min_distance") if isinstance(r, dict) else None
    print(f"{label}: status={env['status']} common_volume={cv and cv['value']} min_distance={md and md['value']} "
          f"boolean_failed={r.get('boolean_failed') if isinstance(r, dict) else r} time={dt:.2f}s "
          f"fp_equal={fingerprint(doc, fresh=True)['digest'] == fp} | expect {expect}", flush=True)
    App.closeDocument(doc.Name)

box = Part.makeBox; sph = Part.makeSphere; cyl = Part.makeCylinder
# rt1 nested spheres
run("rt1 nested sphere r10", sph(10), sph(10 + 1e-6, V(1e-6, 0, 0)), expect="failed true")
run("rt1 nested sphere r100", sph(100), sph(100 + 5e-7, V(5e-7, 0, 0)), expect="failed true")
# touches
run("touch face", box(10, 10, 10), box(10, 10, 10, V(10, 0, 0)), expect="0 / 0 / false")
run("touch edge", box(10, 10, 10), box(10, 10, 10, V(10, 10, 0)), expect="0 / 0 / false")
run("touch vertex", box(10, 10, 10), box(10, 10, 10, V(10, 10, 10)), expect="0 / 0 / false")
run("touch sphere on box point", box(10, 10, 10), sph(5, V(5, 5, 15)), expect="0 / 0 / false")
run("touch cylinder line on box", box(10, 10, 10), cyl(5, 10, V(0, 5, 15), V(1, 0, 0)), expect="0 / 0 / false")
run("touch sphere-sphere point", sph(5), sph(5, V(10, 0, 0)), expect="0 / 0 / false")
# box inside box sharing a face
run("box inside box shared face", box(10, 10, 10), box(5, 5, 5), expect="125 / 0 / false")
run("box inside box shared 3 faces", box(10, 10, 10), box(5, 5, 5, V(0, 0, 0)), expect="125")
# real gaps (default tolerance)
for g in (1.5e-7, 2e-7, 1e-6):
    run(f"gap face {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 0, 0)), expect=f"dist {g}")
    run(f"gap edge {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 10 + g, 0)), expect=f"dist {g*2**0.5:.3g}")
    run(f"gap vertex {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 10 + g, 10 + g)), expect=f"dist {g*3**0.5:.3g}")
    run(f"gap sphere-sphere {g}", sph(5), sph(5, V(10 + g, 0, 0)), expect=f"dist {g}")
    run(f"gap sphere-box {g}", box(10, 10, 10), sph(5, V(5, 5, 15 + g)), expect=f"dist {g}")
# real gaps with loose shape tolerance 1e-2
for g in (1e-3, 5e-3):
    run(f"tol1e-2 gap face {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 0, 0)), tol=1e-2, expect=f"dist {g}")
    run(f"tol1e-2 gap edge {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 10 + g, 0)), tol=1e-2, expect=f"dist {g*2**0.5:.3g}")
    run(f"tol1e-2 gap vertex {g}", box(10, 10, 10), box(10, 10, 10, V(10 + g, 10 + g, 10 + g)), tol=1e-2, expect=f"dist {g*3**0.5:.3g}")
    run(f"tol1e-2 gap sphere-sphere {g}", sph(5), sph(5, V(10 + g, 0, 0)), tol=1e-2, expect=f"dist {g}")
    run(f"tol1e-2 gap sphere-box {g}", box(10, 10, 10), sph(5, V(5, 5, 15 + g)), tol=1e-2, expect=f"dist {g}")
# thin nested part (documented limit): hollow sphere wall 5e-5 inside a sphere 1e-6 larger
run("thin shell nested (doc limit)", sph(10).cut(sph(10 - 5e-5)), sph(10 + 1e-6, V(1e-6, 0, 0)), expect="failed true, else documented limit")
# rt5 lid on 100 / 200 boxes
for n in (100, 200):
    run(f"rt5 lid x{n}", box(n, 1, 1, V(0, 0, 1)), Part.makeCompound([box(1, 1, 1, V(i, 0, 0)) for i in range(n)]), expect="0 / 0 / false, < 40 s")
