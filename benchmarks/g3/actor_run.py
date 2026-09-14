"""Drive the 20 G3 actor plans through the designer loop and record what each one reached.

Runs under ``FreeCADCmd`` because the loop writes real geometry through the Phase-2 mutation
surface:

.. code-block:: powershell

    $FCB = "$env:USERPROFILE\\micromamba\\envs\\fcb"
    $env:PYTHONPATH = "$FCB\\Library\\bin;$FCB\\Library\\lib"
    & "$FCB\\Library\\bin\\FreeCADCmd.exe" "benchmarks\\g3\\actor_run.py"

Three things are wired here and nowhere else:

**The real grader.** ``benchmarks.harness.assertions.evaluate`` measures the produced document
against the case's own compiled checks. The plans were authored from each case's ``spec:`` prose
alone, so the grader is independent of what it grades (AD-13/AD-19).

**The real visual leg.** ``usecases.verify_visual`` bound to the shipped ports and the
``benchmarks/g3/judge.StubJudge``. There is no vision backend, so the leg returns
``visual.unavailable`` and NO part can converge — ``CONVERGENCE_RULE`` is geometry AND visual, and
weakening the conjunction to make parts converge is the exact defect G3.4 exists to catch. The
geometry leg is therefore reported separately per spec so it stays measurable.

**A repair that reads the measurement.** :func:`make_repairer` maps each ``Discrepancy``'s
``measured``-vs-``expected`` pair onto the plan step that produced it, then returns a plan that
EDITS that feature's driving property by the measured difference. It cannot return the build plan
with one number changed: the loop re-executes against the same document, so a rebuild is refused at
its first step and the correction never reaches the geometry. A repairer that re-emitted the same
plan would spend the cap and measure nothing, so one that cannot map a discrepancy returns ``None``
and ends the run at the iteration reached.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
for _extra in (str(REPO_ROOT), str(REPO_ROOT / "src"), str(HERE)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

PLANS_DIR = HERE / "actor-plans"
DEV_DIR = HERE / "dev"
RESULTS = HERE / "actor-results.json"

# How close a measured value must be to the expected one before the repair treats the step as
# already correct. Well under the tightest tolerance any dimensional check carries, so a repair
# never declares a step done that the grader still rejects.
_SETTLED_MM = 1e-6


# ----------------------------------------------------------------------------------------------
# Cases
# ----------------------------------------------------------------------------------------------


def load_case(spec_id: str) -> tuple[list, dict | None]:
    """The case's compiled checks and declared anchor frame.

    The checks are handed straight to the grader and never read by the planning side of this
    module: the plans were authored from the spec prose, and this driver only executes them.
    """
    import yaml

    data = yaml.safe_load((DEV_DIR / spec_id / "case.yaml").read_text(encoding="utf-8"))
    assertions = data.get("assertions") or {}
    return list(assertions.get("checks") or []), assertions.get("anchor_frame")


def load_plans() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(PLANS_DIR.glob("*.json"))
    ]


def checklist_for(spec_text: str) -> list[str]:
    """One checklist entry per sentence of the spec.

    The judge measures the images against this rather than against its own idea of the part, and
    the spec's own sentences are the requirement list the human wrote.
    """
    entries = [part.strip() for part in spec_text.replace("\n", " ").split(".") if part.strip()]
    return entries or [spec_text.strip()]


# ----------------------------------------------------------------------------------------------
# The repair
# ----------------------------------------------------------------------------------------------

# Which plan-step argument a failing check may correct, and the FreeCAD property on the built
# feature that argument drove. A discrepancy names what the artifact measures against what the spec
# asked for; this maps that onto the one value that produced it. A check id absent here is one this
# repairer cannot act on, and it says so rather than guessing.
_REPAIRABLE = {
    "assert.hole_diameter": (("diameter", "Diameter"), ("cut_diameter", "HoleCutDiameter")),
    "assert.expect_extent": (("length", "Length"),),
    "assert.expect_bbox": (("length", "Length"),),
}


def _quantity_steps(plan: dict, argument: str) -> list[tuple[int, dict]]:
    """Every step carrying ``argument`` as a ``{value, unit}`` quantity, with its index."""
    found = []
    for index, step in enumerate(plan.get("steps") or []):
        value = (step.get("args") or {}).get(argument)
        if isinstance(value, dict) and "value" in value:
            found.append((index, step))
    return found


def _one_number(value: object) -> float | None:
    """``value`` as a single float, collapsing a per-feature list that agrees on one value.

    A per-feature primitive reports one measurement per logical hole — ``hole_diameter`` on the
    four-hole mounting plate measures ``[8.0, 8.0, 8.0, 8.0]``. One plan argument drove all four,
    so when they agree the list IS one value and the repair can act on it. When they disagree,
    they came from different steps and no single argument correction is right.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and value:
        numbers = [item for item in value if isinstance(item, (int, float))]
        if len(numbers) == len(value) and len(set(numbers)) == 1:
            return float(numbers[0])
    return None


