import asyncio, json, subprocess
from tclib import *
log = Log("tc-12-12.jsonl")
def netstat():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if "127.0.0.1:8765" in l and "LISTENING" in l]
async def poller(s, stop):
    i = 0
    while not stop.is_set() and i < 40:
        t0 = time.perf_counter()
        try:
            env = await asyncio.wait_for(call(s, "query_capabilities", {}), timeout=90)
            st = env.get("status")
        except Exception as e:
            st = f"EXC {type(e).__name__}: {e}"
        log("poll", i=i, status=st, elapsed=round(time.perf_counter() - t0, 3), listening=bool(netstat()))
        i += 1
        await asyncio.sleep(0.3)
async def main():
    pid, win = ids()
    log("netstat_before", rows=netstat())
    async with mcp_session() as s:
        await call(s, "document_list", {}, log)
        stop = asyncio.Event()
        task = asyncio.create_task(poller(s, stop))
        await asyncio.sleep(0.5)
        t0 = time.perf_counter()
        r = await asyncio.to_thread(cua, "click", {"pid": pid, "window_id": win, "x": 416, "y": 930, "count": 2})
        log("open_example", r=r, t=round(time.perf_counter() - t0, 3))
        await asyncio.sleep(0.4)
        r = await asyncio.to_thread(cua, "get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": str(EVIDENCE / "tc-12-12-busy.png").replace("\\", "/")})
        log("busy_grab", t=round(time.perf_counter() - t0, 3), degraded=r.get("degraded"), n=len(r.get("elements", [])))
        await asyncio.sleep(12)
        stop.set(); await task
        log("netstat_after", rows=netstat())
        d = await call(s, "document_list", {}, log)
        for doc in sc(d).get("documents", []):
            t = await call(s, "query_tree_summary", {"doc": doc["doc"]}, log)
            log("tree_brief", doc=doc["label"], status=t.get("status"), total=sc(t).get("total_objects"))
            json.dump({"h": doc["doc"]}, open("cur.json", "w"))
asyncio.run(main())
