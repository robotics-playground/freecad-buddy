"""Deterministic FreeCADCmd generator for the 5 G0 golden reference models (AD-13).

Run under FreeCADCmd (``FreeCADCmd build_golden_models.py``); the ``tests/infc`` self-check
imports ``MODELS``/``build_model`` and re-measures both the committed ``.FCStd`` and a fresh
rebuild against the independently hand-computed ``expected.yaml``.

Each model uses fixed object ``Name``s and placements so the shapes are reproducible. The
scored fields are volume/bbox/solid-count (measured by the self-check); ``expected.yaml``
also carries a documentary ``serializer: exportBinary`` marker noting the serializer the
Story-1.6 ``fingerprint()`` oracle will hash with — this generator commits no fingerprint
hash (a ``saveAs`` zip is not byte-reproducible, so a committed hash would be unverifiable).
"""

from __future__ import annotations

import os
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent


def _box_10_20_30():
    return Part.makeBox(10, 20, 30)


def _cylinder_r5_h20():
    return Part.makeCylinder(5, 20)


def _sphere_r10():
    return Part.makeSphere(10)


def _box40_hole_r5():
    block = Part.makeBox(40, 40, 10)
    hole = Part.makeCylinder(5, 10, App.Vector(20, 20, 0))
    return block.cut(hole)


def _two_box_compound():
    first = Part.makeBox(10, 10, 10)
    second = Part.makeBox(10, 10, 10, App.Vector(20, 0, 0))
    return Part.makeCompound([first, second])


# id -> (object Name, shape builder). Order fixed for determinism.
MODELS: dict[str, tuple[str, callable]] = {
    "box-10-20-30": ("Box", _box_10_20_30),
    "cylinder-r5-h20": ("Cylinder", _cylinder_r5_h20),
    "sphere-r10": ("Sphere", _sphere_r10),
    "box40-hole-r5": ("BoxHole", _box40_hole_r5),
    "two-box-compound": ("TwoBoxCompound", _two_box_compound),
}


def build_model(model_id: str) -> Part.Shape:
    """Return the reference shape for ``model_id`` (no document involved)."""
    _, builder = MODELS[model_id]
    return builder()


def _save(model_id: str, out_dir: Path) -> Path:
    obj_name, _ = MODELS[model_id]
    shape = build_model(model_id)
    doc = App.newDocument(model_id)
    feature = doc.addObject("Part::Feature", obj_name)
    feature.Shape = shape
    doc.recompute()
    target = out_dir / f"{model_id}.FCStd"
    doc.saveAs(str(target))
    App.closeDocument(doc.Name)
    return target


def build_all(out_dir: Path | None = None) -> list[Path]:
    out_dir = out_dir or HERE
    os.makedirs(out_dir, exist_ok=True)
    return [_save(model_id, out_dir) for model_id in MODELS]


if __name__ == "__main__":
    for path in build_all():
        print(f"wrote {path}")
