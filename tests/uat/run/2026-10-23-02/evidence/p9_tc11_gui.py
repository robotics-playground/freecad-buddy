"""Proxy (:8765) call sequences for the TC-11 scenarios of phase P9, logged by p5_lib.Run5.

    p9_tc11_gui.py 10-given     TC-11-10 Given: document_list baseline and the box fingerprint
    p9_tc11_gui.py 10-when      TC-11-10 When: preview, export_step, verify_export_step, then the checks

The box handle is the one p9_gui.py open recorded in evidence/<tag>-handle.txt.
"""
import json
import sys
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
FINGERPRINT = ("from freecad_buddy.usecases.fingerprint import fingerprint\n"
               "record = fingerprint(doc, fresh=True)\n"
               "result = record['digest'] if isinstance(record, dict) else record.digest")
TEMP_LISTING = ("import os; from freecad_buddy.usecases.documents import temp_dir; "
                "result = (temp_dir(), sorted(os.listdir(temp_dir())))")


def handle(tag):
    return (EVIDENCE / f"{tag}-handle.txt").read_text(encoding="utf-8").strip()


def names(result):
    return sorted(d["name"] for d in result["structured_content"]["documents"])


def tc11_10(step):
    tag = "tc-11-10"
    doc = handle(tag)
    with Run5(tag) as run:
        if step == "given":
            listing = run.call("document_list", {}, "given document_list")
            print("BASELINE names:", names(listing))
            run.call("script_exec", {"doc": doc, "code": FINGERPRINT}, "given fingerprint")
            return
        run.call("document_list", {}, "when document_list recorded")
        run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_body_create",
                                                               "args": {"name": "PreviewBody"}}}, "when preview")
        export = run.call("export_step", {"doc": doc, "path": str(EVIDENCE / "tc-11-10-box.step")}, "when export_step")
        export_id = export["structured_content"]["export_id"]
        run.call("verify_export_step", {"doc": doc, "export_id": export_id}, "when verify_export_step")
        final = run.call("document_list", {}, "then document_list")
        print("FINAL names:", names(final))
        run.call("script_exec", {"doc": doc, "code": FINGERPRINT}, "then fingerprint")
        run.call("script_exec", {"doc": doc, "code": TEMP_LISTING}, "then session temp folder")


def tc11_16(step):
    """TC-11-16 sweep on a separate GUI document; the token stays in this process only."""
    import os
    import shutil
    tag = "tc-11-16"
    appdata = Path(os.environ["APPDATA"]) / "FreeCAD" / "v1-1" / "freecad-buddy"
    token = json.loads((appdata / "rpc-17944.json").read_text(encoding="utf-8"))["token"]
    print("masked token:", f"{token[:4]}...(len {len(token)})")
    gui_audit = EVIDENCE / "tc-11-a-audit.jsonl"
    offset = gui_audit.stat().st_size
    envelopes = []
    with Run5(tag) as run:
        def call(tool, args, label):
            result = run.call(tool, args, label, quiet=True)
            envelopes.append({"tool": tool, "result": result})
            return result
        doc = call("document_create", {"label": "tc11-16"}, "when create")["structured_content"]["doc"]
        call("feature_body_create", {"doc": doc, "name": "Body"}, "when mutation")
        call("query_tree_summary", {"doc": doc}, "when query_tree_summary")
        call("query_object", {"doc": doc, "object": "Body"}, "when query_object")
        call("query_dependencies", {"doc": doc}, "when query_dependencies")
        call("query_capabilities", {}, "when query_capabilities")
        shot = call("query_screenshot", {"doc": doc}, "when query_screenshot")
        run.render(shot, "tc-11-16-render")
        call("verify_recompute", {"doc": doc}, "when verify_recompute")
        call("verify_shape", {"doc": doc, "object": "Body"}, "when verify_shape")
        box = handle(tag)
        export = call("export_step", {"doc": box, "path": str(EVIDENCE / "tc-11-16-box.step")}, "when export_step")
        call("verify_export_step", {"doc": box, "export_id": export["structured_content"]["export_id"]},
             "when verify_export_step")
        call("document_close", {"doc": doc}, "when close tc11-16")
        caps = call("query_capabilities", {}, "then query_capabilities")
    (EVIDENCE / "tc-11-16-e2e-report.json").write_text(json.dumps(envelopes, indent=1), encoding="utf-8")
    with gui_audit.open("rb") as handle_:
        handle_.seek(offset)
        (EVIDENCE / "tc-11-16-audit.jsonl").write_bytes(handle_.read())

    def values(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from values(item)
        elif isinstance(value, list):
            for item in value:
                yield from values(item)
        else:
            yield value
    print("CHECK token in e2e report:", token.encode() in (EVIDENCE / "tc-11-16-e2e-report.json").read_bytes())
    for png in sorted(EVIDENCE.glob("tc-11-16-*.png")):
        print(f"CHECK token in {png.name}:", token.encode() in png.read_bytes())
    print("CHECK token in tc-11-16-audit.jsonl:", token.encode() in (EVIDENCE / "tc-11-16-audit.jsonl").read_bytes())
    for name in ("addon.log", "mcp-proxy.log"):
        print(f"CHECK token in {name}:", token.encode() in (appdata / name).read_bytes())
    print("CHECK query_capabilities field equal to token:",
          any(v == token for v in values(caps.get("structured_content"))))


def tc11_18(step):
    """TC-11-18 GUI leg on a separate document tc11-18; its handle goes to evidence/tc-11-18-doc-handle.txt."""
    import subprocess
    tag = "tc-11-18"
    with Run5(tag) as run:
        if step == "when":
            doc = run.call("document_create", {"label": "tc11-18"}, "when create")["structured_content"]["doc"]
            (EVIDENCE / "tc-11-18-doc-handle.txt").write_text(doc, encoding="utf-8")
            pairs = json.loads(subprocess.check_output([sys.executable, str(EVIDENCE / "p9_pad.py")], text=True))
            for tool, raw in zip(pairs[::2], pairs[1::2]):
                run.call(tool, json.loads(raw.replace("$R1.structured_content.doc", doc)), f"when {tool}", quiet=True)
            edge = [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}]
            run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": {
                "body": "Body", "base": "Pad", "name": "Fillet", "edges": edge,
                "radius": {"value": 1, "unit": "mm"}}}}, "when preview second feature", quiet=True)
            shot = run.call("query_screenshot", {"doc": doc}, "when query_screenshot")
            run.render(shot, "tc-11-18-render")
            link = ((shot.get("structured_content") or {}).get("render") or {}).get("resource_link")
            code = ("import os; from freecad_buddy.usecases.documents import temp_dir; "
                    f"result = (temp_dir(), sorted(os.listdir(temp_dir())), os.getpid(), {link!r})")
            run.call("script_exec", {"doc": doc, "code": code}, "when session folder listing")
        elif step == "mint":
            doc = (EVIDENCE / "tc-11-18-doc-handle.txt").read_text(encoding="utf-8").strip()
            run.call("script_exec", {"doc": doc, "code": "from freecad_buddy.usecases import transaction, preview; "
                     "result = (transaction.temp_snapshot_path(doc), preview._tempdoc_path())"}, "when mint paths")


if __name__ == "__main__":
    scenario, step = sys.argv[1].split("-")
    {"10": tc11_10, "16": tc11_16, "18": tc11_18}[scenario](step)
