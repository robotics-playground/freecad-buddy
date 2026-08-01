"""Marshal must not be used to schedule work onto the thread that then blocks waiting for it.

The GUI addon's ``QtMainThreadExecutor.submit`` posts a Qt event; only the main thread's event
loop delivers it. ``start_bridge`` runs on that same main thread, so marshaling the capability
warm-up there queued an event the blocked thread could never dispatch — a self-deadlock that
burned the full 30 s budget on every GUI start and left the probes unrun.

Qt is unavailable outside FreeCAD, so the executor here is a faithful stand-in: ``submit``
enqueues, and delivery requires the owning thread to pump.
"""

from __future__ import annotations

import threading
import time

import pytest

from freecad_buddy.adapters.marshal import Marshal, MarshalTimeout


class QueueingExecutor:
    """Mirrors ``postEvent``: enqueue only; the owning thread must pump to deliver."""

    def __init__(self) -> None:
        self.queue: list = []

    def submit(self, fn) -> None:
        self.queue.append(fn)

    def process_events(self) -> None:
        while self.queue:
            self.queue.pop(0)()


def test_submitting_to_a_loop_this_thread_must_pump_deadlocks():
    """Pins the failure mode itself, so the shape stays recognisable if it reappears."""
    executor = QueueingExecutor()
    marshal = Marshal(executor)
    ran: list[int] = []

    start = time.monotonic()
    with pytest.raises(MarshalTimeout):
        marshal.call(lambda: ran.append(1), 0.2)

    assert ran == [], "the callable cannot run: the only thread that could deliver it is blocked"
    assert executor.queue, "the work stays queued rather than being dropped"
    assert time.monotonic() - start >= 0.2, "the caller waits out its whole budget"


def test_a_worker_thread_marshaling_into_a_pumped_loop_succeeds():
    """The designed direction still works — the fix must not be to abandon marshaling."""
    executor = QueueingExecutor()
    marshal = Marshal(executor)
    result: dict[str, object] = {}

    def worker() -> None:
        try:
            result["value"] = marshal.call(lambda: "probed", 2.0)
        except MarshalTimeout as exc:  # pragma: no cover - failure path, asserted below
            result["value"] = f"TIMEOUT {exc}"

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    deadline = time.monotonic() + 2.0
    while thread.is_alive() and time.monotonic() < deadline:
        executor.process_events()
        time.sleep(0.005)
    thread.join(timeout=1.0)

    assert result["value"] == "probed"


def test_start_bridge_warms_the_probes_without_marshaling_them():
    """``start_bridge`` already runs on the FreeCAD execution thread, so it must call directly.

    Asserted against the source because the real function needs FreeCAD, Qt and a live GUI. A
    ``marshal.call`` wrapping the warm-up is exactly the construct that deadlocked.
    """
    from pathlib import Path

    bootstrap = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "freecad_buddy"
        / "hosts"
        / "gui_addon"
        / "bootstrap.py"
    )
    source = bootstrap.read_text(encoding="utf-8")

    assert "warm_capability_probes" in source, "the warm-up must still happen"
    assert "marshal.call(shim.warm_capability_probes" not in source, (
        "warm_capability_probes must not be marshaled from start_bridge: that posts an event to "
        "the very thread start_bridge then blocks, so it can never be delivered"
    )
