import os, sys, unittest
ROOT = r"D:\Work\Personal\Sources\fcb-verify-13-18"
sys.path.insert(0, ROOT + r"\src")
sys.path.insert(0, ROOT + r"\tests")
import freecad_buddy.usecases.features as f
sys.stderr.write("FEATURES_FILE=" + f.__file__ + "\n")
names = os.environ["FCB_TESTS"].split(",")
suite = unittest.TestLoader().loadTestsFromNames(["infc.test_feature_tools." + n for n in names])
res = unittest.TextTestRunner(verbosity=2, stream=sys.stderr).run(suite)
sys.stderr.write("RESULT fail=%d error=%d run=%d\n" % (len(res.failures), len(res.errors), res.testsRun))
for t, _ in res.failures + res.errors:
    sys.stderr.write("RED " + t.id() + "\n")