def _scaled(entry: dict) -> tuple[float, float] | None:
    """The ``(measured, expected)`` pair as floats, or ``None`` when either is not a single value.

    A discrepancy that carries no single value a dimensional argument could be set to — a count, a
    boolean, a set of positions that disagree — is not repairable by this rule, and the repairer
    says so rather than guessing.
    """
    measured = _one_number(entry.get("measured"))
    expected = _one_number(entry.get("expected"))
    if measured is None or expected is None:
        return None
    return measured, expected


def _repair_step_value(plan: dict, entry: dict) -> tuple[dict, str] | None:
    """A plan that EDITS the offending feature's driving property to the measured correction.

    The repaired plan is a single ``feature_set_parameters`` step, not the original plan with one
    number changed. The loop re-executes whatever plan it is given against the SAME document, and
    that document already holds the first attempt's objects — a re-emitted build plan is refused at
    its first step (``an object named Body already exists``) and rebuilds nothing, so the corrected
    value never reaches the geometry. Editing the built feature is also what the spec's driving
    dimensions are exposed as named parameters FOR.

    The correction is driven by the MEASURED value: the property is moved by exactly the
    measured-to-expected difference, so a hole that came out 8.0 against an expected 5.5 is set to
    ``its current value - 2.5`` rather than re-emitted unchanged.
    """
    pair = _scaled(entry)
    if pair is None:
        return None
    measured, expected = pair
    if abs(measured - expected) <= _SETTLED_MM:
        return None
    delta = expected - measured

    for argument, prop in _REPAIRABLE.get(entry.get("check_id", ""), ()):
        candidates = _quantity_steps(plan, argument)
        if len(candidates) != 1:
            # Two steps carry this argument, so the measurement does not say which one is wrong.
            # Guessing would move correct geometry, so this discrepancy is left unrepaired.
            continue
        index, step = candidates[0]
        feature = (step.get("args") or {}).get("name")
        if not feature:
            continue
        current = float(step["args"][argument]["value"])
        corrected = round(current + delta, 9)
        if corrected <= 0.0:
            return None
        note = (
            f"{entry['check_id']}: measured {measured}, expected {expected}; "
            f"{feature}.{prop} {current} -> {corrected}"
        )
        # ONLY the edit. The loop executes every step of whatever plan it is handed and stops at
        # the first that does not report OK, so carrying the build steps forward would refuse at
        # step 0 and the edit would never be reached.
        edit = {
            "tool": "feature_set_parameters",
            "args": {
                "feature": feature,
                "parameters": {prop: {"value": corrected, "unit": "mm"}},
            },
            "intent": note,
        }
        return dict(plan, steps=[edit]), note
    return None


