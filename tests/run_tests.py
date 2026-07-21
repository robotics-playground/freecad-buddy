"""In-FreeCAD test runner (decision 002).

Run via ``FreeCADCmd tests/run_tests.py`` — never a foreign ``python -c "import FreeCAD"``
(sidesteps the conda PYTHONPATH edge, feedstock #21). Discovers stdlib-unittest suites
under tests/infc/ and runs them in one process. Phase 0: no cases yet → empty discovery
passes (exit 0). This is tooling, not src/, so stdout use is fine.
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(HERE / "infc"), top_level_dir=str(HERE))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
