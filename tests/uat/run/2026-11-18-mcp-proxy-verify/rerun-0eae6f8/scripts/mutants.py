"""Copy the proxy + its tests into scratch copies, apply one mutant each, run the builder's tests.

    uv run --no-sync --project <repo> python mutants.py <repo> <scratch-out> [mutant ...]
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
ONLY = set(sys.argv[3:])
PROXY = "scripts/automation/mcp_cache_proxy.py"
TESTS = ["tests/external/test_mcp_cache_proxy.py", "tests/external/fake_mcp_upstream.py"]
NL = "\n"

MUTANTS = {
    "M0-none": [],
    "M1-drop-structuredContent": [
        ("        self._last_used = time.monotonic()" + NL + "        return result" + NL,
         "        self._last_used = time.monotonic()" + NL
         + "        return types.CallToolResult(content=result.content, isError=result.isError)" + NL),
    ],
    "M2-resend-after-connection-closed": [
        ("            if error.error.code == types.CONNECTION_CLOSED:" + NL
         + "                await self._retire(connection)" + NL
         + "                raise OutcomeUnknown(str(error)) from error" + NL,
         "            if error.error.code == types.CONNECTION_CLOSED:" + NL
         + "                raise _NotDelivered(str(error)) from error" + NL),
    ],
    "M2b-resend-after-connection-ended": [
        ("        except _ConnectionEnded as error:" + NL
         + "            await self._retire(connection)" + NL
         + "            raise OutcomeUnknown(str(error)) from error",
         "        except _ConnectionEnded as error:" + NL
         + "            raise _NotDelivered(str(error)) from error"),
    ],
    "M3-no-retry-on-session-terminated": [
        ("        except _NotDelivered:" + NL + "            await self._retire(connection)" + NL
         + "        connection = await self._ensure()",
         "        except _NotDelivered as error:" + NL + "            await self._retire(connection)" + NL
         + "            raise UpstreamUnavailable('no retry') from error" + NL
         + "        connection = await self._ensure()"),
    ],
    "M4-no-probe-before-connect": [
        ("            if self._spec.probe is not None and identity is None:", "            if False:"),
    ],
    "M5-no-list-changed": [
        ("                await self._client_session.send_tool_list_changed()", "                pass"),
    ],
    "M6-no-reconnect-lock": [
        ("    async def _ensure(self) -> _Connection:" + NL + "        async with self._lock:",
         "    async def _ensure(self) -> _Connection:" + NL + "        async with asyncio.Lock():"),
    ],
    "M7-close-with-calls-in-flight": [
        ("        if connection.in_flight == 0:" + NL + "            await self._close(connection)" + NL + NL
         + "    async def _close",
         "        if True:" + NL + "            await self._close(connection)" + NL + NL + "    async def _close"),
    ],
    "M8-no-liveness-ping": [
        ("        elif time.monotonic() - self._last_used > LIVENESS_IDLE_SECONDS:", "        elif False:"),
    ],
    "M9-no-in-flight-watch-HANG": [
        ("        watcher = asyncio.ensure_future(self._watch(connection))",
         "        watcher = asyncio.ensure_future(asyncio.sleep(10**6))"),
    ],
    "M10-no-probe-before-send": [
        ("        if self._spec.probe is not None and await self._probe() != connection.identity:",
         "        if False:"),
    ],
    "M11-refresh-loop-catches-only-unavailable": [
        ("            except Exception as error:" + NL + "                # The loop",
         "            except UpstreamUnavailable as error:" + NL + "                # The loop"),
    ],
    "M12-shared-tmp-name": [
        ('f"{self._cache_path.name}.{uuid.uuid4().hex}.tmp"', 'f"{self._cache_path.name}.tmp"'),
    ],
    "M13-no-cache-validation": [
        ("            for tool in tools:" + NL + "                types.Tool.model_validate(tool)" + NL, ""),
    ],
}

if OUT.resolve().is_relative_to(REPO.resolve()):
    raise SystemExit("refusing: output inside the repository")

for name, edits in MUTANTS.items():
    if ONLY and name not in ONLY:
        continue
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
            raise SystemExit(f"{name}: anchor not found exactly once: {old[:70]!r}")
        source = source.replace(old, new)
    source_path.write_text(source, encoding="utf-8")
    assert not (REPO / PROXY).samefile(source_path)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(root / TESTS[0]), "-q", "-p", "no:cacheprovider",
             "--rootdir", str(root), "--durations=2"],
            capture_output=True, text=True, timeout=600, cwd=root,
        )
    except subprocess.TimeoutExpired:
        print(f"{name}: SUITE TIMEOUT after 600s (a test hung past its bound)", flush=True)
        subprocess.run(["taskkill", "/F", "/T", "/FI", f"WINDOWTITLE eq {name}"], capture_output=True)
        continue
    lines = completed.stdout.splitlines()
    failed = [line.split(" - ")[0] for line in lines if line.startswith("FAILED")]
    durations = [line.strip() for line in lines if line.strip()[:1].isdigit() and "s call" in line][:2]
    summary = lines[-1] if lines else completed.stderr[-300:]
    print(f"{name}: {summary} (wall {time.monotonic() - started:.0f}s) slowest={durations}", flush=True)
    for line in failed:
        print(f"    {line.split('::')[-1]}", flush=True)
