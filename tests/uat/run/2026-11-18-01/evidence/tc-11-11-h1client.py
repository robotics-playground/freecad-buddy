"""TC-11-11 H1 stdio client (inside the container; talks only to its own child H1 host)."""
import asyncio, glob, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
run = "/repo/tests/uat/run/2026-11-18-01/evidence"
wd = f"{run}/tc-11-11-workdir"
env = dict(os.environ)
env["FREECAD_BUDDY_WORKDIR"] = wd
env["FREECAD_BUDDY_AUDIT_LOG"] = f"{run}/tc-11-11-audit.jsonl"
def count(): return len(glob.glob(f"{wd}/tmp/FCB_TMP_session_*/FCB_TMP_prev_*"))
def sc(r): return r.structuredContent
def show(tag, r):
    print("##", tag, "isError=", r.isError, flush=True)
    print("   ", json.dumps(sc(r))[:1800] if sc(r) else [getattr(c, "text", None) for c in r.content][:1], flush=True)
async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"], env=env)
    errlog = open(f"{run}/tc-11-11-server.stderr.log", "w")
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("wd sessions", glob.glob(f"{wd}/tmp/FCB_TMP_session_*"), flush=True)
            print("baseline prev count", count())
            c = await s.call_tool("document_create", {"label": "tc1111"}); h = sc(c)["structured_content"]["doc"]; show("create", c)
            code = ("import Part, Sketcher\nb = doc.addObject('PartDesign::Body','Body')\n"
                    "sk = b.newObject('Sketcher::SketchObject','Sketch')\nsk.AttachmentSupport=[(o,'') for o in b.Origin.OriginFeatures if o.Role=='XY_Plane']\nsk.MapMode='FlatFace'\n"
                    "P=FreeCAD.Vector\nfor i,(a,c2) in enumerate([((0,0),(60,0)),((60,0),(60,40)),((60,40),(0,40)),((0,40),(0,0))]):\n    sk.addGeometry(Part.LineSegment(P(a[0],a[1],0),P(c2[0],c2[1],0)))\n"
                    "for i in range(4): sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i+1)%4, 1))\n"
                    "for g in (0,2): sk.addConstraint(Sketcher.Constraint('Horizontal', g))\n"
                    "for g in (1,3): sk.addConstraint(Sketcher.Constraint('Vertical', g))\n"
                    "sk.addConstraint(Sketcher.Constraint('Coincident', 0, 1, -1, 1))\n"
                    "sk.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, 60))\n"
                    "sk.addConstraint(Sketcher.Constraint('DistanceY', 1, 1, 1, 2, 40))\n"
                    "pad = b.newObject('PartDesign::Pad','Pad'); pad.Profile=sk; pad.Length=10\ndoc.recompute()\nresult=(pad.Shape.Volume, [e.Length for e in pad.Shape.Edges][:4], pad.State)")
            c = await s.call_tool("script_exec", {"doc": h, "code": code}); show("build pad", c)
            print("count after build", count())
            c = await s.call_tool("preview_dry_run", {"doc": h, "operation": {"tool": "feature_set_parameters", "args": {"feature": "Pad", "parameters": {"Length": {"value": 12, "unit": "mm"}}}}}); show("preview success", c)
            n1 = count(); print("count after success", n1)
            dl = await s.call_tool("document_list", {}); print("doc list:", [d["label"] for d in sc(dl)["structured_content"]["documents"]])
            c = await s.call_tool("preview_dry_run", {"doc": h, "operation": {"tool": "feature_fillet", "args": {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}], "radius": {"value": 400, "unit": "mm"}}}}); show("preview failing", c)
            n2 = count(); print("count after failing", n2)
            dl = await s.call_tool("document_list", {}); print("doc list:", [d["label"] for d in sc(dl)["structured_content"]["documents"]])
            c = await s.call_tool("preview_dry_run", {"doc": h, "operation": {"tool": "feature_pad", "args": {"body": "Body", "profile": "NoSuchSketch", "name": "Pad2", "length": {"value": 5, "unit": "mm"}}}}); show("preview raising", c)
            n3 = count(); print("count after raising", n3)
            dl = await s.call_tool("document_list", {}); print("doc list:", [d["label"] for d in sc(dl)["structured_content"]["documents"]])
            print("tmp tree:", sorted(os.listdir(glob.glob(f"{wd}/tmp/FCB_TMP_session_*")[0])), flush=True)
asyncio.run(main())