def make_repairer(record: dict, build_plan: dict):
    """A ``Repairer`` that corrects the built part's driving values from the measured discrepancy.

    Every correction is located against ``build_plan`` — the original plan, whose steps still name
    the features and the arguments that drove them. The plan the loop hands back on a repair
    iteration is a one-step edit, so searching THAT for a ``diameter`` argument would find nothing
    from the second repair onwards.

    Returns ``None`` when no discrepancy maps onto a driving value. That is the honest answer: the
    loop then ends at the iteration it reached rather than spending the remaining cap re-running a
    plan nothing changed in. A correction already applied and still measuring wrong also returns
    ``None`` — re-sending the same value would burn the cap without moving the geometry.

    ``record`` collects each repair's note so the result row shows what the loop actually did.
    """
    applied: set[str] = set()

    def repair(_plan, discrepancy, _judge_findings):
        for entry in discrepancy:
            proposal = _repair_step_value(build_plan, entry)
            if proposal is None:
                continue
            repaired, note = proposal
            if note in applied:
                continue
            applied.add(note)
            record.setdefault("repairs", []).append(note)
            return dict(repaired, rationale=note)
        return None

    return repair


# ----------------------------------------------------------------------------------------------
# The visual leg
# ----------------------------------------------------------------------------------------------


class _JudgeAdapter:
    """The 4.1 ``StubJudge`` in the ``JudgeClient`` shape ``verify_visual`` injects.

    The stub predates the port's ``available``/``judge(visual_set)`` signature; adapting it here
    keeps the fail-closed answer intact and changes no seam code. Story 4.4 replaces the whole
    thing with a real vision client.
    """

    def __init__(self, stub):
        self._stub = stub

    def available(self) -> tuple[bool, str | None]:
        return False, self._stub.reason

    def judge(self, visual_set):
        return self._stub.judge(visual_set, "", [])


def make_visual_leg(registry, spec_text: str):
    """Bind the shipped ``verify_visual`` into the loop's ``VisualLeg`` shape.

    This is the production wiring: the ports and the judge are bound once and the loop supplies
    only what varies per iteration. Under ``FreeCADCmd`` there is no GUI, so the render port
    reports unavailable and the leg fails closed with ``visual.unavailable`` — which is the
    correct answer, not a bypass.
    """
    from judge import StubJudge

    from freecad_buddy.adapters.render_probe import OffscreenRenderPort, QtSvgRasterPort
    from freecad_buddy.usecases.verify_visual import verify_visual

    render_port = OffscreenRenderPort()
    raster_port = QtSvgRasterPort()
    judge_client = _JudgeAdapter(StubJudge())
    checklist = checklist_for(spec_text)

    def leg(doc, geometry_passed):
        try:
            envelope = verify_visual(
                registry,
                render_port,
                raster_port,
                judge_client,
                spec_text,
                checklist,
                doc=doc,
                geometry_passed=geometry_passed,
            )
            return envelope["structured_content"]["checks"][0]
        except Exception as exc:  # noqa: BLE001 - an unreachable leg is not-done, never a pass
            from freecad_buddy.contracts import VISUAL_CHECK_ID, VISUAL_UNAVAILABLE_CODE

            return {
                "id": VISUAL_CHECK_ID,
                "measured": None,
                "measured_kind": None,
                "expected": True,
                "tolerance": None,
                "passed": False,
                "detail": {
                    "code": VISUAL_UNAVAILABLE_CODE,
                    "message": f"the visual leg raised {type(exc).__name__}: {exc}",
                    "objects": [],
                },
            }

    return leg


# ----------------------------------------------------------------------------------------------
# The run
# ----------------------------------------------------------------------------------------------


def _failing_families(iteration: dict) -> list[str]:
    """The assertion families a failing iteration reports, deduplicated and ordered."""
    families: list[str] = []
    for entry in iteration.get("discrepancy") or []:
        family = str(entry.get("check_id", "assert.unknown"))
        if family not in families:
            families.append(family)
    return families


