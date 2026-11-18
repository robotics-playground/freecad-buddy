"""Why does a call on a live HTTP session hang when the upstream port is closed (no liveness ping)?"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "none"]
import verify_proxy as v  # noqa: E402  (module body runs main() with probe "none": no probes)

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
for noisy in ("httpcore", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def main():
    tmp = v.OUT / "tmp"
    http = v.Http(tmp / "debug.txt")
    http.start()
    v.pm.LIVENESS_IDLE_SECONDS = 3600.0
    upstream = v.pm.Upstream(http.spec())
    await upstream.call_tool("pid", {})
    connection = upstream._current
    http.stop()
    task = asyncio.ensure_future(upstream.call_tool("pid", {}))
    await asyncio.sleep(10)
    print("call done:", task.done(), "owner done:", connection.owner.done(), flush=True)
    if connection.owner.done():
        print("owner exc:", connection.owner.exception(), flush=True)
    print("pending response streams:", list(connection.session._response_streams), flush=True)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.wait_for(upstream._close(connection), 10)


asyncio.run(main())
