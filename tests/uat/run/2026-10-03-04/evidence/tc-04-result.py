"""Append or replace one scenario record in tc-04-results.json: id priority verdict note file..."""
import json
import sys
from pathlib import Path

path = Path(__file__).resolve().parent / "tc-04-results.json"
rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
sid, priority, verdict, note, *files = sys.argv[1:]
rows = [r for r in rows if r["id"] != sid] + [{"id": sid, "priority": priority, "verdict": verdict, "evidence": files, "note": note}]
rows.sort(key=lambda r: r["id"])
path.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
print(sid, verdict)