def run_one(plan: dict) -> dict:
    """Drive one plan and return its result row."""
    from benchmarks.harness import assertions

    from freecad_buddy.usecases import confirm, designer_loop
    from freecad_buddy.usecases.documents import DocumentRegistry

    spec_id = plan["spec_id"]
    checks, anchor_frame = load_case(spec_id)

    registry = DocumentRegistry()
    previous = confirm.set_auto_approve(True)
    handle = None
    notes: dict = {}
    try:
        handle = registry.document_create(label=spec_id.replace("-", "_"))["structured_content"][
            "doc"
        ]
        record = designer_loop.run_designer_loop(
            registry,
            plan,
            checks,
            assertions.evaluate,
            make_visual_leg(registry, plan["spec_text"]),
            repairer=make_repairer(notes, plan),
            doc=handle,
            run_id=f"g3-actor-{spec_id}",
            anchor_frame=anchor_frame,
        )
    except Exception as exc:  # noqa: BLE001 - a spec that could not be driven is a reported row
        traceback.print_exc()
        return {
            "spec_id": spec_id,
            "status": "EXECUTION_FAILED",
            "converged": False,
            "geometry_pass": False,
            "visual_pass": False,
            "visual_code": None,
            "repairs_used": 0,
            "elapsed_s": 0.0,
            "failing_families": [],
            "step_failure": f"{type(exc).__name__}: {exc}",
            "repairs": [],
        }
    finally:
        confirm.set_auto_approve(previous)
        if handle is not None:
            try:
                registry.document_close(doc=handle)
            except Exception:  # noqa: BLE001 - teardown must not mask the measured result
                pass

    last = record["iterations"][-1]
    detail = last.get("visual_detail") or {}
    return {
        "spec_id": spec_id,
        "status": record["status"],
        "converged": record["converged"],
        "geometry_pass": last["geometry_pass"],
        "visual_pass": last["visual_pass"],
        "visual_code": detail.get("code"),
        "repairs_used": record["repairs_used"],
        "elapsed_s": record["elapsed_s"],
        "failing_families": _failing_families(last),
        "step_failure": last.get("step_failure"),
        "repairs": notes.get("repairs", []),
    }


def main() -> int:
    rows = [run_one(plan) for plan in load_plans()]

    geometry_passed = [row for row in rows if row["geometry_pass"]]
    visual_passed = [row for row in rows if row["visual_pass"]]
    summary = {
        "schema": "fcb.g3-actor-results/1",
        "planned": len(rows),
        # Reported as two separate facts on purpose. The visual leg is fail-closed with no vision
        # backend, so `converged` is 0 by construction; collapsing the two would hide whether the
        # geometry the loop built was right.
        "geometry_passed": len(geometry_passed),
        "visual_passed": len(visual_passed),
        "converged": sum(1 for row in rows if row["converged"]),
        "convergence_rule": "geometry_pass AND visual_pass",
        "visual_unavailable": sum(1 for row in rows if row["visual_code"] == "visual.unavailable"),
        "repairs_used": sum(row["repairs_used"] for row in rows),
        "rows": rows,
    }
    RESULTS.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        f"\nplanned {summary['planned']}  geometry_pass {summary['geometry_passed']}  "
        f"visual_pass {summary['visual_passed']}  converged {summary['converged']}"
    )
    for row in rows:
        mark = "PASS" if row["geometry_pass"] else "FAIL"
        families = ", ".join(row["failing_families"]) or "-"
        print(f"  {mark} {row['spec_id']:<34} {row['status']:<16} {families}")
        if row["step_failure"]:
            print(f"       step_failure: {row['step_failure']}")
    return 0


# FreeCADCmd imports a script file as a module named after the file, so ``__name__`` is
# ``"actor_run"`` there and never ``"__main__"``. The sweep is therefore keyed on the module being
# imported as that entry file, which also keeps a diagnostic that imports this module from driving
# all 20 specs as a side effect.
if __name__ in ("__main__", "actor_run") and not os.environ.get("FREECAD_BUDDY_G3_NO_AUTORUN"):
    main()
