"""Print a markdown verdict table for one TC from evidence/tc-NN-results.json."""
import json, sys
n = sys.argv[1]
rows = [r for r in json.load(open(f"tc-{n}-results.json", encoding="utf-8")) if r.get("id", "").count("-") == 2]
print("| Scenario | Priority | Verdict | Evidence | Note |\n| --- | --- | --- | --- | --- |")
for r in rows:
    ev = ", ".join(f"`{e}`" for e in (r.get("evidence") or [])[:3])
    note = " ".join(str(r.get("note", "")).split())
    if len(note) > 400:
        note = note[:397] + "..."
    print(f"| {r['id']} | {r.get('priority','')} | **{r['verdict'].split()[0]}** | {ev} | {note.replace('|','/')} |")
