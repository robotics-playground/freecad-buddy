import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(r"D:\Work\Personal\Sources\fcb-verify-13-9")
S = Path(os.environ["SCR"])
FC = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
TX = "src/freecad_buddy/usecases/transaction.py"
FE = "src/freecad_buddy/usecases/features.py"
QU = "src/freecad_buddy/usecases/queries.py"
DI = "src/freecad_buddy/adapters/rpc_dispatch.py"
M = {
 "a_no_state_probe_compare": [(TX, "            return state_probe(candidate) == state_before\n", "            return True\n")],
 "b_drop_unit_W": [(FE, '"Pa S T THz Torr True V VA VAs W Wb Ws', '"Pa S T THz Torr True V VA VAs Wb Ws')],
 "c_allow_negative_length": [(FE, "        if millimetres < 0:\n", "        if False:\n")],
 "d_query_recomputes": [(QU, "        lists, totals = _parameter_lists(document, sorted(", "        document.recompute()\n        lists, totals = _parameter_lists(document, sorted(")],
 "e_no_row_cap": [(QU, 'if totals["varset_parameters"] < _MAX_PARAMETER_ROWS:', "if True:"),
                  (QU, 'if totals["spreadsheet_parameters"] < _MAX_PARAMETER_ROWS:', "if True:"),
                  (QU, 'if totals["bindings"] < _MAX_PARAMETER_ROWS:', "if True:")],
 "f_dispatch_drops_code": [(DI, '"code": getattr(exc, "code", None) or status,', '"code": status,')],
}
INFC = "infc.test_feature_parameters,infc.test_query_tools.QueryParametersTest"
only = sys.argv[1:] or list(M)
for name in only:
    originals = {}
    try:
        for rel, old, new in M[name]:
            p = ROOT / rel
            text = originals.setdefault(rel, p.read_bytes().decode("utf-8"))
            cur = p.read_bytes().decode("utf-8")
            assert cur.count(old) == 1, (name, rel, cur.count(old))
            p.write_bytes(cur.replace(old, new).encode("utf-8"))
        home = S / f"fch-m-{name}"; cfg = S / f"cfg-m-{name}"; home.mkdir(exist_ok=True); cfg.mkdir(exist_ok=True)
        env = dict(os.environ, FCB_ROOT=str(ROOT), FCB_TESTS=INFC, FREECAD_USER_HOME=str(home))
        r = subprocess.run([FC, "-u", str(cfg / "user.cfg"), "-s", str(cfg / "system.cfg"), str(S / "mutrun.py")], env=env, capture_output=True, text=True, cwd=str(ROOT), timeout=900)
        lines = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("PKG", "RESULT", "RED"))]
        e = subprocess.run(["uv", "run", "--extra", "dev", "pytest", "-q", "-p", "no:cacheprovider", "tests/external/test_parameters_contract.py", "tests/external/test_mcp_surface.py"], capture_output=True, text=True, cwd=str(ROOT), timeout=900)
        ext = [l for l in e.stdout.splitlines() if l.startswith("FAILED") or re.search(r"\d+ (passed|failed)", l)]
        print(f"== {name}"); print("\n".join(lines)); print("ext:", "\n  ".join(ext)); sys.stdout.flush()
    finally:
        for rel, text in originals.items():
            (ROOT / rel).write_bytes(text.encode("utf-8"))
r = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "src"], capture_output=True, text=True)
print("src clean after mutants:", repr(r.stdout))
