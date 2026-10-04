"""Outside-tool read of an exported file with the fcb-env FreeCAD (not the bridge).
usage: fcb python tc-07-fcbread.py <file> [<file> ...]  -> one JSON line per file."""
import json, sys, os
import FreeCAD, Part, Mesh
for p in sys.argv[1:]:
    out = {"file": p, "exists": os.path.exists(p), "freecad": ".".join(FreeCAD.Version()[:3])}
    try:
        if p.lower().endswith((".step", ".stp")):
            s = Part.read(p)
            out.update(volume=s.Volume, valid=s.isValid(), solids=len(s.Solids), faces=len(s.Faces), edges=len(s.Edges), bbox=[round(s.BoundBox.XLength, 4), round(s.BoundBox.YLength, 4), round(s.BoundBox.ZLength, 4)])
        else:
            m = Mesh.Mesh(p)
            out.update(facets=m.CountFacets, points=m.CountPoints, volume=m.Volume, solid=m.isSolid(), non_manifolds=m.hasNonManifolds(), bbox=[round(m.BoundBox.XLength, 4), round(m.BoundBox.YLength, 4), round(m.BoundBox.ZLength, 4)])
    except Exception as e:
        out["error"] = repr(e)
    print(json.dumps(out))
