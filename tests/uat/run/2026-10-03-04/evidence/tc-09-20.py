import os
import shutil
import subprocess

from tc09lib import *  # noqa
from tc08h1 import h1

APP = EV + "/tc-09-20-append.jsonl"


async def body(m, log):
    if os.path.exists(APP):
        os.remove(APP)
    log.check("Given fresh writable audit target", not os.path.exists(APP), APP)
    doc, obj = await scene(m, log, "tc-09-20")
    async with h1(log, "h1-append", EV + "/tc-09-20-h1.stderr.log", extra={"FREECAD_BUDDY_AUDIT_LOG": APP}) as s:
        a = await s.call("document_create", {"label": "TC0920A"})
        shutil.copy(APP, EV + "/tc-09-20-snap_1.jsonl")
        b = await s.call("document_create", {"label": "TC0920B"})
        shutil.copy(APP, EV + "/tc-09-20-snap_2.jsonl")
        c = await s.call("document_close", {"doc": sc(a).get("doc")})
        shutil.copy(APP, EV + "/tc-09-20-snap_3.jsonl")
    log.note(f"three mutations: {status(a)} {status(b)} {status(c)}")
    t = [open(EV + f"/tc-09-20-snap_{i}.jsonl", encoding="utf-8").read() for i in (1, 2, 3)]
    log.check("compare prints True True True", (t[1].startswith(t[0]), t[2].startswith(t[1]), len(t[0]) < len(t[1]) < len(t[2])) == (True, True, True),
              (t[1].startswith(t[0]), t[2].startswith(t[1]), [len(x) for x in t]))
    n1 = len(t[0].splitlines())
    log.check("no earlier line rewritten: head -n len(snap1) of snap3 == snap1", t[2].splitlines()[:n1] == t[0].splitlines(), n1)
    sizes = [os.path.getsize(EV + f"/tc-09-20-snap_{i}.jsonl") for i in (1, 2, 3)]
    log.check("byte counts strictly increasing", sizes[0] < sizes[1] < sizes[2], sizes)
    recs = [json.loads(ln) for ln in open(APP, encoding="utf-8")]
    log.check("every line complete JSON", True, len(recs))
    log.check("every schema == fcb.audit-record/1", all(r.get("schema") == "fcb.audit-record/1" for r in recs), sorted({r.get("schema") for r in recs}))
    after = [r for r in recs if "verify_verdict" in r]
    before = [r for r in recs if "verify_verdict" not in r]
    log.check("lines >= 2x mutations; after lines carry verify_verdict, before lines do not", len(recs) >= 6 and len(after) == 3 and len(before) == 3,
              {"lines": len(recs), "after": len(after), "before": len(before)})
    g = subprocess.run(["C:/Program Files/Git/bin/bash.exe", "-c",
                        f'cd "{PROJECT}"; grep -nE "\\"w\\"|truncate|rotate|os.remove" src/freecad_buddy/adapters/audit_log.py; echo "exit=$?"; '
                        f'grep -n "open(" src/freecad_buddy/adapters/audit_log.py'], capture_output=True, text=True).stdout
    (EVIDENCE / "tc-09-20-grep.txt").write_text(g, encoding="utf-8")
    log.check("grep for \"w\"|truncate|rotate|os.remove returns nothing", "exit=1" in g, g.strip())
    log.check("only open mode is 'a' at audit_log.py:46", '46:            with open(self._path, "a"' in g and g.count("open(") == 1, g.strip())
    await frame_shot(m, doc, "tc-09-20-after.png")


go("tc-09-20", body)
