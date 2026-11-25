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
 "RT1_noop_goes_through_bracket": [(FE, "    if registry.with_document(doc, changes_nothing):\n", "    if False:\n")],
 "RT2_metadata_change_allowed": [(FE, "            if given is not None and given != current:\n", "            if False:\n")],
 "RT3_unstorable_string_allowed": [(FE, "        if _unstorable(character):\n", "        if False:\n")],
 "RT4_dispatch_reads_any_code": [(DI, "    if isinstance(exc, CodedValidationError) and isinstance(exc.code, str) and exc.code:\n        return exc.code\n    return None\n", "    return getattr(exc, 'code', None)\n")],
 "RT5_varset_name_unchecked": [(FE, "    if varset in _EXPRESSION_RESERVED_NAMES:\n", "    if False:\n")],
 "RT6_shape_not_reserved": [(FE, '_PROJECT_READ_NAMES = frozenset({"Shape", "ElementMapVersion"})', "_PROJECT_READ_NAMES = frozenset()")],
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
