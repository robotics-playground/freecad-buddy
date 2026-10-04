"""GUI document helper over a direct listener connection (the proxy is stopped during TC-10-03..11).
Usage: tc-10-rpcgui.py open <NN> [path] | fitshot <NN> <png> [handle] | close <NN> [handle] | list <NN>
`open` records the handle in tc-10-<NN>-state.json; fit is view_fit_viewport on the listener, with
gui.py fitall as the fallback when it is not OK."""
import json
import sys
import time

from tc10lib import BOX, E, Log, Rpc, gui_py, show_all

cmd, nn = sys.argv[1], sys.argv[2]
log = Log(f"tc-10-{nn}.jsonl")
state = E / f"tc-10-{nn}-state.json"


def conn(tag):
    c = Rpc(log, f"{nn}-{tag}", name="gui")
    hello = c.hello()
    assert "result" in hello, hello
    return c


if cmd == "open":
    path = sys.argv[3] if len(sys.argv) > 3 else BOX
    c = conn("open")
    o = c.call("document_open", {"path": path})
    h = o["structured_content"]["doc"]
    print("open", o["status"], h)
    print("show_all", show_all())
    f = c.call("view_fit_viewport", {"doc": h})
    print("fit", f["status"], (f.get("detail") or {}).get("message"))
    c.close()
    st = json.loads(state.read_text()) if state.exists() else {}
    st["handle"] = h
    state.write_text(json.dumps(st))
    if f["status"] != "OK":
        print("gui fitall", gui_py("fitall"))
        time.sleep(1)
elif cmd == "fitshot":
    png = sys.argv[3]
    h = sys.argv[4] if len(sys.argv) > 4 else json.loads(state.read_text())["handle"]
    c = conn("fit")
    f = c.call("view_fit_viewport", {"doc": h})
    print("fit", f["status"], (f.get("detail") or {}).get("message"))
    c.close()
    if f["status"] != "OK":
        print("gui fitall", gui_py("fitall"))
        time.sleep(1)
    print(gui_py("shot", png))
elif cmd == "shot":
    print(gui_py("shot", sys.argv[3]))
elif cmd == "close":
    h = sys.argv[3] if len(sys.argv) > 3 else json.loads(state.read_text())["handle"]
    c = conn("close")
    print("close", c.call("document_close", {"doc": h})["status"])
    c.close()
elif cmd == "list":
    c = conn("list")
    print(json.dumps(c.call("document_list", {})["structured_content"]))
    c.close()
