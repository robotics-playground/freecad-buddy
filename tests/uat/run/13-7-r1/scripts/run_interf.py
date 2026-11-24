import sys, unittest
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-7\src")
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-7\tests")
import FreeCAD
import freecad_buddy.usecases.queries as q
sys.stderr.write("QUERIES=%s\n" % q.__file__)
suite = unittest.TestLoader().loadTestsFromName("infc.test_query_tools.QueryInterferenceTest")
r = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
for t, _ in r.failures + r.errors:
    sys.stderr.write("RED: %s\n" % t.id())
sys.stderr.write("RESULT run=%d fail=%d err=%d\n" % (r.testsRun, len(r.failures), len(r.errors)))
