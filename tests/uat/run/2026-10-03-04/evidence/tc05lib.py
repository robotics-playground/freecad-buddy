"""TC-05 helpers on top of tc04lib: preview + confirmed apply (host is NOT auto-approve)."""

from tc04lib import *  # noqa: F401,F403
from tc04lib import (  # noqa: F401
    EVIDENCE, Log, Mcp, capture, cua, fitall, go, ids, json, mut, near, pv, q, rect_profile, sc, sel,
    shot, short, snaps, tree_names, vol,
)

HEX64 = __import__("re").compile(r"^[0-9a-f]{64}$")


async def apply(m, doc, tool, args):
    """preview_dry_run, then the tool with the minted confirm. Returns (preview, apply)."""
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
    token = sc(preview).get("preview_id")
    if not token:
        return preview, {"status": "NO_TOKEN", "detail": short(preview)}
    full = dict(args, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"})
    return preview, await m.call(tool, full)


async def body_sketch(m, label, w=20, h=20, pad=None, body="Body", sketch_name="Sketch"):
    doc = sc(await m.call("document_create", {"label": label})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": body})
    await apply(m, doc, "sketch_create", {"name": sketch_name, "body": body, "plane": "XY"})
    geometry, constraints = rect_profile(0, 0, w, h)
    await apply(m, doc, "sketch_add_geometry", {"sketch": sketch_name, "geometry": geometry,
                                                "constraints": constraints})
    if pad is not None:
        await apply(m, doc, "feature_pad", {"body": body, "profile": sketch_name, "name": "Pad",
                                            "length": q(pad)})
    return doc


def fp(envelope, key):
    return (mut(envelope).get(key) or {})


def digest(envelope, key):
    return fp(envelope, key).get("digest")


def tree_has(envelope, name):
    return f'"name": "{name}"' in json.dumps(sc(envelope))


def _stale_temp():
    import os as _o
    temp = _o.environ.get("TEMP") or ""
    return {_o.path.join(temp, p) for p in _o.listdir(temp) if p.startswith("FCB_TMP_snap_")
            and _o.path.getmtime(_o.path.join(temp, p)) < 1790600000}


STALE = _stale_temp()


def new_snaps():
    """Snapshot dirs in $TEMP and the bridge workdir, minus the 10 stale 2026-09-22 dirs in $TEMP."""
    return [p for p in snaps() if p not in STALE]


KEPT = {WORKDIR_TMP + "/FCB_TMP_snap_y8f2dy5z"}  # kept by the TC-05-03 chain unproven rollback (evidence)


def run_snaps():
    """new_snaps() minus snapshot dirs deliberately kept as evidence by earlier TC-05 scenarios."""
    return [p for p in new_snaps() if p.replace("\\", "/") not in KEPT]


async def close_all(m, log):
    for d in sc(await m.call("document_list", {})).get("documents") or []:
        c = await m.call("document_close", {"doc": d["doc"]})
        log.note(f"cleanup previous scenario: document_close {d['label']} -> {c.get('status')}")
