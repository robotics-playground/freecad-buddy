"""TC-09 agent-driven MCP steps for phase P7 against the :8765 proxy: p7_tc09.py <command> [arg ...].

Every MCP call goes to evidence/<tag>-mcp.jsonl through Run7 (p5_lib.Run5 that also keeps the
call's isError flag). ``rejection`` means an MCP protocol rejection: isError set and no
structuredContent, so the client sees only text and no envelope status. The GUI steps (Show All,
capture) run through p1_gui.py; the agent reads every capture.

    open <tag> <golden stem>       document_open + query_tree_summary; prints H and the first object
    fit <tag> <doc>                view_fit_viewport
    close <tag> <doc> ...          document_close each, then document_list
    list <tag>                     document_list
    s04 .. s23 <args>              the scenario's When calls and the checks its Thens name
"""

import json
import os
import re
import sys
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[4]
GOLDEN = REPO / "benchmarks" / "g0" / "golden-models"
ADDON_LOG = Path(os.environ["APPDATA"]) / "FreeCAD" / "v1-1" / "freecad-buddy" / "addon.log"


class Run7(Run5):
    def call(self, tool, args, label="", quiet=False):
        raw = self.client.call(tool, args)
        self.is_error, result = raw["__is_error"], raw["__result"]
        self.log.write(json.dumps({"label": label, "mcp": tool, "args": args, "is_error": self.is_error,
                                   "content_types": raw["__content_types"], "result": result},
                                  ensure_ascii=False) + "\n")
        self.log.flush()
        if quiet:
            print(f"== [{label}] {tool} -> {result.get('status')}")
        else:
            shown = {k: v for k, v in args.items() if k != "doc"}
            print(f"== [{label}] {tool} {json.dumps(shown, ensure_ascii=False)[:240]}")
            print(f"   isError={self.is_error} {json.dumps(result, ensure_ascii=False)[:self.limit]}")
        return result


def out(label, value):
    print(f"CHECK {label}: {json.dumps(value, ensure_ascii=False)[:3000]}")


def sc(result):
    return result.get("structured_content") or {}


def msg(result):
    detail = result.get("detail")
    return detail.get("message") if isinstance(detail, dict) else None


def rejection(result):
    """An MCP protocol rejection: isError, no structuredContent (to_result keeps text + is_error only)."""
    return set(result) == {"text", "is_error"} and result["is_error"] is True


def first_line(result):
    text = result.get("text") or ""
    return text.strip().splitlines()[0] if text.strip() else ""


def tree_lines(result):
    """Rule 9: the lines after the first line and the optional ``framing:`` line."""
    lines = (result.get("text") or "").strip().splitlines()[1:]
    if lines and lines[0].startswith("framing:"):
        lines = lines[1:]
    return lines


def shown(line):
    match = re.match(r"(\w+): (\d+) objects, (\d+) shown", line)
    return (match.group(1), int(match.group(2)), int(match.group(3))) if match else None


def ev(name):
    return str(EVIDENCE / name)


def addon_offset():
    return ADDON_LOG.stat().st_size


def addon_since(offset, name):
    with ADDON_LOG.open("rb") as handle:
        handle.seek(offset)
        data = handle.read().decode("utf-8", "replace")
    (EVIDENCE / name).write_text(data, encoding="utf-8")
    return data


def object_count(run, doc):
    return sc(run.py(doc, "result = len(doc.Objects)", "oracle object count")).get("value_repr")


def cmd_open(tag, stem):
    with Run7(tag) as run:
        r = run.call("document_open", {"path": str(GOLDEN / f"{stem}.FCStd")}, "given open")
        doc = sc(r).get("doc")
        t = run.call("query_tree_summary", {"doc": doc}, "given tree")
        names = [line.split(" ")[2] for line in tree_lines(t) if line[:1] in ("v", "-")]
        print(f"H={doc} OBJ={names[0] if names else None}")


def cmd_fit(tag, doc):
    with Run7(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "fit")


def cmd_close(tag, *docs):
    with Run7(tag) as run:
        for doc in docs:
            run.call("document_close", {"doc": doc}, "cleanup close")
        r = run.call("document_list", {}, "cleanup list")
        out("open documents", [(d.get("doc"), d.get("label")) for d in sc(r).get("documents", [])])


