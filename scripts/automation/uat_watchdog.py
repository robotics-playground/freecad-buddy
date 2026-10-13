"""Liveness check for a manual UAT run: is the harness still able to drive and observe FreeCAD?

A UAT run depends on four independent things staying alive: the ``cua-driver`` session that
drives and captures the GUI, the FreeCAD process, the MCP proxy on ``:8765``, and the bridge
behind it. When one dies the symptom is a stalled run, not an error — the 2026-09-13-02 run lost
its ``cua-driver`` session twice and each loss surfaced only as an empty capture several calls
later. This turns each of those into a named non-zero exit.

Run between test cases::

    uv run python scripts/automation/uat_watchdog.py --pid 26912 --window 398030

Exits 0 when every check passes, 1 naming the first failure. ``--revive`` (default on) restarts a
lapsed ``cua-driver`` session in place and reports that it did, which is usually enough to keep a
run going. Every subprocess and socket call carries an explicit timeout, so the watchdog itself
cannot become the thing that hangs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# A watchdog that waits as long as the thing it is watching is useless. Every external call is
# bounded well under the 30 s budget of the cheapest MCP tool.
_CALL_TIMEOUT_S = 15.0
_HTTP_TIMEOUT_S = 10.0

_PROXY_URL = "http://127.0.0.1:8765/mcp/"

# The reserved prefix the bridge uses for both snapshot directories and render output.
_SNAP_PREFIX = "FCB_TMP_snap_"
_SHOT_PREFIX = "FCB_TMP_shot_"


class CheckFailed(Exception):
    """A named liveness failure. The message is what the operator needs to act on."""


def _cua(command: str, payload: dict) -> dict:
    """Call one ``cua-driver`` tool and return its parsed reply.

    A lapsed session is refused in **plain text**, not JSON ("session 'uat' has ended; ..."), so an
    unparseable reply is returned as ``{"_text": ...}`` rather than raised. That keeps the
    distinction the caller needs: a dead session is a revivable condition, an unreachable binary
    is not.

    :raises CheckFailed: the binary is missing or the call timed out.
    """
    exe = shutil.which("cua-driver")
    if exe is None:
        raise CheckFailed("cua-driver is not on PATH")
    try:
        done = subprocess.run(
            [exe, "call", command, "--json", json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=_CALL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise CheckFailed(f"cua-driver {command} timed out after {_CALL_TIMEOUT_S:g}s") from exc
    text = (done.stdout or done.stderr or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        return {"_text": text}


def check_cua_session(session: str, revive: bool) -> str:
    """The named ``cua-driver`` session is active, reviving it once if it has lapsed."""
    reply = _cua("get_session", {"session": session})
    if reply.get("active"):
        return f"cua session {session!r} active"
    # An ended session is refused in plain text, so anything that is not active:true is treated as
    # lapsed and start_session is the thing that reports whether it came back.
    reason = reply.get("_text") or reply
    if not revive:
        raise CheckFailed(f"cua session {session!r} is not active: {reason}")
    started = _cua("start_session", {"session": session})
    if not started.get("active"):
        raise CheckFailed(f"cua session {session!r} could not be revived: {started}")
    return f"cua session {session!r} REVIVED (was dead)"


def check_window(session: str, pid: int, window_id: int | None) -> str:
    """FreeCAD is running and its window is enumerable, which is what capture needs."""
    reply = _cua("list_windows", {"session": session, "pid": pid})
    windows = reply.get("windows") or []
    if not windows:
        raise CheckFailed(f"FreeCAD pid {pid} has no enumerable window (process gone?)")
    if window_id is not None:
        ids = [w.get("window_id") for w in windows]
        if window_id not in ids:
            raise CheckFailed(f"window {window_id} is gone; live windows: {ids}")
    title = windows[0].get("title", "")
    return f"FreeCAD pid {pid} window ok ({title.strip()!r})"


def check_proxy() -> str:
    """The MCP proxy answers an ``initialize`` handshake.

    A LISTENING socket is not enough: the 2026-09-13-02 run saw the port bound by a proxy whose
    client had gone, so the handshake is the real check.
    """
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "uat-watchdog", "version": "1"},
            },
        }
    ).encode()
    request = urllib.request.Request(
        _PROXY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S) as reply:
            payload = reply.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise CheckFailed(f"MCP proxy on :8765 did not answer initialize ({exc})") from exc
    if "serverInfo" not in payload:
        raise CheckFailed(f"MCP proxy answered without serverInfo: {payload[:200]!r}")
    return "MCP proxy on :8765 answered initialize"


def check_temp(since: datetime | None) -> str:
    """Report reserved-prefix leftovers, and fail on a snapshot leaked since ``since``.

    A surviving ``FCB_TMP_snap_`` means a mutation bracket did not close, which invalidates the
    snapshot assertions of every scenario that follows. Render output (``FCB_TMP_shot_``) is only
    counted: it accumulates by design today (finding R2-04) and is not a reason to stop a run.
    """
    root = Path(tempfile.gettempdir())
    snaps = sorted(p for p in root.glob(f"{_SNAP_PREFIX}*") if p.is_dir())
    shots = sorted(root.glob(f"{_SHOT_PREFIX}*"))
    if since is not None:
        fresh = [p for p in snaps if _created_after(p, since)]
        if fresh:
            names = ", ".join(p.name for p in fresh[:5])
            raise CheckFailed(f"{len(fresh)} snapshot dir(s) leaked since cutoff: {names}")
    return f"temp: {len(snaps)} snapshot dir(s) total, {len(shots)} render file(s)"


def _created_after(path: Path, since: datetime) -> bool:
    """True when ``path`` was created after ``since``; an unreadable stat is not evidence.

    ``st_birthtime`` is the real creation time where the platform exposes it; on Windows, where
    this suite runs, ``st_ctime`` already is creation time.
    """
    try:
        stat = path.stat()
    except OSError:
        return False
    created = getattr(stat, "st_birthtime", None) or getattr(stat, "st_ctime")
    return datetime.fromtimestamp(created) > since


def parse_since(value: str) -> datetime:
    """Parse the ``--since`` cutoff as local naive time, the form ``_created_after`` compares.

    An aware timestamp (``+07:00``, ``Z``) is converted to local time and its offset dropped:
    comparing it with the naive ``datetime.fromtimestamp`` raises ``TypeError``.
    """
    try:
        since = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an ISO timestamp: {value!r}") from exc
    if since.tzinfo is not None:
        since = since.astimezone().replace(tzinfo=None)
    return since


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="uat", help="cua-driver session id (default: uat)")
    parser.add_argument("--pid", type=int, required=True, help="FreeCAD process id")
    parser.add_argument("--window", type=int, default=None, help="expected FreeCAD window id")
    parser.add_argument(
        "--since",
        type=parse_since,
        default=None,
        help="ISO timestamp; fail if a snapshot dir was created after it",
    )
    parser.add_argument(
        "--no-revive",
        dest="revive",
        action="store_false",
        help="report a lapsed cua session instead of restarting it",
    )
    args = parser.parse_args()

    checks = (
        ("cua-session", lambda: check_cua_session(args.session, args.revive)),
        ("freecad-window", lambda: check_window(args.session, args.pid, args.window)),
        ("mcp-proxy", check_proxy),
        ("temp-hygiene", lambda: check_temp(args.since)),
    )

    for name, run in checks:
        try:
            print(f"ok   {name}: {run()}")
        except CheckFailed as exc:
            print(f"FAIL {name}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
