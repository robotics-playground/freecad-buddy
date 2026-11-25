"""Drive TC-21 on the container MCP proxy and capture the FreeCAD window with cua-driver.

Usage (host, repo uv env): uv run python tc21.py <scenario> <pid> <window_id>
Writes out-<scenario>.json (every call, raw structuredContent) and prints one line per check.
The checks print the observed value next to the expected one; grading is done by the reader.
"""

import ast
import asyncio
import json
import subprocess
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"
EVIDENCE = "/repo/tests/uat/run/13-17-r1/evidence"
HERE = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]
SCENARIO, PID, WID = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
records = []


def mm(v):
    return {"value": v, "unit": "mm"}


def box(name, x=0):
    args = {"kind": "box", "name": name, "length": mm(10), "width": mm(10), "height": mm(10)}
    if x:
        args["placement"] = {"base": {"x": mm(x)}}
    return args


def env_of(res):
    sc = res.structuredContent or {}
    return sc


def note(label, observed, expected=None):
    line = f"CHECK {label}: observed={observed!r}" + ("" if expected is None else f" expected={expected!r}")
    print(line)
    records.append({"check": label, "observed": observed, "expected": expected})


def shot(name):
    payload = json.dumps(
        {"pid": PID, "window_id": WID, "screenshot_out_file": f"{EVIDENCE}/{name}.png"}
    )
    cp = subprocess.run(
        ["docker", "exec", "-i", "-u", "cua", "fcb-desktop", "bash", "-c",
         'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call get_window_state'],
        input=payload, capture_output=True, text=True,
    )
    try:
        data = json.loads(cp.stdout)
        info = {k: data.get(k) for k in ("screenshot_file_path", "element_count")}
    except Exception:  # noqa: BLE001
        info = {"rc": cp.returncode, "err": cp.stderr[-300:]}
    records.append({"shot": name, **info})
    print(f"SHOT {name}: {info}")


class Session:
    def __init__(self, s):
        self.s = s
        self.doc = None

    async def call(self, tool, **args):
        if self.doc is not None and tool != "document_create" and "doc" not in args and tool != "document_list":
            args["doc"] = self.doc
        t0 = time.time()
        res = await self.s.call_tool(tool, args)
        env = env_of(res)
        rec = {"tool": tool, "args": args, "seconds": round(time.time() - t0, 3), "isError": res.isError,
               "structuredContent": env,
               "text": [b.text for b in res.content if getattr(b, "type", "") == "text"]}
        records.append(rec)
        status = env.get("status")
        detail = env.get("detail") or {}
        print(f"CALL {tool} -> {status} {detail.get('code', '')} {str(detail.get('message', ''))[:150]}")
        if tool == "document_create" and status == "OK":
            self.doc = env["structured_content"]["doc"]
        return env

    async def py(self, code):
        env = await self.call("script_exec", code=code)
        rep = (env.get("structured_content") or {}).get("value_repr")
        try:
            return ast.literal_eval(rep)
        except Exception:  # noqa: BLE001
            return rep


def vol(env):
    return (((env.get("structured_content") or {}).get("feature_state") or {}).get("shape_summary") or {}).get("volume")


