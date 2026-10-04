"""Upsert one scenario row into tc-99-results.json and rewrite the file.

usage: tc-99-results-add.py <row.json>
"""
import json, sys
from pathlib import Path

path = Path(__file__).resolve().parent / "tc-99-results.json"
rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
row = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = [r for r in rows if r["id"] != row["id"]] + [row]
rows.sort(key=lambda r: r["id"])
path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(rows)} rows; {row['id']} = {row['verdict']}")
