"""TC-08 agent-driven scenarios for phase P5, one function per step group: p5_tc08.py <name> [arg ...].
FreeCAD runs with FREECAD_BUDDY_AUTO_APPROVE=0, so every fixture mutation is previewed, then applied
with its confirm (p4_lib.Run4.mut). The GUI steps (fit fallback, capture) run through p1_gui.py /
p5_gui.py; the agent reads every capture."""

import json
import sys
import time
from datetime import datetime, timezone

from p4_lib import EDGE1
from p5_lib import Run5, q

TOKEN_FILE = (r"C:\Users\thuan\AppData\Local\Temp\claude\D--Work-Personal-Sources-freecad-buddy"
              r"\1d05bc05-6255-4b66-ad49-2004ccbeed34\scratchpad\tc-08-12-token.json")
PAD30 = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}


def out(label, value):
    print(f"CHECK {label}: {json.dumps(value, ensure_ascii=False)[:1500]}")


def sc(result):
    return result.get("structured_content") or {}


def fit(tag, doc):
    with Run5(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "fit")


def close(tag, *docs):
    with Run5(tag) as run:
        for doc in docs:
            run.call("document_close", {"doc": doc}, "cleanup close")


def pre():
    with Run5("tc-08-pre") as run:
        run.call("query_capabilities", {}, "freecad_version")
        doc = run.call("document_create", {"label": "tc-08-pre"}, "create")["structured_content"]["doc"]
        run.tempdocs(doc, "no stale preview TempDocs")
        run.call("document_close", {"doc": doc}, "cleanup")


def tc08_01_given():
    with Run5("tc-08-01") as run:
        doc = run.fixture_sketch("tc-08-01")
        print("DOC", doc)


def tc08_01(doc):
    with Run5("tc-08-01", limit=4000) as run:
        r = run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": PAD30}}, "when preview pad 30")
        diff = sc(r).get("diff") or {}
        out("status/detail/schema", [r.get("status"), r.get("detail"), diff.get("schema")])
        out("deltas", diff.get("deltas"))
        out("counts", diff.get("counts"))
        out("names", {k: diff.get(k) for k in ("touched", "new", "deleted")})
        out("validity", diff.get("validity"))
        out("tnp_precheck", diff.get("tnp_precheck"))
        out("token", [str(sc(r).get("preview_id"))[:16], sc(r).get("expires_at")])


def tc08_02_given():
    with Run5("tc-08-02") as run:
        doc = run.fixture_pad("tc-08-02")
        run.tempdocs(doc, "given no stale TempDocs")
        print("DOC", doc)


def tc08_02(doc):
    with Run5("tc-08-02", limit=1500) as run:
        m1 = run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "when mass before")
        l1 = run.call("document_list", {}, "when list before")
        r = run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_set_parameters",
                     "args": {"feature": "Pad", "parameters": {"Length": q(80)}}}}, "when preview Length 80")
        m2 = run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "when mass after")
        l2 = run.call("document_list", {}, "when list after")
        out("preview status / volume delta", [r.get("status"), (sc(r).get("diff") or {}).get("deltas", {}).get("volume")])
        out("volume before/after", [sc(m1).get("volume"), sc(m2).get("volume")])
        out("mass identical", json.dumps(sc(m1), sort_keys=True) == json.dumps(sc(m2), sort_keys=True))
        out("bbox/com equal", [sc(m1).get("bbox") == sc(m2).get("bbox"), sc(m1).get("com") == sc(m2).get("com")])
        out("list before/after", [[d["doc"] for d in sc(l1)["documents"]], [(d["doc"], d["name"]) for d in sc(l2)["documents"]]])
        run.tempdocs(doc, "then TempDoc check")
        f = run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": {
            "body": "Body", "base": "Pad", "name": "Fillet", "edges": EDGE1, "radius": q(500)}}}, "then failing preview (fillet 500)")
        out("failing preview", [f.get("status"), (f.get("detail") or {}).get("message") if isinstance(f.get("detail"), dict) else None,
                                (sc(f).get("diff") or {}).get("validity")])
        run.tempdocs(doc, "then TempDoc check after failing preview")


def tc08_05_given():
    with Run5("tc-08-05") as run:
        doc = run.fixture_pad("tc-08-05")
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, "given render port")
        out("render", [r.get("status"), (sc(r).get("render") or {}).get("resource_link")])
        print("DOC", doc)


