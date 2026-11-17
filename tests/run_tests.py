"""In-FreeCAD test runner (decision 002).

Run via ``FreeCADCmd -u <temp>/user.cfg -s <temp>/system.cfg tests/run_tests.py`` — never a
foreign ``python -c "import FreeCAD"`` (sidesteps the conda PYTHONPATH edge, feedstock #21).
FreeCADCmd writes both profile files on exit, so a run without ``-u``/``-s`` rewrites the
developer's own. Discovers stdlib-unittest suites
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


def _is_top_level_script() -> bool:
    """Whether this file is the script the interpreter was launched with.

    FreeCADCmd runs a script with ``__name__`` set to the file stem rather than ``"__main__"``
    on some platforms, so the standard guard alone would silently skip discovery; this also
    matches ``__file__`` against every launch argument, because options such as ``-u <cfg>``
    come before the script.
    """
    if __name__ == "__main__":
        return True
    own = Path(__file__).resolve()
    return any(Path(arg).resolve() == own for arg in sys.argv[1:])


if _is_top_level_script():
    sys.exit(main())
