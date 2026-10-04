from tc08lib import *  # noqa

DOC = "fcb-doc:0ud_NhyZg8-64qbpATi41Q"


async def body(m, log):
    log.note("same-operation re-preview refused 'an object named Probe already exists' (TC expects OK; name collision). Re-run with name Probe2.")
    pr = await preview(m, DOC, "feature_body_create", {"name": "Probe2"})
    a = await call_with(m, DOC, "feature_body_create", {"name": "Probe2"}, {"preview_id": token(pr)})
    log.check("fresh preview (name Probe2) token apply returns OK", a.get("status") == "OK", short(a))
    log.write({"tree": await names(m, DOC, 2)})


go("tc-08-07b", body)
