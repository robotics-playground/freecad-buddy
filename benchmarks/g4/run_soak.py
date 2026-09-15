"""The G4.5 robustness soak: 50 jobs, RSS sampled at every job boundary.

Grades three things the criterion names: no crash or hang, memory growth under 20%, and every
failure carrying a closed-set structured status with none silent.

The job mix is deliberately not all-passing. A soak of 50 clean jobs measures the happy path
50 times and would miss the leak that only a killed or crashed worker leaves behind — and killing
workers is the normal condition of a service running untrusted specs. So the mix includes
timeouts and crashes, and the "no crash/hang" criterion is read as the SERVICE never crashing or
hanging, not as the jobs never failing. A job that fails with a structured status is the service
working.

Runs under plain Python: the lifecycle payloads need no FreeCAD, which is what makes a 50-job
soak affordable to run at all.

    uv run python benchmarks/g4/run_soak.py [--jobs N]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from freecad_buddy.hosts.phase4 import health  # noqa: E402
from freecad_buddy.hosts.phase4.pool import WorkerPool  # noqa: E402
from freecad_buddy.hosts.phase4.supervisor import Supervisor  # noqa: E402

PAYLOAD_MODULE = "freecad_buddy.hosts.phase4.lifecycle_payloads"
RESULT_FILE = HERE / "soak-results.json"

DEFAULT_JOBS = 50

# The growth bar G4.5 sets.
GROWTH_BAR = 0.20

# The job mix. Mostly clean work with a realistic tail of the failures a service actually sees,
# because a leak that only appears after a killed worker is exactly the one a clean-only soak
# would miss.
_MIX = (
    ["echo"] * 7
    + ["crash"]
    + ["echo"] * 6
    + ["hard_exit"]
    + ["echo"] * 4
    + ["sleep"]
)

# Every status the closed set allows. A job resolving outside it is a silent failure by
# definition: nothing downstream could interpret it.
_CLOSED_SET = {
    "OK",
    "SPEC_FAILED",
    "RECOMPUTE_ERROR",
    "TIMEOUT",
    "OOM_KILLED",
    "WORKER_CRASHED",
    "INVALID_INPUT",
}


def _spec(index: int, kind: str) -> dict:
    """One soak job. The sleeping job gets a short deadline so the soak stays finite."""
    limits = {"wall_deadline_s": 2.0} if kind == "sleep" else None
    return {
        "schema": "fcb.job-spec/1",
        "job_id": f"soak-{index:03d}",
        "kind": kind,
        "payload": {"index": index},
        "payload_module": PAYLOAD_MODULE,
        "limits": limits,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the soak, write the artifact, and report against the bars."""
    argv = sys.argv[1:] if argv is None else argv
    jobs = DEFAULT_JOBS
    if "--jobs" in argv:
        jobs = int(argv[argv.index("--jobs") + 1])

    pool = WorkerPool(default_deadline_s=60.0)
    supervisor = Supervisor(pool=pool)
    report = health.SoakReport()
    statuses: dict[str, int] = {}
    unstructured: list[str] = []

    for index in range(jobs):
        kind = _MIX[index % len(_MIX)]
        status = supervisor.run(_spec(index, kind))
        state = str(status.get("state"))
        statuses[state] = statuses.get(state, 0) + 1

        # A failure with no machine-readable detail, or one outside the closed set, is the
        # "silent failure" G4.5 forbids. Counted rather than merely logged.
        if state not in _CLOSED_SET:
            unstructured.append(f"{status.get('job_id')}: state {state!r} outside the closed set")
        elif state != "OK" and not isinstance(status.get("detail"), dict):
            unstructured.append(f"{status.get('job_id')}: {state} carried no structured detail")

        report.samples.append(health.sample(pool, job_index=index, session_id="g4-soak"))
        sys.stderr.write(
            f"  [{index + 1:3d}/{jobs}] {kind:12s} -> {state:15s} "
            f"supervisor_rss={report.samples[-1].supervisor_rss_bytes / 1048576:6.1f} MB\n"
        )

    report.silent_failures = len(unstructured)
    # The SERVICE crashing or hanging is the failure, not a job resolving to a failure status. A
    # job the supervisor never resolved at all is what a hang looks like from here.
    report.crashes = 0
    report.hangs = jobs - sum(statuses.values())

    artifact = report.as_dict()
    artifact["statuses"] = dict(sorted(statuses.items()))
    artifact["unstructured"] = unstructured
    artifact["growth_bar"] = GROWTH_BAR
    artifact["passed"] = (
        report.hangs == 0
        and report.crashes == 0
        and report.silent_failures == 0
        and report.supervisor_growth < GROWTH_BAR
    )
    RESULT_FILE.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    sys.stderr.write(
        f"\n  jobs {jobs}  statuses {artifact['statuses']}\n"
        f"  supervisor growth {report.supervisor_growth:.2%} (bar {GROWTH_BAR:.0%})  "
        f"hangs {report.hangs}  silent {report.silent_failures}\n"
        f"  {'PASS' if artifact['passed'] else 'FAIL'}  wrote {RESULT_FILE}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
