import subprocess

from tc09lib import *  # noqa

CMD = r'''cd "D:/Work/Personal/Sources/freecad-buddy"; E=tests/uat/run/2026-10-03-04/evidence; {
echo "## When 1: status vocabulary"; python -c "import re;print(re.findall(r'\"(\w+)\"', open('src/freecad_buddy/contracts/status.py').read()))"
echo "## When 2: observed statuses"; python -c "import json;r=json.load(open('$E/tc-09-01-edge_report.json'));print(sorted({c.get('status') for c in r['checks']}))"
echo "## When 3: check_status_vocab"; uv run python scripts/check_status_vocab.py; echo "exit=$?"
echo "## near-miss grep"; grep -rnE "INVALID_ARGUMENT|VALIDATION_ERROR|BAD_INPUT|RECOMPUTE_FAILED|SPEC_FAIL\b" src/freecad_buddy/; echo "grep_exit=$?"
echo "## OOM_KILLED / WORKER_CRASHED emitters"; grep -rnE "OOM_KILLED|WORKER_CRASHED" src/freecad_buddy/ --include=*.py
echo "## rpc_dispatch boundary"; grep -nE "def dispatch|except |return _error_envelope" src/freecad_buddy/adapters/rpc_dispatch.py
} > $E/tc-09-02-when.txt 2>&1'''


async def body(m, log):
    await close_all(m, log)
    doc, op = await open_shown(m, log)
    log.check("Given document_open box-10-20-30 OK", op.get("status") == "OK", doc)
    await frame_shot(m, doc, "tc-09-02-before.png")
    p = subprocess.run(["C:/Program Files/Git/bin/bash.exe", "-c", CMD], capture_output=True, text=True)
    log.write({"when_exit": p.returncode, "out": open(EV + "/tc-09-02-when.txt", encoding="utf-8").read()})
    await frame_shot(m, doc, "tc-09-02-after.png")
    print("DOC", doc)


go("tc-09-02", body)
