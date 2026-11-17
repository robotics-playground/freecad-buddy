"""Run scripts/automation/run_mcp_e2e.py unchanged, with the H1 interpreter of h1-setup.txt.

The sweep hard-codes the fcb micromamba env, which this machine does not have. This wrapper
replaces only ``_fcb_env`` (interpreter and child environment, as p0_h1.py builds it) and
``OUT_DIR`` (evidence/<tag>-e2e/), then runs the sweep's own ``_run``. Exit code is the sweep's.
    p1_e2e.py <tag>
"""

import os
import sys
from pathlib import Path

import anyio

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[4]
sys.path.insert(0, str(REPO / "scripts" / "automation"))

import run_mcp_e2e  # noqa: E402

FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
H1_PYTHON = os.environ["FCB_PYTHON"]
OUT = EVIDENCE / f"{sys.argv[1]}-e2e"


def h1_env():
    child = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    child["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(Path(FREECAD_BIN).parent / "lib")
    child["PATH"] = FREECAD_BIN + os.pathsep + child.get("PATH", "")
    child["FREECAD_BUDDY_AUDIT_LOG"] = str(OUT / "audit.jsonl")
    return H1_PYTHON, child


run_mcp_e2e.OUT_DIR = OUT
run_mcp_e2e._fcb_env = h1_env
raise SystemExit(anyio.run(run_mcp_e2e._run))
