"""Copy the proxy + its tests into scratch copies, apply one mutant each, run the builder's tests.

    uv run --no-sync --project <repo> python mutants.py <repo> <scratch-out>
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
PROXY = "scripts/automation/mcp_cache_proxy.py"
TESTS = ["tests/external/test_mcp_cache_proxy.py", "tests/external/fake_mcp_upstream.py"]

MUTANTS = {
    "M0-none": [],
    "M1-drop-structuredContent": [
        ("        self._last_used = time.monotonic()\n        return result\n",
         "        self._last_used = time.monotonic()\n"
         "        return types.CallToolResult(content=result.content, isError=result.isError)\n"),
    ],
    "M2-resend-after-connection-closed": [
        ("                await self._retire(connection)\n                raise OutcomeUnknown(str(error)) from error\n",
         "                raise _NotDelivered(str(error)) from error\n"),
    ],
    "M3-no-retry-on-session-terminated": [
        ("        except _NotDelivered:\n            await self._retire(connection)\n        connection = await self._ensure()",
         "        except _NotDelivered as error:\n            await self._retire(connection)\n"
         "            raise UpstreamUnavailable('no retry') from error\n        connection = await self._ensure()"),
    ],
    "M4-no-port-probe": [
        ("            if port is not None and not await asyncio.to_thread(_port_is_open, port):",
         "            if False:"),
    ],
    "M5-no-list-changed": [
        ("                await self._client_session.send_tool_list_changed()", "                pass"),
    ],
    "M6-no-reconnect-lock": [
        ("    async def _ensure(self) -> _Connection:\n        async with self._lock:",
         "    async def _ensure(self) -> _Connection:\n        async with asyncio.Lock():"),
    ],
    "M7-close-with-calls-in-flight": [
        ("        if connection.in_flight == 0:\n            await self._close(connection)\n\n    async def _close",
         "        if True:\n            await self._close(connection)\n\n    async def _close"),
    ],
    "M8-no-liveness-ping": [
        ("        if time.monotonic() - self._last_used > LIVENESS_IDLE_SECONDS:",
         "        if False:"),
    ],
}

if OUT.resolve().is_relative_to(REPO.resolve()):
    raise SystemExit("refusing: output inside the repository")

for name, edits in MUTANTS.items():
    root = OUT / name
    if root.exists():
        shutil.rmtree(root)
    for relative in [PROXY, *TESTS]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)
    source_path = root / PROXY
    source = source_path.read_text(encoding="utf-8")
    for old, new in edits:
        if source.count(old) != 1:
            raise SystemExit(f"{name}: anchor not found exactly once: {old[:60]!r}")
        source = source.replace(old, new)
    source_path.write_text(source, encoding="utf-8")
    assert not (REPO / PROXY).samefile(source_path)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(root / TESTS[0]), "-q", "-p", "no:cacheprovider",
             "--rootdir", str(root)],
            capture_output=True, text=True, timeout=300, cwd=root,
        )
    except subprocess.TimeoutExpired:
        print(f"{name}: TIMEOUT after 300s (a test hung = mutant detected by hang)", flush=True)
        continue
    failed = [line.split(" - ")[0] for line in completed.stdout.splitlines() if line.startswith("FAILED")]
    summary = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else completed.stderr[-300:]
    print(f"{name}: {summary}", flush=True)
    for line in failed:
        print(f"    {line.split('::')[-1]}", flush=True)
