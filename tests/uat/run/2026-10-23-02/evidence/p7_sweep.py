"""Run a repo MCP sweep (scripts/automation/run_mcp_edge_cases.py or run_mcp_e2e.py) for phase P7
against the H1 host this run uses, with every output in the run folder.

    uv run python p7_sweep.py <edge|e2e> <out-folder-name>

The sweep code runs unchanged. Two module globals are replaced, nothing else:
- ``_fcb_env``: the sweeps hard-code the micromamba ``fcb`` env, which is not on this machine
  (evidence/h1-setup.txt). The replacement returns the H1 interpreter of h1-setup.txt with the
  environment p0_h1.py gives it: PYTHONPATH and PATH to FreeCAD 1.1.4, every inherited
  FREECAD_BUDDY_* removed, the audit log in the output folder.
- ``OUT_DIR``: the sweeps write to ``_automation/``; writing there would overwrite files outside
  the run folder. The replacement is ``evidence/<out-folder-name>``.
The exit code is the sweep's own ``_run()`` return value.
"""

import os
import sys
from pathlib import Path

import anyio

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[4]
sys.path.insert(0, str(REPO / "scripts" / "automation"))

import run_mcp_e2e  # noqa: E402
import run_mcp_edge_cases  # noqa: E402

H1_PYTHON = os.environ["FCB_PYTHON"]
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"


def main():
    kind, folder = sys.argv[1], sys.argv[2]
    out_dir = EVIDENCE / folder

    def fcb_env():
        child = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
        child["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(Path(FREECAD_BIN).parent / "lib")
        child["PATH"] = FREECAD_BIN + os.pathsep + child.get("PATH", "")
        child["FREECAD_BUDDY_AUDIT_LOG"] = str(out_dir / "audit.jsonl")
        return H1_PYTHON, child

    module = run_mcp_edge_cases if kind == "edge" else run_mcp_e2e
    for target in (run_mcp_e2e, run_mcp_edge_cases):
        target.OUT_DIR = out_dir
        target._fcb_env = fcb_env
    os.chdir(EVIDENCE)
    code = anyio.run(module._run)
    print(f"exit code of _run(): {code}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
