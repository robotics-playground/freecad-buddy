"""In-FreeCAD broken-doc self-check (stdlib unittest, discovered by tests/run_tests.py).

Opens each committed G1 broken-doc ``fixture.FCStd``, recomputes, and asserts the case's named
``expected.object`` exists and is genuinely in error (``getStatusString()`` non-empty) — an
independent self-check that every committed fixture really breaks on its named object (G1.2
requires *the* failing object). Opens documents via raw ``App.openDocument`` (a raw open in a
test is acceptable here); every opened doc is closed.
"""

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

import FreeCAD as App
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BROKEN_DIR = REPO_ROOT / "benchmarks" / "g1" / "dev" / "broken-docs"

sys.path.insert(0, str(BROKEN_DIR))
import build_broken_docs as gen  # noqa: E402

EXPECTED_COUNT = 30
_BUILD_FLAG = gen._BUILD_FLAG


def _load_case(case_id: str) -> dict:
    return yaml.safe_load((BROKEN_DIR / case_id / "case.yaml").read_text(encoding="utf-8"))


class BrokenDocsG1Test(unittest.TestCase):
    def test_each_committed_fixture_is_broken_on_its_named_object(self):
        """Open, recompute, assert the named object is in error (non-empty status string)."""
        for case_id in gen.CASES:
            case = _load_case(case_id)
            expected_object = case["expected"]["object"]
            fcstd = BROKEN_DIR / case_id / "fixture.FCStd"
            self.assertTrue(fcstd.is_file(), f"missing committed fixture {fcstd}")
            doc = App.openDocument(str(fcstd))
            try:
                doc.recompute()
                obj = doc.getObject(expected_object)
                self.assertIsNotNone(
                    obj, f"{case_id}: expected object {expected_object!r} not in document"
                )
                status = obj.getStatusString()
                self.assertTrue(
                    status,
                    f"{case_id}: object {expected_object!r} is not in error "
                    f"(empty getStatusString())",
                )
            finally:
                App.closeDocument(doc.Name)

    def test_import_with_generator_path_as_argv_does_not_rebuild(self):
        """Import with argv[1] set to the generator's own path must not touch any fixture."""
        fixtures = sorted(BROKEN_DIR.rglob("fixture.FCStd"))
        self.assertEqual(len(fixtures), EXPECTED_COUNT, "no fixtures to compare against")
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures}

        generator_path = BROKEN_DIR / "build_broken_docs.py"
        saved_argv = sys.argv[:]
        saved_flag = os.environ.get(_BUILD_FLAG)
        self.addCleanup(self._restore_argv_and_flag, saved_argv, saved_flag)
        sys.argv = [str(generator_path), str(generator_path)]
        os.environ.pop(_BUILD_FLAG, None)

        spec = importlib.util.spec_from_file_location("_broken_docs_reimport", generator_path)
        self.assertIsNotNone(spec, f"cannot load {generator_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertFalse(module._build_requested(), "build must not be requested without the flag")
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures}
        self.assertEqual(before, after, "import must not modify any committed fixture")

    def test_build_flag_enables_only_on_the_documented_value(self):
        """The opt-in fires for "1" and stays off for absent, empty, and non-enabling values."""
        saved_flag = os.environ.get(_BUILD_FLAG)
        self.addCleanup(self._restore_argv_and_flag, sys.argv[:], saved_flag)
        for value, expected in (("1", True), ("0", False), ("", False), ("true", False)):
            with self.subTest(value=value):
                os.environ[_BUILD_FLAG] = value
                self.assertIs(gen._build_requested(), expected)
        os.environ.pop(_BUILD_FLAG, None)
        self.assertFalse(gen._build_requested())

    def test_build_flag_is_not_set_while_the_suite_runs(self):
        """An ambient enabling flag would let any import of the generator rewrite the fixtures."""
        self.assertNotEqual(os.environ.get(_BUILD_FLAG), "1")

    def _restore_argv_and_flag(self, saved_argv: list, saved_flag) -> None:
        sys.argv = saved_argv
        if saved_flag is None:
            os.environ.pop(_BUILD_FLAG, None)
        else:
            os.environ[_BUILD_FLAG] = saved_flag

    def test_case_set_equality_and_count(self):
        case_dirs = {p.parent.name for p in BROKEN_DIR.rglob("case.yaml")}
        generator_ids = set(gen.CASES)
        committed = {p.parent.name for p in BROKEN_DIR.rglob("fixture.FCStd")}
        self.assertEqual(case_dirs, generator_ids, "case dirs vs generator CASES")
        self.assertEqual(committed, generator_ids, "committed fixtures vs generator CASES")
        self.assertEqual(len(generator_ids), EXPECTED_COUNT, "expected exactly 30 cases")


if __name__ == "__main__":
    unittest.main()
