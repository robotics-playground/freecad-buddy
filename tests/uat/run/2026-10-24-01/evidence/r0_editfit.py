"""Open a sketch in Sketcher edit mode, fit the view, optionally set the camera, and capture.

    r0_editfit.py <tag> <sketch> <out stem> [iso|top|keep]

The sketch is looked up in every open document by Name; the document that holds it is used.
The call and its result are appended to evidence/<tag>-mcp.jsonl. Edit mode stays open.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402
import mcp_client  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
CODE = """import FreeCADGui
obj = doc.getObject({name!r})
if obj is not None:
    gui = FreeCADGui.getDocument(doc.Name)
    if gui.getInEdit() is None or gui.getInEdit().Object.Name != obj.Name:
        gui.setEdit(obj)
    view = gui.activeView()
    if {camera!r} == "iso":
        view.viewIsometric()
    elif {camera!r} == "top":
        view.viewTop()
    view.fitAll()
obj is not None"""


def main():
    tag, sketch, stem = sys.argv[1:4]
    camera = sys.argv[4] if len(sys.argv) > 4 else "keep"
    with mcp_client.McpClient() as client, (EVIDENCE / f"{tag}-mcp.jsonl").open("a", encoding="utf-8") as log:
        for entry in client.call("document_list", {})["structured_content"]["documents"]:
            args = {"doc": entry["doc"], "code": CODE.format(name=sketch, camera=camera)}
            result = client.call("script_exec", args)
            log.write(json.dumps({"editfit": True, "mcp": "script_exec", "args": args, "result": result}, ensure_ascii=False) + "\n")
            print(entry["label"], result.get("status"), (result.get("structured_content") or {}).get("value_repr"))
    time.sleep(1.0)
    pid = launch.running_freecad_pids()[0]
    window_id = capture.main_window(pid)["window_id"]
    out = EVIDENCE / f"{stem}.png"
    capture.capture(pid, window_id, out)
    print(out)


if __name__ == "__main__":
    main()
