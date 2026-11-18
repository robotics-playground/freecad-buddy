"""Call the real run.main for R0 and then a launch-group re-run, in the spec's folder forms."""
import json
import sys
from pathlib import Path

RUNNER = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(RUNNER))
import launch  # noqa: E402
import run  # noqa: E402

launch.preflight = lambda: None
real_run = run.run
FAILED_GROUP_ENV = {"FREECAD_BUDDY_SCRIPT_EXEC": "0"}


class FakeSession:
    def __init__(self, env):
        self.env = env
        self.info = {"freecad_version": "1.1.4"}

    def __enter__(self):
        if R0[0] and self.env:
            raise RuntimeError("launch group did not start")
        return self

    def __exit__(self, *exc):
        return False


def fake_scenario(item, session, run_dir):
    return run._identity(item) | {
        "verdict": run.PASS, "reasons": [], "errors": [], "capture": None,
        "findings": [], "disagreements": [], "agent_check": None,
    }


R0 = [True]
run.run_scenario = fake_scenario
run.run = lambda scenarios, run_dir: real_run(scenarios, run_dir, open_session=lambda env, audit: FakeSession(env))
scen = RUNNER.parent / "scenarios"
r0_files = [str(scen / n) for n in ("tc-02-01.json", "tc-02-02.json", "tc-05-03.json")]
r0 = OUT / "runner"
code0 = run.main([*r0_files, "--out", str(r0)])
before = (r0 / "results.json").read_bytes()
data0 = json.loads(before)
print("R0 exit", code0, "seed", data0["run"]["sample_seed"], data0["run"]["sample_seed_source"],
      [(s["id"], s["verdict"], s.get("not_run", False)) for s in data0["scenarios"]])
R0[0] = False
rerun = OUT / "runner-rerun-1"
code1 = run.main([str(scen / "tc-05-03.json"), "--out", str(rerun)])
data1 = json.loads((rerun / "results.json").read_text(encoding="utf-8"))
print("rerun exit", code1, "seed", data1["run"]["sample_seed"],
      [(s["id"], s["verdict"], s.get("not_run", False)) for s in data1["scenarios"]])
after = (r0 / "results.json").read_bytes()
print("R0 results.json unchanged:", before == after, "R0 files:", sorted(p.name for p in r0.iterdir()))
# Gate-count rule of the spec: R0 rows, except re-run group scenarios replaced by re-run rows.
rerun_ids = {s["id"] for s in data1["scenarios"]}
rows = {s["id"]: s for s in data0["scenarios"] if s["id"] not in rerun_ids}
for s in data1["scenarios"]:
    assert s["id"] not in rows
    rows[s["id"]] = s
print("gate rows", len(rows), "R0 ids", len(data0["scenarios"]), "duplicates", len(data0["scenarios"]) - len(rows),
      [(k, v["verdict"], v.get("not_run", False)) for k, v in sorted(rows.items())])
