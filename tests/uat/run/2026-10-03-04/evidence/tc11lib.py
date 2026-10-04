"""TC-11 helpers: GUI MCP session (tc05lib), H1 inline host (tc08h1), baseline/after captures, results file."""

import json as _json
import os as _os

from tc05lib import *  # noqa: F401,F403
from tc05lib import EVIDENCE, Log, Mcp, apply, capture, close_all, sc, short  # noqa: F401
from tc08h1 import H1, h1, h1_env  # noqa: F401

REPO = "D:/Work/Personal/Sources/freecad-buddy"
BOX = REPO + "/benchmarks/g0/golden-models/box-10-20-30.FCStd"
RESULTS = EVIDENCE / "tc-11-results.json"


def record(sid, priority, verdict, evidence, note):
    rows = _json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    rows = [r for r in rows if r["id"] != sid]
    rows.append({"id": sid, "priority": priority, "verdict": verdict, "evidence": evidence, "note": note})
    rows.sort(key=lambda r: r["id"])
    RESULTS.write_text(_json.dumps(rows, indent=1), encoding="utf-8")


async def baseline(m, log, tag):
    """Close leftovers, open the golden box in the GUI, fit, capture <tag>-before.png. Returns the handle."""
    await close_all(m, log)
    opened = await m.call("document_open", {"path": BOX})
    doc = sc(opened).get("doc")
    log.check("Given document_open box-10-20-30 OK", opened.get("status") == "OK", short(opened))
    log.note(f"golden box opens hidden; GUI View>Visibility>Show All Objects: {show_all()}")
    fit, rec = await capture(m, doc, f"{tag}-before.png")
    log.check("Given baseline fit OK (MCP or GUI Fit All)", fit.get("view_fit_viewport") == "OK" or "gui_fitall" in fit, fit)
    log.check("Given baseline captured", rec.get("exists"), rec.get("file"))
    return doc


async def closing(m, log, doc, tag):
    fit, rec = await capture(m, doc, f"{tag}-after.png")
    log.check("Then (visual) model framed: view_fit_viewport OK", fit.get("view_fit_viewport") == "OK", fit)
    log.check("Then (visual) after captured (pixel judgement by agent, see results)", rec.get("exists"), rec.get("file"))


async def fingerprint(m, doc):
    """Live-document fingerprint digest, read from a preview of a harmless op (diff.fingerprint_before)."""
    env = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_body_create",
                                                                   "args": {"name": "FpProbe"}}})
    return ((sc(env).get("diff") or {}).get("fingerprint_before")), env.get("status")


def show_all():
    import time as _t
    from tc03lib import cua, ids
    pid, win = ids()
    r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    _t.sleep(0.8)
    return {"effect": r.get("effect"), "route": r.get("route"), "error": r.get("error") or r.get("_raw")}


def mask(token):
    return f"{token[:4]}…(len {len(token)})" if token else None


def fcb_env_clean(extra=None):
    """H1 env without the inherited operator flags."""
    return h1_env(extra, drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE"))


TEMP = _os.environ.get("TEMP") or ""
