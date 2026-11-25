"""Run named infc tests from FCB_REPO; write pass/fail per test to FCB_OUT."""

import os
import sys
import unittest

REPO = os.environ["FCB_REPO"]
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import FreeCAD  # noqa: E402,F401

names = [n for n in os.environ["FCB_TESTS"].split(",") if n]
suite = unittest.TestLoader().loadTestsFromNames(names)


class Collect(unittest.TextTestResult):
    pass


result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
with open(os.environ["FCB_OUT"], "w") as out:
    out.write(f"ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}\n")
    for test, trace in result.failures + result.errors:
        last = [line for line in trace.strip().splitlines() if line.strip()][-1]
        out.write(f"RED {test.id()} :: {last[:300]}\n")
