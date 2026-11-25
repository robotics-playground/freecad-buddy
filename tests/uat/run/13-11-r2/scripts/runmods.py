import os, sys, unittest, io
R = r"D:\Work\Personal\Sources\fcb-verify-13-11"
sys.path.insert(0, R + r"\tests"); sys.path.insert(0, R + r"\src")
buf = io.StringIO()
try:
    suite = unittest.TestLoader().loadTestsFromNames(os.environ["FCB_MODS"].split(","))
    res = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    lines = [l for l in buf.getvalue().splitlines() if l.endswith(("FAIL", "ERROR")) or l.startswith(("FAIL:", "ERROR:", "Ran ", "OK", "FAILED"))]
except Exception:
    import traceback; lines = [traceback.format_exc()]
open(os.environ["FCB_OUT"], "w").write("\n".join(lines))
