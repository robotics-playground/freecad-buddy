"""Print each step of runner scenarios from runner/results.json, one line each: r0_steps.py <width> <id> [<id> ...]."""
import json
import sys
from pathlib import Path

results = json.loads((Path(__file__).resolve().parents[1] / "runner" / "results.json").read_text(encoding="utf-8"))
scenarios = {s["id"]: s for s in results["scenarios"]}
width = int(sys.argv[1])
for scenario_id in sys.argv[2:]:
    print("=====", scenario_id)
    for index, step in enumerate(scenarios[scenario_id]["steps"], 1):
        result = step.get("result")
        if isinstance(result, dict) and isinstance(result.get("detail"), dict):
            result = dict(result)
            detail = dict(result["detail"])
            detail.pop("data", None)
            result["detail"] = detail
        print(index, step.get("name"), step.get("mcp") or step.get("menu"),
              json.dumps(step.get("args"), ensure_ascii=False)[:width], "->",
              json.dumps(result, ensure_ascii=False)[:width])