def cmd_list(tag):
    with Run7(tag) as run:
        r = run.call("document_list", {}, "list")
        out("open documents", [(d.get("doc"), d.get("label")) for d in sc(r).get("documents", [])])


def s04(doc, obj):
    with Run7("tc-09-04") as run:
        calls = [
            ("query_tree_summary", {"doc": doc, "depth": "1"}),
            ("export_step", {"doc": doc, "path": 42, "objects": [obj]}),
            ("export_step", {"doc": doc, "path": ev("tc-09-04-t.step"), "objects": {"0": obj}}),
            ("export_stl", {"doc": doc, "path": ev("tc-09-04-t.stl"), "linear": "0.1"}),
        ]
        results = [run.call(tool, args, "when") for tool, args in calls]
        out("rejections", [rejection(r) for r in results])
        out("texts", [r.get("text") for r in results])
        out("any status OK", [r.get("status") for r in results])
        out("tc-09-04-t.* files", sorted(p.name for p in EVIDENCE.glob("tc-09-04-t.*")))


def s05(doc, obj):
    surface = json.loads((EVIDENCE / "tc-09-05-tool_surface.json").read_text(encoding="utf-8"))
    out("surface command", sorted(k for k, v in surface.items() if v["addProps"] is not False))
    with Run7("tc-09-05") as run:
        calls = [
            ("verify_shape", {"doc": doc, "object": obj, "strict": True}),
            ("query_tree_summary", {"doc": doc, "max_nodes": 50}),
            ("export_step", {"doc": doc, "path": ev("tc-09-05-u.step"), "overwrite": True}),
            ("document_close", {"doc": doc, "force": True}),
            ("query_capabilities", {"verbose": True}),
        ]
        results = [run.call(tool, args, "when") for tool, args in calls]
        out("rejections", [rejection(r) for r in results])
        out("texts", [r.get("text") for r in results])
        out("statuses", [r.get("status") for r in results])
        listed = run.call("document_list", {}, "then document_list")
        out("document_list names H", doc in [d.get("doc") for d in sc(listed).get("documents", [])])
        out("tc-09-05-u.step exists", (EVIDENCE / "tc-09-05-u.step").exists())


def s07(doc):
    offset = addon_offset()
    with Run7("tc-09-07") as run:
        actual = object_count(run, doc)
        out("actual object count (oracle)", actual)
        depth = {}
        for value in (0, -1, 2147483647, 1):
            depth[value] = run.call("query_tree_summary", {"doc": doc, "depth": value}, f"when depth {value}")
        out("depth 0 / -1 rejections", [rejection(depth[0]), rejection(depth[-1])])
        out("depth 0 / -1 texts", [depth[0].get("text"), depth[-1].get("text")])
        big = depth[2147483647]
        out("depth max first line", first_line(big))
        out("depth max shown vs actual", [shown(first_line(big)), actual])
        one = depth[1]
        lines = tree_lines(one)
        out("depth 1 first line", first_line(one))
        out("depth 1 shown vs tree lines", [shown(first_line(one)), len(lines)])
        out("depth 1 connector lines", [line for line in lines if line.startswith(("|-- ", "`-- "))])
        edges = {}
        for value in (0, -1, 1):
            edges[value] = run.call("query_dependencies", {"doc": doc, "max_edges": value}, f"when max_edges {value}")
        out("max_edges 0 / -1 rejections", [rejection(edges[0]), rejection(edges[-1])])
        out("max_edges 0 / -1 texts", [edges[0].get("text"), edges[-1].get("text")])
        out("max_edges 1", [edges[1].get("status"), sc(edges[1])])
        base = {"doc": doc, "body": "Body", "name": "TC0907Pattern", "kind": "linear",
                "direction": {"kind": "mapped_name", "object": "BoxHole", "mapped_name": "Edge1"},
                "length": {"value": 20, "unit": "mm"}}
        pattern = [run.call("feature_pattern", {**base, "occurrences": n}, f"when occurrences {n}") for n in (0, 1)]
        out("occurrences 0 / 1 rejections", [rejection(r) for r in pattern])
        out("occurrences 0 / 1 texts", [r.get("text") for r in pattern])
        out("object count after (oracle)", object_count(run, doc))
    log = addon_since(offset, "tc-09-07-addonlog.txt")
    out("addon log since offset: ValidationError / Traceback lines",
        [line for line in log.splitlines() if "ValidationError" in line or "Traceback" in line])
    edge_log = (EVIDENCE / "tc-09-01-edge.stderr.log").read_text(encoding="utf-8", errors="replace")
    out("tc-09-01-edge.stderr.log ValidationError traceback lines",
        [line for line in edge_log.splitlines() if "Traceback" in line])


