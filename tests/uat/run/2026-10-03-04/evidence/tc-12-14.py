import asyncio, json, subprocess, os
from tclib import *
log = Log("tc-12-14.jsonl")
DISC = os.path.expandvars(r"%APPDATA%\FreeCAD\v1-1\freecad-buddy")
def state(tag):
    ps = subprocess.run(["powershell", "-NoProfile", "-c", "Get-Process -Name freecad -EA SilentlyContinue | Select-Object -Expand Id; '---'; Get-CimInstance Win32_Process -Filter \"ProcessId=36996 or ProcessId=32288\" | Select-Object -Expand ProcessId"], capture_output=True, text=True).stdout.split()
    ns = [l.strip() for l in subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout.splitlines() if ":8765" in l]
    files = sorted(os.listdir(DISC))
    log("state", tag=tag, procs=ps, netstat=ns, disc=[f for f in files if f.startswith("rpc-")])
async def main():
    async with mcp_session() as s:
        await call(s, "document_list", {}, log)
    state("before")
    snap("tc-12-14-before.png")
    r = menu_retry(["File", "Exit"], tries=10, wait=6); log("exit_menu", r=r)
    for i in range(20):
        time.sleep(1)
        if not subprocess.run(["powershell", "-NoProfile", "-c", "Get-Process -Name freecad -EA SilentlyContinue"], capture_output=True, text=True).stdout.strip():
            log("gone_after_s", s=i + 1); break
    time.sleep(2)
    state("after")
    pid, _ = ids()
    log("list_windows", r=cua("list_windows", {"pid": pid}))
    t0 = time.perf_counter()
    try:
        async with mcp_session() as s:
            await asyncio.wait_for(call(s, "query_capabilities", {}, log), 20)
        log("client_call", result="UNEXPECTED OK")
    except BaseException as e:
        log("client_call", result=f"{type(e).__name__}: {str(e)[:200]}", elapsed=round(time.perf_counter() - t0, 3))
asyncio.run(main())
