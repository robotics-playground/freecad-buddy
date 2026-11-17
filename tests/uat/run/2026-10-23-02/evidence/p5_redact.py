"""Cut every preview_id value in the given JSONL files to its first 16 characters, in place:
p5_redact.py <file> [...]. p0_h1.py logs raw results; the run keeps no whole token."""
import re
import sys

PATTERN = re.compile(r'("preview_id": ")(fcb-preview:[^"]{0,4})[^"]*(")')
for name in sys.argv[1:]:
    with open(name, encoding="utf-8") as handle:
        text = handle.read()
    redacted, count = PATTERN.subn(lambda m: m.group(1) + m.group(2) + "...(redacted)" + m.group(3), text)
    with open(name, "w", encoding="utf-8") as handle:
        handle.write(redacted)
    print(name, count, "preview_id value(s) redacted")
