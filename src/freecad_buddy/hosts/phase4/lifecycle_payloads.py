"""Payloads that exercise the job lifecycle without doing any CAD work.

Importing this module registers them. A spec naming ``payload_module:
"freecad_buddy.hosts.phase4.lifecycle_payloads"`` gets them in the worker process.

These exist because the lifecycle — spawn, deadline, tree-kill, crash, status — is what story 5.2
proves, and proving it needs jobs that fail in each specific way on demand. A design job cannot
be made to segfault reliably; ``crash`` can. They ship in ``src`` rather than in the tests
because the G4 fault suite drives them too, and a benchmark that imported a test module would
couple the gate to the test layout.

None of them imports FreeCAD: the lifecycle is indifferent to what the payload computes.
"""

from __future__ import annotations

import os
import sys
import time

from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.job import JobSpec
from freecad_buddy.hosts.phase4.worker import register


def echo(spec: JobSpec) -> ResultEnvelope:
    """Return immediately with the spec's payload — the clean-completion path."""
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": dict(spec.get("payload") or {}),
        "text": f"echo {spec.get('job_id', '')}",
    }


def sleep(spec: JobSpec) -> ResultEnvelope:
    """Sleep past any sane deadline — the hang the supervisor must be able to kill.

    Deliberately longer than the default deadline so a test cannot pass by accident when its
    own timeout is misconfigured.
    """
    time.sleep(3600)
    return echo(spec)


def spawn_child_then_sleep(spec: JobSpec) -> ResultEnvelope:
    """Spawn a grandchild, then hang — the orphan case a top-PID kill would leave behind.

    Writes the grandchild's pid to stderr so a test can assert the whole tree died, not just the
    worker. This is the payload that distinguishes a real tree-kill from a kill that looks right.
    """
    import subprocess

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    sys.stderr.write(f"grandchild_pid={child.pid}\n")
    sys.stderr.flush()
    time.sleep(3600)
    return echo(spec)


def crash(spec: JobSpec) -> ResultEnvelope:
    """Raise — the worker that dies mid-job."""
    raise RuntimeError("payload crashed on purpose")


def hard_exit(spec: JobSpec) -> ResultEnvelope:
    """Leave the process without unwinding — the abnormal exit no ``except`` can observe.

    ``os._exit`` skips cleanup entirely, which is the closest a pure-Python payload gets to the
    native OCCT fault the G4 suite plants. The supervisor must still resolve it rather than hang.
    """
    os._exit(3)


def allocate(spec: JobSpec) -> ResultEnvelope:
    """Allocate until the process is stopped — the runaway a memory ceiling must catch."""
    blocks = []
    while True:
        blocks.append(bytearray(64 * 1024 * 1024))


def silent_success(spec: JobSpec) -> ResultEnvelope:
    """Exit cleanly having written nothing — a worker claiming success it cannot evidence.

    The supervisor must refuse this rather than read the empty result as ``OK``; that refusal is
    the "HTTP 200 for a bad part" hole closed at the lifecycle level.
    """
    os._exit(0)


register("echo", echo)
register("sleep", sleep)
register("spawn_child_then_sleep", spawn_child_then_sleep)
register("crash", crash)
register("hard_exit", hard_exit)
register("allocate", allocate)
register("silent_success", silent_success)
