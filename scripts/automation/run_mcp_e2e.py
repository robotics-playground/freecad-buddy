"""Fully-automated end-to-end MCP test harness for the FreeCAD bridge.

Spawns the headless H1 server (FreeCAD + MCP in one interpreter) as a subprocess, drives it
over the MCP stdio protocol, exercises the whole tool surface against real golden-model
geometry, captures the server's stderr, and writes a machine-readable report. No FreeCAD GUI,
no manual restarts: this process owns the H1 subprocess lifecycle.

Run from the uv env (which has the ``mcp`` client): ``uv run python scripts/automation/run_mcp_e2e.py``.
The H1 server runs under the conda ``fcb`` env python (which has FreeCAD + mcp + oracles).

Outputs (under ``_automation/``):
  e2e_report.json      per-tool pass/fail with real measured values
  server.stderr.log    the H1 server's captured stderr (agent reads this for plugin errors)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "_automation"
GOLDEN_DIR = REPO / "benchmarks" / "g0" / "golden-models"

# Analytic expected values for the golden models (independent oracle; see expected.yaml).
GOLDEN_EXPECTED = {
    "box-10-20-30": {"volume": 6000.0, "solids": 1},
    "cylinder-r5-h20": {"volume": 1570.7963, "solids": 1},
    "sphere-r10": {"volume": 4188.7902, "solids": 1},
    "box40-hole-r5": {"volume": 15214.6018, "solids": 1},
    "two-box-compound": {"volume": 2000.0, "solids": 2},
}


def _fcb_env() -> tuple[str, dict]:
    """The fcb conda env python and the child env that makes ``import FreeCAD`` resolve."""
    env_dir = Path(os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb"))
    py = env_dir / "python.exe"
    lib_bin = env_dir / "Library" / "bin"
    lib_lib = env_dir / "Library" / "lib"
    child = dict(os.environ)
    child["PYTHONPATH"] = str(lib_bin)
    child["PATH"] = os.pathsep.join([str(lib_bin), str(lib_lib), child.get("PATH", "")])
    # Route the H1 server's own audit log under _automation so a run leaves no repo-root litter.
    child["FREECAD_BUDDY_AUDIT_LOG"] = str(OUT_DIR / "audit.jsonl")
    return str(py), child


def _status(res) -> str:
    return (res.structuredContent or {}).get("status", "NO_STATUS")


def _payload(res) -> dict:
    return (res.structuredContent or {}).get("structured_content", {})


def _rel(measured: float, expected: float) -> float:
    return abs(measured - expected) / abs(expected) if expected else abs(measured)


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def record(self, tool: str, ok: bool, detail: str = "", status: str = "") -> None:
        self.checks.append({"tool": tool, "ok": ok, "status": status, "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {tool:26} {status} {detail}")

    def summary(self) -> dict:
        passed = sum(1 for c in self.checks if c["ok"])
        return {
            "total": len(self.checks),
            "passed": passed,
            "failed": len(self.checks) - passed,
            "all_passed": passed == len(self.checks),
            "checks": self.checks,
        }


async def _sweep(session: ClientSession, rep: Report) -> None:
    # 1. tools/list
    tools = await session.list_tools()
    names = {t.name for t in tools.tools}
    rep.record("tools/list", len(names) >= 20, f"{len(names)} tools", "OK")

    # 2. query_capabilities
    cap = await session.call_tool("query_capabilities", {})
    csc = _payload(cap)
    rep.record(
        "query_capabilities",
        _status(cap) == "OK" and csc.get("freecad_version"),
        f"freecad={csc.get('freecad_version')} render={csc.get('render')}",
        _status(cap),
    )

    # 3-N. per golden model: open, measure, verify, export + verify-export, screenshot
    for name, expected in GOLDEN_EXPECTED.items():
        fcstd = GOLDEN_DIR / f"{name}.FCStd"
        if not fcstd.is_file():
            rep.record(f"open:{name}", False, "fixture missing", "MISSING")
            continue
        opened = await session.call_tool("document_open", {"path": str(fcstd)})
        if _status(opened) != "OK":
            rep.record(f"open:{name}", False, str(_payload(opened)), _status(opened))
            continue
        handle = _payload(opened)["doc"]
        # The nested tree lives under "tree"; it was "nodes" when this harness was written and
        # the rename went unnoticed because a None object name fails the checks rather than the
        # call, so every downstream measurement reported a tool defect that did not exist.
        obj = _payload(await session.call_tool("query_tree_summary", {"doc": handle}))
        tree = obj.get("tree") or []
        obj_name = tree[0]["name"] if tree else None
        if obj_name is None:
            rep.record(f"tree_summary:{name}", False, f"no root node in {sorted(obj)}", "NO_ROOT")
            continue

        # query_mass_properties — real volume within 0.1 %
        mp = await session.call_tool(
            "query_mass_properties", {"doc": handle, "object": obj_name}
        )
        vol = _payload(mp).get("volume", {}).get("value")
        vol_ok = vol is not None and _rel(vol, expected["volume"]) <= 0.001
        rep.record(
            f"query_mass_properties:{name}",
            vol_ok,
            f"volume={vol} (expect {expected['volume']}, rel_ok={vol_ok})",
            _status(mp),
        )

        # verify_shape
        vs = await session.call_tool("verify_shape", {"doc": handle, "object": obj_name})
        rep.record(f"verify_shape:{name}", _status(vs) == "OK", "", _status(vs))

        # STEP export + paired verify (no third-party oracle; pure FreeCAD round-trip)
        step_path = str(OUT_DIR / f"{name}.step")
        es = await session.call_tool(
            "export_step", {"doc": handle, "path": step_path, "objects": [obj_name]}
        )
        if _status(es) == "OK":
            eid = _payload(es)["export_id"]
            ve = await session.call_tool(
                "verify_export_step", {"doc": handle, "export_id": eid}
            )
            rep.record(f"verify_export_step:{name}", _status(ve) == "OK", "", _status(ve))

        # STL export + verify (trimesh + stdlib oracles run in-process under H1)
        stl_path = str(OUT_DIR / f"{name}.stl")
        el = await session.call_tool(
            "export_stl", {"doc": handle, "path": stl_path, "objects": [obj_name]}
        )
        if _status(el) == "OK":
            lid = _payload(el)["export_id"]
            vl = await session.call_tool("verify_export_stl", {"doc": handle, "export_id": lid})
            failed = [
                c["id"]
                for c in _payload(vl).get("checks", [])
                if not c.get("passed")
            ]
            rep.record(
                f"verify_export_stl:{name}",
                _status(vl) == "OK",
                "" if _status(vl) == "OK" else f"failed_checks={failed}",
                _status(vl),
            )

        # screenshot (offscreen render in H1) — best-effort visual
        shot = await session.call_tool("query_screenshot", {"doc": handle, "view": {"camera": "iso"}})
        srender = _payload(shot).get("render", {})
        link = srender.get("resource_link")
        shot_ok = _status(shot) == "OK" and srender.get("available") and link and Path(link).is_file()
        rep.record(
            f"query_screenshot:{name}",
            bool(shot_ok),
            f"link={link}" if shot_ok else f"available={srender.get('available')} reason={srender.get('reason')}",
            _status(shot),
        )
        if shot_ok:
            # copy the first successful render out for the agent to view
            dest = OUT_DIR / "sample_render.png"
            dest.write_bytes(Path(link).read_bytes())

        await session.call_tool("document_close", {"doc": handle})

    # document_create / save / close lifecycle on a fresh scratch doc
    dc = await session.call_tool("document_create", {"label": "scratch"})
    if _status(dc) == "OK":
        sh = _payload(dc)["doc"]
        sp = str(OUT_DIR / "scratch.FCStd")
        sv = await session.call_tool("document_save", {"doc": sh, "path": sp})
        rep.record("document_save", _status(sv) == "OK", "", _status(sv))
        do = await session.call_tool("document_open", {"path": sp})
        rep.record("document_open(reopen)", _status(do) == "OK", "", _status(do))
        # Reopening the just-saved file returns the same live document, so close that one handle
        # only; a second close on the aliased original would fault on a stale handle.
        reopened = _payload(do)["doc"] if _status(do) == "OK" else None
        await session.call_tool("document_close", {"doc": reopened or sh})
    else:
        rep.record("document_create", False, str(_payload(dc)), _status(dc))


async def _run() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    stderr_path = OUT_DIR / "server.stderr.log"
    py, child_env = _fcb_env()
    if not Path(py).is_file():
        print(f"fcb env python not found at {py}; run the micromamba setup first", file=sys.stderr)
        return 2

    params = StdioServerParameters(
        command=py,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--mode", "inline", "--transport", "stdio"],
        env=child_env,
    )
    rep = Report()
    print("Spawning headless H1 FreeCAD MCP server + running the tool sweep...\n")
    with open(stderr_path, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await _sweep(session, rep)

    result = rep.summary()
    (OUT_DIR / "e2e_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n{result['passed']}/{result['total']} checks passed")
    print(f"report: {OUT_DIR / 'e2e_report.json'}")
    print(f"server stderr: {stderr_path}")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(anyio.run(_run))
