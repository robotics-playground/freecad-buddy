"""Drive the G4 fault cases against the stub service and write each validator's results file.

Unlike the G2/G3 drivers this one does NOT run inside FreeCAD. A G4 fault is a supervisor-level
event — a deadline, a memory cap, an abnormal exit, a re-check verdict — and none of them needs
geometry to decide. The stub answers each case from its own declaration, so the whole suite is
driveable in the uv environment.

That also bounds what these numbers mean, and the bound is recorded on every row rather than left
for a reader to infer: this measures whether the SUITE can separate a planted fault from a clean
control against a known-good mapping. It measures nothing about a real service, because there is
no real service. Story 5.2-5.4 replace the stub, and the same cases then measure the real thing.

Writes ``<validator>.json`` beside this file in the handoff shape every gate scorer reads:
``{"rows": [{"id", "outcome", "detected_by"}], "skipped": [{"id", "reason"}], ...}``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
G4_ROOT = HERE.parent
if str(G4_ROOT) not in sys.path:
    sys.path.insert(0, str(G4_ROOT))

from stub_service import (  # noqa: E402
    CLEAN_STATUS,
    JobStatusSchemaError,
    resolve,
)

# Carried onto every registry row this driver feeds. The measurement is real; what it measures is
# the suite against a declared mapping, not a service. A row without this reads as a service
# result, which would be the fabricated authority this whole registry exists to prevent.
GRADED_BY = (
    "benchmarks/g4/fault-injection/drive_g4_faults.py resolving each case against "
    "benchmarks/g4/stub_service.py, whose fault-to-status mapping was authored before any service "
    "exists. No job was run: no supervisor, worker pool or sandbox is implemented (stories "
    "5.2-5.4)."
)

INDEPENDENCE_CAVEAT = (
    "NOT a service measurement. The stub answers from each case's own declaration, so these bars "
    "demonstrate that the suite separates planted faults from clean controls against a known-good "
    "mapping — the entry-gate property (AD-19). A real sensitivity number requires the supervisor "
    "of story 5.2 and, for OOM_KILLED specifically, the sandbox of story 5.3: until that jail "
    "exists nothing here distinguishes a sandbox kill from a host OOM kill."
)


def _case_files() -> list[Path]:
    """Every G4 fault ``case.yaml``, ordered by suite-relative POSIX path.

    The exact-name filter keeps the set platform-independent: ``rglob`` is case-insensitive on
    Windows, so a miscased ``Case.YAML`` would otherwise be driven there and not on Linux CI.
    """
    return sorted(
        (p for p in HERE.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(HERE).as_posix(),
    )


def drive_case(case: dict) -> str:
    """Return the outcome vocabulary value for one case.

    Planted cases yield ``DETECTED`` / ``MISSED``; controls yield ``PASS_CLEAN`` /
    ``FALSE_ALARM``. A malformed answer counts as detection for a planted case, because refusing
    a bad shape is the service declining to ship it.
    """
    planted = (case.get("fault") or {}).get("kind") == "planted_defect"
    try:
        status = resolve(case)
        clean = status.get("state") == CLEAN_STATUS
    except JobStatusSchemaError:
        clean = False
    if planted:
        return "MISSED" if clean else "DETECTED"
    return "PASS_CLEAN" if clean else "FALSE_ALARM"


def drive() -> dict[str, dict]:
    """Drive every case; return ``{validator: results-file body}``."""
    by_validator: dict[str, dict] = {}
    for case_yaml in _case_files():
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"{case_yaml}: case.yaml must be a mapping")
        validator = str(data.get("targets_validator", "")).split("@", 1)[0]
        if not validator:
            raise SystemExit(f"{case_yaml}: missing 'targets_validator'")
        body = by_validator.setdefault(
            validator,
            {
                "rows": [],
                "skipped": [],
                "graded_by": GRADED_BY,
                "independence_caveat": INDEPENDENCE_CAVEAT,
            },
        )
        body["rows"].append(
            {
                "id": data["id"],
                "outcome": drive_case(data),
                "detected_by": data.get("detected_by"),
            }
        )
    return by_validator


def main(argv: list[str] | None = None) -> int:
    """Drive the suite and write one results file per validator.

    ``--check`` drives without writing, so the suite's structure can be verified while the working
    tree stays clean.
    """
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    results = drive()

    for validator, body in sorted(results.items()):
        counts: dict[str, int] = {}
        for row in body["rows"]:
            counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
        summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        sys.stderr.write(f"  {validator:20s} {len(body['rows']):2d} case(s)  {summary}\n")
        if not check_only:
            path = HERE / f"{validator}.json"
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    if check_only:
        sys.stderr.write("\n  --check: no results file written\n")
    else:
        sys.stderr.write(f"\n  wrote {len(results)} results file(s) under {HERE}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