def s08(doc, obj):
    with Run7("tc-09-08") as run:
        absent = run.call("verify_shape", {"doc": doc, "object": obj}, "when checks absent")
        null = run.call("verify_shape", {"doc": doc, "object": obj, "checks": None}, "when checks null")
        empty = run.call("verify_shape", {"doc": doc, "object": obj, "checks": []}, "when checks []")

        def facts(result):
            return [(c.get("id"), "expected" in c) for c in sc(result).get("checks", [])]

        out("checks absent", [absent.get("status"), facts(absent)])
        out("checks null rejection", [rejection(null), null.get("text")])
        out("checks [] ", [empty.get("status"), facts(empty)])
        out("same fact ids", [c[0] for c in facts(absent)] == [c[0] for c in facts(empty)])
        d_absent = run.call("query_tree_summary", {"doc": doc}, "when depth absent")
        d_null = run.call("query_tree_summary", {"doc": doc, "depth": None}, "when depth null")
        top = [line for line in tree_lines(d_absent) if line[:1] in ("v", "-")]
        out("depth absent first line / top-level lines / all tree lines",
            [first_line(d_absent), len(top), len(tree_lines(d_absent))])
        out("depth null rejection", [rejection(d_null), d_null.get("text")])
        a_absent = run.call("export_step", {"doc": doc, "path": ev("tc-09-08-n.step")}, "when ap absent")
        a_null = run.call("export_step", {"doc": doc, "path": ev("tc-09-08-n2.step"), "ap": None}, "when ap null")
        out("ap absent status", a_absent.get("status"))
        path = EVIDENCE / "tc-09-08-n.step"
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        out("grep -c AP242 tc-09-08-n.step", sum("AP242" in line for line in text.splitlines()))
        out("FILE_SCHEMA line", [line for line in text.splitlines() if "FILE_SCHEMA" in line])
        out("ap null rejection", [rejection(a_null), a_null.get("text")])
        out("tc-09-08-n2.step exists", (EVIDENCE / "tc-09-08-n2.step").exists())


def s09(doc):
    offset = addon_offset()
    with Run7("tc-09-09", limit=600) as run:
        label = "a" * 4096
        created = run.call("document_create", {"label": label}, "when label 4096")
        out("label 4096 status", [created.get("status"), sc(created).get("doc")])
        listed = run.call("document_list", {}, "then document_list")
        match = [d for d in sc(listed).get("documents", []) if d.get("doc") == sc(created).get("doc")]
        out("document_list label length", [len(d.get("label") or "") for d in match])
        path = ev("tc-09-09-" + "b" * 8192 + ".FCStd")
        opened = run.call("document_open", {"path": path}, "when path 8192")
        out("long path status / message names path / message length",
            [opened.get("status"), path in (msg(opened) or ""), len(msg(opened) or "")])
        name = "c" * 65536
        queried = run.call("query_object", {"doc": doc, "object": name}, "when object 65536")
        out("long object status / message prefix / equals",
            [queried.get("status"), (msg(queried) or "")[:30], msg(queried) == f"unknown object: {name}"])
        for label_, result in (("path", opened), ("object", queried)):
            data = (result.get("detail") or {}).get("data") or {}
            out(f"{label_} traceback length", len(data.get("traceback") or ""))
        capabilities = run.call("query_capabilities", {}, "then query_capabilities", quiet=True)
        out("query_capabilities after", capabilities.get("status"))
        print("H_LONG", sc(created).get("doc"))
    log = addon_since(offset, "tc-09-09-addonlog.txt")
    out("addon log handshake / frame lines",
        [line[:300] for line in log.splitlines() if "handshake required" in line or "frame" in line.lower()])


