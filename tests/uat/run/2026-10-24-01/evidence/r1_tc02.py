"""Phase R1 TC-02 MCP steps on the live GUI proxy. Each call is logged to evidence/<tag>-mcp.jsonl.

    r1_tc02.py <scenario> <step>      e.g. r1_tc02.py 05 given

The handle of a scenario is kept in evidence/tc-02-<nn>-vars.json between steps, so GUI steps
(cua-driver) can run between the MCP steps.
"""

import json
import sys
from pathlib import Path

from r1_p5_lib import Run5
from r1_p3_lib import q

EVIDENCE = Path(__file__).resolve().parent
GOLDEN = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models"


def load(tag):
    path = EVIDENCE / f"{tag}-vars.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(tag, values):
    (EVIDENCE / f"{tag}-vars.json").write_text(json.dumps(values, indent=1), encoding="utf-8")


def tree(run, doc, label, **args):
    result = run.call("query_tree_summary", {"doc": doc, **args}, label, quiet=True)
    print(f"---- [{label}] {json.dumps(args)}")
    print(result.get("text") if "text" in result else json.dumps(result)[:1500])
    return result


def plate(run, doc, length=10):
    run.call("feature_body_create", {"doc": doc, "name": "Body"}, "given body", quiet=True)
    run.rect(doc, "Body", "Sketch", 0, 0, 60, 40, label="given")
    run.call("feature_pad", {"doc": doc, "body": "Body", "profile": "Sketch", "name": "Pad", "length": q(length)},
             "given pad", quiet=True)
    run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "given volume")


def s05(run, step, v):
    tag = "tc-02-05"
    if step == "given":
        doc = run.call("document_create", {"label": "tc-02-05-plate"}, "given create")["structured_content"]["doc"]
        save(tag, {"H": doc})
        plate(run, doc)
        tree(run, doc, "given focus Body", focus="Body")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        return
    doc = v["H"]
    if step == "when":
        tree(run, doc, "depth1", depth=1)
        tree(run, doc, "depth3", depth=3)
        tree(run, doc, "focus Body depth2", focus="Body", depth=2)
        tree(run, doc, "expand Pad", expand=["Pad"])
        tree(run, doc, "types PAD", filters={"types": ["PAD"]})
        tree(run, doc, "types PartDesign::Pad", filters={"types": ["PartDesign::Pad"]})
        tree(run, doc, "name_pattern ^Pad", filters={"name_pattern": "^Pad"})
        tree(run, doc, "types PAD + zzz", filters={"types": ["PAD"], "name_pattern": "zzz"})
        tree(run, doc, "unknown focus", focus="NoSuchObject")
        tree(run, doc, "focus Body before hide", focus="Body")
        tree(run, doc, "visible_only", filters={"visible_only": True})
        tree(run, doc, "unknown_filter", filters={"unknown_filter": True})
    elif step == "focus":
        tree(run, doc, sys.argv[3] if len(sys.argv) > 3 else "focus Body", focus="Body")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def s07(run, step, v):
    tag = "tc-02-07"
    if step == "given":
        doc = run.call("document_create", {"label": "tc-02-07-plate"}, "given create")["structured_content"]["doc"]
        save(tag, {"H": doc})
        plate(run, doc)
        tree(run, doc, "given depth3", depth=3)
        return
    doc = v["H"]
    if step == "when":
        run.call("query_dependencies", {"doc": doc, "object": "Pad"}, "per-object Pad")
        run.call("query_dependencies", {"doc": doc}, "whole document")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def s08(run, step, v):
    tag = "tc-02-08"
    if step == "given":
        doc = run.call("document_create", {"label": "tc-02-08-plate"}, "given create")["structured_content"]["doc"]
        save(tag, {"H": doc})
        plate(run, doc)
        run.py(doc, "doc.getObject('Body').Placement = App.Placement(App.Vector(30, 20, 10), "
                    "App.Rotation(App.Vector(0, 0, 1), 30)); doc.recompute()", "given body placement")
        run.call("query_placement", {"doc": doc, "object": "Body"}, "given body placement read")
        run.faces(doc, "Pad")
        return
    doc = v["H"]
    if step == "datum":
        run.call("feature_datum", {"doc": doc, "body": "Body", "name": "DatumPlane", "kind": "plane",
                                   "attachment": json.loads(sys.argv[3]), "offset": q(5)}, "given datum")
    elif step == "when":
        for name in ("Body", "Pad", "DatumPlane"):
            run.call("query_placement", {"doc": doc, "object": name}, f"placement {name}")
        run.py(doc, "s = doc.addObject('Spreadsheet::Sheet', 'NoPlacementSheet'); doc.recompute(); result = s.Name",
               "given no-placement object")
        run.call("query_placement", {"doc": doc, "object": "NoPlacementSheet"}, "placement NoPlacementSheet")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def s09(run, step, v):
    tag = "tc-02-09"
    if step == "given":
        run.call("document_list", {}, "given list")
        return
    if step == "list":
        result = run.call("document_list", {}, sys.argv[3] if len(sys.argv) > 3 else "list")
        docs = (result.get("structured_content") or {}).get("documents") or []
        if docs:
            save(tag, {"H": docs[0]["doc"]})
        return
    doc = v["H"]
    if step == "reads":
        tree(run, doc, "adopted tree")
        run.call("query_mass_properties", {"doc": doc, "object": "BoxHole"}, "adopted volume")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
    elif step == "close":
        run.call("document_close", {"doc": doc}, "cleanup close")


