"""TC-06 preconditions."""
import subprocess
from tc06lib import *


async def body(m, log):
    log.note("git HEAD: " + subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True).stdout.strip())
    log.note("git status --short src: " + repr(subprocess.run(["git", "status", "--short", "src"], capture_output=True, text=True, cwd="D:/Work/Personal/Sources/freecad-buddy").stdout))
    ps = subprocess.run(["powershell", "-NoProfile", "-c", "Get-Process freecad | Select Id,MainWindowTitle | ConvertTo-Json"], capture_output=True, text=True).stdout
    log.note("Get-Process freecad: " + ps.strip().replace("\n", " "))
    log.check("one FreeCAD GUI open, title 'FreeCAD 1.1.1'", "FreeCAD 1.1.1" in ps,
              "title is 'FreeCAD 1.1.4' -> stale TC literal (test-case defect); GUI open = yes" if "1.1.4" in ps else ps)
    ns = subprocess.run("netstat -ano", capture_output=True, text=True, shell=True).stdout
    rows = [l.strip() for l in ns.splitlines() if ":8765" in l and "LISTENING" in l]
    log.check(":8765 LISTENING", bool(rows), rows)
    st = subprocess.run(["cua-driver", "status"], capture_output=True, text=True).stdout
    log.check("cua-driver status reports daemon, not Session 0", "running" in st and "Session 0" not in st, st.splitlines()[0] if st else st)
    caps = await m.call("query_capabilities", {})
    log.check("query_capabilities render == gui_constructed", sc(caps).get("render") == "gui_constructed", sc(caps).get("render"))
    log.note("capabilities: " + json.dumps(sc(caps))[:600])
    pid, win = ids()
    lw = cua("list_windows", {"pid": pid})
    titles = [(w["window_id"], w["title"]) for w in lw.get("windows", [])]
    log.check("list_windows has FreeCAD main window", any(w == win for w, _ in titles), titles)
    log.check("evidence dir writable", EVIDENCE.exists(), str(EVIDENCE))
    docs = sc(await m.call("document_list", {})).get("documents")
    log.note(f"open documents at start: {docs}")

go("tc-06-00", body)
