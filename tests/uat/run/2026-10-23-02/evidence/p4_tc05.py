"""TC-05 agent-driven scenarios for phase P4, one function per step group: p4_tc05.py <name> [doc ...].
The visual steps (Show All, Fit All, capture, read) run separately through p1_gui.py / p2_gui.py."""

import sys

from p4_lib import EDGE1, Run4, q

PAD = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}


def pre():
    with Run4("tc-05-pre") as run:
        run.call("query_capabilities", {}, "freecad_version")
        doc = run.call("document_create", {"label": "tc-05-pre"}, "create")["structured_content"]["doc"]
        run.snapshot_check(doc)
        run.call("document_close", {"doc": doc}, "cleanup")


def tc05_01():
    with Run4("tc-05-01") as run:
        doc = run.fixture_sketch("tc-05-01")
        run.call("query_mass_properties", {"doc": doc, "object": "Body"}, "when pre-mutation state")
        run.mut(doc, "feature_pad", PAD, "when pad")
        run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "then volume")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
        print("DOC", doc)


SPY = ("import os\nfrom freecad_buddy.usecases import transaction as _t\n_orig = _t._delete_snapshot\n_t._fcb_seen = []\n"
       "def _spy(path):\n    _t._delete_snapshot = _orig\n    _t._fcb_seen.append((path, sorted(os.listdir(os.path.dirname(path)))))\n"
       "    return _orig(path)\n_t._delete_snapshot = _spy\nresult = 'armed'")
SPY_READ = ("import os\nfrom freecad_buddy.usecases import transaction as _t\n"
            "result = [(p, files, os.path.exists(os.path.dirname(p))) for p, files in _t._fcb_seen]")
FCBAK = ("import os\nfrom freecad_buddy.usecases.documents import temp_dir\n"
         "result = [f for _, _, fs in os.walk(temp_dir()) for f in fs if f.endswith('.FCBak')]")
TEMP_DIR = "from freecad_buddy.usecases.documents import temp_dir\nresult = (doc.Name, temp_dir())"


def preview(run, doc, tool, args, label):
    return run.call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}}, label)


def apply(run, doc, tool, args, previewed, label):
    token = (previewed.get("structured_content") or {}).get("preview_id")
    return run.call(tool, {"doc": doc, **args, "confirm": {"preview_id": token}}, label)


def tc05_02():
    with Run4("tc-05-02") as run:
        doc = run.fixture_sketch("tc-05-02")
        run.snapshot_check(doc, "given snapshot check")
        previewed = preview(run, doc, "feature_pad", PAD, "when preview")
        run.py(doc, SPY, "when arm spy")
        apply(run, doc, "feature_pad", PAD, previewed, "when apply")
        run.py(doc, SPY_READ, "when read spy")
        run.py(doc, TEMP_DIR, "oracle doc name and temp_dir")
        run.snapshot_check(doc, "then snapshot check")
        run.py(doc, FCBAK, "then FCBak")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
        run.py(doc, "from freecad_buddy.usecases import transaction as _t\nresult = _t._delete_snapshot.__name__",
               "cleanup spy gone")
        print("DOC", doc)


FILLET2 = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": EDGE1, "radius": q(2)}
FILLET500 = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": EDGE1, "radius": q(500)}


def tc05_04():
    with Run4("tc-05-04", limit=1800) as run:
        doc = run.fixture_pad("tc-05-04")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "given/when tree before")
        previewed = preview(run, doc, "feature_fillet", FILLET2, "when preview")
        apply(run, doc, "feature_fillet", FILLET2, previewed, "when apply")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "when tree after")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
        print("DOC", doc)


def tc05_05_given():
    with Run4("tc-05-05", limit=1800) as run:
        doc = run.fixture_pad("tc-05-05")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc05_05_when(doc):
    with Run4("tc-05-05", limit=4000) as run:
        previewed = preview(run, doc, "feature_fillet", FILLET500, "when preview")
        apply(run, doc, "feature_fillet", FILLET500, previewed, "when apply")
        run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "then volume")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.snapshot_check(doc, "then snapshot check")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")



