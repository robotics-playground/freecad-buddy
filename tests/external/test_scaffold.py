"""Scaffold structure assertions: ring dirs + key files exist, empty inits are
byte-empty, and check_imports passes clean on the real tree."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG = REPO_ROOT / "src" / "freecad_buddy"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_imports  # noqa: E402


def test_ring_dirs_exist():
    for ring in ("contracts", "usecases", "adapters", "hosts"):
        assert (PKG / ring / "__init__.py").is_file(), f"missing {ring}/__init__.py"


def test_key_files_exist():
    expected = [
        PKG / "__init__.py",
        PKG / "usecases" / "shim.py",
        PKG / "adapters" / "marshal.py",
        PKG / "adapters" / "render_probe.py",
        PKG / "adapters" / "rpc_listener.py",
        PKG / "hosts" / "main.py",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "scripts" / "check_imports.py",
        REPO_ROOT / "addon" / "package.xml",
        REPO_ROOT / "tests" / "run_tests.py",
        REPO_ROOT / "tests" / "infc" / "__init__.py",
    ]
    for p in expected:
        assert p.is_file(), f"missing {p}"


def test_decision_notes_exist():
    notes = sorted((REPO_ROOT / "docs" / "decisions").glob("00*.md"))
    assert len(notes) >= 7, f"expected >=7 decision notes, found {len(notes)}"
    stems = {p.name.split("-")[0] for p in notes}
    assert {"001", "002", "003", "004", "005", "006", "007"} <= stems


def test_empty_inits_are_byte_empty():
    for ring in ("adapters", "hosts"):
        init = PKG / ring / "__init__.py"
        assert init.stat().st_size == 0, f"{ring}/__init__.py must be byte-empty"


def test_root_init_has_version_only():
    import ast

    text = (PKG / "__init__.py").read_text(encoding="utf-8")
    assert "__version__" in text
    tree = ast.parse(text)
    assert not [
        n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
    ], "root __init__.py must declare a version only, with no imports"


def test_check_imports_clean_on_real_tree():
    violations = check_imports.check_tree(PKG)
    assert violations == [], "\n".join(str(v) for v in violations)
