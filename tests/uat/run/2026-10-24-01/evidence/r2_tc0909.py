"""TC-09-09 steps for phase R2: r2_tc0909.py given | when <H> | cap | close <doc> ...

given: document_create TC0909Scratch, then document_open box-10-20-30 as <H> (printed).
when:  the three oversized calls, document_list, query_capabilities; CHECK lines for the Thens.
"""
import json
import sys

from r2_p5_lib import Run5

GOLDEN = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"
EVIDENCE = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-24-01/evidence"


def out(label, value):
    print(f"CHECK {label}: {json.dumps(value, ensure_ascii=False)[:1200]}")


def message(result):
    detail = result.get("detail")
    return detail.get("message") if isinstance(detail, dict) else None


def main():
    step = sys.argv[1]
    with Run5("tc-09-09", limit=400) as run:
        if step == "given":
            s = run.call("document_create", {"label": "TC0909Scratch"}, "given scratch")
            h = run.call("document_open", {"path": GOLDEN}, "given open H")
            print("SCRATCH", (s.get("structured_content") or {}).get("doc"), "H", (h.get("structured_content") or {}).get("doc"))
        elif step == "when":
            handle = sys.argv[2]
            created = run.call("document_create", {"label": "a" * 4096}, "when label 4096")
            out("label 4096 status", created.get("status"))
            listed = run.call("document_list", {}, "then document_list")
            labels = [d.get("label") or "" for d in (listed.get("structured_content") or {}).get("documents", [])]
            out("document_list label lengths", [len(x) for x in labels])
            opened = run.call("document_open", {"path": f"{EVIDENCE}/tc-09-09-{'b' * 8192}.FCStd"}, "when path 8192")
            msg = message(opened) or ""
            out("path 8192 status / message head / names path", [opened.get("status"), msg[:160], ("b" * 200) in msg, len(msg)])
            queried = run.call("query_object", {"doc": handle, "object": "c" * 65536}, "when object 65536")
            msg = message(queried) or ""
            data = (queried.get("detail") or {}).get("data") or {}
            out("object 65536 status / message head / length", [queried.get("status"), msg[:40], len(msg)])
            out("traceback length", len(data.get("traceback") or ""))
            caps = run.call("query_capabilities", {}, "then query_capabilities")
            out("query_capabilities status", caps.get("status"))
            print("LONGDOC", (created.get("structured_content") or {}).get("doc"))
        elif step == "close":
            for doc in sys.argv[2:]:
                run.call("document_close", {"doc": doc}, "cleanup close")


main()
