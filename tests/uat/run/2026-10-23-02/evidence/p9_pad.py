"""Print the p9_h1.py call pairs that build a padded 20 x 20 x 30 box on the document of call 1:
Body, a fully constrained 20 x 20 Sketch on XY, Pad 30 mm (auto-approve on, so no confirm).

    p9_pad.py      one JSON array of strings: tool, args, tool, args, ...
"""
import json


def q(value):
    return {"value": value, "unit": "mm"}


DOC = "$R1.structured_content.doc"
GEOMETRY = [{"kind": "line_segment", "start": s, "end": e} for s, e in
            (([0, 0], [20, 0]), ([20, 0], [20, 20]), ([20, 20], [0, 20]), ([0, 20], [0, 0]))]
CONSTRAINTS = [
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
PAIRS = [
    "feature_body_create", {"doc": DOC, "name": "Body"},
    "sketch_create", {"doc": DOC, "name": "Sketch", "body": "Body", "plane": "XY"},
    "sketch_add_geometry", {"doc": DOC, "sketch": "Sketch", "geometry": GEOMETRY, "constraints": CONSTRAINTS},
    "feature_pad", {"doc": DOC, "body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)},
]
print(json.dumps([p if isinstance(p, str) else json.dumps(p) for p in PAIRS]))
