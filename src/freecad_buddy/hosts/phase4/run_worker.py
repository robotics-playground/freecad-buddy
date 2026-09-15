"""Worker process entry: read a spec on stdin, run it, write the envelope to stdout.

Spawned by ``pool.WorkerPool`` as ``python -m freecad_buddy.hosts.phase4.run_worker``. A module
entry rather than a pickled callable because the pool owns a real subprocess — it needs the pid
to kill the tree, which ``ProcessPoolExecutor`` does not expose.

The protocol is deliberately small: JSON in on stdin, one JSON line out on stdout, diagnostics on
stderr, exit code says whether the process itself survived. stdout carries the protocol here for
the same reason it does under MCP stdio — a stray ``print`` corrupts it — so every diagnostic in
this process goes to stderr.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Run one job and exit. Return the process exit code.

    An exception from the payload exits non-zero WITHOUT writing an envelope, which the
    supervisor observes as a crash. The worker never names its own terminal status: status is the
    supervisor's (``status_map``), and a worker that could call itself ``OK`` would be the
    unchecked worker claim the whole design refuses.
    """
    try:
        spec = json.loads(sys.stdin.read() or "{}")
    except ValueError as exc:
        sys.stderr.write(f"worker: unreadable spec: {exc}\n")
        return 2

    from freecad_buddy.hosts.phase4.worker import run_job

    try:
        envelope = run_job(spec)
    except Exception as exc:  # noqa: BLE001 - the boundary turns any failure into an exit code
        sys.stderr.write(f"worker: {type(exc).__name__}: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(envelope))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
