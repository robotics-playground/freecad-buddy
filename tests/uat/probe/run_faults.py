"""Prove the UAT probe detects each planted fault in ``faults/cases.json`` (AD-13).

    docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/probe/run_faults.py

Per case: start a FreeCAD of its own with the probe (``-M``), a temporary ``-u`` user config,
the bridge addon disabled and the case's plant macro; wait for the probe discovery file and the
macro's done marker; take the snapshot(s); compare them with the clean expectation; end that
FreeCAD. A fault is detected when its named field mismatches. A control is a false alarm when
any snapshot mismatches or two snapshots of the same scene differ. Exit 0 only when every fault
is detected and no control is flagged. Ends only the processes it started.

Runs inside the ``fcb-desktop`` container with the launch code of the scripted runner
(``tests/uat/runner/launch.py``): FreeCAD is the AppImage under ``/opt/freecad``, and the
discovery file is under the user's ``~/.local/share``.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
FAULTS_DIR = PROBE_DIR / "faults"
REPO_ROOT = PROBE_DIR.parents[2]
START_TIMEOUT_S = 120.0
LAYOUT_TIMEOUT_S = 30.0
REQUIRED_FAULTS = 5
REQUIRED_CONTROLS = 2

sys.path.insert(0, str(PROBE_DIR))
sys.path.insert(0, str(PROBE_DIR.parent / "runner"))
import expect  # noqa: E402
import launch  # noqa: E402

LaunchError = launch.LaunchError


def discovery_file(pid):
    return launch.discovery_file(pid)


def wait_until_planted(process, done_marker):
    """Wait for the marker and the probe file of the FreeCAD below ``process``, not ``AppRun``."""
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LaunchError(f"FreeCAD exited with code {process.returncode}")
        discoveries = [discovery_file(pid) for pid in sorted(launch.started_pids(process.pid))]
        discovery = next((found for found in discoveries if found is not None), None)
        if discovery is not None and done_marker.exists():
            error = done_marker.read_text(encoding="utf-8")
            if error:
                raise LaunchError(f"plant macro failed: {error}")
            return json.loads(discovery.read_text(encoding="utf-8"))
        time.sleep(0.5)
    raise LaunchError(f"no discovery file or plant marker after {START_TIMEOUT_S:.0f} s")


def wait_until_laid_out(record):
    """Wait until the 3D view has a visible region.

    The plant marker is written before the window manager has placed the main window. A snapshot
    taken then has ``view.clipped`` of ``None`` and a view rectangle that moves a moment later, so
    a clean scene would read as a false alarm.
    """
    deadline = time.monotonic() + LAYOUT_TIMEOUT_S
    while time.monotonic() < deadline:
        view = launch.get_snapshot(record)["view"]
        if view is not None and view["clipped"] is not None:
            return
        time.sleep(0.5)
    raise LaunchError(f"the 3D view had no visible region after {LAYOUT_TIMEOUT_S:.0f} s")


def take_snapshots(case, scene):
    with tempfile.TemporaryDirectory(prefix="fcb-probe-", ignore_cleanup_errors=True) as work:
        work = Path(work)
        scene_copy = work / scene.name
        shutil.copy2(scene, scene_copy)
        done_marker = work / "planted"
        environment = launch.launch_environment({}, work / "audit.jsonl") | {
            "FCB_PROBE_SCENE": str(scene_copy),
            "FCB_PROBE_PLANT_DONE": str(done_marker),
        }
        command = [
            *launch.freecad_command(work),
            "--disable-addon",
            "FreeCADBuddy",
            str(FAULTS_DIR / case["macro"]),
        ]
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            record = wait_until_planted(process, done_marker)
            wait_until_laid_out(record)
            return [launch.get_snapshot(record) for _ in range(case.get("queries", 1))]
        finally:
            launch.stop(process)


def check_case_set(cases):
    """Raise ``ValueError`` unless the set can prove 5/5 detected and 0/2 false alarms."""
    kinds = [case.get("kind") for case in cases]
    unknown = sorted({kind for kind in kinds if kind not in ("fault", "control")}, key=str)
    if unknown:
        raise ValueError(f"unknown case kind(s) {unknown}")
    if kinds.count("fault") < REQUIRED_FAULTS or kinds.count("control") < REQUIRED_CONTROLS:
        raise ValueError(
            f"need at least {REQUIRED_FAULTS} faults and {REQUIRED_CONTROLS} controls, "
            f"got {kinds.count('fault')} and {kinds.count('control')}"
        )


def judge(case, snapshots, expectation):
    """Return ``(flagged, detail)``: whether the probe reported a bad state, and why."""
    mismatches = [m for snapshot in snapshots for m in expect.compare(snapshot, expectation)]
    if case["kind"] == "fault":
        named = [m for m in mismatches if m["field"] == case["field"]]
        return bool(named), json.dumps(named or mismatches)
    if any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        return True, "snapshot changed between queries"
    return bool(mismatches), json.dumps(mismatches)


def main():
    spec = json.loads((FAULTS_DIR / "cases.json").read_text(encoding="utf-8"))
    scene = REPO_ROOT / spec["scene"]
    try:
        check_case_set(spec["cases"])
    except ValueError as exc:
        print(f"invalid faults/cases.json: {exc}")
        return 2
    detected = false_alarms = 0
    faults = [case for case in spec["cases"] if case["kind"] == "fault"]
    controls = [case for case in spec["cases"] if case["kind"] == "control"]
    for case in spec["cases"]:
        try:
            flagged, detail = judge(case, take_snapshots(case, scene), spec["expectation"])
        except Exception as exc:
            # No verdict is a failed case either way: a fault not detected, a control flagged.
            flagged, detail = case["kind"] == "control", f"no verdict: {type(exc).__name__}: {exc}"
        if case["kind"] == "fault":
            detected += flagged
            verdict = "DETECTED" if flagged else "MISSED"
        else:
            false_alarms += flagged
            verdict = "FALSE ALARM" if flagged else "CLEAN"
        print(f"{verdict:<11} {case['id']}: {detail}")
    print(f"detected {detected}/{len(faults)}")
    print(f"false alarms {false_alarms}/{len(controls)}")
    return 0 if detected == len(faults) and false_alarms == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
