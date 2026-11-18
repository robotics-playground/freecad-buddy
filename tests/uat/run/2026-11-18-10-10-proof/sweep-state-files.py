"""D3 sweep: a command that names a FreeCAD-state file or folder but does not run in the container.

Looks at every code span (backticks) and every fenced line of tests/uat/testcases for a shell command
word (grep, cat, ls, tail, head, wc, find, stat, test, mv, rm, sed, diff, tee, sha256sum) together with a
state name (addon.log, mcp-proxy.log, rpc-, user.cfg, system.cfg, FCB_TMP, freecad-buddy/, workdir,
audit.jsonl, FCB_USER_DIR, FCB_CONFIG_DIR, /tmp). A span that holds `docker exec`, `fcb-py`,
`$FCB_PYTHON`, `script_exec` or `mcp ` runs in the container (or through the bridge) and is fine.
A span under `$RUN_DIR` is a run-folder file that the host reads. Usage: python sweep-state-files.py [testcases-dir]. Prints each remaining hit as file:line: span; exit 1 when there is one.
"""

import glob
import os
import re
import sys

COMMAND = re.compile(
    r"(?<![\w-])(grep|cat|ls|tail|head|wc|find|stat|test|mv|rm|sed|diff|tee|sha256sum)\b"
)
STATE = re.compile(
    r"addon\.log|mcp-proxy\.log|rpc-[<*\w]|user\.cfg|system\.cfg|FCB_TMP|freecad-buddy/|workdir"
    r"|audit\.jsonl|FCB_USER_DIR|FCB_CONFIG_DIR|(?<![\w.])/tmp"
)
INSIDE = re.compile(r"docker exec|fcb-py|\$FCB_PYTHON|script_exec|mcp |\"\$FCB_CUA\"")
hits = []
folder = sys.argv[1] if len(sys.argv) > 1 else "tests/uat/testcases"
for path in sorted(glob.glob(f"{folder}/TC-*.md")):
    fence = False
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle.read().split("\n"), 1):
            if line.startswith("```"):
                fence = not fence
                continue
            spans = [line] if fence else line.split("`")[1::2]
            for span in spans:
                if ("$RUN_DIR" in span and "FCB_USER_DIR" not in span) or " src/" in span:
                    continue  # a run-folder file (the host reads it) or a source grep
                if COMMAND.search(span) and STATE.search(span) and not INSIDE.search(span):
                    hits.append(f"{os.path.basename(path)}:{number}: {span[:160]}")
print(f"hits: {len(hits)}")
for hit in hits:
    print(hit)
sys.exit(1 if hits else 0)
