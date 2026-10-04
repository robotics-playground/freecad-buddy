"""Calibrate the slow fixture on H1 with Delay=3: preview_dry_run and verify_recompute durations."""
import asyncio, json
from tc10lib import E, Log, h1
log = Log("tc-10-05-calib.jsonl")
async def main():
    async with h1(log, "05-calib", str(E / "tc-10-05-calib.stderr.log")) as s:
        o = await s.call("document_open", {"path": str(E / "tc-10-slow-3.FCStd")})
        h = o["structured_content"]["doc"]
        p = await s.call("preview_dry_run", {"doc": h, "operation": {"tool": "feature_body_create", "args": {"name": "Body"}}, "render": "off"})
        v = await s.call("verify_recompute", {"doc": h})
        await s.call("document_close", {"doc": h})
    for line in log.path.read_text().splitlines():
        r = json.loads(line); print(r["tool"], r["seconds"], r["envelope"].get("status"), (r["envelope"].get("detail") or {}).get("message"))
asyncio.run(main())
