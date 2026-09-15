"""Drive the committed G3 plans through the Phase 4 design payload and record the rate.

**What this measures, and what it does not.** G4.1 reads "run the 20-spec Phase 3 benchmark via
job API". That benchmark has two halves: an ACTOR that turns spec text into a plan, and a LOOP
that executes the plan and grades the result. Only the loop exists in code — `benchmarks/runner.py`
says so directly ("no designer actor ... nothing translates a spec into a plan"), and the 20 plans
under `actor-plans/` are committed output from an offline generator.

So this carries PLANS through the service, not SPECS. It measures the loop end to end through the
Phase 4 payload: document creation, per-step preview-token approval, mutation, grading. It is not
G4.1, and the artifact it writes says so in its own text rather than leaving a bare rate for a
reader to mistake for one.

Geometry and visual are recorded as two rates. The visual leg is unavailable wherever no judge
backend and no GUI exist, so a single "converged" number would report every geometry-passing part
as a failure and make the geometry result unmeasurable.

Run under FreeCADCmd, which is where FreeCAD is importable:

    FreeCADCmd benchmarks/g4/run_parity.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
_SEARCH_PATHS = (
    REPO_ROOT / "src",
    REPO_ROOT / "benchmarks",
    REPO_ROOT / "benchmarks" / "g3",
    REPO_ROOT,
)
for path in _SEARCH_PATHS:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import yaml  # noqa: E402

DEV_DIR = REPO_ROOT / "benchmarks" / "g3" / "dev"
PLANS_DIR = REPO_ROOT / "benchmarks" / "g3" / "actor-plans"
RESULT_FILE = HERE / "parity-results.json"

# What this run measured, carried INTO the artifact so the number never travels without it.
SCOPE = (
    "Committed plans driven through the Phase 4 design payload. This measures the designer LOOP "
    "through the job service, not the G4.1 criterion: G4.1 requires the 20-SPEC benchmark, and no "
    "spec-to-plan translator exists (benchmarks/runner.py). The actor half is absent, so its "
    "contribution to the rate is neither measured nor claimed here."
)

VISUAL_SCOPE = (
    "The visual leg is unavailable in this environment: no vision backend and no GUI under "
    "FreeCADCmd, and on this branch no part exposes driving parameters, so the judge drawing "
    "refuses. visual_pass is 0 by construction and convergence is therefore 0. The geometry rate "
    "is the measurable half and is reported separately for that reason."
)


def grader(document, checks, anchor_frame=None):
    """The deterministic geometry grader, reached through the benchmark harness."""
    from harness import assertions

    return assertions.evaluate(document, checks, anchor_frame)


def visual_leg(registry, spec_text: str):
    """The visual half, bound the way the G3 actor run binds it.

    Fails closed with ``visual.unavailable`` wherever no judge answers — which is the correct
    answer here, not a bypass.
    """
    from actor_run import make_visual_leg

    return make_visual_leg(registry, spec_text)


def _cases() -> list[tuple[str, dict, dict]]:
    """Every dev case that has a committed plan, as ``(spec_id, case, plan)``."""
    found = []
    for plan_path in sorted(PLANS_DIR.glob("*.json")):
        spec_id = plan_path.stem
        case_path = DEV_DIR / spec_id / "case.yaml"
        if not case_path.is_file():
            continue
        case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        found.append((spec_id, case, plan))
    return found


def run_one(spec_id: str, case: dict, plan: dict) -> dict:
    """Run one case through the design payload and return its row."""
    from freecad_buddy.hosts.phase4 import designer_payload

    assertions_block = case.get("assertions") or {}
    spec = {
        "schema": "fcb.job-spec/1",
        "job_id": f"parity-{spec_id}",
        "kind": "design",
        "payload": {
            "spec_id": spec_id,
            "plan": plan,
            "checks": assertions_block.get("checks"),
            "anchor_frame": assertions_block.get("anchor_frame"),
            "spec_text": case.get("spec", ""),
            "grader_module": __name__,
            "visual_module": __name__,
        },
    }
    started = time.monotonic()
    try:
        envelope = designer_payload.run_design(spec)
    except Exception as exc:  # noqa: BLE001 - a raised payload is a failed row, never a crash here
        return {
            "spec_id": spec_id,
            "geometry_pass": False,
            "visual_pass": False,
            "converged": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": round(time.monotonic() - started, 2),
        }
    content = envelope["structured_content"]
    return {
        "spec_id": spec_id,
        "geometry_pass": bool(content["geometry_pass"]),
        "visual_pass": bool(content["visual_pass"]),
        "converged": bool(content["converged"]),
        "repairs_used": content.get("repairs_used"),
        "elapsed_s": round(content.get("elapsed_s", 0.0), 2),
    }


def main() -> int:
    """Run every case, write the artifact, and print the two rates."""
    cases = _cases()
    if not cases:
        sys.stderr.write("no committed plans found; nothing to measure\n")
        return 1

    rows = []
    for index, (spec_id, case, plan) in enumerate(cases, start=1):
        row = run_one(spec_id, case, plan)
        rows.append(row)
        sys.stderr.write(
            f"  [{index:2d}/{len(cases)}] {spec_id:34s} geometry={row['geometry_pass']!s:5s} "
            f"visual={row['visual_pass']!s:5s} {row['elapsed_s']:6.2f}s"
            f"{'  ' + row['error'] if row.get('error') else ''}\n"
        )

    total = len(rows)
    geometry = sum(1 for r in rows if r["geometry_pass"])
    visual = sum(1 for r in rows if r["visual_pass"])
    converged = sum(1 for r in rows if r["converged"])

    artifact = {
        "schema": "fcb.g4-parity/1",
        "scope": SCOPE,
        "visual_scope": VISUAL_SCOPE,
        "total": total,
        "geometry_pass": geometry,
        "visual_pass": visual,
        "converged": converged,
        "geometry_rate": round(geometry / total, 4) if total else 0.0,
        "converged_rate": round(converged / total, 4) if total else 0.0,
        "rows": rows,
    }
    RESULT_FILE.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    sys.stderr.write(
        f"\n  planned {total}  geometry_pass {geometry}  visual_pass {visual}  "
        f"converged {converged}\n  wrote {RESULT_FILE}\n"
    )
    return 0


def _is_top_level_script() -> bool:
    """Whether this file was invoked as the script, under either interpreter.

    ``FreeCADCmd script.py`` does NOT set ``__name__`` to ``"__main__"``, so the usual guard
    never fires and the script exits silently having done nothing. ``tests/run_tests.py`` carries
    the same check for the same reason.
    """
    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
    return False


if _is_top_level_script():
    sys.exit(main())
