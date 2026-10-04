import glob
from tc05lib import *

ARGS = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
INJECT = (
    "from freecad_buddy.usecases import transaction as _t\n"
    "_orig_rm = _t.run_mutation\n"
    "class _CommitBoom:\n"
    "    def __init__(self, d):\n"
    "        object.__setattr__(self, '_d', d)\n"
    "    def __getattr__(self, n):\n"
    "        return getattr(self._d, n)\n"
    "    def __setattr__(self, n, v):\n"
    "        setattr(self._d, n, v)\n"
    "    def commitTransaction(self):\n"
    "        raise RuntimeError('injected commit failure')\n"
    "def _rm(document, *a, **k):\n"
    "    _t.run_mutation = _orig_rm\n"
    "    out_doc, env = _orig_rm(_CommitBoom(document), *a, **k)\n"
    "    if isinstance(out_doc, _CommitBoom):\n"
    "        out_doc = out_doc._d\n"
    "    return out_doc, env\n"
    "_t.run_mutation = _rm\n"
    "result = 'armed'")


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0510"][0]["doc"]
    log.note("TC's literal patch is impossible on this build: 'cannot set commitTransaction attribute of immutable type App.Document' (TypeError), "
             "and the instance attribute is read-only (tc-05-10-probe). Equivalent injection: a one-shot wrapper on transaction.run_mutation hands the "
             "bracket a delegating proxy whose commitTransaction raises RuntimeError('injected commit failure'); every other call reaches the real document.")
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": ARGS}})
    token = sc(preview).get("preview_id")
    inj = await m.call("debug_exec", {"doc": doc, "code": INJECT})
    log.note(f"inject -> {short(inj)} {sc(inj).get('value_repr')}")
    env = await m.call("feature_pad", dict(ARGS, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    mb = mut(env)
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r} isError={env.get('_isError')}")
    log.check("failure reported as ResultEnvelope with status SPEC_FAILED", "status" in env and env.get("status") == "SPEC_FAILED", short(env))
    log.check("explanation == 'RuntimeError: injected commit failure'", pv(env).get("explanation") == "RuntimeError: injected commit failure", pv(env).get("explanation"))
    log.check("rolled_back true", mb.get("rolled_back") is True, mb.get("rolled_back"))
    log.check("snapshot_path null and no new snapshot dir", mb.get("snapshot_path", "MISSING") is None and run_snaps() == [], {"snapshot_path": mb.get("snapshot_path", "MISSING"), "dirs": run_snaps()})
    fbr = mb.get("fingerprint_before") or {}
    log.check("fingerprint_after null, fingerprint_before full record", mb.get("fingerprint_after", "MISSING") is None and bool(fbr.get("digest")) and isinstance(fbr.get("objects"), list) and bool(fbr.get("serializer")),
              {"after": mb.get("fingerprint_after", "MISSING"), "before_keys": sorted(fbr)})
    log.note(f"rollback_proven={mb.get('rollback_proven')} (commit-failure path reports rolled_back without a re-hash proof)")
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.note(f"Pad in tree after injected failure: {tree_has(tr, 'Pad')}")
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Body"})
    log.note(f"Body mass after injected failure: status={pm.get('status')} vol={vol(pm)}")
    fit, rec = await capture(m, doc, "tc-05-10-after.png")
    log.note(f"after fit (taken BEFORE the closing feature_pad) = {fit}")
    p2, e2 = await apply(m, doc, "feature_pad", ARGS)
    log.check("bracket closed: subsequent well-formed feature_pad OK on same handle", e2.get("status") == "OK", short(e2))
    fit2, rec2 = await capture(m, doc, "tc-05-10-closing-pad.png")
    log.note(f"closing pad capture fit={fit2}")


go("tc-05-10b", body)
