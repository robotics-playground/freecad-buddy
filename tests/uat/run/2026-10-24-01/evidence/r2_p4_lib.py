"""MCP helpers for phase P4 (TC-05), on top of p3_lib.Run.

Differences from p3_lib.Run:
- every call also records the MCP ``isError`` flag (TC-05-05 asserts it), as ``is_error`` in the log;
- ``preview_id`` tokens are shortened to their first 16 characters in the log and on stdout;
- ``mut`` previews a mutation, then applies it with the returned ``confirm`` (the host runs with
  FREECAD_BUDDY_AUTO_APPROVE=0, so every mutation needs one);
- stdout shows the whole envelope (``status``, ``detail``, ``text``, ``structured_content``).

    from p4_lib import Run4
    with Run4("tc-05-01") as run:
        doc = run.fixture_sketch("tc-05-01")   # Body + fully constrained 20 x 20 Sketch on XY
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import mcp_client  # noqa: E402
from r2_p3_lib import Run, q  # noqa: E402

_to_result = mcp_client.to_result
mcp_client.to_result = lambda call_result: {"__is_error": bool(call_result.isError),
                                            "__result": _to_result(call_result)}

SNAPSHOT_CHECK = ("import os\nfrom freecad_buddy.usecases.documents import temp_dir\nroot = temp_dir()\n"
                  "result = sorted(n for n in os.listdir(root) if n.startswith('FCB_TMP_snap_'))")
EDGE1 = [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}]


def redact(value):
    if isinstance(value, dict):
        return {k: (v[:16] + "...(redacted)" if k == "preview_id" and isinstance(v, str) else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class Run4(Run):
    def __init__(self, tag, limit=2600):
        super().__init__(tag, limit)

    def call(self, tool, args, label="", quiet=False):
        raw = self.client.call(tool, args)
        is_error, result = raw["__is_error"], raw["__result"]
        self.log.write(json.dumps({"label": label, "mcp": tool, "args": redact(args), "is_error": is_error,
                                   "result": redact(result)}, ensure_ascii=False) + "\n")
        self.log.flush()
        if quiet:
            print(f"== [{label}] {tool} -> {result.get('status')}")
        else:
            shown = {k: v for k, v in args.items() if k != "doc"}
            print(f"== [{label}] {tool} {json.dumps(redact(shown), ensure_ascii=False)[:300]}")
            print(f"   isError={is_error} {json.dumps(redact(result), ensure_ascii=False)[:self.limit]}")
        return result

    def mut(self, doc, tool, args, label="", quiet=False):
        """Preview ``tool(args)``, then apply it with the preview's confirm; return (preview, apply)."""
        preview = self.call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}},
                            f"{label} preview", quiet=quiet)
        token = (preview.get("structured_content") or {}).get("preview_id")
        applied = self.call(tool, {"doc": doc, **args, "confirm": {"preview_id": token}}, f"{label} apply",
                            quiet=quiet)
        return preview, applied

    def snapshot_check(self, doc, label="snapshot check"):
        return self.py(doc, SNAPSHOT_CHECK, label)

    def fixture_sketch(self, label_doc):
        """Body + fully constrained 20 x 20 mm rectangle ``Sketch`` on XY, built with confirmed mutations."""
        doc = self.call("document_create", {"label": label_doc}, "given create")["structured_content"]["doc"]
        self.mut(doc, "feature_body_create", {"name": "Body"}, "given body", quiet=True)
        self.mut(doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"}, "given sketch", quiet=True)
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
        self.mut(doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": geometry, "constraints": constraints},
                 "given sketch geometry", quiet=True)
        self.call("verify_sketch", {"doc": doc, "sketch": "Sketch"}, "given verify_sketch")
        return doc

    def fixture_pad(self, label_doc):
        """``fixture_sketch`` plus a 30 mm ``Pad``."""
        doc = self.fixture_sketch(label_doc)
        self.mut(doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)},
                 "given pad", quiet=True)
        self.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "given volume")
        return doc

    def fixture_fillet(self, label_doc):
        """``fixture_pad`` plus a 2 mm ``Fillet`` on Pad Edge1."""
        doc = self.fixture_pad(label_doc)
        self.mut(doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": EDGE1,
                                         "radius": q(2)}, "given fillet", quiet=True)
        return doc
