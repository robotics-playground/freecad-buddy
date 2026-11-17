"""Open a sketch in Sketcher edit mode, or close edit mode, by script_exec (TC-03 Preconditions).

    p0_edit.py <tag> <sketch name>     setEdit on that sketch in the open document holding it
    p0_edit.py <tag> --reset           resetEdit on every open document
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import mcp_client  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
SET = "import FreeCADGui\nobj = doc.getObject({name!r})\nif obj is not None:\n    FreeCADGui.getDocument(doc.Name).setEdit(obj)\nobj is not None"
RESET = "import FreeCADGui\nFreeCADGui.getDocument(doc.Name).resetEdit()"


def main():
    tag, target = sys.argv[1], sys.argv[2]
    with mcp_client.McpClient() as client, (EVIDENCE / f"{tag}-mcp.jsonl").open("a", encoding="utf-8") as log:
        documents = client.call("document_list", {})["structured_content"]["documents"]
        for entry in documents:
            code = RESET if target == "--reset" else SET.format(name=target)
            args = {"doc": entry["doc"], "code": code}
            result = client.call("script_exec", args)
            log.write(json.dumps({"mcp": "script_exec", "args": args, "result": result}, ensure_ascii=False) + "\n")
            print(entry["label"], result.get("status"), json.dumps(result.get("structured_content"))[:200])


if __name__ == "__main__":
    main()