def square(run, doc, sketch, face, x0, y0, size, label):
    """A fully constrained size x size square on ``face`` with its first corner at (x0, y0)."""
    run.mut(doc, "sketch_create", {"name": sketch, "body": "Body", "face": face}, f"{label} {sketch}", quiet=True)
    x1, y1 = x0 + size, y0 + size
    geometry = [{"kind": "line_segment", "start": a, "end": b} for a, b in
                (([x0, y0], [x1, y0]), ([x1, y0], [x1, y1]), ([x1, y1], [x0, y1]), ([x0, y1], [x0, y0]))]
    constraints = [
        {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
        {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
        {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(size)},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(size)},
    ] + Run4.position(x0, y0)
    run.mut(doc, "sketch_add_geometry", {"sketch": sketch, "geometry": geometry, "constraints": constraints},
            f"{label} {sketch} geometry", quiet=True)
    return run.call("verify_sketch", {"doc": doc, "sketch": sketch}, f"{label} verify {sketch}")


def tc05_06_given():
    with Run4("tc-05-06", limit=1500) as run:
        doc = run.fixture_fillet("tc-05-06")
        run.faces(doc, "Fillet")
        print("DOC", doc)


def tc05_06_given2(doc, face):
    with Run4("tc-05-06", limit=2500) as run:
        top = {"kind": "mapped_name", "object": "Fillet", "mapped_name": face}
        square(run, doc, "Sketch001", top, 7, 7, 5, "given")
        run.mut(doc, "feature_pocket", {"body": "Body", "profile": "Sketch001", "name": "Pocket", "length": q(900)},
                "given pocket 900")
        run.call("query_dependencies", {"doc": doc}, "given dependencies")
        run.call("document_list", {}, "given label before")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")


def tc05_06_when(doc):
    with Run4("tc-05-06", limit=3500) as run:
        pattern = {"body": "Body", "name": "Pattern", "kind": "linear", "originals": ["Pocket"],
                   "direction": {"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}, "occurrences": 200}
        run.mut(doc, "feature_pattern", pattern, "when reproducer 1 pattern")
        run.snapshot_check(doc, "after reproducer 1 snapshot check")
        run.mut(doc, "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}},
                "when reproducer 2 radius 400")
        run.snapshot_check(doc, "after reproducer 2 snapshot check")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("document_list", {}, "then label")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


LOOSE_SKETCH = ("import Part, Sketcher\nfrom FreeCAD import Vector as V\nbody = doc.getObject('Body')\n"
                "xy = [f for f in body.Origin.OriginFeatures if f.Role == 'XY_Plane'][0]\n"
                "sk = body.newObject('Sketcher::SketchObject', 'LooseSketch')\nsk.AttachmentSupport = [(xy, '')]\n"
                "sk.MapMode = 'FlatFace'\npts = [V(0, 0, 0), V(20, 0, 0), V(20, 20, 0), V(0, 20, 0)]\n"
                "for i in range(4):\n    sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))\n"
                "for i in range(4):\n    sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))\n"
                "for i, kind in enumerate(['Horizontal', 'Vertical', 'Horizontal', 'Vertical']):\n"
                "    sk.addConstraint(Sketcher.Constraint(kind, i))\ndoc.recompute()\nresult = sk.solve()")
GOOD = {"body": "Body", "base": "Pad", "name": "GoodFillet", "edges": EDGE1, "radius": q(2)}
BAD = {"body": "Body", "base": "Pad", "name": "BadFillet", "edges": EDGE1, "radius": q(500)}
MISSING = {"body": "Body", "base": "NoSuchPad", "name": "MissingFillet", "edges": EDGE1, "radius": q(2)}


def follow_up(run, doc, path):
    run.mut(doc, "feature_fillet", GOOD, f"{path} follow-up GoodFillet")
    run.snapshot_check(doc, f"{path} snapshot check")
    run.call("document_undo", {"doc": doc}, f"{path} document_undo")


def tc05_09():
    with Run4("tc-05-09", limit=2200) as run:
        doc = run.fixture_pad("tc-05-09")
        run.py(doc, LOOSE_SKETCH, "path1 given LooseSketch (dof 4)")
        run.call("verify_sketch", {"doc": doc, "sketch": "LooseSketch"}, "path1 given verify LooseSketch")
        run.mut(doc, "feature_pad", {"body": "Body", "profile": "LooseSketch", "name": "LoosePad", "length": q(10)},
                "path1 failing pad on under-constrained sketch")
        follow_up(run, doc, "path1")
        run.mut(doc, "feature_fillet", BAD, "path2 failing BadFillet 500 mm")
        follow_up(run, doc, "path2")
        preview(run, doc, "feature_fillet", MISSING, "path3 failing preview missing base")
        run.call("feature_fillet", {"doc": doc, **MISSING}, "path3 failing apply missing base (no token to send)")
        follow_up(run, doc, "path3")
        run.mut(doc, "feature_fillet", GOOD, "final GoodFillet re-applied for the visual")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "final tree")
        run.snapshot_check(doc, "final snapshot check")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")
        print("DOC", doc)


COMMIT_PATCH = ("from freecad_buddy.usecases import transaction as _t\n_orig = _t.run_mutation\nclass _Proxy:\n"
                "    def __init__(self, d):\n        object.__setattr__(self, '_d', d)\n"
                "    def __getattr__(self, name):\n        return getattr(self._d, name)\n"
                "    def __setattr__(self, name, value):\n        setattr(self._d, name, value)\n"
                "    def commitTransaction(self):\n        raise RuntimeError('injected commit failure')\n"
                "def _wrap(document, *args, **kwargs):\n    _t.run_mutation = _orig\n"
                "    out, envelope = _orig(_Proxy(document), *args, **kwargs)\n"
                "    return (document if isinstance(out, _Proxy) else out), envelope\n_t.run_mutation = _wrap\nresult = 'armed'")


def tc05_10_given():
    with Run4("tc-05-10", limit=1500) as run:
        doc = run.fixture_sketch("tc-05-10")
        run.py(doc, "result = 1", "given script_exec on")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc05_10_when(doc):
    with Run4("tc-05-10", limit=3500) as run:
        previewed = preview(run, doc, "feature_pad", PAD, "when preview")
        run.py(doc, COMMIT_PATCH, "when patch commit")
        apply(run, doc, "feature_pad", PAD, previewed, "when apply")
        run.snapshot_check(doc, "then snapshot check")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "oracle tree after injected failure")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def tc05_10_closing(doc):
    with Run4("tc-05-10", limit=1500) as run:
        run.mut(doc, "feature_pad", PAD, "then bracket closed: well-formed pad")
        run.py(doc, "from freecad_buddy.usecases import transaction as _t\nresult = _t.run_mutation.__name__",
               "cleanup wrapper gone")


SETUP_PATCH = ("from freecad_buddy.usecases import tnp_guard as _g\n_orig = _g.snapshot_references\n"
               "def _boom(document):\n    _g.snapshot_references = _orig\n    raise RuntimeError('injected setup failure')\n"
               "_g.snapshot_references = _boom\nresult = 'armed'")


def given_pad_fit(tag):
    with Run4(tag, limit=1500) as run:
        doc = run.fixture_pad(tag)
        run.py(doc, "result = 1", "given script_exec on")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def setup_failure(doc, tag):
    with Run4(tag, limit=3500) as run:
        previewed = preview(run, doc, "feature_fillet", FILLET2, "when preview")
        run.py(doc, SETUP_PATCH, "when patch snapshot_references")
        apply(run, doc, "feature_fillet", FILLET2, previewed, "when apply")
        run.snapshot_check(doc, "then snapshot check")
        run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "then volume")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def tc05_12_undo(doc):
    with Run4("tc-05-12", limit=1500) as run:
        run.call("document_undo", {"doc": doc}, "then no transaction opened: document_undo")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "oracle tree after undo")


