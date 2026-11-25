"""Root-cause evidence for the multi-object 3MF parse failure in the GUI host."""
import json, os, re, sys, zipfile
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-5\tests\uat\runner")
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-5\src")
from mcp_client import McpClient

HOST = r"D:\Work\Personal\Sources\fcb-verify-13-5\tests\uat\run\13-5-r1\evidence"
CT = "/repo/tests/uat/run/13-5-r1/evidence"
OUT = {}
H = json.load(open(os.path.join(HOST, "summary.json")))["handles"]["H"]
LOG = []
with McpClient("http://127.0.0.1:18765/mcp") as c:
    def call(tool, args):
        r = c.call(tool, args)
        LOG.append({"tool": tool, "args": args, "result": r})
        return r
    # 1. FreeCAD's own writer, no bridge rename: three Mesh::Feature objects through Mesh.export
    code = (
        "import Mesh, MeshPart\n"
        "fs = []\n"
        "for n in ('BoxA', 'Cyl', 'Sph'):\n"
        "    f = doc.addObject('Mesh::Feature', 'Raw' + n)\n"
        "    f.Mesh = MeshPart.meshFromShape(Shape=doc.getObject(n).Shape, LinearDeflection=0.1, AngularDeflection=0.5, Relative=False)\n"
        "    fs.append(f)\n"
        f"Mesh.export(fs, r'{CT}/cause-raw-three.3mf')\n"
        f"Mesh.export(fs[:1], r'{CT}/cause-raw-one.3mf')\n"
        "for f in fs: doc.removeObject(f.Name)\n"
        "doc.recompute()"
    )
    OUT["raw_export"] = call("script_exec", {"doc": H, "code": code})["status"]
    # 2. One-object 3MF through the product path (K-1 path) still verifies in the GUI host
    w = call("export_3mf", {"doc": H, "path": f"{CT}/tc-07-11-one.3mf", "objects": ["BoxA"]})
    v = call("verify_export_3mf", {"doc": H, "export_id": w["structured_content"]["export_id"]})
    OUT["one_object_3mf"] = {"write": w["status"], "verify": v["status"],
                             "checks": [(ch["id"], ch["passed"]) for ch in v["structured_content"]["checks"]]}

for name in ("cause-raw-three.3mf", "cause-raw-one.3mf", "tc-07-11-three.3mf"):
    with zipfile.ZipFile(os.path.join(HOST, name)) as z:
        ct = z.read("[Content_Types].xml").decode()
        OUT[name] = {"png_defaults": len(re.findall(r'Extension="png"', ct)),
                     "parts": [i.filename for i in z.infolist()]}

# 3. The same multi-object file with the duplicate png Default lines removed: does the 3MF leg pass?
from freecad_buddy.adapters import export_oracle
src = os.path.join(HOST, "tc-07-11-three.3mf")
fixed = os.path.join(HOST, "cause-dedup-three.3mf")
with zipfile.ZipFile(src) as z, zipfile.ZipFile(fixed, "w", zipfile.ZIP_DEFLATED) as out:
    for info in z.infolist():
        data = z.read(info.filename)
        if info.filename == "[Content_Types].xml":
            seen, lines = set(), []
            for line in data.decode().splitlines():
                key = line.strip()
                if key.startswith("<Default") and key in seen:
                    continue
                seen.add(key); lines.append(line)
            data = "\n".join(lines).encode()
        out.writestr(info, data)
band = lambda area: 0.1 * area * 1.0  # placeholder replaced below
try:
    from freecad_buddy.usecases.exports import mesh_volume_band
    band = lambda area: mesh_volume_band(0.1, area)
except Exception as exc:
    OUT["band_import_error"] = repr(exc)
import math
objs = [
    {"name": "BoxA", "label": "Alpha", "volume": 1000.0, "band": band(600.0)},
    {"name": "Cyl", "label": "Beta", "volume": math.pi * 4 * 10, "band": band(2 * math.pi * 2 * 10 + 2 * math.pi * 4)},
    {"name": "Sph", "label": "Gamma", "volume": 4 / 3 * math.pi * 125, "band": band(4 * math.pi * 25)},
]
total = sum(o["volume"] for o in objs)
res = export_oracle.mesh3mf_oracle(fixed, True, total, 71.0, 2, objs)
OUT["dedup_oracle"] = {"ok": res["ok"], "checks": [(ch["id"], ch["passed"], ch.get("measured")) for ch in res["checks"]]}
json.dump(LOG, open(os.path.join(HOST, "cause-mcp-log.json"), "w"), indent=1, default=str)
json.dump(OUT, open(os.path.join(HOST, "cause-summary.json"), "w"), indent=1, default=str)
print(json.dumps(OUT, indent=1, default=str))
