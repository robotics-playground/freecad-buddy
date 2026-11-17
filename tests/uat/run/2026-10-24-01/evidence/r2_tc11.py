"""H1 call sequences for the TC-11 scenarios of phase R2 (from 2026-10-23-02 p9_tc11.py); each runs r2_h1sh.py once.

    r2_tc11.py 11      TC-11-11: three preview exit paths, FCB_TMP_prev_ counted after each
    r2_tc11.py 12      TC-11-12: commit, proven rollback, and the three script_exec fault patches

Paths use forward slashes (a backslash path in a call once held a TAB character).
"""
import json
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
E = EVIDENCE.as_posix()
D = "$R1.structured_content.doc"
EDGE1 = [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}]


def mm(value):
    return {"value": value, "unit": "mm"}


def pad_pairs():
    return json.loads(subprocess.check_output([sys.executable, str(EVIDENCE / "r2_pad.py")], text=True))


def big_fillet(name):
    """A 50 mm fillet on an edge of the tip ``Fillet``: larger than the 20 x 20 x 30 box allows."""
    return {"body": "Body", "base": "Fillet", "name": name, "radius": mm(50),
            "edges": [{"kind": "mapped_name", "object": "Fillet", "mapped_name": "Edge1"}]}


def preview(tool, args):
    return json.dumps({"doc": D, "operation": {"tool": tool, "args": args}})


def fillet(radius):
    return {"body": "Body", "base": "Pad", "name": "Fillet", "edges": EDGE1, "radius": mm(radius)}


def run(tag, variables, pairs, note):
    cmd = ["uv", "run", "python", str(EVIDENCE / "r2_h1sh.py"), tag, *variables, "--", *pairs]
    subprocess.run(cmd, cwd=EVIDENCE, env={**__import__("os").environ, "P9_NOTE": note})


def tc11_11():
    count = ('echo "FCB_TMP_prev_ count: $(ls -d tc-11-11-workdir/tmp/FCB_TMP_session_*/FCB_TMP_prev_* 2>/dev/null '
             '| wc -l)"; ls -R tc-11-11-workdir/tmp')
    pairs = ["document_create", json.dumps({"label": "tc11-11"}), *pad_pairs(),
             "@sh", count,
             "preview_dry_run", preview("feature_fillet", fillet(1)), "@sh", count, "document_list", "{}",
             "preview_dry_run", preview("feature_fillet", fillet(50)), "@sh", count, "document_list", "{}",
             "preview_dry_run", preview("feature_pad", {"body": "Body", "profile": "NoSuchSketch", "name": "Pad2",
                                                        "length": mm(5)}),
             "@sh", count, "document_list", "{}"]
    run("tc-11-11-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-11-h1-audit.jsonl",
                        f"FREECAD_BUDDY_WORKDIR={E}/tc-11-11-workdir"], pairs, "TC-11-11")


PATCH_COMMIT = """import freecad_buddy.usecases.transaction as t
class _CommitRaises:
    def __init__(self, d): object.__setattr__(self, "_d", d)
    def __getattr__(self, n): return getattr(self._d, n)
    def __setattr__(self, n, v): setattr(self._d, n, v)
    def commitTransaction(self): raise RuntimeError("tc-11-12 forced commit failure")
t._fcb_saved = t.run_mutation
def _wrapped(document, *a, **k):
    out, env = t._fcb_saved(_CommitRaises(document), *a, **k)
    return getattr(out, "_d", out), env
t.run_mutation = _wrapped
result = "patched run_mutation"
"""
PATCH_UNPROVEN = """import freecad_buddy.usecases.transaction as t
t._fcb_saved = t._prove_rollback
def _not_proven(document, fp_before, snapshot_path, undo_enabled):
    raise t.RollbackNotProven("tc-11-12 forced", document, fp_before)
t._prove_rollback = _not_proven
result = "patched _prove_rollback"
"""
PATCH_UNHASHABLE = """import freecad_buddy.usecases.transaction as t
t._fcb_saved = t.fingerprint
def _raises(*a, **k):
    raise RuntimeError("tc-11-12 forced unhashable")
t.fingerprint = _raises
result = "patched fingerprint"
"""


def restore(name):
    return "\n".join(["import freecad_buddy.usecases.transaction as t", f"t.{name} = t._fcb_saved",
                      f"result = t.{name} is t._fcb_saved"])


def tc11_12():
    count = ('echo "FCB_TMP_snap_ count: $(ls -d tc-11-12-workdir/tmp/FCB_TMP_session_*/FCB_TMP_snap_* 2>/dev/null '
             '| wc -l)"; ls -R tc-11-12-workdir/tmp')
    def ex(code):
        return json.dumps({"doc": D, "code": code})
    pairs = ["document_create", json.dumps({"label": "tc11-12"}), *pad_pairs(),
             "@sh", count,
             "feature_fillet", json.dumps({"doc": D, **fillet(1)}), "@sh", count,
             "feature_fillet", json.dumps({"doc": D, **big_fillet("FilletBig")}), "@sh", count,
             "script_exec", ex(PATCH_COMMIT),
             "feature_body_create", json.dumps({"doc": D, "name": "BodyC"}),
             "script_exec", ex(restore("run_mutation")), "@sh", count,
             "script_exec", ex(PATCH_UNPROVEN),
             "feature_fillet", json.dumps({"doc": D, **big_fillet("FilletBig2")}),
             "script_exec", ex(restore("_prove_rollback")), "@sh", count,
             "script_exec", ex(PATCH_UNHASHABLE),
             "feature_body_create", json.dumps({"doc": D, "name": "BodyU"}),
             "script_exec", ex(restore("fingerprint")), "@sh", count,
             "script_exec", ex("import os; result = os.getpid()")]
    run("tc-11-12-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-12-h1-audit.jsonl",
                        f"FREECAD_BUDDY_WORKDIR={E}/tc-11-12-workdir"], pairs, "TC-11-12")


