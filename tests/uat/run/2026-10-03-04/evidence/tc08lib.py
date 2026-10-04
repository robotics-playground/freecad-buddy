"""TC-08 helpers on top of tc05lib: preview tokens, gate refusals, tempdoc probes, framed captures.

Host is NOT auto-approve, so every Given mutation goes preview_dry_run -> tool + confirm.
"""

from tc05lib import *  # noqa: F401,F403
from tc05lib import (  # noqa: F401
    EVIDENCE, Log, Mcp, apply, body_sketch, capture, cua, digest, fitall, fp, go, ids, json, mut, near, pv,
    q, rect_profile, sc, shot, short, tree_names, vol, WORKDIR_TMP,
)

import glob as _glob
import os as _os
import time as _time

STALE_PREV = "FCB_TMP_prev_rtoduji3"  # dated 2026-09-22, predates this run, unreadable (Permission denied)

PAD30 = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 30, "unit": "mm"}}


def prev_dirs():
    """FCB_TMP_prev_* dirs in $TEMP (what the TC names) and the bridge workdir tmp (where preview.py puts them)."""
    temp = _os.environ.get("TEMP") or ""
    found = _glob.glob(_os.path.join(temp, "FCB_TMP_prev_*")) + _glob.glob(WORKDIR_TMP + "/FCB_TMP_prev_*")
    return sorted(p.replace("\\", "/") for p in found if STALE_PREV not in p)


def msg(envelope):
    d = envelope.get("detail")
    if isinstance(d, dict):
        return d.get("message") or ""
    return str(d or envelope.get("_raw") or "")


async def preview(m, doc, tool, args, **extra):
    body = {"doc": doc, "operation": {"tool": tool, "args": args}}
    body.update(extra)
    return await m.call("preview_dry_run", body)


def token(envelope):
    return sc(envelope).get("preview_id")


def diff(envelope):
    return sc(envelope).get("diff") or {}


async def call_with(m, doc, tool, args, confirm):
    full = dict(args, doc=doc)
    if confirm is not _MISSING:
        full["confirm"] = confirm
    return await m.call(tool, full)


_MISSING = object()


async def frame_shot(m, doc, png):
    """Fit (MCP, falling back to the GUI Fit All) and capture the real window."""
    fit = await m.fit(doc)
    _time.sleep(1.0)
    rec = shot(png)
    m.log.write({"capture": png, "fit": fit, "shot": rec})
    print("capture", png, fit, rec.get("title"))
    return fit, rec


async def names(m, doc, depth=3):
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": depth})
    out = []

    def walk(nodes):
        for n in nodes or []:
            out.append(n.get("name"))
            walk(n.get("children"))

    walk(sc(tr).get("tree"))
    return out
MISSING = _MISSING
