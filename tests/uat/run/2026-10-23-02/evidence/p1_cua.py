"""One cua-driver call with its JSON on stdin: p1_cua.py <tool> '<json>' [--elements [<text>]].

Prints the answer. With --elements it prints one line per element (token, role, enabled, label,
frame) instead, filtered to labels containing <text> when given.
"""

import json
import subprocess
import sys

tool, payload = sys.argv[1], json.loads(sys.argv[2])
completed = subprocess.run(["cua-driver", "call", tool], input=json.dumps(payload),
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
if "--elements" not in sys.argv:
    print(completed.stdout[:6000], completed.stderr[:2000], f"exit={completed.returncode}")
    sys.exit(0)
needle = sys.argv[sys.argv.index("--elements") + 1].lower() if len(sys.argv) > sys.argv.index("--elements") + 1 else ""
answer = json.loads(completed.stdout)
for element in answer.get("elements", []):
    label = element.get("label") or ""
    if needle in label.lower():
        print(element.get("element_token"), element.get("role"), element.get("enabled"), repr(label)[:100], element.get("frame"))
print({k: v for k, v in answer.items() if k not in ("elements", "tree_markdown")})
