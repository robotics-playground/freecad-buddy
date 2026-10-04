"""Append/replace one row in tc-01-rerun-results.json. Usage: tc01r_res.py <id> <priority> <verdict> <ev1,ev2> <note>"""
import json, sys
from pathlib import Path
p = Path(__file__).resolve().parent / "tc-01-rerun-results.json"
rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
i, pr, v, ev, note = sys.argv[1:6]
rows = [r for r in rows if r["id"] != i] + [{"id": i, "priority": pr, "verdict": v, "evidence": [e for e in ev.split(",") if e], "note": note}]
rows.sort(key=lambda r: r["id"])
p.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(i, v)