def s10(doc, obj):
    offset = addon_offset()
    with Run7("tc-09-10") as run:
        nested = "leaf"
        for _ in range(10):
            nested = {"a": nested}
        deep = run.call("verify_shape", {"doc": doc, "object": obj, "checks": [{"fn": nested}]}, "when nested fn")
        plain = run.call("verify_shape", {"doc": doc, "object": obj, "checks": ["expect_volume"]}, "when non-object")
        tol = run.call("verify_shape", {"doc": doc, "object": obj, "checks": [
            {"fn": "expect_volume", "expect": 6000, "tol": {"rel": {"deep": {"deeper": 0.001}}}}]}, "when nested tol")
        out("nested fn", [deep.get("status"), msg(deep), rejection(deep)])
        out("non-object", [rejection(plain), plain.get("text")])
        out("nested tol", [tol.get("status"), msg(tol), rejection(tol)])
        out("nested fn / tol carry a status", ["status" in deep, "status" in tol])
        after = run.call("verify_shape", {"doc": doc, "object": obj}, "then survives")
        out("verify_shape after", after.get("status"))
    log = addon_since(offset, "tc-09-10-addonlog.txt")
    edge_log = (EVIDENCE / "tc-09-01-edge.stderr.log").read_text(encoding="utf-8", errors="replace")
    out("RecursionError in edge stderr / addon log",
        [line for line in edge_log.splitlines() + log.splitlines() if "recursionerror" in line.lower()])


def s11(doc):
    surface = json.loads((EVIDENCE / "tc-09-05-tool_surface.json").read_text(encoding="utf-8"))
    with Run7("tc-09-11") as run:
        results = [run.call("query_tree_summary", {"doc": doc, "max_nodes": n}, f"when max_nodes {n}") for n in (0, 50)]
        out("rejections", [rejection(r) for r in results])
        out("texts", [r.get("text") for r in results])
        out("any OK / truncated", [(r.get("status"), "truncated" in (r.get("text") or "")) for r in results])
        out("property-list command", surface["query_tree_summary"]["props"])
        plain = run.call("query_tree_summary", {"doc": doc}, "then plain")
        out("plain first line / truncated", [first_line(plain), "truncated" in first_line(plain)])
        one = run.call("query_tree_summary", {"doc": doc, "depth": 1}, "then depth 1")
        out("depth 1 shown vs tree lines", [shown(first_line(one)), len(tree_lines(one))])
    report = json.loads((EVIDENCE / "tc-09-01-edge_report.json").read_text(encoding="utf-8"))
    out("edge report retired_max_nodes_rejected",
        [c for c in report["checks"] if c["tool"] == "retired_max_nodes_rejected"])


def s13(doc):
    with Run7("tc-09-13") as run:
        reads = [run.call(tool, {"doc": doc, "object": "NoSuchObject"}, "when")
                 for tool in ("query_object", "query_mass_properties", "query_placement", "verify_shape")]
        out("read statuses", [r.get("status") for r in reads])
        out("read messages", [msg(r) for r in reads])
        export = run.call("export_step", {"doc": doc, "path": ev("tc-09-13-o.step"), "objects": ["NoSuchObject"]},
                          "when export")
        out("export", [export.get("status"), msg(export)])
        out("tc-09-13-o.step exists", (EVIDENCE / "tc-09-13-o.step").exists())
        case = [run.call(tool, {"doc": doc, "object": "box"}, "then case") for tool in ("query_object", "verify_shape")]
        out("case-differing name", [(r.get("status"), msg(r)) for r in case])
        empty = run.call("verify_shape", {"doc": doc, "object": ""}, "then empty name")
        out("empty object name", [empty.get("status"), msg(empty), (sc(empty).get("subject") or {})])


def s14():
    offset = addon_offset()
    with Run7("tc-09-14") as run:
        doc = run.fixture_pad("TC0914")
        run.call("verify_sketch", {"doc": doc, "sketch": "Sketch"}, "given verify_sketch")
        before = run.call("query_tree_summary", {"doc": doc}, "given node count")
        out("node count before", first_line(before))
        print(f"H={doc}")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
    print("NOW_CAPTURE_BEFORE")
    return doc, offset