async def tc01(x):
    await x.call("document_list")
    await x.call("document_create", label="tc21_ops")
    a = await x.call("feature_part_primitive", **box("A"))
    b = await x.call("feature_part_primitive", **box("B", 5))
    note("given A,B status", [a["status"], b["status"]], ["OK", "OK"])
    note("given A,B volume", [vol(a), vol(b)], [1000, 1000])
    note("given A type/top-level", await x.py("result = [doc.A.TypeId, doc.A.getParentGeoFeatureGroup() is None]"), ["Part::Box", True])
    cut = await x.call("feature_part_boolean", operation="cut", base="A", tools=["B"], name="CutAB")
    com = await x.call("feature_part_boolean", operation="common", base="A", tools=["B"], name="CommonAB")
    fus = await x.call("feature_part_boolean", operation="fuse", base="A", tools=["B"], name="FuseAB")
    note("ops status", [cut["status"], com["status"], fus["status"]], ["OK"] * 3)
    note("ops envelope volume", [vol(cut), vol(com), vol(fus)], [500, 500, 1500])
    note("ops Shape.Volume", await x.py("result = [round(doc.CutAB.Shape.Volume, 6), round(doc.CommonAB.Shape.Volume, 6), round(doc.FuseAB.Shape.Volume, 6)]"), [500.0, 500.0, 1500.0])
    note("ops TypeId", await x.py("result = [doc.CutAB.TypeId, doc.CommonAB.TypeId, doc.FuseAB.TypeId]"), ["Part::Cut", "Part::Common", "Part::Fuse"])
    note("inputs hidden", await x.py("result = [doc.A.Visibility, doc.B.Visibility]"), [False, False])
    names = ["CutAB", "CommonAB", "FuseAB"]
    for shown in names:
        code = "\n".join(f"doc.{n}.Visibility = {n == shown}" for n in names) + "\nresult = 'set'"
        await x.py(code)
        await x.call("view_fit_viewport")
        time.sleep(1.5)
        shot(f"tc-21-01-{shown}")
    for i in range(1, 7):
        u = await x.call("document_undo")
        left = await x.py("result = doc.getObject('CutAB') is None")
        note(f"undo {i}", [u["status"], left])
        if left is True:
            break
    note("after undo", await x.py("result = [doc.getObject('FuseAB'), doc.getObject('CommonAB'), doc.getObject('CutAB'), doc.A.Visibility, doc.B.Visibility]"), [None, None, None, True, True])
    await x.call("view_fit_viewport")
    time.sleep(1.5)
    shot("tc-21-01-after-undo")
    print("DOC", x.doc)


async def tc02(x):
    await x.call("document_list")
    await x.call("document_create", label="tc21_empty")
    a = await x.call("feature_part_primitive", **box("A"))
    f = await x.call("feature_part_primitive", **box("Far", 100))
    note("given status", [a["status"], f["status"]], ["OK", "OK"])
    await x.call("view_fit_viewport")
    time.sleep(1.5)
    shot("tc-21-02-before")
    e = await x.call("feature_part_boolean", operation="common", base="A", tools=["Far"], name="Nothing")
    mut = (e.get("structured_content") or {}).get("mutation") or {}
    note("refusal", [e["status"], (e.get("detail") or {}).get("code"), mut.get("rolled_back"), mut.get("rollback_proven")],
         ["RECOMPUTE_ERROR", "part_boolean.empty_result", True, "not null"])
    tree = await x.call("query_tree_summary")
    note("tree names", json.dumps(tree.get("structured_content"))[:600])
    note("nothing left", await x.py("result = [doc.getObject('Nothing'), doc.A.Visibility, doc.Far.Visibility]"), [None, True, True])
    time.sleep(1.5)
    shot("tc-21-02-after")
    ball = await x.call("feature_part_primitive", kind="sphere", name="Ball", radius=mm(4))
    u = await x.call("document_undo")
    note("next call + undo", [ball["status"], u["status"], await x.py("result = [doc.getObject('Ball'), doc.getObject('A') is not None]")], ["OK", "OK", [None, True]])
    print("DOC", x.doc)


REV_CODE = (
    "import Part, Sketcher, FreeCAD as App\nV = App.Vector\nrev = doc.addObject('Part::Feature', 'Rev')\n"
    "box = Part.makeBox(10, 10, 10, V(5, 0, 0))\nbox.reverse()\nrev.Shape = box\n"
    "body = doc.addObject('PartDesign::Body', 'Body')\nsk = body.newObject('Sketcher::SketchObject', 'Profile')\n"
    "sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], '')]\nsk.MapMode = 'FlatFace'\n"
    "for i, (a, b) in enumerate([((0,0),(8,0)), ((8,0),(8,16)), ((8,16),(0,16)), ((0,16),(0,0))]):\n"
    "    sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))\n"
    "for i in range(4):\n    sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))\n"
    "doc.recompute()\npad = body.newObject('PartDesign::Pad', 'Pad')\npad.Profile = sk\npad.Length = 5\n"
    "doc.recompute()\nresult = 'built'"
)


