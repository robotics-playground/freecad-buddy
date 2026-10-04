import time
from tc08lib import *  # noqa

T = json.loads((EVIDENCE / "tc-08-12-token.json").read_text(encoding="utf-8"))


async def body(m, log):
    now = time.time()
    log.note(f"post-deadline call at {now:.3f}; mint call {T['mint_call_ts']:.3f}; elapsed {now - T['mint_call_ts']:.1f} s; expires_at {T['expires_at']}")
    r = await call_with(m, T["doc"], "feature_body_create", {"name": "Probe"}, {"preview_id": T["token"]})
    want = "confirm.preview_id has expired; re-run preview_dry_run"
    log.check("post-deadline spent+expired token refused as EXPIRED", r.get("status") != "OK" and want in msg(r), short(r, 300))
    log.check("message is NOT the already-authorized message", "has already authorized a mutation" not in msg(r), msg(r))
    tr = await names(m, T["doc"], 2)
    log.check("tree lists exactly one Probe body", tr.count("Probe") == 1, tr)
    await frame_shot(m, T["doc"], "tc-08-12-after.png")


if __name__ == "__main__":
    wait = T["exp_ts"] + 2 - time.time()
    if wait > 0:
        print("sleeping", round(wait, 1))
        time.sleep(wait)
    go("tc-08-12b", body)
