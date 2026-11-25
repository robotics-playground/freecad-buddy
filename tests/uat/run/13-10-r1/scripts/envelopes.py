"""Record normalized envelopes of several mutation tools, to diff base against head.

Env: FCB_REPO (worktree root), FCB_OUT (json path).
"""

import json
import os
import re
import sys
import unittest

REPO = os.environ["FCB_REPO"]
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from freecad_buddy.usecases import features, sketches  # noqa: E402
from infc.test_feature_tools import _FeatureFixture, mm, sub  # noqa: E402

RESULTS = {}
VOLATILE = re.compile(r"(digest|timestamp|session|snapshot|path|_ms|elapsed|duration|time|params_digest)", re.I)


def normalize(value):
    if isinstance(value, dict):
        return {k: ("<v>" if VOLATILE.search(k) and not isinstance(v, (dict, list)) else normalize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def tnp_summary(envelope):
    sc = envelope.get("structured_content") or {}
    block = sc.get("mutation") or {}
    audit = (block.get("post_verify") or {}).get("tnp_audit") or {}
    return {
        "status": envelope.get("status"),
        "rolled_back": block.get("rolled_back"),
        "audit_status": audit.get("status"),
        "verdicts": sorted(
            f"{f.get('owner')}.{f.get('prop')}={f.get('verdict')}" for f in audit.get("findings") or []
        ),
    }


class Record(_FeatureFixture):
    def record(self, key, envelope):
        RESULTS[key] = {"summary": tnp_summary(envelope), "envelope": normalize(envelope)}

    def test_sequence(self):
        document = self.document()
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 20.0, 30.0)
        self.record(
            "feature_pad",
            features.feature_pad(self.registry, doc=self.handle, body="Body", profile="Profile", name="Pad", length=mm(10.0)),
        )
        shape = document.getObject("Pad").Shape
        edge = next(
            f"Edge{i}"
            for i, e in enumerate(shape.Edges, 1)
            if all(abs(v.Point.z - 10.0) < 1e-9 and abs(v.Point.y) < 1e-9 for v in e.Vertexes)
        )
        self.record(
            "feature_fillet",
            features.feature_fillet(self.registry, doc=self.handle, body="Body", base="Pad", name="Fillet", edges=[sub("Pad", edge)], radius=mm(2.0)),
        )
        self.record(
            "feature_set_parameters",
            features.feature_set_parameters(self.registry, doc=self.handle, feature="Pad", parameters={"Length": {"value": 12.0, "unit": "mm"}}),
        )
        # A free-standing sketch with a 4-DoF rectangle; the tool pins it.
        loose = self.loose_rect_sketch(body, "Loose", 16.0, 8.0)
        self.record(
            "sketch_add_constraint",
            sketches.sketch_add_constraint(
                self.registry,
                doc=self.handle,
                sketch="Loose",
                constraints=[
                    {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
                    {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 16.0, "unit": "mm"}},
                    {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": 8.0, "unit": "mm"}},
                ],
            ),
        )
        # A sketch whose extra pinned line carries an expression-bound length; removing the line
        # makes FreeCAD drop its constraints and their binding (an op's own removal).
        extra = document.getObject("Loose")
        line = extra.addGeometry(Part.LineSegment(App.Vector(0, 20, 0), App.Vector(5, 20, 0)), False)
        extra.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, line, 1, 0.0))
        extra.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, line, 1, 20.0))
        extra.addConstraint(Sketcher.Constraint("Horizontal", line))
        idx = extra.addConstraint(Sketcher.Constraint("Distance", line, 5.0))
        extra.renameConstraint(idx, "extra_len")
        extra.setExpression(".Constraints.extra_len", "5 mm + 0 mm")
        document.recompute()
        RESULTS["remove_geometry_setup"] = {"dof": extra.solve(), "bindings": list(extra.ExpressionEngine), "valid": extra.isValid()}
        self.record(
            "sketch_remove_geometry_bound",
            sketches.sketch_remove_geometry(self.registry, doc=self.handle, sketch="Loose", geo_ids=[line]),
        )
        RESULTS["after_remove_bindings"] = list(document.getObject("Loose").ExpressionEngine)


if __name__ == "__main__" or True:
    suite = unittest.TestLoader().loadTestsFromTestCase(Record)
    outcome = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    RESULTS["_test_ok"] = outcome.wasSuccessful()
    RESULTS["_errors"] = [str(e[1])[-2000:] for e in outcome.errors + outcome.failures]
    with open(os.environ["FCB_OUT"], "w") as out:
        json.dump(RESULTS, out, indent=1, sort_keys=True, default=str)
