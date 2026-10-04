import sys
from tc14lib import *

PHASE = sys.argv[1]


async def body(m, log):
    if PHASE == "before":
        o = await m.call("document_open", {"path": BOX})
        h = sc(o).get("doc")
        log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
        f = await m.call("view_fit_viewport", {"doc": h})
        log.check("Given fit OK", f.get("status") == "OK", f.get("text"))
        shot("tc-14-15-before.png")
        (EVIDENCE / "tc-14-15-handle.txt").write_text(h)
    else:
        h = (EVIDENCE / "tc-14-15-handle.txt").read_text().strip()
        f = await m.call("view_fit_viewport", {"doc": h})
        log.check("Then fit OK after probe", f.get("status") == "OK", f.get("text"))
        pid, _ = ids()
        log.note(f"windows {[w['title'] for w in cua('list_windows', {'pid': pid}).get('windows', [])]}")
        shot("tc-14-15-after.png")


go(f"tc-14-15-{PHASE}", body)
