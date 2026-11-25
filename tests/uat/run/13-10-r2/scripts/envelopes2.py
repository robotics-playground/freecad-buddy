"""Round 2 L12: envelopes of feature_parameters_define (new and no-op), feature_pad,
document_object_delete and document_undo, plus the application transaction state after each.
Env: FCB_REPO, FCB_OUT."""

import json
import os
import re
import sys
import unittest

REPO = os.environ["FCB_REPO"]
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import FreeCAD as App  # noqa: E402

from freecad_buddy.usecases import features  # noqa: E402
from infc.test_feature_tools import _FeatureFixture, mm  # noqa: E402

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


class Record(_FeatureFixture):
    def record(self, key, envelope):
        document = self.document()
        RESULTS[key] = {
            "status": envelope.get("status"),
            "code": (envelope.get("detail") or {}).get("code"),
            "app_active_after": str(App.getActiveTransaction()),
            "pending_after": document.HasPendingTransaction,
            "envelope": normalize(envelope),
        }

    def test_sequence(self):
        document = self.document()
        length = {"name": "height", "type": "length", "value": {"value": 10, "unit": "mm"}}
        self.record("define_new", features.feature_parameters_define(self.registry, doc=self.handle, varset="Params", parameters=[length]))
        self.record("define_noop", features.feature_parameters_define(self.registry, doc=self.handle, varset="Params", parameters=[length]))
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 20.0, 30.0)
        self.record("feature_pad", features.feature_pad(self.registry, doc=self.handle, body="Body", profile="Profile", name="Pad", length=mm(10.0)))
        spare = document.addObject("Part::Box", "Spare")
        spare.setExpression("Height", "Params.height")
        user = document.addObject("Part::Box", "User")
        user.setExpression("Length", "Spare.Length * 2")
        document.recompute()
        self.record("delete_refused_dependent", _safe(lambda: features.document_object_delete(self.registry, doc=self.handle, objects=["Spare"])))
        lone = document.addObject("Part::Box", "Lone")
        document.recompute()
        self.record("delete_plain", _safe(lambda: features.document_object_delete(self.registry, doc=self.handle, objects=["Lone"])))
        self.record("delete_with_dependents", _safe(lambda: features.document_object_delete(self.registry, doc=self.handle, objects=["Spare"], with_dependents=True)))
        self.record("delete_unknown", _safe(lambda: features.document_object_delete(self.registry, doc=self.handle, objects=["Nope"])))
        self.record("document_undo", self.registry.document_undo(doc=self.handle))
        # After all calls: a raw change, then undo must revert exactly that change's predecessor
        # without an open-transaction refusal.
        RESULTS["final"] = {"app_active": str(App.getActiveTransaction()), "pending": document.HasPendingTransaction, "undo_names": list(document.UndoNames)[:6]}


def _safe(call):
    try:
        return call()
    except Exception as exc:  # noqa: BLE001
        return {"status": f"raised {type(exc).__name__}", "detail": {"code": getattr(exc, "code", None), "message": str(exc)[:200]}}


suite = unittest.TestLoader().loadTestsFromTestCase(Record)
outcome = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
RESULTS["_test_ok"] = outcome.wasSuccessful()
RESULTS["_errors"] = [str(e[1])[-2000:] for e in outcome.errors + outcome.failures]
with open(os.environ["FCB_OUT"], "w") as out:
    json.dump(RESULTS, out, indent=1, sort_keys=True, default=str)
