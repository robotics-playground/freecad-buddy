"""TC-10-07 H1 stdio client (run inside the container; talks only to its own child H1 host)."""
import asyncio, json, os, subprocess, sys, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
run = "/repo/tests/uat/run/2026-11-18-01/evidence"
env = dict(os.environ)
for k in ("FREECAD_BUDDY_SCRIPT_EXEC", "FREECAD_BUDDY_UNATTENDED", "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED"):
    env.pop(k, None)
env["FREECAD_BUDDY_AUDIT_LOG"] = f"{run}/tc-10-07-audit.jsonl"
G = "/repo/benchmarks/g0/golden-models/"
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
def sc(res): return res.structuredContent
async def call(s, name, args):
    t = time.monotonic(); r = await s.call_tool(name, args); return r, time.monotonic() - t
def show(tag, r, dt):
    print("##", tag, "elapsed=%.2f" % dt, "isError=", r.isError)
    print("   ", json.dumps(sc(r))[:1500] if sc(r) else [getattr(c, "text", None) for c in r.content][:1], flush=True)
async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"], env=env)
    errlog = open(f"{run}/tc-10-07-server.stderr.log", "w")
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = [t.name for t in (await s.list_tools()).tools]
            print("script_exec listed", "script_exec" in names)
            c, dt = await call(s, "document_open", {"path": G + "box-10-20-30.FCStd"}); show("open D", c, dt); D = sc(c)["structured_content"]["doc"]
            c, dt = await call(s, "document_open", {"path": G + "cylinder-r5-h20.FCStd"}); show("open E", c, dt); E = sc(c)["structured_content"]["doc"]
            wpid = sh("pgrep -f 'hosts.headless.worker$' | head -1")
            print("worker pid", wpid, "cmd", open("/proc/%s/cmdline" % wpid).read().replace(chr(0), " "), flush=True)
            code = "import time, Part\nend = time.monotonic() + 75\nwhile time.monotonic() < end:\n    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nresult = 'done'"
            t0 = time.monotonic()
            c, dt = await call(s, "script_exec", {"doc": D, "code": code}); show("script_exec D", c, dt)
            cpu1 = sh(f"ps -o cputimes= -p {wpid}"); time.sleep(3); cpu2 = sh(f"ps -o cputimes= -p {wpid}")
            print("worker cpu s:", cpu1, cpu2, flush=True)
            c, dt = await call(s, "query_object", {"doc": E, "object": "Cylinder"}); show("query_object E #1 (t=%.1f)" % (time.monotonic() - t0), c, dt)
            while time.monotonic() - t0 < 65: time.sleep(0.5)
            c, dt = await call(s, "query_object", {"doc": E, "object": "Cylinder"}); show("query_object E #2 (t=%.1f)" % (time.monotonic() - t0), c, dt)
            print("worker alive after escalation:", sh(f"ps -p {wpid} -o pid="), flush=True)
            while time.monotonic() - t0 < 85: time.sleep(0.5)
            c, dt = await call(s, "query_object", {"doc": E, "object": "Cylinder"}); show("query_object E #3 (t=%.1f)" % (time.monotonic() - t0), c, dt)
asyncio.run(main())
