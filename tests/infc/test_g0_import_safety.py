"""In-FreeCAD import-safety check for the G0 generators, scorers, and collector.

Each of these modules carries a module-level side effect — rebuilding committed fixtures,
running a scoring pass that rewrites ``_registry/validators.yaml``, or running an evidence
collection — behind a guard. Importing any of them for its helpers must never fire that guard,
including when ``sys.argv[1]`` happens to be the module's own path (the condition the previous
argv-matching guard keyed on, reachable because ``tests/infc`` imports several of these modules
inside the same ``FreeCADCmd tests/run_tests.py`` process).
"""

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
G0_DIR = REPO_ROOT / "benchmarks" / "g0"
EXPORT_FAULT_DIR = G0_DIR / "export-fault-injection"
FAULT_DIR = G0_DIR / "fault-injection"

for _path in (EXPORT_FAULT_DIR, FAULT_DIR, G0_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# (module path, flag attribute, opt-in predicate attribute)
GUARDED_MODULES = (
    (EXPORT_FAULT_DIR / "build_export_fault_fixtures.py", "_BUILD_FLAG", "_build_requested"),
    (EXPORT_FAULT_DIR / "score_export_verify.py", "_RUN_FLAG", "_run_requested"),
    (FAULT_DIR / "score_verify_shape.py", "_RUN_FLAG", "_run_requested"),
    (G0_DIR / "collect_evidence_infc.py", "_RUN_FLAG", "_run_requested"),
)

_AMBIENT_FLAGS = {
    "FREECAD_BUDDY_BUILD_EXPORT_FAULT_FIXTURES": os.environ.get(
        "FREECAD_BUDDY_BUILD_EXPORT_FAULT_FIXTURES"
    ),
    "FREECAD_BUDDY_RUN_EXPORT_SCORER": os.environ.get("FREECAD_BUDDY_RUN_EXPORT_SCORER"),
    "FREECAD_BUDDY_RUN_FAULT_SCORER": os.environ.get("FREECAD_BUDDY_RUN_FAULT_SCORER"),
    "FREECAD_BUDDY_RUN_EVIDENCE_COLLECTOR": os.environ.get("FREECAD_BUDDY_RUN_EVIDENCE_COLLECTOR"),
}


def _import_fresh(module_path: Path):
    """Import ``module_path`` under a throwaway name so module-level code really re-runs."""
    name = f"_import_safety_{module_path.stem}"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


class G0ImportSafetyTest(unittest.TestCase):
    def _suite_digest(self) -> str:
        """Digest every committed fixture and the validator registry."""
        digest = hashlib.sha256()
        paths = sorted(
            list(EXPORT_FAULT_DIR.glob("*/export.*"))
            + list(EXPORT_FAULT_DIR.glob("*/case.yaml"))
            + [REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"]
        )
        for path in paths:
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _restore_argv(self, argv):
        sys.argv = argv

    def _restore_flag(self, flag: str, value):
        if value is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = value

    def test_import_with_own_path_as_argv_has_no_side_effect(self):
        """The exact condition the old argv guard fired on must now be inert."""
        before = self._suite_digest()
        self.addCleanup(self._restore_argv, list(sys.argv))

        for module_path, flag_attr, predicate_attr in GUARDED_MODULES:
            with self.subTest(module=module_path.name):
                sys.argv = ["FreeCADCmd", str(module_path)]
                module = _import_fresh(module_path)
                predicate = getattr(module, predicate_attr)
                self.assertFalse(
                    predicate(),
                    f"{module_path.name} must not treat argv[1] as a run request",
                )
                self.assertEqual(
                    before,
                    self._suite_digest(),
                    f"importing {module_path.name} must not touch fixtures or the registry",
                )
                self.assertTrue(hasattr(module, flag_attr))

    def test_import_without_the_flag_has_no_side_effect(self):
        """Absent, empty, and non-enabling flag values all leave the guard closed."""
        before = self._suite_digest()

        for module_path, flag_attr, predicate_attr in GUARDED_MODULES:
            flag = getattr(_import_fresh(module_path), flag_attr)
            self.addCleanup(self._restore_flag, flag, os.environ.get(flag))
            for value in (None, "0", "", "true"):
                with self.subTest(module=module_path.name, flag=value):
                    if value is None:
                        os.environ.pop(flag, None)
                    else:
                        os.environ[flag] = value
                    module = _import_fresh(module_path)
                    self.assertFalse(getattr(module, predicate_attr)())
                    self.assertEqual(before, self._suite_digest())

    def test_opt_in_predicate_accepts_only_the_documented_value(self):
        for module_path, flag_attr, _ in GUARDED_MODULES:
            module = _import_fresh(module_path)
            flag = getattr(module, flag_attr)
            predicate_in = getattr(
                module,
                "_build_requested_in" if flag_attr == "_BUILD_FLAG" else "_run_requested_in",
            )
            with self.subTest(module=module_path.name):
                self.assertTrue(predicate_in({flag: "1"}))
                for value in ("0", "", "true", "yes"):
                    self.assertFalse(predicate_in({flag: value}))
                self.assertFalse(predicate_in({}))

    def test_no_enabling_flag_was_ambiently_set_when_the_suite_started(self):
        """An ambient enabling flag would let any import rewrite fixtures or the registry."""
        for flag, value in _AMBIENT_FLAGS.items():
            with self.subTest(flag=flag):
                self.assertNotEqual(value, "1")


if __name__ == "__main__":
    unittest.main()