def s14_when(doc, offset):
    offset = int(offset)
    with Run7("tc-09-14") as run:
        sketch = [run.call(tool, {"doc": doc, "sketch": "NoSuchSketch"}, "when")
                  for tool in ("verify_sketch", "query_sketch_info")]
        out("unknown sketch", [(r.get("status"), msg(r)) for r in sketch])
        wrong = run.call("verify_sketch", {"doc": doc, "sketch": "Body"}, "when non-sketch")
        out("non-sketch Body", [wrong.get("status"), msg(wrong)])
        feature = run.call("feature_set_parameters", {"doc": doc, "feature": "NoSuchFeature",
                                                      "parameters": {"Length": {"value": 12, "unit": "mm"}}},
                           "when unknown feature")
        out("unknown feature", [feature.get("status"), msg(feature)])
        recompute = run.call("verify_recompute", {"doc": doc}, "then verify_recompute")
        out("verify_recompute", recompute.get("status"))
        after = run.call("query_tree_summary", {"doc": doc}, "then node count")
        out("node count after", first_line(after))
    log = addon_since(offset, "tc-09-14-addonlog.txt")
    out("addon log INFO lines with INVALID_INPUT", [line[:240] for line in log.splitlines() if "INVALID_INPUT" in line])
    out("addon log Traceback lines", [line for line in log.splitlines() if "Traceback" in line])


def s15(doc):
    with Run7("tc-09-15") as run:
        result = run.call("verify_recompute", {"doc": {"handle": "fcb-doc:x"}}, "when H2")
        out("H2", [rejection(result), result.get("text")])


def s16(doc):
    with Run7("tc-09-16") as run:
        before = {d.get("doc") for d in sc(run.call("document_list", {}, "given list")).get("documents", [])}
        paths = [ev("tc-09-16-nope-missing.FCStd"), ev("tc-09-16-no_such_dir/x.FCStd"), "",
                 str(REPO / "AGENTS.md")]
        results = [run.call("document_open", {"path": p}, "when") for p in paths]
        out("statuses", [r.get("status") for r in results])
        out("messages", [msg(r) for r in results])
        out("message contains sent path", [p in (msg(r) or "") for p, r in zip(paths, results)])
        out("AGENTS.md message has 'Invalid project file <path>'",
            f"Invalid project file {paths[3]}" in (msg(results[3]) or ""))
        out("structured_content.doc present", [bool(sc(r).get("doc")) for r in results])
        after = {d.get("doc") for d in sc(run.call("document_list", {}, "then list")).get("documents", [])}
        out("new handles", sorted(after - before))
    report = json.loads((EVIDENCE / "tc-09-01-edge_report.json").read_text(encoding="utf-8"))
    out("edge report open_bad_path", [c for c in report["checks"] if c["tool"] == "open_bad_path"])


def s23_round(stem):
    with Run7("tc-09-23") as run:
        r = run.call("document_open", {"path": str(GOLDEN / f"{stem}.FCStd")}, "round trip open")
        doc = sc(r).get("doc")
        shape = run.call("verify_shape", {"doc": doc, "object": "Box",
                                          "checks": [{"fn": "expect_volume", "expect": 6000}]}, "round trip verify_shape")
        step = run.call("export_step", {"doc": doc, "path": ev("tc-09-23-rt.step")}, "round trip export_step")
        export_id = sc(step).get("export_id")
        verified = run.call("verify_export_step", {"doc": doc, "export_id": export_id}, "round trip verify_export_step")
        volume = {c.get("id"): c for c in sc(verified).get("checks", [])}.get("export_step.volume") or {}
        out("statuses", [r.get("status"), shape.get("status"), step.get("status"), verified.get("status")])
        out("export_step.volume check", volume)
        print(f"H={doc}")


def s23_end(doc):
    with Run7("tc-09-23") as run:
        code = ("import os; from freecad_buddy.usecases.documents import temp_dir; root = temp_dir(); "
                "result = [root, sorted(n for n in os.listdir(root) if n.startswith(('FCB_TMP_snap_', 'FCB_TMP_prev_')))]")
        run.py(doc, code, "then temp folder")
        run.call("document_close", {"doc": doc}, "round trip close")
        listed = run.call("document_list", {}, "then document_list")
        out("open documents", [(d.get("doc"), d.get("name"), d.get("label")) for d in sc(listed).get("documents", [])])


COMMANDS = {"open": cmd_open, "fit": cmd_fit, "close": cmd_close, "list": cmd_list, "s04": s04, "s05": s05,
            "s07": s07, "s08": s08, "s09": s09, "s10": s10, "s11": s11, "s13": s13, "s14": s14,
            "s14_when": s14_when, "s15": s15, "s16": s16, "s23_round": s23_round, "s23_end": s23_end}

if __name__ == "__main__":
    result = COMMANDS[sys.argv[1]](*sys.argv[2:])
    if result:
        print("RETURN", result)