def s10(run, step, v):
    tag = "tc-02-10"
    if step == "given":
        a = run.call("document_open", {"path": f"{GOLDEN}/box-10-20-30.FCStd"}, "given open A")["structured_content"]["doc"]
        b = run.call("document_open", {"path": f"{GOLDEN}/two-box-compound.FCStd"}, "given open B")["structured_content"]["doc"]
        save(tag, {"A": a, "B": b})
        run.call("document_list", {}, "given list")
        return
    if step == "read1":
        result = tree(run, v["A"], "A first read")
        v["first"] = result
        save(tag, v)
    elif step == "read2":
        result = tree(run, v["A"], "A re-read")
        print("handle unchanged:", v["A"])
        print("equal field for field:", result == v["first"])
        tree(run, v["B"], "B tree")
        run.call("query_mass_properties", {"doc": v["B"], "object": "TwoBoxCompound"}, "B mass")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": v["B"]}, "then fit B")
    elif step == "close":
        run.call("document_close", {"doc": v["A"]}, "cleanup close A")
        run.call("document_close", {"doc": v["B"]}, "cleanup close B")


def s11(run, step, v):
    tag = "tc-02-11"
    if step == "given":
        doc = run.call("document_create", {"label": "tc-02-11-plate"}, "given create")["structured_content"]["doc"]
        save(tag, {"H": doc})
        plate(run, doc)
        tree(run, doc, "given depth2", depth=2)
        return
    doc = v["H"]
    if step == "when":
        tree(run, doc, "depth1", depth=1)
        tree(run, doc, "depth omitted")
        tree(run, doc, "depth0", depth=0)
        tree(run, doc, "depth-1", depth=-1)
        tree(run, doc, "max_nodes 0", max_nodes=0)
        tree(run, doc, "depth2 max_nodes 5", depth=2, max_nodes=5)
        tree(run, doc, "depth2 after rejections", depth=2)


def s14(run, step, v):
    tag = "tc-02-14"
    if step == "given":
        doc = run.call("document_create", {"label": "tc-02-14-nested"}, "given create")["structured_content"]["doc"]
        save(tag, {"H": doc})
        run.py(doc, "outer = doc.addObject('App::Part','OuterPart'); inner = doc.addObject('App::Part','InnerPart'); "
                    "outer.addObject(inner); box = doc.addObject('Part::Box','LinkTarget'); inner.addObject(box); "
                    "link = doc.addObject('App::Link','BoxLink'); link.LinkedObject = box; link.Placement.Base.x = 20; "
                    "outer.addObject(link); doc.recompute()", "given build")
        tree(run, doc, "given depth5", depth=5)
        return
    doc = v["H"]
    if step == "when":
        tree(run, doc, "depth1", depth=1)
        tree(run, doc, "depth5", depth=5)
        tree(run, doc, "depth5 again", depth=5)
        tree(run, doc, "focus InnerPart depth3", focus="InnerPart", depth=3)
        tree(run, doc, "focus LinkTarget", focus="LinkTarget")
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
    elif step == "close":
        run.call("document_close", {"doc": doc}, "cleanup close")


def s18(run, step, v):
    tag = "tc-02-18"
    if step == "given":
        return
    if step == "when":
        doc = run.call("document_open", {"path": f"{GOLDEN}/cylinder-r5-h20.FCStd"}, "when open")["structured_content"]["doc"]
        save(tag, {"H": doc})
        ev = str(EVIDENCE).replace("\\", "/")
        run.call("document_save", {"doc": doc, "path": f"{ev}/tc-02-18-readonly.FCStd"}, "save readonly")
        run.call("document_save", {"doc": doc, "path": f"{ev}/tc-02-18-no-such-dir/out.FCStd"}, "save missing dir")
        run.call("document_save", {"doc": doc, "path": ev}, "save onto directory")
        return
    doc = v["H"]
    if step == "then":
        ev = str(EVIDENCE).replace("\\", "/")
        tree(run, doc, "tree after failures")
        run.call("document_save", {"doc": doc, "path": f"{ev}/tc-02-18-writable.FCStd"}, "save writable")
        run.call("query_capabilities", {}, "caps", quiet=True)
    elif step == "fit":
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
    elif step == "close":
        run.call("document_close", {"doc": doc}, "cleanup close")


def close(run, step, v):
    run.call("document_close", {"doc": v["H"]}, "cleanup close")


def main():
    scenario, step = sys.argv[1], sys.argv[2]
    tag = f"tc-02-{scenario}"
    v = load(tag)
    with Run5(tag, limit=6000) as run:
        if step == "close" and scenario in ("05", "07", "08", "11"):
            close(run, step, v)
            return
        globals()[f"s{scenario}"](run, step, v)


if __name__ == "__main__":
    main()
