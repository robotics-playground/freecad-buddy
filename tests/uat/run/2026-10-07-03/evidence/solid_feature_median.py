"""Calls-per-feature median that counts only solid features, plus the FreeCAD tool mix.

Same rule as ``scripts/automation/session_metrics.py``, except that ``feature_body_create`` and
``feature_datum`` are not features. Run from the repo root in the uv env::

    uv run python tests/uat/run/2026-10-07-03/evidence/solid_feature_median.py <transcript.jsonl>[:<max results>] ...
"""

import collections
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts" / "automation"))

from replay_result_sizes import _argument  # noqa: E402
from session_metrics import _TOOL_PREFIX, _status, _text  # noqa: E402

NOT_SOLID = {"feature_set_parameters", "feature_body_create", "feature_datum"}

for spec in sys.argv[1:]:
    path, limit = _argument(spec)
    tool_names = {}
    calls = 0
    previous = None
    samples = []
    tools = collections.Counter()
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if limit is not None and calls >= limit:
                break
            record = json.loads(line)
            if record.get("isSidechain"):
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if limit is not None and calls >= limit:
                    break
                if item.get("type") == "tool_use":
                    tool_names[item["id"]] = item["name"]
                    continue
                name = tool_names.get(item.get("tool_use_id"), "")
                if item.get("type") != "tool_result" or not name.startswith(_TOOL_PREFIX):
                    continue
                calls += 1
                tool = name[len(_TOOL_PREFIX) :]
                tools[tool] += 1
                is_solid = tool.startswith("feature_") and tool not in NOT_SOLID
                if is_solid and _status(_text(item.get("content"))) == "OK":
                    if previous is not None:
                        samples.append(calls - previous)
                    previous = calls
    median = statistics.median(samples) if samples else None
    print(f"{path.stem[:8]}: solid-feature median {median} over {len(samples)} features")
    print("  tools:", ", ".join(f"{tool} {count}" for tool, count in tools.most_common()))