def tc08_05(doc):
    with Run5("tc-08-05", limit=1200) as run:
        op = {"tool": "feature_set_parameters", "args": {"feature": "Pad", "parameters": {"Length": q(40)}}}
        a = run.call("preview_dry_run", {"doc": doc, "operation": op, "render": "off"}, "when render off")
        b = run.call("preview_dry_run", {"doc": doc, "operation": op, "render": "auto"}, "when render auto")
        c = run.call("preview_dry_run", {"doc": doc, "operation": op, "render": "sometimes"}, "then render sometimes")
        out("off", [a.get("status"), (sc(a).get("diff") or {}).get("render")])
        out("auto", [b.get("status"), (sc(b).get("diff") or {}).get("render")])
        out("sometimes", c)


def tc08_06_given():
    with Run5("tc-08-06", limit=1500) as run:
        doc = run.fixture_sketch("tc-08-06")
        u = run.call("document_undo", {"doc": doc}, "given undo available (undoes the sketch geometry)")
        out("given undo", [u.get("status"), (u.get("detail") or {}).get("message") if isinstance(u.get("detail"), dict) else None,
                           sc(u).get("undone")])
        geometry = [{"kind": "line_segment", "start": s, "end": e} for s, e in
                    (([0, 0], [20, 0]), ([20, 0], [20, 20]), ([20, 20], [0, 20]), ([0, 20], [0, 0]))]
        constraints = [
            {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
            {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
            {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
            {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
            {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
            {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
            {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(20)},
            {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(20)},
            {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        ]
        run.mut(doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": geometry, "constraints": constraints},
                "given re-apply sketch geometry", quiet=True)
        v = run.call("verify_sketch", {"doc": doc, "sketch": "Sketch"}, "given verify_sketch")
        out("sketch", (sc(v).get("subject") or {}))
        print("DOC", doc)


def undo_summary(label, u):
    s = sc(u)
    out(label, {"status": u.get("status"), "detail": u.get("detail") if u.get("status") != "OK" else None,
                "matches_pre_op": s.get("matches_pre_op"), "fingerprint_before": s.get("fingerprint_before"),
                "fingerprint_after": s.get("fingerprint_after"), "undone": s.get("undone"),
                "restored_objects": s.get("restored_objects"), "undo_count": s.get("undo_count"), "text": u.get("text")})


def tc08_06(doc):
    with Run5("tc-08-06", limit=1500) as run:
        _, a = run.mut(doc, "feature_pad", PAD30, "when pad 1")
        fp = (sc(a).get("mutation") or {}).get("fingerprint_before") or {}
        out("pad 1 fingerprint_before", fp)
        u1 = run.call("document_undo", {"doc": doc, "expect_fingerprint": fp.get("digest")}, "when undo string form")
        undo_summary("undo string form", u1)
        _, a2 = run.mut(doc, "feature_pad", PAD30, "when pad 2")
        fp2 = (sc(a2).get("mutation") or {}).get("fingerprint_before") or {}
        out("pad 2 fingerprint_before", fp2)
        u2 = run.call("document_undo", {"doc": doc, "expect_fingerprint": fp2}, "when undo object form")
        undo_summary("undo object form", u2)
        run.mut(doc, "feature_pad", PAD30, "then pad 3 (for the no-expectation undo)", quiet=True)
        u3 = run.call("document_undo", {"doc": doc}, "then undo without expect_fingerprint")
        undo_summary("undo no expectation", u3)
        t1 = run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree before wrong type")
        u4 = run.call("document_undo", {"doc": doc, "expect_fingerprint": 42}, "then undo expect_fingerprint 42")
        out("undo 42", u4)
        t2 = run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree after wrong type")
        out("tree unchanged by the refused undo", t1 == t2)


def tc08_12_part1(doc):
    with Run5("tc-08-12", limit=1500) as run:
        call_time = datetime.now(timezone.utc)
        p = run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_body_create", "args": {"name": "Probe"}}},
                     "when preview Probe")
        token = sc(p).get("preview_id")
        expires = sc(p).get("expires_at")
        out("call time / expires_at", [call_time.isoformat(), expires])
        try:
            exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            out("expires_at - call time (s)", (exp - call_time).total_seconds())
        except Exception as exc:  # report, do not stop
            out("expires parse", str(exc))
        a = run.call("feature_body_create", {"doc": doc, "name": "Probe", "confirm": {"preview_id": token}}, "when apply (spends)")
        out("apply", [a.get("status")])
        time.sleep(1.0)
        s = run.call("feature_body_create", {"doc": doc, "name": "Probe", "confirm": {"preview_id": token}},
                     "then spent-not-expired (1 s after apply)")
        out("spent", [s.get("status"), s.get("detail", {}).get("message") if isinstance(s.get("detail"), dict) else s])
        with open(TOKEN_FILE, "w", encoding="utf-8") as handle:
            json.dump({"token": token, "expires_at": expires, "mint_call_utc": call_time.isoformat()}, handle)
        print("token stored in the session scratchpad (removed after part 2)")


def tc08_12_part2(doc):
    import os
    with open(TOKEN_FILE, encoding="utf-8") as handle:
        saved = json.load(handle)
    with Run5("tc-08-12", limit=1500) as run:
        now = datetime.now(timezone.utc)
        out("now / expires_at", [now.isoformat(), saved["expires_at"]])
        e = run.call("feature_body_create", {"doc": doc, "name": "Probe", "confirm": {"preview_id": saved["token"]}},
                     "when spent-and-expired")
        out("expired", [e.get("status"), e.get("detail", {}).get("message") if isinstance(e.get("detail"), dict) else e])
    os.remove(TOKEN_FILE)


def tc08_12_part3(doc):
    with Run5("tc-08-12", limit=1500) as run:
        t = run.call("query_tree_summary", {"doc": doc, "depth": 2}, "then tree before Probe3")
        p, a = run.mut(doc, "feature_body_create", {"name": "Probe3"}, "then fresh token Probe3")
        out("Probe3 apply", a.get("status"))


GATED = [
    ("feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad2", "length": q(30)}),
    ("feature_pocket", {"body": "Body", "profile": "Sketch", "name": "Pocket2", "length": q(5)}),
    ("feature_revolve", {"body": "Body", "profile": "Sketch", "name": "Rev2",
                         "axis": {"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}}),
    ("feature_hole", {"body": "Body", "profile": "Sketch", "name": "Hole2"}),
    ("feature_fillet", {"body": "Body", "base": "Fillet", "name": "Fillet2",
                        "edges": [{"kind": "mapped_name", "object": "Fillet", "mapped_name": "Edge1"}], "radius": q(1)}),
    ("feature_chamfer", {"body": "Body", "base": "Fillet", "name": "Chamfer2",
                         "edges": [{"kind": "mapped_name", "object": "Fillet", "mapped_name": "Edge1"}], "size": q(1)}),
    ("feature_pattern", {"body": "Body", "name": "Pattern2", "kind": "linear", "features": ["Pad"]}),
    ("feature_mirror", {"body": "Body", "name": "Mirror2",
                        "mirror_plane": {"kind": "mapped_name", "object": "Pad", "mapped_name": "Face1"}}),
    ("feature_datum", {"body": "Body", "name": "Datum2", "kind": "plane",
                       "attachment": {"kind": "mapped_name", "object": "Pad", "mapped_name": "Face1"}}),
    ("feature_body_create", {"name": "Body2"}),
    ("feature_set_parameters", {"feature": "Pad", "parameters": {"Length": q(35)}}),
    ("sketch_create", {"name": "Sketch2", "plane": "XZ", "body": "Body"}),
    ("sketch_add_geometry", {"sketch": "Sketch", "geometry": [{"kind": "line_segment", "start": [2, 2], "end": [5, 5]}]}),
    ("sketch_remove_geometry", {"sketch": "Sketch", "geo_ids": [0]}),
    ("sketch_add_constraint", {"sketch": "Sketch", "constraints": [{"type": "Horizontal", "first": 0}]}),
    ("sketch_remove_constraint", {"sketch": "Sketch", "constraints": [1]}),
    ("sketch_set_datum", {"sketch": "Sketch", "constraint": 9, "value": q(25)}),
    ("sketch_toggle_construction", {"sketch": "Sketch", "geo_ids": [0]}),
    ("sketch_add_external_geometry", {"sketch": "Sketch", "edge": {"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}}),
]
GATE_MESSAGE = ("this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as "
                "confirm.preview_id")


def tc08_17_given():
    with Run5("tc-08-17") as run:
        doc = run.fixture_fillet("tc-08-17")
        run.call("query_tree_summary", {"doc": doc, "depth": 4}, "given tree")
        print("DOC", doc)


def tc08_17_refusals(doc):
    with Run5("tc-08-17", limit=600) as run:
        t1 = run.call("query_tree_summary", {"doc": doc, "depth": 4}, "when tree before")
        rows = []
        for tool, args in GATED:
            r = run.call(tool, {"doc": doc, **args}, f"when {tool} without confirm", quiet=True)
            message = r.get("detail", {}).get("message") if isinstance(r.get("detail"), dict) else r.get("text")
            rows.append((tool, r.get("status"), message == GATE_MESSAGE, message if message != GATE_MESSAGE else "<gate message>"))
        for row in rows:
            print("ROW", row)
        print("CHECK refused", sum(1 for r in rows if r[1] != "OK"), "of", len(rows), "; gate message on",
              sum(1 for r in rows if r[2]))
        n = run.call("feature_pad", {"doc": doc, **GATED[0][1], "confirm": None}, "then confirm null")
        out("confirm null", n)
        t2 = run.call("query_tree_summary", {"doc": doc, "depth": 4}, "then tree after")
        out("tree unchanged", t1 == t2)


def tc08_17_rest(doc, evidence):
    with Run5("tc-08-17", limit=900) as run:
        s = run.call("document_save", {"doc": doc, "path": f"{evidence}/tc-08-17-save.FCStd"}, "then save without confirm")
        e = run.call("export_stl", {"doc": doc, "objects": ["Pad"], "path": f"{evidence}/tc-08-17-export.stl"},
                     "then export_stl without confirm")
        out("save/export", [s.get("status"), e.get("status")])
        for tool, args in (("feature_body_create", {"name": "Probe"}),
                           ("sketch_create", {"name": "Sketch2", "plane": "XZ", "body": "Body"}),
                           ("feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(1.5)}})):
            p, a = run.mut(doc, tool, args, f"then sample {tool}")
            out(f"sample {tool}", [p.get("status"), a.get("status")])
        v = run.call("feature_set_parameters", {"doc": doc, "feature": "Pad", "parameters": {"Visibility": False}},
                     "then display-state Visibility false, no confirm")
        out("visibility false", [v.get("status"), (sc(v).get("mutation") or {}).get("changed")])
        r = run.call("feature_set_parameters", {"doc": doc, "feature": "Pad", "parameters": {"Visibility": True}},
                     "then restore Visibility true, no confirm")
        out("visibility true", [r.get("status"), (sc(r).get("mutation") or {}).get("changed")])


def tc08_18_fixture(path):
    with Run5("tc-08-18") as run:
        doc = run.fixture_sketch("tc-08-18-fixture")
        run.call("document_save", {"doc": doc, "path": path}, "given save fixture")
        run.call("document_close", {"doc": doc}, "given close fixture")


def tc08_19_given():
    with Run5("tc-08-19") as run:
        doc = run.fixture_sketch("tc-08-19")
        run.tempdocs(doc, "given no stale TempDocs")
        print("DOC", doc)


def tc08_19(doc, evidence):
    with Run5("tc-08-19", limit=1500) as run:
        for label, op in (("document_save", {"tool": "document_save", "args": {"path": f"{evidence}/tc-08-19-save.FCStd"}}),
                          ("script_exec", {"tool": "script_exec", "args": {"code": "1"}}),
                          ("no_such_tool", {"tool": "no_such_tool", "args": {}}),
                          ("missing tool", {"args": {"name": "Pad"}}),
                          ("args not object", {"tool": "feature_pad", "args": "not an object"})):
            r = run.call("preview_dry_run", {"doc": doc, "operation": op}, f"when {label}")
            msg = r.get("detail", {}).get("message") if isinstance(r.get("detail"), dict) else r.get("text")
            out(label, [r.get("status"), msg])
        run.tempdocs(doc, "then TempDoc check")
        m = run.call("preview_dry_run", {"doc": doc}, "then missing operation")
        out("missing operation", m)


def tc08_20_given():
    with Run5("tc-08-20") as run:
        b = run.call("document_create", {"label": "tc-08-20-B"}, "given doc B")["structured_content"]["doc"]
        a = run.fixture_sketch("tc-08-20-A")
        run.call("document_list", {}, "given two handles")
        print("DOC A", a, "B", b)


def tc08_20(a, b):
    with Run5("tc-08-20", limit=1200) as run:
        args = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
        r1 = run.call("preview_dry_run", {"doc": a, "operation": {"tool": "feature_pad", "args": {"doc": a, **args}}},
                      "when args.doc = A")
        r2 = run.call("preview_dry_run", {"doc": a, "operation": {"tool": "feature_pad", "args": {"doc": b, **args}}},
                      "when args.doc = B")
        for label, r in (("args.doc A", r1), ("args.doc B", r2)):
            out(label, [r.get("status"), r.get("detail", {}).get("message") if isinstance(r.get("detail"), dict) else r])
        run.tempdocs(a, "then TempDoc check on A")
        run.call("query_tree_summary", {"doc": a, "depth": 3}, "then tree A")
        run.call("query_tree_summary", {"doc": b, "depth": 3}, "then tree B")
        ok = run.call("preview_dry_run", {"doc": a, "operation": {"tool": "feature_pad", "args": args}}, "then without args.doc")
        token = sc(ok).get("preview_id")
        out("without args.doc", ok.get("status"))
        x = run.call("feature_pad", {"doc": b, **args, "confirm": {"preview_id": token}}, "then apply A's token on B")
        out("token on B", [x.get("status"), x.get("detail", {}).get("message") if isinstance(x.get("detail"), dict) else x])
        run.call("query_tree_summary", {"doc": b, "depth": 3}, "then tree B after")


def tc08_21_given():
    with Run5("tc-08-21") as run:
        doc = run.call("document_create", {"label": "UndoProbe"}, "given UndoProbe")["structured_content"]["doc"]
        print("DOC", doc)


def tc08_21_stack(doc):
    with Run5("tc-08-21", limit=1500) as run:
        e1 = run.call("document_undo", {"doc": doc}, "when undo on empty stack")
        undo_summary("empty stack", e1)
        p, a = run.mut(doc, "feature_body_create", {"name": "Body"}, "when body create")
        out("body create", a.get("status"))
        u = run.call("document_undo", {"doc": doc}, "when first undo")
        undo_summary("first undo", u)
        e2 = run.call("document_undo", {"doc": doc}, "when undo past bottom")
        undo_summary("past bottom", e2)
        run.call("query_tree_summary", {"doc": doc, "depth": 2}, "then tree")


PATCH = ("from freecad_buddy.usecases import shim\nshim._saved_enable_undo = shim.enable_undo\n"
         "shim.enable_undo = lambda document: False\ndoc.UndoMode = 0")
UNPATCH = ("from freecad_buddy.usecases import shim\nshim.enable_undo = shim._saved_enable_undo\n"
           "del shim._saved_enable_undo\ndoc.UndoMode = 1")


def tc08_21_faults():
    with Run5("tc-08-21", limit=1500) as run:
        off = run.call("document_create", {"label": "UndoOff"}, "when UndoOff")["structured_content"]["doc"]
        run.py(off, PATCH, "when plant UndoMode 0")
        u = run.call("document_undo", {"doc": off}, "when undo on UndoMode 0")
        undo_summary("UndoMode 0", u)
        r = run.py(off, UNPATCH, "when restore UndoMode 1")
        out("restore", r.get("status"))
        run.py(off, "doc.addObject('Part::Box', 'Box')\ndoc.recompute()", "when add Box (no transaction)")
        p, a = run.mut(off, "feature_body_create", {"name": "Probe"}, "when typed mutation Probe")
        out("Probe", a.get("status"))
        run.py(off, "doc.getObject('Box').Length = 0", "when break Box outside the undo stack")
        b = run.call("document_undo", {"doc": off}, "when undo that recomputes the broken Box")
        undo_summary("broken undo", b)
        out("broken undo errors", sc(b).get("errors") or b.get("detail"))
        print("DOC OFF", off)


def tc08_21_txn_given():
    with Run5("tc-08-21") as run:
        doc = run.fixture_pad("TxnProbe")
        print("DOC TXN", doc)


def tc08_21_txn(doc):
    with Run5("tc-08-21", limit=1500) as run:
        run.py(doc, "result = (doc.HasPendingTransaction, doc.getAvailableUndoNames()[:3])", "when GUI transaction state")
        u = run.call("document_undo", {"doc": doc}, "when undo with a GUI-open transaction")
        undo_summary("open transaction", u)



def fixture_sketch(tag, label):
    with Run5(tag) as run:
        doc = run.fixture_sketch(label)
        print("DOC", doc)


if __name__ == "__main__":
    globals()[sys.argv[1]](*sys.argv[2:])
