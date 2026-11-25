import sys
import unittest

import FreeCAD  # noqa: F401  -- adds Mod paths first, so the copy can be put ahead of them

COPY = "D:/Work/Personal/Sources/fcb-verify-13-8"
sys.path.insert(0, COPY + "/src")
sys.path.insert(0, COPY + "/tests")
for name in [m for m in sys.modules if m == "freecad_buddy" or m.startswith("freecad_buddy.")]:
    del sys.modules[name]
import freecad_buddy.usecases.queries as q  # noqa: E402

sys.stderr.write("IMPORTED " + q.__file__ + "\n")
assert q.__file__.replace("\\", "/").startswith(COPY), q.__file__
pattern = sys.argv[-1] if sys.argv[-1].startswith("test_") else "test*.py"
suite = unittest.TestLoader().discover(
    start_dir=COPY + "/tests/infc", pattern=pattern, top_level_dir=COPY + "/tests"
)
result = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
sys.stderr.write(f"RESULT run={result.testsRun} fail={len(result.failures)} err={len(result.errors)} skip={len(result.skipped)}\n")
sys.exit(0 if result.wasSuccessful() else 1)
