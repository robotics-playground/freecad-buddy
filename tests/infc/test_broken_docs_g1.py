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
import shutil
import sys
import tempfile
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
_AMBIENT_BUILD_FLAG = os.environ.get(_BUILD_FLAG)


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

    def test_import_without_the_enabling_flag_does_not_rebuild(self):
        """Import must create, remove, or modify nothing under the fixture root."""
        fixtures = sorted(BROKEN_DIR.glob("*/fixture.FCStd"))
        self.assertEqual(
            len(fixtures),
            EXPECTED_COUNT,
            f"expected {EXPECTED_COUNT} fixtures, found {len(fixtures)}",
        )
        before = self._fixture_tree_digest()

        self.addCleanup(self._restore_flag, os.environ.get(_BUILD_FLAG))
        for flag_value in (None, "0", ""):
            with self.subTest(flag=flag_value):
                if flag_value is None:
                    os.environ.pop(_BUILD_FLAG, None)
                else:
                    os.environ[_BUILD_FLAG] = flag_value
                module = self._load_generator_afresh()
                self.assertFalse(module._build_requested())
                self.assertEqual(
                    before,
                    self._fixture_tree_digest(),
                    "import must not add, drop, or modify any file under the fixture root",
                )

    def test_enabling_flag_runs_the_build_at_module_level(self):
        """With the flag on, importing the module builds — into ``base_dir``, not over commits."""
        before = self._fixture_tree_digest()
        target = Path(tempfile.mkdtemp(prefix="fcb_broken_docs_build_"))
        self.addCleanup(shutil.rmtree, target, True)
        self.addCleanup(self._restore_flag, os.environ.get(_BUILD_FLAG))
        os.environ[_BUILD_FLAG] = "1"

        module = self._load_generator_afresh(build_into=target)

        self.assertTrue(module._build_requested())
        self.assertEqual(
            sorted(p.parent.name for p in target.glob("*/fixture.FCStd")),
            sorted(gen.CASES),
            "the module-level build must write every case into base_dir",
        )
        self.assertEqual(
            before,
            self._fixture_tree_digest(),
            "a redirected build must leave the committed fixtures untouched",
        )

    def test_build_flag_enables_only_on_the_documented_value(self):
        """The opt-in fires for "1" and stays off for absent, empty, and non-enabling values."""
        for value, expected in (("1", True), ("0", False), ("", False), ("true", False)):
            with self.subTest(value=value):
                self.assertIs(gen._build_requested_in({_BUILD_FLAG: value}), expected)
        self.assertFalse(gen._build_requested_in({}))

    def test_build_flag_was_not_ambiently_set_when_the_suite_started(self):
        """An ambient enabling flag would let any import of the generator rewrite the fixtures."""
        self.assertNotEqual(_AMBIENT_BUILD_FLAG, "1")

    def test_case_set_equality_and_count(self):
        case_dirs = {p.parent.name for p in BROKEN_DIR.rglob("case.yaml")}
        generator_ids = set(gen.CASES)
        committed = {p.parent.name for p in BROKEN_DIR.rglob("fixture.FCStd")}
        self.assertEqual(case_dirs, generator_ids, "case dirs vs generator CASES")
        self.assertEqual(committed, generator_ids, "committed fixtures vs generator CASES")
        self.assertEqual(len(generator_ids), EXPECTED_COUNT, "expected exactly 30 cases")

    def _fixture_tree_digest(self) -> dict:
        """Path -> sha256 for every file under the fixture root, so new files show up too."""
        return {
            p.relative_to(BROKEN_DIR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(BROKEN_DIR.rglob("*"))
            if p.is_file()
        }

    def _load_generator_afresh(self, build_into: Path | None = None):
        """Execute the generator as a throwaway module.

        ``build_into`` runs a byte-identical copy from that directory instead, so the module's
        own ``HERE = Path(__file__).parent`` points there and a build cannot reach the commits.
        """
        generator_path = BROKEN_DIR / "build_broken_docs.py"
        if build_into is not None:
            generator_path = Path(shutil.copy2(generator_path, build_into))
        spec = importlib.util.spec_from_file_location("_broken_docs_reimport", generator_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _restore_flag(self, saved_flag: str | None) -> None:
        """Restore the flag, never re-arming an enabling value the suite must not run under."""
        if saved_flag is None or saved_flag == "1":
            os.environ.pop(_BUILD_FLAG, None)
        else:
            os.environ[_BUILD_FLAG] = saved_flag


if __name__ == "__main__":
    unittest.main()
