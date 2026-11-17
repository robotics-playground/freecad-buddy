"""Append one H1 launch line to launch-log.tsv: r2_h1log.py <tag> <start> <end> <home> <env text>.
Tabs separate the six columns (phase, start, pid, profile, env, end); lines end CRLF like the
lines r2_launch.ps1 writes."""
import sys
from pathlib import Path

tag, start, end, home, env = sys.argv[1:6]
line = "\t".join([f"R2 H1 {tag}", start, "H1 worker (r2_h1.py stdio child; pid not recorded)",
                  f"FREECAD_USER_HOME={home} (in-process import FreeCAD; no -u/-s)",
                  rf"FCB_ENV scratchpad\rerun\fcbenv\fcb; {env} (all other FREECAD_BUDDY_* removed)", end])
log = Path(__file__).resolve().parent / "launch-log.tsv"
with log.open("ab") as handle:
    handle.write(line.encode("utf-8") + b"\r\n")
print(line)
