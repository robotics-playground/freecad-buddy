"""In-FreeCAD golden-model self-check (stdlib unittest, discovered by tests/run_tests.py).

Validates the COMMITTED .FCStd fixtures against the independently hand-computed
``expected.yaml`` (independent-oracle self-check, AD-13). Opens documents via raw
``App.openDocument`` — the AD-20 ``document_*`` usecases do not exist yet (Story 1.4), so a
raw open in a TEST is acceptable here; every opened doc is closed.
"""

import sys
import unittest
from pathlib import Path

import FreeCAD as App
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "benchmarks" / "g0" / "golden-models"

sys.path.insert(0, str(GOLDEN_DIR))
import build_golden_models as gen  # noqa: E402

# Models that are single closed solids (two-box-compound is a 2-solid compound: skip isValid
# sweep expectation of a single solid, but it is still a valid shape).
SOLID_MODELS = {"box-10-20-30", "cylinder-r5-h20", "sphere-r10", "box40-hole-r5"}


def _load_expected() -> dict:
    return yaml.safe_load((GOLDEN_DIR / "expected.yaml").read_text(encoding="utf-8"))


def _bbox_triple(shape) -> list[float]:
    bb = shape.BoundBox
    return [bb.XLength, bb.YLength, bb.ZLength]


def _rel_close(measured: float, expected: float, rel: float) -> bool:
    if expected == 0:
        return abs(measured) <= rel
    return abs(measured - expected) / abs(expected) <= rel


class GoldenModelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = _load_expected()
        cls.rel = cls.expected["tolerance"]["rel"]
        cls.models = cls.expected["models"]

    def _assert_shape_matches(self, model_id: str, shape, where: str):
        spec = self.models[model_id]
        self.assertTrue(
            _rel_close(shape.Volume, spec["volume"], self.rel),
            f"{model_id} [{where}] volume {shape.Volume} != {spec['volume']}",
        )
        for axis, (measured, expected) in enumerate(zip(_bbox_triple(shape), spec["bbox"])):
            self.assertTrue(
                _rel_close(measured, expected, self.rel),
                f"{model_id} [{where}] bbox[{axis}] {measured} != {expected}",
            )
        self.assertEqual(
            len(shape.Solids),
            spec["solids"],
            f"{model_id} [{where}] solids {len(shape.Solids)} != {spec['solids']}",
        )

    def test_committed_fcstd_match_expected(self):
        """Open every committed .FCStd and re-measure (catches a stale/corrupt file)."""
        for model_id in self.models:
            fcstd = GOLDEN_DIR / f"{model_id}.FCStd"
            self.assertTrue(fcstd.is_file(), f"missing committed model {fcstd}")
            doc = App.openDocument(str(fcstd))
            try:
                self.assertEqual(
                    len(doc.Objects), 1,
                    f"{model_id}: committed doc has {len(doc.Objects)} objects, expected 1",
                )
                shape = doc.Objects[0].Shape
                self._assert_shape_matches(model_id, shape, "committed")
                if model_id in SOLID_MODELS:
                    self.assertTrue(shape.isValid(), f"{model_id} committed shape !isValid()")
            finally:
                App.closeDocument(doc.Name)

    def test_regenerate_and_remeasure_drift(self):
        """Rebuild each model in-process and re-measure (guards generator drift)."""
        for model_id in self.models:
            shape = gen.build_model(model_id)
            self._assert_shape_matches(model_id, shape, "regenerated")

    def test_model_id_set_equality_all_directions(self):
        expected_ids = set(self.models)
        generator_ids = set(gen.MODELS)
        committed_ids = {p.stem for p in GOLDEN_DIR.glob("*.FCStd")}
        self.assertEqual(expected_ids, generator_ids, "expected.yaml vs generator MODELS")
        self.assertEqual(expected_ids, committed_ids, "expected.yaml vs committed *.FCStd")


if __name__ == "__main__":
    unittest.main()
