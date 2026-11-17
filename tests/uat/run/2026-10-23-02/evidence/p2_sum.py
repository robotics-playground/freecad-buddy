"""Print p0_call.py output lines (stdin) one per call: tool, status, then the structured content or text, cut to N chars.
    ... | p2_sum.py [N]"""
import json
import sys

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 700
for line in sys.stdin:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        print(line.rstrip()[:300])
        continue
    result = record["result"]
    args = {k: v for k, v in record["args"].items() if k not in ("doc",)}
    body = result.get("structured_content")
    shown = json.dumps(body, ensure_ascii=False) if body not in (None, {}) else result.get("text")
    detail = result.get("detail")
    message = detail.get("message") if isinstance(detail, dict) else None
    print(f"== {record['mcp']} {json.dumps(args, ensure_ascii=False)[:300]}")
    print(f"   status={result.get('status')} is_error={result.get('is_error')} message={message}")
    print(f"   {str(shown)[:limit]}")
