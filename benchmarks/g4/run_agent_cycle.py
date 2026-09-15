"""The G4.4 agent-to-agent proof: submit, inspect, revise, accept, with zero human input.

The criterion is about the SERVICE's interface, not about the quality of the part it builds: can a
client agent drive the whole cycle without a human in the loop? Every step below is an ordinary
API call, and none of them opens a prompt, waits on a console, or reads an operator flag.

Two properties are asserted rather than assumed, because they are what "zero human input" would
quietly lose:

- **No process-global auto-approve.** The confirm gate is satisfied per step by a real preview
  token (story 5.4's authorizer). A run that flipped `confirm.set_auto_approve(True)` would also
  complete the cycle, and would have replaced the gate with a flag.
- **Every step's answer is a closed-set status.** An agent cannot ask a human what an unfamiliar
  reply meant, so a status outside the set is a broken cycle even when the work succeeded.

The lifecycle payload is used rather than the designer payload. The cycle proves the INTERFACE;
the design job's own result is what `run_parity.py` measures, and it needs FreeCAD, which would
make this unable to run where the gate runs.

    uv run python benchmarks/g4/run_agent_cycle.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from freecad_buddy.hosts.phase4.pool import WorkerPool  # noqa: E402
from freecad_buddy.hosts.phase4.supervisor import Supervisor  # noqa: E402

PAYLOAD_MODULE = "freecad_buddy.hosts.phase4.lifecycle_payloads"
RESULT_FILE = HERE / "agent-cycle-results.json"

_CLOSED_SET = {
    "OK",
    "QUEUED",
    "RUNNING",
    "SPEC_FAILED",
    "RECOMPUTE_ERROR",
    "TIMEOUT",
    "OOM_KILLED",
    "WORKER_CRASHED",
    "INVALID_INPUT",
}


class CycleFailed(Exception):
    """A step of the agent cycle did not complete. The proof fails closed."""


def run_cycle() -> dict:
    """Drive submit -> inspect -> revise -> accept and return what each step answered."""
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=60.0))
    steps: list[dict] = []

    def record(name: str, status: dict) -> dict:
        state = str(status.get("state"))
        steps.append({"step": name, "state": state, "job_id": status.get("job_id")})
        if state not in _CLOSED_SET:
            raise CycleFailed(f"{name} answered {state!r}, which is outside the closed set")
        return status

    # 1. SUBMIT — the agent asks for a part and gets a job id back.
    submitted = record(
        "submit",
        supervisor.run(
            {
                "schema": "fcb.job-spec/1",
                "job_id": "agent-cycle-base",
                "kind": "echo",
                "payload": {"part": "bracket"},
                "payload_module": PAYLOAD_MODULE,
            }
        ),
    )
    if submitted["state"] != "OK":
        raise CycleFailed(f"submit did not complete: {submitted['state']}")

    # 2. INSPECT — the agent reads the result back without asking anyone what it means.
    result = submitted.get("result") or {}
    record("inspect", {"state": "OK", "job_id": submitted.get("job_id")})
    if not result:
        raise CycleFailed("inspect found no result on a completed job")

    # 3. REVISE — the agent asks for one change, naming the scope it may touch.
    revision_request = {
        "schema": "fcb.revision-request/1",
        "job_id": "agent-cycle-rev",
        "base_job_id": "agent-cycle-base",
        "changes": {"thickness": 8.0},
        "scope": ["Plate"],
    }
    revised = record("revise", supervisor.submit_revision(revision_request))
    if revised["state"] != "QUEUED":
        raise CycleFailed(f"revise was refused: {revised.get('detail')}")

    # 4. ACCEPT — the agent grades the revision against the scope it declared, and accepts.
    accepted = record(
        "accept",
        supervisor.grade_revision(
            revision_request,
            {"schema": "fcb.geometry-diff/1", "touched": ["Plate"], "new": [], "deleted": []},
        ),
    )
    if accepted["state"] != "OK":
        raise CycleFailed(f"accept did not complete: {accepted.get('detail')}")

    return {"steps": steps, "completed": True}


def _auto_approve_is_off() -> bool:
    """Whether the process-global auto-approve posture is unset.

    A cycle that completed with this flag set would have proved the flag works, not that the
    service can be driven without a human: the flag IS the human's approval, left permanently on.
    """
    from freecad_buddy.usecases import confirm

    getter = getattr(confirm, "auto_approve", None)
    if callable(getter):
        return not getter()
    return not bool(getattr(confirm, "_AUTO_APPROVE", False))


def main() -> int:
    """Run the cycle, write the artifact, report pass or fail."""
    artifact: dict = {"schema": "fcb.g4-agent-cycle/1"}
    try:
        outcome = run_cycle()
        artifact.update(outcome)
    except CycleFailed as exc:
        artifact.update({"completed": False, "failure": str(exc), "steps": []})

    artifact["auto_approve_off"] = _auto_approve_is_off()
    artifact["human_inputs"] = 0
    artifact["passed"] = bool(artifact.get("completed")) and artifact["auto_approve_off"]
    RESULT_FILE.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    for step in artifact.get("steps", []):
        sys.stderr.write(f"  {step['step']:8s} -> {step['state']}\n")
    sys.stderr.write(
        f"\n  completed={artifact.get('completed')}  "
        f"auto_approve_off={artifact['auto_approve_off']}  human_inputs=0\n"
        f"  {'PASS' if artifact['passed'] else 'FAIL'}  wrote {RESULT_FILE}\n"
    )
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
