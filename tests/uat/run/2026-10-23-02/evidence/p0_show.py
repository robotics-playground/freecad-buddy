"""Print step results of one runner scenario from runner/results.json: p0_show.py <id> [step ...]."""
import json
import sys
from pathlib import Path

results = json.loads((Path(__file__).resolve().parents[1] / "runner" / "results.json").read_text(encoding="utf-8"))
record = next(s for s in results["scenarios"] if s["id"] == sys.argv[1])
for step in record["steps"]:
    if len(sys.argv) > 2 and step.get("name") not in sys.argv[2:]:
        continue
    print(json.dumps(step, ensure_ascii=False)[:3000])
