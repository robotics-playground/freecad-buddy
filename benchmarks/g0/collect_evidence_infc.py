"""In-FreeCADCmd evidence collector for G0.3 (golden suite) and G0.5 (STEP round-trip).

Runs under ``FreeCADCmd`` with the collection opt-in set, so that importing this module never
starts a collection run::

    FREECAD_BUDDY_RUN_EVIDENCE_COLLECTOR=1 FreeCADCmd collect_evidence_infc.py --run <id>

It writes two evidence report JSONs into the passed ``--run <id>``
dir; the runner's ``run`` command ingests + re-derives them into ``reports/``. Each report is
built via ``report_build.evidence_report`` — the verdict is DERIVED from measured checks, never
asserted, so this collector cannot self-grade (AD-13).

Stdlib + FreeCAD + contracts only (this is the ONLY FreeCAD-touching new file).

Usage: ``FreeCADCmd benchmarks/g0/collect_evidence_infc.py --run <id>``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SRC = REPO_ROOT / "src"
for _p in (str(SRC), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness.report_build import evidence_report  # noqa: E402

GOLDEN_DIR = HERE / "golden-models"
_REL_TOL = 0.001


def _load_expected() -> dict:
    """Parse the small fixed ``expected.yaml`` shape without pyyaml (AD-12: no ext deps here)."""
    text = (GOLDEN_DIR / "expected.yaml").read_text(encoding="utf-8")
    models: dict[str, dict] = {}
    current: str | None = None
    in_models = False
    for raw in text.splitlines():
        if raw.strip().startswith("#") or not raw.strip():
            continue
        if raw.startswith("models:"):
            in_models = True
            continue
        if not in_models:
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if indent == 2 and stripped.endswith(":"):
            current = stripped[:-1]
            models[current] = {}
        elif current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            value = value.strip()
            if value.startswith("["):
                models[current][key.strip()] = [
                    float(v) for v in value[1:-1].split(",") if v.strip()
                ]
            else:
                models[current][key.strip()] = float(value)
    return models


def _rel_close(measured: float, expected: float) -> bool:
    if expected == 0:
        return abs(measured) <= _REL_TOL
    return abs(measured - expected) / abs(expected) <= _REL_TOL


def _bbox_triple(shape) -> list[float]:
    bb = shape.BoundBox
    return [bb.XLength, bb.YLength, bb.ZLength]


def _golden_check(model_id: str, shape, spec: dict) -> dict:
    """One G0.3 check per golden model: volume ∧ bbox ∧ solid count within ±0.1%."""
    vol_ok = _rel_close(shape.Volume, spec["volume"])
    bbox_ok = all(_rel_close(m, e) for m, e in zip(_bbox_triple(shape), spec["bbox"]))
    solids_ok = len(shape.Solids) == int(spec["solids"])
    passed = vol_ok and bbox_ok and solids_ok
    return {
        "id": f"G0.3.{model_id}",
        "measured": {
            "volume": shape.Volume,
            "bbox": _bbox_triple(shape),
            "solids": len(shape.Solids),
        },
        "expected": {"volume": spec["volume"], "bbox": spec["bbox"], "solids": spec["solids"]},
        "passed": passed,
        "detail": {
            "code": "ok" if passed else "spec_failed.golden_mismatch",
            "message": f"{model_id}: volume={vol_ok} bbox={bbox_ok} solids={solids_ok}",
        },
    }


def collect_g0_3() -> dict:
    """Open each committed golden model, measure its shape, build the G0.3 evidence report."""
    expected = _load_expected()
    checks = []
    for model_id, spec in expected.items():
        doc = App.openDocument(str(GOLDEN_DIR / f"{model_id}.FCStd"))
        try:
            checks.append(_golden_check(model_id, doc.Objects[0].Shape, spec))
        finally:
            App.closeDocument(doc.Name)
    return evidence_report("G0.3", checks, _banner())


def collect_g0_5() -> dict:
    """Create a box → export STEP → re-import → compare volume/isValid/topology counts."""
    doc = App.newDocument("FCB_TMP_g0_5")
    step_path = Path(App.getUserAppDataDir()) / "fcb_g0_5_roundtrip.step"
    try:
        source = doc.addObject("Part::Feature", "Src")
        source.Shape = Part.makeBox(10, 20, 30)
        doc.recompute()
        src = source.Shape
        src.exportStep(str(step_path))

        reimported = Part.Shape()
        reimported.read(str(step_path))

        vol_ok = _rel_close(reimported.Volume, src.Volume)
        valid_ok = bool(reimported.isValid())
        counts_ok = (
            len(reimported.Solids) == len(src.Solids)
            and len(reimported.Faces) == len(src.Faces)
            and len(reimported.Edges) == len(src.Edges)
        )
        passed = vol_ok and valid_ok and counts_ok
        check = {
            "id": "G0.5.step_roundtrip",
            "measured": {
                "volume": reimported.Volume,
                "isValid": valid_ok,
                "solids": len(reimported.Solids),
                "faces": len(reimported.Faces),
                "edges": len(reimported.Edges),
            },
            "expected": {
                "volume": src.Volume,
                "isValid": True,
                "solids": len(src.Solids),
                "faces": len(src.Faces),
                "edges": len(src.Edges),
            },
            "passed": passed,
            "detail": {
                "code": "ok" if passed else "spec_failed.step_roundtrip",
                "message": f"volume={vol_ok} isValid={valid_ok} counts={counts_ok}",
            },
        }
        return evidence_report("G0.5", [check], _banner())
    finally:
        App.closeDocument(doc.Name)
        if step_path.exists():
            step_path.unlink()


def _banner() -> dict:
    return {"freecad_version": ".".join(App.Version()[:3]), "element_map_version": None}


def _write(run_dir: Path, criterion: str, report: dict) -> None:
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{criterion}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="collect_evidence_infc.py")
    parser.add_argument("--run", dest="run_id", required=True)
    args = parser.parse_args(argv)

    run_dir = REPO_ROOT / "benchmarks" / "gate-artifacts" / "g0" / args.run_id
    _write(run_dir, "G0.3", collect_g0_3())
    _write(run_dir, "G0.5", collect_g0_5())
    sys.stderr.write(f"collect_evidence_infc: wrote G0.3 + G0.5 into {run_dir / 'evidence'}\n")
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_EVIDENCE_COLLECTOR"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit collection-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether direct execution or an explicit opt-in asked for a collection run.

    An import never collects: ``__name__`` is the module name and the flag is absent.
    """
    return __name__ == "__main__" or _run_requested_in(os.environ)


if _run_requested():
    # FreeCADCmd passes the script path as argv[1]; user args follow.
    _launched_by_path = bool(sys.argv[1:]) and Path(sys.argv[1]).name == Path(__file__).name
    _args = sys.argv[2:] if _launched_by_path else sys.argv[1:]
    sys.exit(main(_args))
