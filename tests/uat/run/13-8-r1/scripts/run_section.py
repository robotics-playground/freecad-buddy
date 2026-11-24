import os
import sys
import unittest

import FreeCAD  # noqa: F401

COPY = "D:/Work/Personal/Sources/fcb-verify-13-8"
sys.path.insert(0, COPY + "/src")
sys.path.insert(0, COPY + "/tests")
for name in [m for m in sys.modules if m == "freecad_buddy" or m.startswith("freecad_buddy.")]:
    del sys.modules[name]
import freecad_buddy.usecases.queries as q  # noqa: E402

assert q.__file__.replace("\\", "/").startswith(COPY), q.__file__
from infc import test_query_tools as t  # noqa: E402

only = os.environ.get("ONLY_TEST")
loader = unittest.TestLoader()
suite = loader.loadTestsFromName(f"QuerySectionTest.{only}" if only else "QuerySectionTest", t)
result = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
for test, _ in result.failures + result.errors:
    sys.stderr.write(f"RED {test.id().split('.')[-1]} {getattr(test, '_subDescription', lambda: '')()}\n")
sys.stderr.write(f"RESULT run={result.testsRun} fail={len(result.failures)} err={len(result.errors)}\n")
