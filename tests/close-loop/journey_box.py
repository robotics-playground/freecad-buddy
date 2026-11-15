"""Close-loop journey: an agent builds a box through MCP and FreeCAD's own window shows it.

Runs on the host against the `fcb-desktop` container (see tests/close-loop/README.md):
    uv run python tests/close-loop/journey_box.py

1. MCP (container proxy via the 127.0.0.1:18765 relay): close the documents earlier runs left,
   create a document, add a 30x20x10 box, fit the view.
2. cua-driver in the container: grab FreeCAD's window screenshot into a fresh file.
3. MCP: close the document, so FreeCAD can later quit without a save-changes dialog.
4. PASS only when the 3D view region of that screenshot holds a shaded solid. The screenshot is
   copied to tests/close-loop/evidence/ and must still be looked at.

The check is on pixels because the FreeCAD 1.1.4 AppImage's Qt is built without the AT-SPI bridge:
cua-driver sees FreeCAD's top-level window but none of its widgets, so there is no tree row to read.

A failed tool call does not stop the run: the window is observed either way, so a run where the box
was never built proves the observation step reports the absence.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "http://127.0.0.1:18765/mcp"
CONTAINER = "fcb-desktop"
CUA_DRIVER = "/usr/local/bin/cua-driver"
CONTAINER_SHOT = "/tmp/journey-box.png"
EVIDENCE = Path(__file__).resolve().parent / "evidence" / "journey-box.png"
BOX_CODE = """
box = doc.addObject("Part::Box", "CloseLoopBox")
box.Length, box.Width, box.Height = 30, 20, 10
doc.recompute()
result = box.Name
"""
# Share of the 3D-view region that must be shaded solid. Measured on the 1600x1000 desktop:
# the fitted box covers 49.6-49.7% of the region, the empty view of a run where the
# box was never built 0.0-0.1%.
MIN_SOLID_SHARE = 0.10
# The 3D view as fractions of the window screenshot: right of the Model panel, below the
# toolbars, above the document tabs, left of the navigation cube.
VIEW_REGION = (0.18, 0.16, 0.88, 0.92)
# Run with the container's Python, which has Pillow. A solid face is a mid grey: darker than the
# light background, and low in saturation unlike the coloured axis and navigation-cube marks.
SOLID_SHARE_SCRIPT = """
import sys
from PIL import Image
image = Image.open(sys.argv[1]).convert("RGB")
w, h = image.size
left, top, right, bottom = (float(v) for v in sys.argv[2:6])
region = image.crop((int(left * w), int(top * h), int(right * w), int(bottom * h)))
pixels = list(region.getdata())
solid = sum(1 for r, g, b in pixels if max(r, g, b) < 200 and max(r, g, b) - min(r, g, b) < 30)
print(solid / len(pixels))
"""


async def run_journey() -> tuple[list[str], float | None, str]:
    """Build, observe, close; return the MCP problems met, the solid share and what was seen."""
    async with streamable_http_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.call_tool("document_list", {})
            for document in _content(listed).get("documents", []):
                await session.call_tool("document_close", {"doc": document["doc"]})
            created = await session.call_tool("document_create", {"label": "CloseLoopJourney"})
            doc = _content(created).get("doc")
            if not doc:
                problem = f"document_create returned no doc handle: {created.structuredContent}"
                return [problem], None, "not observed"
            problems = [
                problem
                for name, arguments in (
                    ("script_exec", {"doc": doc, "code": BOX_CODE}),
                    ("view_fit_viewport", {"doc": doc}),
                )
                if (problem := _failure(name, await session.call_tool(name, arguments)))
            ]
            share, detail = observe_window()
            await session.call_tool("document_close", {"doc": doc})
            return problems, share, detail


def _failure(name: str, reply) -> str | None:
    """A one-line problem when a tool call did not end OK, else ``None``."""
    status = (reply.structuredContent or {}).get("status")
    if not reply.isError and status == "OK":
        return None
    text = " ".join(c.text for c in reply.content if hasattr(c, "text"))
    return f"{name} failed: status={status} {text[:200]}"


def _content(reply) -> dict:
    """The tool payload inside the freecad-buddy result envelope."""
    return (reply.structuredContent or {}).get("structured_content") or {}


def _in_container(*command: str) -> str:
    done = subprocess.run(
        ["docker", "exec", "-u", "cua", CONTAINER, *command],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{command[:3]} exited {done.returncode}: {done.stderr.strip()[-300:]}")
    return done.stdout


def _cua(tool: str, arguments: dict) -> dict:
    """Call one cua-driver tool inside the container desktop session and return its JSON."""
    # Tool and JSON travel as positional arguments, never spliced into the shell text.
    out = _in_container(
        "bash",
        "-c",
        f'eval "$(fcb-session-env)"; exec {CUA_DRIVER} call "$1" "$2"',
        "cua-driver",
        tool,
        json.dumps(arguments),
    )
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"cua-driver {tool} printed no JSON: {out[:200]!r}")
    return json.loads(out[start:])


def observe_window() -> tuple[float | None, str]:
    """Screenshot FreeCAD's window; return the solid share of its 3D view and a description."""
    freecad = next(
        (w for w in _cua("list_windows", {})["windows"] if w["app_name"] == "FreeCAD"), None
    )
    if freecad is None:
        return None, "no FreeCAD window on the container desktop"
    # A screenshot left by an earlier run must never be measured as this run's.
    _in_container("rm", "-f", CONTAINER_SHOT)
    _cua(
        "get_window_state",
        {
            "pid": freecad["pid"],
            "window_id": freecad["window_id"],
            "include_accessibility_tree": False,
            "screenshot_out_file": CONTAINER_SHOT,
        },
    )
    if _in_container("sh", "-c", f"test -s {CONTAINER_SHOT} && echo yes || true").strip() != "yes":
        return None, "cua-driver wrote no screenshot"
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["docker", "cp", f"{CONTAINER}:{CONTAINER_SHOT}", str(EVIDENCE)],
        capture_output=True,
        check=True,
    )
    share = float(
        _in_container(
            "/opt/venv/bin/python3",
            "-c",
            SOLID_SHARE_SCRIPT,
            CONTAINER_SHOT,
            *map(str, VIEW_REGION),
        )
    )
    return share, f"window {freecad['title']!r}; solid share of the 3D view {share:.1%}"


def main() -> int:
    problems, share, detail = asyncio.run(run_journey())
    for problem in problems:
        print(f"MCP: {problem}")
    print(f"GUI: {detail}")
    print(f"evidence: {EVIDENCE}")
    shown = share is not None and share >= MIN_SOLID_SHARE
    if shown and not problems:
        print("PASS: FreeCAD's 3D view shows a shaded solid; look at the screenshot too")
        return 0
    verdict = "shown" if shown else "missing"
    print(f"FAIL: solid {verdict} in FreeCAD's 3D view (need >= {MIN_SOLID_SHARE:.0%})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
