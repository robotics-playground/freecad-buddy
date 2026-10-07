"""Time the bridge overhead of one parameter change on a large document, then prove an abort.

Runs inside FreeCAD, headless or as a GUI macro. Opens a copy of a document through
``DocumentRegistry`` with auto-approve on and repeats, five times:

- ``T``: ``feature_set_parameters`` sets ``<feature>.Length`` from A to B (the whole tool call:
  gate, snapshot, transaction, recompute, post-verify, commit, after-fingerprint);
- ``R``: a plain write of A back to ``Length`` and ``document.recompute()``.

After each ``R`` the document is fingerprinted, untimed. ``R`` rebuilds every object downstream of
the feature, so without it every ``T`` would pay a cold gate fingerprint of those objects. In an
agent loop the previous call's after-fingerprint has already cached the current shapes, so the
gate starts warm; this measures that case.

The overhead of one change is ``T - R``; the report gives each sample and the medians. It then runs
one ``run_mutation`` whose op sets ``Length`` and raises, and checks that the rollback is
``rolled_back_verified`` on the same document object and that ``FreeCAD.closeDocument`` was never
called. The document copy is never saved. The process exits non-zero when the run raised or the
abort check failed.

Inputs come from the environment, so the same file runs both ways:

- ``FCB_DRAWER_COPY`` (required): absolute path of the document copy to open;
- ``FCB_TIMING_OUT`` (required): absolute path of the JSON report to write;
- ``FCB_TIMING_FEATURE`` (default ``duct_pilot``), ``FCB_TIMING_LENGTHS`` (default ``6.0,5.5``,
  the A and B lengths in mm).

Headless::

    $env:FCB_DRAWER_COPY = "<copy>.FCStd"; $env:FCB_TIMING_OUT = "<report>.json"
    & "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" scripts/automation/time_mutation_overhead.py

In the GUI, start ``freecad.exe`` with the same variables and this file as its argument.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import traceback
from pathlib import Path
from typing import NoReturn

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import FreeCAD  # noqa: E402

from freecad_buddy.usecases import confirm, features, transaction  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402
from freecad_buddy.usecases.fingerprint import fingerprint  # noqa: E402

RUNS = 5


class _PlantedFailure(RuntimeError):
    """The failure the abort run's op raises after its write."""


def _length(value: float) -> dict:
    return {"Length": {"value": value, "unit": "mm"}}


def _time_runs(registry, handle, feature, length_a, length_b) -> list[dict]:
    samples = []
    for _ in range(RUNS):
        started = time.perf_counter()
        envelope = features.feature_set_parameters(
            registry, doc=handle, feature=feature, parameters=_length(length_b)
        )
        tool_seconds = time.perf_counter() - started
        if envelope["status"] != "OK":
            raise RuntimeError(f"feature_set_parameters failed: {envelope['detail']}")

        document = registry.with_document(handle, lambda _h, d: d)
        started = time.perf_counter()
        document.getObject(feature).Length = length_a
        document.recompute()
        recompute_seconds = time.perf_counter() - started
        fingerprint(document)
        samples.append(
            {
                "tool_seconds": tool_seconds,
                "recompute_seconds": recompute_seconds,
                "overhead_seconds": tool_seconds - recompute_seconds,
            }
        )
    return samples


def _abort_run(registry, handle, feature, length_b) -> dict:
    document = registry.with_document(handle, lambda _h, d: d)
    closed = []
    real_close = FreeCAD.closeDocument

    def recording_close(name):
        closed.append(name)
        return real_close(name)

    def op(target):
        target.getObject(feature).Length = length_b
        raise _PlantedFailure("planted failure after the Length write")

    FreeCAD.closeDocument = recording_close
    try:
        started = time.perf_counter()
        returned, envelope = transaction.run_mutation(document, handle, "timed abort", op)
        seconds = time.perf_counter() - started
    finally:
        FreeCAD.closeDocument = real_close
    block = envelope["structured_content"]["mutation"]
    return {
        "seconds": seconds,
        "status": envelope["status"],
        "rollback_proven": block["rollback_proven"],
        "same_document": returned is document,
        "close_document_calls": closed,
        "passed": (
            block["rollback_proven"] == "rolled_back_verified"
            and returned is document
            and not closed
        ),
    }


def _refuse(message: str) -> NoReturn:
    """Exit non-zero naming the fault; FreeCADCmd does not print a ``SystemExit`` message."""
    print(message, file=sys.stderr)
    raise SystemExit(1)


def _inputs() -> tuple[str, Path, str, float, float]:
    """Read and check the environment before anything runs; exit non-zero naming a fault."""
    copy = os.environ.get("FCB_DRAWER_COPY", "")
    out = os.environ.get("FCB_TIMING_OUT", "")
    if not os.path.isfile(copy):
        _refuse(f"FCB_DRAWER_COPY must name an existing document copy, got {copy!r}")
    if not out or not os.path.isdir(os.path.dirname(out)):
        _refuse(f"FCB_TIMING_OUT must name a file in an existing directory, got {out!r}")
    lengths = os.environ.get("FCB_TIMING_LENGTHS", "6.0,5.5")
    try:
        length_a, length_b = (float(value) for value in lengths.split(","))
    except ValueError:
        _refuse(f"FCB_TIMING_LENGTHS must be two numbers 'A,B', got {lengths!r}")
    feature = os.environ.get("FCB_TIMING_FEATURE", "duct_pilot")
    return copy, Path(out), feature, length_a, length_b


def main(copy: str, feature: str, length_a: float, length_b: float) -> dict:
    report: dict = {"document": copy, "feature": feature, "lengths": [length_a, length_b]}
    report["mode"] = "gui" if FreeCAD.GuiUp else "headless"
    previous = confirm.set_auto_approve(True)
    registry = DocumentRegistry()
    try:
        handle = registry.document_open(copy)["structured_content"]["doc"]
        document = registry.with_document(handle, lambda _h, d: d)
        report["objects"] = len(document.Objects)
        samples = _time_runs(registry, handle, feature, length_a, length_b)
        report["samples"] = samples
        for key in ("tool_seconds", "recompute_seconds", "overhead_seconds"):
            report[f"median_{key}"] = statistics.median(sample[key] for sample in samples)
        report["abort"] = _abort_run(registry, handle, feature, length_b)
    except Exception:  # noqa: BLE001 - the report must name the failure in either host
        report["error"] = traceback.format_exc()
    finally:
        confirm.set_auto_approve(previous)
    return report


_copy, _out, _feature, _length_a, _length_b = _inputs()
_report = main(_copy, _feature, _length_a, _length_b)
_out.write_text(json.dumps(_report, indent=2), encoding="utf-8")
print(json.dumps(_report, indent=2), file=sys.stderr)
if "error" in _report or not _report["abort"]["passed"]:
    sys.exit(1)
