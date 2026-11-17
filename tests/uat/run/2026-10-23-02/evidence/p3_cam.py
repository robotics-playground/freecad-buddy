"""Look along (dx, dy, dz) at (x, y, z) with a view height of h mm in the active 3D view of every open
document: p3_cam.py <tag> dx dy dz x y z h. A framing aid like p0_cam.py; the scene is not changed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import mcp_client  # noqa: E402

CODE = """import FreeCADGui
from pivy import coin
view = FreeCADGui.getDocument(doc.Name).activeView()
view.setViewDirection(({dx}, {dy}, {dz}))
cam = view.getCameraNode()
d = cam.orientation.getValue().multVec(coin.SbVec3f(0, 0, -1))
cam.position.setValue(coin.SbVec3f({x}, {y}, {z}) - d * 200)
cam.height.setValue({h})"""


def main():
    tag, dx, dy, dz, x, y, z, h = sys.argv[1:9]
    with mcp_client.McpClient() as client, (Path(__file__).resolve().parent / f"{tag}-mcp.jsonl").open("a", encoding="utf-8") as log:
        for entry in client.call("document_list", {})["structured_content"]["documents"]:
            args = {"doc": entry["doc"], "code": CODE.format(dx=dx, dy=dy, dz=dz, x=x, y=y, z=z, h=h)}
            result = client.call("script_exec", args)
            log.write(json.dumps({"camera": True, "mcp": "script_exec", "args": args, "result": result}) + "\n")
            print(entry["label"], result.get("status"), (result.get("detail") or {}).get("message"))


if __name__ == "__main__":
    main()
