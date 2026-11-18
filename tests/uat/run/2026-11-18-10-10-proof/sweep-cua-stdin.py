"""R2 sweep: a `"$FCB_CUA" <tool>` call with no JSON on standard input.

A tool call reads its JSON from stdin, so each one must follow `echo '<json>' |`. `status`, `doctor`,
`list-tools` and `describe` take no stdin. Looks at every code span and every fenced line of
tests/uat/testcases (and test-plan.md, APPENDIX-B). Exit 1 when a call has no `echo ... |` before it.
"""

import glob
import os
import re
import sys

CALL = re.compile(r'"\$FCB_CUA" (?!status\b|doctor\b|list-tools\b|describe\b)([a-z_]+)')
files = sorted(glob.glob("tests/uat/testcases/TC-*.md")) + [
    "tests/uat/test-plan.md",
    "tests/uat/APPENDIX-B-environment-setup.md",
]
hits = []
for path in files:
    fence = False
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle.read().split("\n"), 1):
            if line.startswith("```"):
                fence = not fence
                continue
            for span in [line] if fence else line.split("`")[1::2]:
                for match in CALL.finditer(span):
                    if not re.search(r"echo '[^']*' \| *$", span[: match.start()]):
                        hits.append(f"{os.path.basename(path)}:{number}: {span[:140]}")
print(f"calls without stdin: {len(hits)}")
for hit in hits:
    print(hit)
sys.exit(1 if hits else 0)
