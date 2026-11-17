"""TC-11-18 GUI leg for phase R2 (auto-approve on, the default posture): r2_tc1118.py gui | clean <doc> <snap> <prev>.

gui: document_create tc11-18, Body + Sketch + Pad 30 (committed), preview_dry_run of a feature_fillet r1, query_screenshot
     (render copied to evidence/tc-11-18-render.png), the in-process session-folder listing, the two minted paths, os.getpid().
"""
import json
import subprocess
import sys
from pathlib import Path

from r2_p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
LISTING = "import os; from freecad_buddy.usecases.documents import temp_dir; result = (temp_dir(), sorted(os.listdir(temp_dir())))"
MINT = ("from freecad_buddy.usecases import transaction, preview; "
        "result = (transaction.temp_snapshot_path(doc), preview._tempdoc_path())")


def sc(result):
    return result.get("structured_content") or {}


def main():
    with Run5("tc-11-18", limit=600) as run:
        if sys.argv[1] == "gui":
            doc = sc(run.call("document_create", {"label": "tc11-18"}, "when create tc11-18"))["doc"]
            pairs = json.loads(subprocess.check_output([sys.executable, str(EVIDENCE / "r2_pad.py")], text=True))
            for tool, raw in zip(pairs[::2], pairs[1::2]):
                args = json.loads(raw.replace("$R1.structured_content.doc", doc))
                result = run.call(tool, args, f"when {tool}", quiet=True)
            print("PAD", result.get("status"))
            fillet = {"body": "Body", "base": "Pad", "name": "Fillet", "radius": {"value": 1, "unit": "mm"},
                      "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}]}
            p = run.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": fillet}},
                         "when preview fillet", quiet=True)
            print("PREVIEW", p.get("status"))
            shot = run.call("query_screenshot", {"doc": doc}, "when query_screenshot", quiet=True)
            print("RENDER", (sc(shot).get("render") or {}).get("resource_link"))
            run.render(shot, "tc-11-18-render")
            for label, code in (("when listing", LISTING), ("when minted paths", MINT),
                                ("when pid", "import os; result = os.getpid()")):
                print(label.upper(), sc(run.py(doc, code, label)).get("value_repr"))
            print("DOC", doc)
        else:
            doc, snap, prev = sys.argv[2:5]
            code = ("import os, shutil\nout = []\nfor p in (%r, %r):\n    d = os.path.dirname(p)\n"
                    "    if os.path.isdir(d):\n        shutil.rmtree(d); out.append((os.path.basename(d), 'removed'))\n"
                    "    else:\n        out.append((os.path.basename(d), 'absent'))\nresult = out") % (snap, prev)
            print("CLEAN", sc(run.py(doc, code, "cleanup minted dirs")).get("value_repr"))


main()
