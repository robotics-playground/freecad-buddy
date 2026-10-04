from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "TwoProbe"})).get("doc")
    for up in ("TwoLengths", "?TwoLengths"):
        b = "B" + up.strip("?")
        await m.call("feature_body_create", {"doc": h, "name": b + up.count("?") * "Q"})
        await sketch(m, h, "P" + b + up.count("?") * "Q", b + up.count("?") * "Q", rect_profile(0, 0, 20, 30))
        e = await m.call("feature_pad", {"doc": h, "body": b + up.count("?") * "Q", "profile": "P" + b + up.count("?") * "Q",
                                         "name": "Pad" + up.count("?") * "Q", "length": q(10), "second_length": q(4), "up_to": up})
        log.note(f"up_to={up!r}: {short(e, 400)} vol={ss(e).get('volume')} bbox={ss(e).get('bbox')}")
    await m.call("document_close", {"doc": h})


go("tc-04-04-probe", body)