def tc11_15():
    pad = pad_pairs()
    snap = ('n=$(wc -l < tc-11-15-append.jsonl); echo "$n" > tc-11-15-batch1-lines.txt; '
            'sha256sum tc-11-15-append.jsonl | tee tc-11-15-batch1-sha256.txt; cp tc-11-15-append.jsonl tc-11-15-batch1-copy.jsonl; '
            'echo "batch1 lines: $n"')
    pairs = ["document_create", json.dumps({"label": "tc11-15"}), *pad[:4], "@sh", snap, *pad[4:],
             "feature_fillet", json.dumps({"doc": D, **fillet(1)})]
    run("tc-11-15-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-15-append.jsonl"], pairs, "TC-11-15 batches 1 and 2")


def tc11_15_writer(number):
    pairs = ["document_create", json.dumps({"label": f"tc11-15-w{number}"}), *pad_pairs(),
             "feature_fillet", json.dumps({"doc": D, **fillet(1)})]
    run(f"tc-11-15-writer{number}-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-15-append.jsonl"], pairs,
        f"TC-11-15 concurrent writer {number}")


def tc11_10():
    pairs = ["document_create", json.dumps({"label": "tc11-10"}), *pad_pairs(),
             "document_list", "{}",
             "preview_dry_run", preview("feature_fillet", fillet(1)),
             "export_step", json.dumps({"doc": D, "path": f"{E}/tc-11-10-h1-box.step", "objects": ["Body"]}),
             "verify_export_step", json.dumps({"doc": D, "export_id": "$PREV.structured_content.export_id"}),
             "document_list", "{}",
             "@sh", "ls -R tc-11-10-workdir/tmp"]
    run("tc-11-10-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-10-h1-audit.jsonl",
                        f"FREECAD_BUDDY_WORKDIR={E}/tc-11-10-workdir"], pairs, "TC-11-10 H1 leg")


def tc11_14():
    folder = f"{E}/tc-11-14-userdocs"
    def listing(n):
        return f"ls -la --time-style=full-iso tc-11-14-userdocs | tee tc-11-14-listing{n}.txt"
    doc = "$PREV.structured_content.doc"
    bad_export = "fcb-export:not-issued"
    reads = [
        "query_capabilities", "{}",
        "query_tree_summary", json.dumps({"doc": "$R2.structured_content.doc"}),
        "query_object", json.dumps({"doc": "$R2.structured_content.doc", "object": "Box"}),
        "query_mass_properties", json.dumps({"doc": "$R2.structured_content.doc", "object": "Box"}),
        "query_dependencies", json.dumps({"doc": "$R2.structured_content.doc"}),
        "query_sketch_info", json.dumps({"doc": "$R2.structured_content.doc", "sketch": "Box"}),
        "query_placement", json.dumps({"doc": "$R2.structured_content.doc", "object": "Box"}),
        "query_screenshot", json.dumps({"doc": "$R2.structured_content.doc"}),
        "verify_shape", json.dumps({"doc": "$R2.structured_content.doc", "object": "Box"}),
        "verify_sketch", json.dumps({"doc": "$R2.structured_content.doc", "sketch": "Box"}),
        "verify_recompute", json.dumps({"doc": "$R2.structured_content.doc"}),
        "verify_export_step", json.dumps({"doc": "$R2.structured_content.doc", "export_id": bad_export}),
        "verify_export_stl", json.dumps({"doc": "$R2.structured_content.doc", "export_id": bad_export}),
        "verify_export_3mf", json.dumps({"doc": "$R2.structured_content.doc", "export_id": bad_export}),
        "preview_dry_run", json.dumps({"doc": "$R2.structured_content.doc",
                                       "operation": {"tool": "feature_body_create", "args": {"name": "PreviewBody"}}}),
        "document_close", json.dumps({"doc": "$R2.structured_content.doc"}),
    ]
    pairs = ["@sh", listing(1),
             "document_open", json.dumps({"path": f"{folder}/box-copy.FCStd"}), *reads,
             "@sh", listing(2),
             "document_open", json.dumps({"path": f"{folder}/box-copy.FCStd"}),
             "export_stl", json.dumps({"doc": doc, "path": f"{folder}/tc11-export.stl", "objects": ["Box"]}),
             "document_save", json.dumps({"doc": "$R20.structured_content.doc"}),
             "@sh", listing(3)]
    run("tc-11-14-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-14-h1-audit.jsonl",
                        f"FREECAD_BUDDY_WORKDIR={E}/tc-11-14-workdir"], pairs, "TC-11-14")


def tc11_18():
    pairs = ["document_create", json.dumps({"label": "tc11-18"}), *pad_pairs(),
             "query_screenshot", json.dumps({"doc": D}),
             "script_exec", json.dumps({"doc": D, "code": "import os; result = os.getpid()"}),
             "@sh", "ls -R tc-11-18-workdir"]
    run("tc-11-18-h1", [f"FREECAD_BUDDY_AUDIT_LOG={E}/tc-11-18-h1-audit.jsonl",
                        f"FREECAD_BUDDY_WORKDIR={E}/tc-11-18-workdir"], pairs, "TC-11-18 H1 leg")


if __name__ == "__main__":
    if sys.argv[1] == "15w":
        tc11_15_writer(sys.argv[2])
        sys.exit()
    {"10": tc11_10, "14": tc11_14, "18": tc11_18, "11": tc11_11, "12": tc11_12, "15": tc11_15}[sys.argv[1]]()
