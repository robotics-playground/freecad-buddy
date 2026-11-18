"""Compare each function of the ported G3 GUI scripts with the 2026-10-03-04 source by AST."""
import ast
import sys

pairs = [
    ("tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py", "tests/uat/g3-gui/g3_gui_replay.py"),
    ("tests/uat/run/2026-10-03-04/evidence/gui.py", "tests/uat/g3-gui/gui.py"),
]


def functions(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return {
        n.name: ast.dump(n)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


for source, port in pairs:
    a, b = functions(source), functions(port)
    print(port, {name: ("same" if a[name] == b.get(name) else "CHANGED") for name in a},
          "new:", sorted(set(b) - set(a)))
