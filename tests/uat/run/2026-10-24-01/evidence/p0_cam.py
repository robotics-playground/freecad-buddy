"""Point the active 3D view at (x, y, z) with a view height of h mm, keeping the camera direction:
p0_cam.py <tag> x y z h. A framing aid for small details; the scene is not changed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import mcp_client  # noqa: E402

CODE = """import FreeCADGui
from pivy import coin
cam = FreeCADGui.getDocument(doc.Name).activeView().getCameraNode()
d = cam.orientation.getValue().multVec(coin.SbVec3f(0, 0, -1))
cam.position.setValue(coin.SbVec3f({x}, {y}, {z}) - d * 200)
cam.height.setValue({h})"""


def main():
    tag, x, y, z, h = sys.argv[1:6]
    with mcp_client.McpClient() as client, (Path(__file__).resolve().parent / f"{tag}-mcp.jsonl").open("a", encoding="utf-8") as log:
        for entry in client.call("document_list", {})["structured_content"]["documents"]:
            args = {"doc": entry["doc"], "code": CODE.format(x=x, y=y, z=z, h=h)}
            result = client.call("script_exec", args)
            log.write(json.dumps({"camera": True, "mcp": "script_exec", "args": args, "result": result}) + "\n")
            print(entry["label"], result.get("status"))


if __name__ == "__main__":
    main()
