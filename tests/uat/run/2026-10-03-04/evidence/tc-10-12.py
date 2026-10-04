"""TC-10-12: FreeCAD killed through the OS while a call is in flight through the H2 proxy.
Usage: tc-10-12.py given | when | reopen"""
import asyncio
import glob
import json
import os
import shutil
import subprocess
import sys
import time

from tc10lib import APPDIR, BOX, E, Log, fc_ids, gui, gui_py, proxy_listening, show_all

log = Log("tc-10-12.jsonl")
COPY = (E / "tc-10-12-box.FCStd").as_posix()
state = E / "tc-10-12-state.json"


async def given():
    shutil.copy(BOX, COPY)
    async with gui(log, "12-given") as g:
        o = await g.call("document_open", {"path": COPY})
        h = o["structured_content"]["doc"]
        print("open", o["status"], h, "show_all", show_all())
        sv = await g.call("document_save", {"doc": h, "path": COPY})
        print("save", sv["status"])
        dl = await g.call("document_list", {})
        print("document_list", json.dumps(dl["structured_content"]))
        f = await g.call("view_fit_viewport", {"doc": h})
        print("fit", f["status"])
        state.write_text(json.dumps({"handle": h}))
    print(gui_py("shot", "tc-10-12-before.png"))


def terminate(pid):
    ps = (E / "tc-10-12-kill.ps1")
    ps.write_text(
        "Add-Type @'\nusing System; using System.Runtime.InteropServices;\npublic static class K { "
        "[DllImport(\"kernel32.dll\",SetLastError=true)] public static extern IntPtr OpenProcess(int a,bool b,int pid);\n"
        "[DllImport(\"kernel32.dll\",SetLastError=true)] public static extern bool TerminateProcess(IntPtr h,uint c); }\n'@\n"
        f"$h=[K]::OpenProcess(1,$false,{pid}); \"terminate {pid} -> \" + [K]::TerminateProcess($h,1)\n")
    return subprocess.run(["powershell", "-NoProfile", "-File", str(ps)], capture_output=True, text=True).stdout.strip()


async def when():
    pid, _ = fc_ids()
    h = json.loads(state.read_text())["handle"]
    proxy_log = os.path.join(APPDIR, "mcp-proxy.log")
    n0 = sum(1 for _ in open(proxy_log, encoding="utf-8", errors="replace"))
    out = {"freecad_pid": pid}
    async with gui(log, "12-when") as g:
        # Back-to-back previews keep one call outstanding at every instant, so the kill lands mid-call
        # (attempt 1 used a single 0.15 s-delayed kill and the call had already finished).
        done = {"n": 0, "statuses": []}

        async def loop():
            while True:
                env = await g.call("preview_dry_run", {"doc": h, "operation": {"tool": "feature_body_create",
                                                                              "args": {"name": "Body"}}, "render": "auto"})
                done["n"] += 1
                done["statuses"].append(env.get("status"))
                if env.get("status") != "OK":
                    return env

        call = asyncio.create_task(loop())
        await asyncio.sleep(3.0)
        out["completed_before_kill"] = done["n"]
        out["in_flight_at_kill"] = not call.done()
        t_kill = time.time()
        out["kill"] = await asyncio.to_thread(terminate, pid)
        try:
            env = await asyncio.wait_for(call, timeout=180)
            out["statuses_tail"] = done["statuses"][-3:]
            out["response"] = {"seconds_after_kill": round(time.time() - t_kill, 2), "status": env.get("status"),
                               "message": (env.get("detail") or {}).get("message"), "data": (env.get("detail") or {}).get("data")}
        except asyncio.TimeoutError:
            out["response"] = "NO RESPONSE within 180 s"
        except Exception as exc:  # the client must get an envelope, never an exception
            out["response"] = f"RAISED {type(exc).__name__}: {exc}"
    out["client_session_exited_cleanly"] = True
    time.sleep(2)
    out["freecad_alive"] = subprocess.run(["powershell", "-NoProfile", "-c", f"(Get-Process -Id {pid} -EA SilentlyContinue | Measure-Object).Count"],
                                          capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["uv", "run", "python", "_automation/uat/fcb.py", "--list"], cwd=str(E.parents[4]), capture_output=True, text=True, timeout=120)
    out["tools_list_after_kill"] = {"rc": r.returncode, "stdout_head": r.stdout[:200], "stderr_tail": r.stderr[-300:]}
    out["proxy_listening"] = proxy_listening()
    lines = open(proxy_log, encoding="utf-8", errors="replace").readlines()[n0:]
    out["proxy_log_new"] = [ln.rstrip() for ln in lines][-15:]
    out["proxy_log_crash_or_connection"] = [ln.rstrip() for ln in lines if "crash" in ln.lower() or "connection" in ln.lower()][:8]
    df = os.path.join(APPDIR, f"rpc-{pid}.json")
    try:
        json.load(open(df))
        out["discovery_file_dead_pid"] = "exists and parses as JSON"
    except FileNotFoundError:
        out["discovery_file_dead_pid"] = "absent"
    except ValueError as exc:
        out["discovery_file_dead_pid"] = f"CORRUPT: {exc}"
    (E / "tc-10-12-checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


async def reopen():
    async with gui(log, "12-reopen") as g:
        names = (await g.s.list_tools()).tools
        print("tools/list after restart:", len(names))
        o = await g.call("document_open", {"path": COPY})
        h = o["structured_content"]["doc"]
        f = await g.call("view_fit_viewport", {"doc": h})
        print("open", o["status"], h, "fit", f["status"], (f.get("detail") or {}).get("message"))
        state.write_text(json.dumps({"handle": h, "tools_after_restart": len(names)}))
    print(gui_py("shot", "tc-10-12-after.png"))


asyncio.run({"given": given, "when": when, "reopen": reopen}[sys.argv[1]]())