async def tc03(x):
    await x.call("document_list")
    await x.call("document_create", label="tc21_trust")
    a = await x.call("feature_part_primitive", **box("A"))
    s = await x.call("script_exec", code=REV_CODE)
    note("given status", [a["status"], s["status"]], ["OK", "OK"])
    note("given check", await x.py("result = [doc.Rev.Shape.Volume < 0, doc.Pad.getParentGeoFeatureGroup().Name]"), [True, "Body"])
    bad = await x.call("feature_part_boolean", operation="cut", base="A", tools=["Rev"], name="BadCut")
    pad = await x.call("feature_part_boolean", operation="cut", base="A", tools=["Pad"], name="PadCut")
    bd, pd = bad.get("detail") or {}, pad.get("detail") or {}
    note("reversed refused", [bad["status"], bd.get("code"), "Rev" in str(bd.get("message")), "reversed" in str(bd.get("message"))],
         ["INVALID_INPUT", "part_boolean.untrusted_shape", True, True])
    note("pad refused", [pad["status"], pd.get("code"), "Pad" in str(pd.get("message")), "Body" in str(pd.get("message"))],
         ["INVALID_INPUT", "part_boolean.not_top_level", True, True])
    ok = await x.call("feature_part_boolean", operation="cut", base="Body", tools=["A"], name="BodyCut")
    note("Body accepted", ok["status"], "OK")
    note("no writes", await x.py("result = [doc.getObject('BadCut'), doc.getObject('PadCut')]"), [None, None])
    await x.call("view_fit_viewport")
    time.sleep(1.5)
    shot("tc-21-03-after")
    print("DOC", x.doc)


async def tc04(x):
    await x.call("document_list")
    await x.call("document_create", label="tc21_kinds")
    cut_args = dict(operation="cut", base="Plate", tools=["Pin", "Horn"], name="Drilled", refine=False)
    calls = [
        ("feature_part_primitive", dict(kind="cylinder", name="Pin", radius=mm(2), height=mm(30), placement={"base": {"x": mm(5), "y": mm(5), "z": mm(-5)}})),
        ("feature_part_primitive", dict(kind="cone", name="Horn", radius1=mm(3), radius2=mm(0), height=mm(20), placement={"base": {"x": mm(25), "y": mm(5), "z": mm(-5)}})),
        ("feature_part_primitive", dict(kind="torus", name="Ring", radius1=mm(10), radius2=mm(2), placement={"base": {"x": mm(60)}})),
        ("feature_part_primitive", dict(kind="box", name="Plate", length=mm(40), width=mm(10), height=mm(10))),
        ("feature_part_boolean", dict(cut_args)),
    ]
    st = [(await x.call(t, **a))["status"] for t, a in calls]
    note("five calls", st, ["OK"] * 5)
    note("volumes", await x.py("result = [round(doc.Pin.Shape.Volume, 3), round(doc.Horn.Shape.Volume, 3), round(doc.Ring.Shape.Volume, 3)]"), [376.991, 188.496, 789.568])
    note("types/refine", await x.py("result = [doc.Drilled.TypeId, doc.Drilled_tools.TypeId, doc.Drilled.Refine, doc.Drilled_tools.Refine]"), ["Part::Cut", "Part::MultiFuse", False, False])
    note("cut volume", await x.py("result = round(doc.Drilled.Shape.Volume, 3)"), 3797.76)
    note("visibility", await x.py("result = [doc.Plate.Visibility, doc.Pin.Visibility, doc.Horn.Visibility, doc.Drilled_tools.Visibility, doc.Drilled.Visibility]"), [False, False, False, False, True])
    u = await x.call("document_undo")
    note("undo", [u["status"], await x.py("result = [doc.getObject('Drilled'), doc.getObject('Drilled_tools'), doc.Plate.Visibility, doc.Pin.Visibility, doc.Horn.Visibility]")], ["OK", [None, None, True, True, True]])
    redo = await x.call("feature_part_boolean", **dict(cut_args))
    note("redo cut", redo["status"], "OK")
    bad = await x.call("feature_part_primitive", kind="torus", name="Bad", radius1=mm(2), radius2=mm(2))
    note("bad torus", [bad["status"], (bad.get("detail") or {}).get("code"), await x.py("result = doc.getObject('Bad')")], ["INVALID_INPUT", "part_primitive.dimension", None])
    await x.call("view_fit_viewport")
    time.sleep(1.5)
    shot("tc-21-04-after")
    print("DOC", x.doc)


async def main():
    async with streamablehttp_client(URL, timeout=60, sse_read_timeout=300) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await {"01": tc01, "02": tc02, "03": tc03, "04": tc04}[SCENARIO](Session(s))
    with open(f"{HERE}/out-tc21-{SCENARIO}.json", "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=1, default=str)


asyncio.run(main())
