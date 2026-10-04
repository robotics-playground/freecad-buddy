import asyncio, json, subprocess, os
from tclib import *
log = Log("tc-12-15.jsonl")
DISC = os.path.expandvars(r"%APPDATA%\FreeCAD\v1-1\freecad-buddy")
FC = json.load(open("fc.json"))
def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-c", cmd], capture_output=True, text=True)
def state(tag):
    p = ps(f"Get-Process -Name freecad -EA SilentlyContinue | Select-Object -Expand Id; '---'; Get-CimInstance Win32_Process -Filter \"ProcessId={FC['proxy_listener_pid']} or ProcessId={FC['proxy_spawned_pid']}\" | Select-Object -Expand ProcessId").stdout.split()
    ns = [l.strip() for l in subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout.splitlines() if ":8765" in l and "LISTEN" in l]
    log("state", tag=tag, procs=p, listen=ns, disc=[f for f in os.listdir(DISC) if f == f"rpc-{FC['pid']}.json"])
async def long_call():
    t0 = time.perf_counter()
    try:
        async with mcp_session() as s:
            env = await asyncio.wait_for(call(s, "document_open", {"path": "C:/Program Files/FreeCAD 1.1/data/examples/ArchDetail.FCStd"}), 120)
            log("inflight_result", status=env.get("status"), detail=str(env.get("detail"))[:300], elapsed=round(time.perf_counter() - t0, 3))
    except BaseException as e:
        log("inflight_result", status=f"EXC {type(e).__name__}", detail=repr(e)[:400], elapsed=round(time.perf_counter() - t0, 3))
async def main():
    async with mcp_session() as s:
        c = await call(s, "document_create", {"label": "TC1215Scratch"}, log)
        await call(s, "document_list", {}, log)
    state("before")
    time.sleep(1)
    snap("tc-12-15-before.png")
    task = asyncio.create_task(long_call())
    await asyncio.sleep(1.5)
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(1, False, FC["pid"])
    ok = k32.TerminateProcess(h, 1)
    log("terminate_process", pid=FC["pid"], handle=bool(h), ok=bool(ok), last_error=k32.GetLastError(), note="Stop-Process -Force is denied (Access is denied, attempt 1) and kill_app refuses foreign processes; TerminateProcess(PROCESS_TERMINATE) as in TC-01-14/TC-10-12")
    await task
    time.sleep(2)
    state("after_kill")
    log("list_windows", r=cua("list_windows", {"pid": FC["pid"]}))
    t0 = time.perf_counter()
    try:
        async with mcp_session() as s:
            env = await asyncio.wait_for(call(s, "query_capabilities", {}), 20)
            log("post_kill_call", status=env.get("status"), detail=str(env)[:300], elapsed=round(time.perf_counter() - t0, 3))
    except BaseException as e:
        log("post_kill_call", status=f"EXC {type(e).__name__}", detail=repr(e)[:300], elapsed=round(time.perf_counter() - t0, 3))
asyncio.run(main())
