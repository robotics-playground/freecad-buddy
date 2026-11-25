"""Probe: does a feature_set_expression / other tool rollback leave an application-level active
transaction that reopens on the next document change? Env FCB_REPO, FCB_OUT."""

import os
import sys

REPO = os.environ["FCB_REPO"]
sys.path.insert(0, os.path.join(REPO, "src"))
import FreeCAD as App  # noqa: E402

from freecad_buddy.usecases import confirm, features  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402

out = []
confirm.set_auto_approve(True)
registry = DocumentRegistry()
handle = registry.document_create("probe")["structured_content"]["doc"]
doc = registry.with_document(handle, lambda h, d: d)


def state(tag):
    out.append(f"{tag}: app_active={App.getActiveTransaction()} pending={doc.HasPendingTransaction} undo={doc.UndoCount} names={list(doc.UndoNames)[:3]}")


state("start")
r = features.feature_parameters_define(registry, doc=handle, varset="Params", parameters=[{"name": "height", "type": "length", "value": {"value": 10, "unit": "mm"}}])
state(f"define {r['status']}")
box = doc.addObject("Part::Box", "Box")
doc.recompute()
state("raw box added")
r = features.feature_set_expression(registry, doc=handle, expressions=[{"object": "Box", "path": "Length", "expression": "Params.height"}])
state(f"bind {r['status']}")
r = features.feature_set_expression(registry, doc=handle, expressions=[{"object": "Box", "path": "Length", "expression": "Box.Length + 1 mm"}])
state(f"cycle {r['status']} rb={r['structured_content'].get('mutation', {}).get('rolled_back')}")
box.Height = 3
state("after raw property change")
doc.recompute()
state("after recompute")
r = features.feature_set_parameters(registry, doc=handle, feature="Box", parameters={"Width": {"value": 99999, "unit": "mm"}, "Height": {"value": -1, "unit": "mm"}}) if False else None
with open(os.environ["FCB_OUT"], "w") as f:
    f.write("\n".join(out) + "\n")

# Does a later successful mutation clear the leak, and can document_undo run after it?
r = features.feature_parameters_define(registry, doc=handle, varset="Params", parameters=[{"name": "height", "type": "length", "value": {"value": 12, "unit": "mm"}}])
state(f"define-after-leak {r['status']}")
try:
    u = registry.document_undo(doc=handle)
    state(f"undo-after-define {u['status']} undone={u['structured_content'].get('undone')}")
except Exception as exc:
    state(f"undo-after-define raised {exc}")

# Second document: the in-bracket no-op (equivalent text) path.
handle2 = registry.document_create("probe2")["structured_content"]["doc"]
doc2 = registry.with_document(handle2, lambda h, d: d)
App.setActiveTransaction  # noqa: B018
App.closeActiveTransaction() if App.getActiveTransaction() else None
features.feature_parameters_define(registry, doc=handle2, varset="P", parameters=[{"name": "a", "type": "length", "value": {"value": 2, "unit": "mm"}}])
b2 = doc2.addObject("Part::Box", "B")
doc2.recompute()
features.feature_set_expression(registry, doc=handle2, expressions=[{"object": "B", "path": "Length", "expression": "P.a * 2"}])
out.append(f"probe2 stored={list(b2.ExpressionEngine)} app_active={App.getActiveTransaction()}")
r = features.feature_set_expression(registry, doc=handle2, expressions=[{"object": "B", "path": "Length", "expression": "P.a*2"}])
sc = r["structured_content"]
out.append(f"probe2 equivalent {r['status']} undo_steps={sc.get('undo_steps')} unchanged={len(sc.get('unchanged', []))} app_active={App.getActiveTransaction()} pending={doc2.HasPendingTransaction}")
b2.Height = 4
out.append(f"probe2 after raw change app_active={App.getActiveTransaction()} pending={doc2.HasPendingTransaction}")
with open(os.environ["FCB_OUT"], "w") as f:
    f.write("\n".join(out) + "\n")
