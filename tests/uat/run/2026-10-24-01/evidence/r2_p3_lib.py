"""MCP helpers for phase P3 (TC-04): one logged client per scenario tag and the fixture builders
the TC-04 Givens share. Every call is appended to evidence/<tag>-mcp.jsonl and summarised on stdout.

    from p3_lib import Run
    with Run("tc-04-05") as run:
        doc = run.doc("Plate")
        run.plate(doc)                      # PlateBody / PlateProfile / PlatePad 60 x 40 x 5
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import mcp_client  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
MM = "mm"


def q(value, unit=MM):
    return {"value": value, "unit": unit}


def summary(result, limit):
    status = result.get("status")
    detail = result.get("detail")
    message = detail.get("message") if isinstance(detail, dict) else None
    content = result.get("structured_content")
    if isinstance(content, dict) and isinstance(content.get("mutation"), dict):
        mutation = content["mutation"]
        same = (mutation.get("fingerprint_before") or {}).get("digest") == \
            (mutation.get("fingerprint_after") or {}).get("digest")
        post = dict(mutation.get("post_verify") or {})
        post.pop("tnp_audit", None)
        body = {"rolled_back": mutation.get("rolled_back"), "rollback": mutation.get("rollback_state"),
                "snapshot_path": mutation.get("snapshot_path"), "fingerprint_equal": same,
                "post_verify": post, "tnp": ((mutation.get("post_verify") or {}).get("tnp_audit") or {}).get("status"),
                "feature_state": content.get("feature_state"),
                "other": {k: v for k, v in content.items() if k not in ("mutation", "feature_state")}}
    elif content is not None:
        body = content
    else:
        body = {k: v for k, v in result.items() if k not in ("status", "detail", "schema")}
    text = json.dumps(body, ensure_ascii=False)
    data = detail.get("data") if isinstance(detail, dict) else None
    extra = f"\n   detail.data={json.dumps(data, ensure_ascii=False)[:400]}" if data and status != "OK" else ""
    return f"status={status} message={message}\n   {text[:limit]}{extra}"


class Run:
    def __init__(self, tag, limit=900):
        self.tag = tag
        self.limit = limit
        self.client = mcp_client.McpClient()
        self.log = None

    def __enter__(self):
        self.client.__enter__()
        self.log = (EVIDENCE / f"{self.tag}-mcp.jsonl").open("a", encoding="utf-8")
        return self

    def __exit__(self, *exc_info):
        self.log.close()
        self.client.__exit__(*exc_info)

    def call(self, tool, args, label="", quiet=False):
        result = self.client.call(tool, args)
        self.log.write(json.dumps({"label": label, "mcp": tool, "args": args, "result": result},
                                  ensure_ascii=False) + "\n")
        self.log.flush()
        if quiet:
            print(f"== [{label}] {tool} -> {result.get('status')}")
        else:
            shown = {k: v for k, v in args.items() if k != "doc"}
            print(f"== [{label}] {tool} {json.dumps(shown, ensure_ascii=False)[:260]}")
            print(f"   {summary(result, self.limit)}")
        return result

    def doc(self, label):
        return self.call("document_create", {"label": label}, "create")["structured_content"]["doc"]

    def py(self, doc, code, label="oracle"):
        return self.call("script_exec", {"doc": doc, "code": code}, label)

    def rect(self, doc, body, sketch, x0, y0, width, height, plane="XY", face=None, label="given", names=(None, None)):
        """A fully constrained width x height rectangle with its first corner at (x0, y0)."""
        args = {"doc": doc, "name": sketch, "body": body}
        if face:
            args["face"] = face
        else:
            args["plane"] = plane
        self.call("sketch_create", args, f"{label} {sketch}", quiet=True)
        x1, y1 = x0 + width, y0 + height
        geometry = [{"kind": "line_segment", "start": s, "end": e} for s, e in
                    (([x0, y0], [x1, y0]), ([x1, y0], [x1, y1]), ([x1, y1], [x0, y1]), ([x0, y1], [x0, y0]))]
        constraints = [
            {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
            {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
            {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
            {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
            {"type": "Horizontal", "first": 0},
            {"type": "Horizontal", "first": 2},
            {"type": "Vertical", "first": 1},
            {"type": "Vertical", "first": 3},
            {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(width)},
            {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(height)},
        ]
        constraints += self.position(x0, y0, names)
        return self.call("sketch_add_geometry", {"doc": doc, "sketch": sketch, "geometry": geometry,
                                                 "constraints": constraints}, f"{label} {sketch} geometry", quiet=True)

    @staticmethod
    def position(x0, y0, names=(None, None)):
        """Constraints that pin point (geometry 0, start) to (x0, y0) from the sketch origin."""
        if x0 == 0 and y0 == 0 and names == (None, None):
            return [{"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1}]
        out = []
        for kind, value, name in (("DistanceX", x0, names[0]), ("DistanceY", y0, names[1])):
            if value >= 0:
                c = {"type": kind, "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": q(value)}
            else:
                c = {"type": kind, "first": 0, "first_pos": 1, "second": -1, "second_pos": 1, "value": q(-value)}
            if name:
                c["name"] = name
            out.append(c)
        return out

    def plate(self, doc, body="PlateBody", label="given"):
        self.call("feature_body_create", {"doc": doc, "name": body}, f"{label} body", quiet=True)
        self.rect(doc, body, "PlateProfile", 0, 0, 60, 40, label=label)
        self.call("feature_pad", {"doc": doc, "body": body, "profile": "PlateProfile", "name": "PlatePad",
                                  "length": q(5)}, f"{label} pad", quiet=True)
        return self.call("query_mass_properties", {"doc": doc, "object": "PlatePad"}, f"{label} volume")

    def edges(self, doc, name):
        code = (f"o = doc.getObject({name!r}); result = [(i + 1, round(e.Length, 3), [round(v, 3) for v in "
                "(e.BoundBox.XMin, e.BoundBox.YMin, e.BoundBox.ZMin, e.BoundBox.XMax, e.BoundBox.YMax, "
                "e.BoundBox.ZMax)]) for i, e in enumerate(o.Shape.Edges)]")
        return self.py(doc, code, f"oracle edges {name}")

    def faces(self, doc, name):
        code = (f"o = doc.getObject({name!r}); result = [(i + 1, type(f.Surface).__name__, [round(v, 3) for v in "
                "(f.BoundBox.XMin, f.BoundBox.YMin, f.BoundBox.ZMin, f.BoundBox.XMax, f.BoundBox.YMax, "
                "f.BoundBox.ZMax)]) for i, f in enumerate(o.Shape.Faces)]")
        return self.py(doc, code, f"oracle faces {name}")

    def snaps(self, doc, label):
        """The FCB_TMP_snap_* entries of the session temp folder, listed in-process."""
        code = ("import os, glob; root = os.path.join(os.environ.get('FREECAD_BUDDY_WORKDIR') or "
                "os.path.join(FreeCAD.getUserAppDataDir(), 'freecad-buddy', 'workdir'), 'tmp'); "
                "result = sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, "
                "'FCB_TMP_session_*', 'FCB_TMP_snap_*')))")
        return self.py(doc, code, label)