ROOT = "D:/Work/Personal/Sources/freecad-buddy"
RUN_EVIDENCE = ROOT + "/tests/uat/run/2026-10-23-02/evidence"


def tc05_13_open(which):
    path = {"a": ROOT + "/benchmarks/g0/golden-models/box-10-20-30.FCStd",
            "b": RUN_EVIDENCE + "/tc-05-13-box-copy.FCStd"}[which]
    with Run4("tc-05-13", limit=800) as run:
        run.call("document_open", {"path": path}, f"when open {which}")


def tc05_13_probe(handle_a, handle_b):
    with Run4("tc-05-13", limit=2500) as run:
        for name, doc in (("a", handle_a), ("b", handle_b)):
            preview(run, doc, "feature_body_create", {"name": "Probe"}, f"when probe preview {name}")
        doc = handle_b
        run.mut(doc, "feature_body_create", {"name": "Body"}, "then successful mutation on b: body")
        run.mut(doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"}, "then b sketch", quiet=True)
        geometry = [{"kind": "line_segment", "start": a, "end": b} for a, b in
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
        run.mut(doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": geometry, "constraints": constraints},
                "then b sketch geometry", quiet=True)
        run.mut(doc, "feature_pad", PAD, "then b feature_pad")



def fit(doc, tag):
    with Run4(tag, limit=600) as run:
        run.call("view_fit_viewport", {"doc": doc}, "then fit")



def tc05_16_given():
    with Run4("tc-05-16", limit=1500) as run:
        doc_a = run.fixture_fillet("tc-05-16-a")
        run.call("query_dependencies", {"doc": doc_a}, "given A dependencies")
        run.call("query_capabilities", {}, "given element map")
        doc_b = run.call("document_create", {"label": "tc-05-16-b"}, "given B create")["structured_content"]["doc"]
        run.mut(doc_b, "feature_body_create", {"name": "PlateBody"}, "given B body", quiet=True)
        run.mut(doc_b, "sketch_create", {"name": "PlateProfile", "plane": "XY", "body": "PlateBody"}, "given B profile",
                quiet=True)
        geometry = [{"kind": "line_segment", "start": a, "end": b} for a, b in
                    (([0, 0], [60, 0]), ([60, 0], [60, 40]), ([60, 40], [0, 40]), ([0, 40], [0, 0]))]
        constraints = [
            {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
            {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
            {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
            {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
            {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
            {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
            {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
            {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(60),
             "name": "PlateWidth"},
            {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(40),
             "name": "PlateDepth"},
        ]
        run.mut(doc_b, "sketch_add_geometry", {"sketch": "PlateProfile", "geometry": geometry,
                                               "constraints": constraints}, "given B rect", quiet=True)
        run.mut(doc_b, "feature_pad", {"body": "PlateBody", "profile": "PlateProfile", "name": "PlatePad",
                                       "length": q(5)}, "given B pad", quiet=True)
        run.mut(doc_b, "sketch_create", {"name": "BossProfile", "body": "PlateBody",
                                         "face": {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face6"}},
                "given B boss sketch", quiet=True)
        run.mut(doc_b, "sketch_add_geometry", {"sketch": "BossProfile", "geometry": [
            {"kind": "circle", "center": [30, 20], "radius": q(5)}], "constraints": [
            {"type": "DistanceX", "first": 0, "first_pos": 3, "value": q(30)},
            {"type": "DistanceY", "first": 0, "first_pos": 3, "value": q(20)},
            {"type": "Radius", "first": 0, "value": q(5), "name": "BossRadius"}]}, "given B circle", quiet=True)
        run.py(doc_b, "e = doc.getObject('PlatePad').Shape.getElement('Edge3')\nresult = round(e.Length, 3)",
               "given B edge oracle")
        run.mut(doc_b, "sketch_add_external_geometry", {"sketch": "BossProfile", "edge": {
            "kind": "mapped_name", "object": "PlatePad", "mapped_name": "Edge3"}}, "given B project", quiet=True)
        run.call("verify_sketch", {"doc": doc_b, "sketch": "BossProfile"}, "given B verify BossProfile")
        run.call("query_dependencies", {"doc": doc_b}, "given B dependencies")
        run.call("query_mass_properties", {"doc": doc_b, "object": "PlatePad"}, "given B volume")
        run.call("view_fit_viewport", {"doc": doc_b}, "given B fit")
        print("DOC", doc_a, doc_b)


def tc05_16_when(doc_a, doc_b):
    with Run4("tc-05-16", limit=4000) as run:
        chamfer = {"body": "Body", "base": "Pad", "name": "Chamfer", "edges": [
            {"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge2"}], "size": q(3)}
        preview(run, doc_a, "feature_chamfer", chamfer, "when A off-Tip chamfer preview")
        run.call("query_tree_summary", {"doc": doc_a, "depth": 3}, "then A tree")
        run.mut(doc_b, "feature_set_parameters", {"feature": "PlatePad", "parameters": {"Length": q(30)}},
                "when B thicken plate")
        run.call("query_mass_properties", {"doc": doc_b, "object": "PlatePad"}, "then B volume")
        run.call("view_fit_viewport", {"doc": doc_b}, "then B fit")



def tc05_17_given():
    with Run4("tc-05-17", limit=1500) as run:
        doc = run.fixture_fillet("tc-05-17")
        run.call("query_mass_properties", {"doc": doc, "object": "Fillet"}, "given fillet")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc05_17_when(doc):
    with Run4("tc-05-17", limit=4000) as run:
        run.mut(doc, "sketch_remove_geometry", {"sketch": "Sketch", "geo_ids": [0]}, "when remove geometry 0")
        run.call("query_mass_properties", {"doc": doc, "object": "Fillet"}, "then fillet intact")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


SWAP_PATCH = ("import shutil\nfrom freecad_buddy.usecases import shim, transaction as _t\nshim._fcb_enable_undo = shim.enable_undo\n"
              "shim.enable_undo = lambda d: False\ndoc.UndoMode = 0\n_orig = _t._restore_from_snapshot\n"
              "def _swap(document, snapshot_path):\n    _t._restore_from_snapshot = _orig\n"
              "    shutil.copyfile('<PROJECT_ROOT>/benchmarks/g0/golden-models/sphere-r10.FCStd', snapshot_path)\n"
              "    return _orig(document, snapshot_path)\n_t._restore_from_snapshot = _swap\nresult = doc.UndoMode"
              ).replace("<PROJECT_ROOT>", ROOT)


def snapshot_exists(run, doc, envelope, label):
    path = (((envelope.get("structured_content") or {}).get("mutation")) or {}).get("snapshot_path")
    if path:
        run.py(doc, f"import os\nresult = os.path.exists(r'{path}')", label)
        run.py(doc, f"import os\nresult = sorted(os.listdir(os.path.dirname(r'{path}')))", f"{label} listing")
    else:
        print("no snapshot_path on the envelope")


def tc05_07_when(doc):
    with Run4("tc-05-07", limit=4000) as run:
        previewed = preview(run, doc, "feature_fillet", FILLET500, "when preview")
        run.py(doc, SWAP_PATCH, "when undo off + swap patch")
        applied = apply(run, doc, "feature_fillet", FILLET500, previewed, "when apply")
        snapshot_exists(run, doc, applied, "then snapshot on disk")
        run.call("document_list", {}, "oracle documents")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "oracle tree")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")



def tc05_07_cleanup(doc):
    with Run4("tc-05-07", limit=800) as run:
        run.py(doc, "from freecad_buddy.usecases import shim\nshim.enable_undo = shim._fcb_enable_undo\ndoc.UndoMode = 1\n"
                    "result = shim.enable_undo(doc)", "cleanup restore undo (snapshot folder NOT removed: P4 rule)")
        run.snapshot_check(doc, "cleanup snapshot check")
        run.call("document_close", {"doc": doc}, "cleanup close")


FP_PATCH = ("from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\n_state = {'n': 0}\n"
            "def _fp(d, *args, **kwargs):\n    _state['n'] += 1\n    if _state['n'] == 1:\n        _t.fingerprint = _orig\n"
            "        raise RuntimeError('injected serializer failure')\n    return _orig(d, *args, **kwargs)\n"
            "_t.fingerprint = _fp\nresult = 'armed'")


def tc05_11(doc):
    with Run4("tc-05-11", limit=4000) as run:
        previewed = preview(run, doc, "feature_pad", PAD, "when preview")
        run.py(doc, FP_PATCH, "when patch fingerprint")
        applied = apply(run, doc, "feature_pad", PAD, previewed, "when apply")
        snapshot_exists(run, doc, applied, "then snapshot kept")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("query_mass_properties", {"doc": doc, "object": "Pad"}, "then volume")
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def tc05_11_given():
    with Run4("tc-05-11", limit=1500) as run:
        doc = run.fixture_sketch("tc-05-11")
        run.py(doc, "result = 1", "given script_exec on")
        print("DOC", doc)


def close(doc, tag):
    with Run4(tag) as run:
        run.call("document_close", {"doc": doc}, "cleanup")


if __name__ == "__main__":
    name, args = sys.argv[1], sys.argv[2:]
    globals()[name](*args)
