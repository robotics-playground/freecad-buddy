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
# Make the package importable under FreeCADCmd without a global `pip install -e .` (CI installs
# it; local FreeCADCmd runs off the source tree). Editable installs still take precedence.
SRC = HERE.parent / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(HERE / "infc"), top_level_dir=str(HERE))
    # Pin the stream to stderr: under FreeCADCmd the default stream binding is not surfaced,
    # so failures would otherwise run silently. stdout stays clean for any stdio protocol.
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stderr)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
