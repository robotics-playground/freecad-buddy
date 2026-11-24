import os, sys, tempfile
import FreeCAD as App
out = []
chars = {"NUL": "\x00", "BEL_U+0007": "\x07", "U+0084": "\x84", "U+0085": "\x85", "U+FDD0": "\ufdd0", "U+FFFE": "\ufffe", "TAB": "\t", "e_acute": "\xe9"}
d = App.newDocument("rt3")
v = d.addObject("App::VarSet", "P")
for i, (k, c) in enumerate(chars.items()):
    v.addProperty("App::PropertyString", f"s{i}", "G")
    setattr(v, f"s{i}", "a" + c + "b")
d.recompute()
path = os.path.join(os.environ["SCR"], "rt3.FCStd")
d.saveAs(path)
mem = {k: repr(getattr(v, f"s{i}")) for i, k in enumerate(chars)}
App.closeDocument(d.Name)
d2 = App.openDocument(path)
v2 = d2.getObject("P")
for i, (k, c) in enumerate(chars.items()):
    back = getattr(v2, f"s{i}")
    out.append(f"{k}: in-memory={mem[k]} reopened={back!r} kept={back == 'a' + c + 'b'}")
sys.path.insert(0, os.path.join(os.environ["FCB_ROOT"], "src"))
from freecad_buddy.usecases.features import _unstorable
for k, c in chars.items():
    out.append(f"{k}: tool refuses={_unstorable(c)}")
open(os.path.join(os.environ["SCR"], "rt3-probe.txt"), "w").write("\n".join(out))
