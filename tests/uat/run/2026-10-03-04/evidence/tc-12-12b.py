import asyncio, json, subprocess
from tclib import *
log = Log("tc-12-12b.jsonl")
H = json.load(open("cur.json"))["h"]
def netstat():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if "127.0.0.1:8765" in l and "LISTENING" in l]
async def poller(s, stop):
    i = 0
    while not stop.is_set() and i < 60:
        t0 = time.perf_counter()
        try:
            env = await asyncio.wait_for(call(s, "query_capabilities", {}), timeout=90); st = env.get("status")
        except Exception as e:
            st = f"EXC {type(e).__name__}: {e}"
        log("poll", i=i, status=st, elapsed=round(time.perf_counter() - t0, 3), listening=bool(netstat()))
        i += 1; await asyncio.sleep(0.25)
async def main():
    pid, win = ids()
    async with mcp_session() as s:
        stop = asyncio.Event(); task = asyncio.create_task(poller(s, stop))
        await asyncio.sleep(0.5)
        t0 = time.perf_counter()
        tm = asyncio.create_task(asyncio.to_thread(menu_retry, ["Edit", "Refresh"], 6, 5))
        await asyncio.sleep(0.3)
        g = await asyncio.to_thread(cua, "get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": str(EVIDENCE / "tc-12-12-busy.png").replace("\\", "/")})
        log("busy_grab", t=round(time.perf_counter() - t0, 3), degraded=g.get("degraded"), n=len(g.get("elements", [])))
        r = await tm; log("refresh_menu", r=r, t=round(time.perf_counter() - t0, 3))
        await asyncio.sleep(8); stop.set(); await task
        log("netstat_after", rows=netstat())
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
asyncio.run(main())
