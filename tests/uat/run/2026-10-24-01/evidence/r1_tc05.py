"""TC-05 agent-driven scenarios for phase R1 (from 2026-10-23-02 p4_tc05.py): r1_tc05.py <name> [doc ...].
The host runs with FREECAD_BUDDY_AUTO_APPROVE=0, so every mutation is previewed and confirmed (Run4.mut).
The visual steps (fit, capture, read) run separately through r1_gui1.py / r1_shot.sh."""

import sys

from r1_p4_lib import Run4, q


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
        run.snapshot_check(doc, "precondition snapshot check")
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
    with Run4("tc-05-06", limit=4000) as run:
        run.mut(doc, "sketch_remove_geometry", {"sketch": "Sketch001", "geo_ids": [0]},
                "when reproducer 1 sketch_remove_geometry")
        run.snapshot_check(doc, "after reproducer 1 snapshot check")
        run.mut(doc, "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}},
                "when reproducer 2 radius 400")
        run.snapshot_check(doc, "after reproducer 2 snapshot check")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("document_list", {}, "then label")


def tc05_17_given():
    with Run4("tc-05-17", limit=1500) as run:
        doc = run.fixture_fillet("tc-05-17")
        run.call("query_capabilities", {}, "given element map", quiet=True)
        run.call("query_mass_properties", {"doc": doc, "object": "Fillet"}, "given fillet")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc05_17_when(doc):
    with Run4("tc-05-17", limit=4000) as run:
        run.mut(doc, "sketch_remove_geometry", {"sketch": "Sketch", "geo_ids": [0]}, "when remove geometry 0")
        run.call("query_mass_properties", {"doc": doc, "object": "Fillet"}, "then fillet intact")


def fit(doc, tag):
    with Run4(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "then fit")


def close(doc, tag):
    with Run4(tag) as run:
        run.call("document_close", {"doc": doc}, "cleanup close")


if __name__ == "__main__":
    name, args = sys.argv[1], sys.argv[2:]
    globals()[name](*args)
