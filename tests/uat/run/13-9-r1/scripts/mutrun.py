import os, sys, unittest
ROOT = os.environ["FCB_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import freecad_buddy
sys.stderr.write("PKG %s\n" % freecad_buddy.__file__)
names = os.environ["FCB_TESTS"].split(",")
suite = unittest.TestLoader().loadTestsFromNames(names)
r = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
sys.stderr.write("RESULT run=%d fail=%d err=%d\n" % (r.testsRun, len(r.failures), len(r.errors)))
for t, _ in r.failures + r.errors:
    sys.stderr.write("RED %s\n" % t.id())
