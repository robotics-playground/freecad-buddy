"""CI helper (FreeCAD-free): emit one G0.4 matrix-leg evidence file.

Each headless CI leg calls this to write ``evidence/G0.4.<leg>.json`` carrying that leg's
green boolean + test count. The runner's ``_ingest_g0_4`` requires BOTH pinned roster legs
(1.0.x, 1.1.x) present ∧ green ∧ >=30 tests; a single present green leg never greens G0.4.

Usage: ``python benchmarks/g0/emit_ci_evidence.py --run <id> --leg 1.1.x --green true \
        --tests 42``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BENCHMARKS_ROOT = Path(__file__).resolve().parents[1]


def _run_dir(run_id: str) -> Path:
    return BENCHMARKS_ROOT / "gate-artifacts" / "g0" / run_id


def emit(run_id: str, leg: str, green: bool, tests: int) -> Path:
    """Write ``evidence/G0.4.<leg>.json`` atomically into the run dir; return its path."""
    evidence_dir = _run_dir(run_id) / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"G0.4.{leg}.json"
    payload = {"leg": leg, "green": green, "test_count": tests}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emit_ci_evidence.py")
    parser.add_argument("--run", dest="run_id", required=True)
    parser.add_argument("--leg", required=True, help="matrix leg id, e.g. 1.1.x")
    parser.add_argument("--green", required=True, help="true/false")
    parser.add_argument("--tests", type=int, required=True, help="test count for this leg")
    args = parser.parse_args(argv)

    green = args.green.strip().lower() == "true"
    path = emit(args.run_id, args.leg, green, args.tests)
    sys.stderr.write(f"emit_ci_evidence: wrote {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
