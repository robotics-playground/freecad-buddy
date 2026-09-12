"""check_imports violation-detection cases from the I/O matrix. Builds a tmp package tree
per case and asserts the checker flags bad rings/Qt and passes the good ones."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_imports  # noqa: E402


def _make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "freecad_buddy"
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


def _rules(violations):
    return " ".join(v.rule for v in violations)


def test_clean_tree_passes(tmp_path):
    root = _make_tree(tmp_path, {
        "__init__.py": '__version__ = "0.0.1"\n',
        "contracts/__init__.py": "import json\nimport dataclasses\n",
        "usecases/mod.py": (
            "import json\nimport FreeCAD\nfrom freecad_buddy.contracts import status\n"
        ),
        "adapters/marshal.py": "import threading\n",
        "hosts/main.py": "import argparse\nfrom freecad_buddy.usecases import shim\n",
    })
    assert check_imports.check_tree(root) == []


def test_outward_import_in_usecases_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from freecad_buddy.hosts import main\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected outward-import violation"
    assert "usecases/bad.py" in str(v[0])
    assert "inward" in _rules(v)


def test_qt_in_usecases_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "import FreeCADGui\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "Qt" in _rules(v) or "FreeCADGui" in _rules(v)


def test_pyside_in_usecases_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from PySide2 import QtCore\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "PySide" in _rules(v)


def test_third_party_in_contracts_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "contracts/bad.py": "import trimesh\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "stdlib-only" in _rules(v)


def test_third_party_in_usecases_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "import trimesh\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "whitelist" in _rules(v)


def test_qt_in_marshal_flagged(tmp_path):
    # marshal.py holds no Qt: the pump lives in hosts/gui_addon/pump.py, so the
    # adapters Qt carve-out is render_probe.py alone (AD-1).
    root = _make_tree(tmp_path, {
        "adapters/marshal.py": "from PySide6 import QtCore\n",
    })
    v = check_imports.check_tree(root)
    assert v, "marshal.py must not be Qt-exempt"
    assert "Qt" in _rules(v) or "FreeCADGui" in _rules(v)


def test_qt_exempt_adapters_holds_exactly_render_probe():
    # AD-29: the live camera lives in hosts/gui_addon/, so this list must never grow a second
    # entry. Without this assertion the single-exemption rule is convention only.
    assert check_imports.QT_EXEMPT_ADAPTERS == frozenset({"adapters/render_probe.py"})


def test_qt_in_render_probe_allowed(tmp_path):
    root = _make_tree(tmp_path, {
        "adapters/render_probe.py": "import FreeCADGui\n",
    })
    assert check_imports.check_tree(root) == []


def test_qt_in_other_adapter_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "adapters/rpc_listener.py": "import FreeCADGui\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "Qt" in _rules(v) or "FreeCADGui" in _rules(v)


def test_adapters_importing_hosts_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "adapters/bad.py": "from freecad_buddy.hosts import main\n",
    })
    v = check_imports.check_tree(root)
    assert v
    assert "inward" in _rules(v)


def test_freecad_app_whitelist_allowed_in_usecases(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/ok.py": "import Part\nimport Sketcher\nimport MeshPart\n",
    })
    assert check_imports.check_tree(root) == []


def test_relative_outward_import_flagged(tmp_path):
    # from ..hosts import main inside usecases/ points outward.
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from ..hosts import main\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected relative outward-import violation"
    assert "outward" in _rules(v)


def test_relative_inward_import_allowed(tmp_path):
    # from ..contracts import status inside usecases/ points inward — allowed.
    root = _make_tree(tmp_path, {
        "usecases/ok.py": "from ..contracts import status\n",
    })
    assert check_imports.check_tree(root) == []


def test_from_freecad_buddy_import_ring_flagged(tmp_path):
    # 2-segment form: from freecad_buddy import hosts (ring in the names list).
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from freecad_buddy import hosts\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected 2-segment outward-import violation"
    assert "hosts" in _rules(v)


def test_multi_alias_import_second_ring_flagged(tmp_path):
    # import freecad_buddy.contracts, freecad_buddy.hosts — 2nd alias is outward.
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "import freecad_buddy.contracts, freecad_buddy.hosts\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected the second (outward) alias to be flagged"
    assert "hosts" in _rules(v)


def test_nested_marshal_not_qt_exempt(tmp_path):
    # A nested adapters/sub/marshal.py must NOT inherit the marshal Qt exemption.
    root = _make_tree(tmp_path, {
        "adapters/sub/marshal.py": "import FreeCADGui\n",
    })
    v = check_imports.check_tree(root)
    assert v, "nested same-named file must not be Qt-exempt"
    assert "Qt" in _rules(v) or "FreeCADGui" in _rules(v)


def test_unparseable_file_reported_not_crash(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/broken.py": "def (:\n",  # syntax error
    })
    v = check_imports.check_tree(root)
    assert v, "syntax error should yield a violation, not a crash"
    assert "unparseable" in _rules(v)


def test_relative_names_import_ring_flagged(tmp_path):
    # from .. import hosts inside usecases/ names the ring via node.names, not node.module.
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from .. import hosts\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected relative from-import-names outward violation"
    assert "outward" in _rules(v)


def test_relative_names_import_from_top_ring_flagged(tmp_path):
    # from .. import usecases inside contracts/ (climb == package depth boundary).
    root = _make_tree(tmp_path, {
        "contracts/bad.py": "from .. import usecases\n",
    })
    v = check_imports.check_tree(root)
    assert v, "expected boundary-climb relative-names outward violation"
    assert "outward" in _rules(v)


def test_relative_climb_above_package_root_flagged(tmp_path):
    # from ....x escapes the package root entirely — must be flagged, not silently clean.
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "from ....x import y\n",
    })
    v = check_imports.check_tree(root)
    assert v, "over-climbing relative import must be flagged"
    assert "climbs above the package root" in _rules(v)


def test_package_root_qt_import_flagged(tmp_path):
    # A file directly at the package root is not in a ring but still runs in FreeCAD.
    root = _make_tree(tmp_path, {
        "util.py": "import FreeCADGui\n",
    })
    v = check_imports.check_tree(root)
    assert v, "Qt at package root must be flagged"
    assert "Qt" in _rules(v) or "FreeCADGui" in _rules(v)


def test_package_root_third_party_flagged(tmp_path):
    root = _make_tree(tmp_path, {
        "util.py": "import trimesh\n",
    })
    v = check_imports.check_tree(root)
    assert v, "third-party at package root must be flagged"
    assert "non-ring" in _rules(v)


def test_package_root_stdlib_and_version_only_clean(tmp_path):
    root = _make_tree(tmp_path, {
        "__init__.py": '__version__ = "0.0.1"\n',
        "util.py": "import json\nfrom freecad_buddy.contracts import status\n",
    })
    assert check_imports.check_tree(root) == []


def test_non_ring_subpackage_qt_and_third_party_flagged(tmp_path):
    # A file in a non-ring subpackage (depth >= 2, head not a ring) must inherit the
    # non-ring Qt-ban + stdlib/FreeCAD-App floor — not be silently skipped.
    root = _make_tree(tmp_path, {
        "util/helper.py": "import FreeCADGui\nimport trimesh\n",
    })
    v = check_imports.check_tree(root)
    assert v, "non-ring subpackage import must be flagged, not escaped"
    assert all("util/helper.py" in str(x) for x in v), "violation must name the offending file"
    rules = _rules(v)
    assert "Qt" in rules or "FreeCADGui" in rules
    assert "non-ring" in rules  # third-party trimesh caught by the stdlib/FreeCAD-App floor
    # firstparty + stdlib + FreeCAD-App whitelist in a non-ring subpackage stay allowed
    # (rings are inward of it; App modules obey the same floor as package-root files).
    clean = _make_tree(tmp_path / "clean", {
        "util/helper.py": (
            "import json\nimport Part\nfrom freecad_buddy.contracts import status\n"
        ),
    })
    assert check_imports.check_tree(clean) == []


def test_non_ring_subpackage_relative_overclimb_flagged(tmp_path):
    # A relative import that climbs above the package root from a depth >= 2 non-ring file
    # must be flagged, matching ring-file behavior — not silently allowed as "inward".
    root = _make_tree(tmp_path, {
        "util/helper.py": "from ....escape import x\n",
    })
    v = check_imports.check_tree(root)
    assert v, "over-climbing relative import in a non-ring subpackage must be flagged"
    assert "climbs above the package root" in _rules(v)


def test_active_document_access_flagged_in_usecases(tmp_path):
    root = _make_tree(tmp_path, {
        "usecases/bad.py": "import FreeCAD\nd = FreeCAD.ActiveDocument\n",
    })
    v = check_imports.check_tree(root)
    assert v, "FreeCAD.ActiveDocument must be flagged"
    assert "ActiveDocument" in _rules(v)
    assert "banned" in _rules(v)


def test_set_active_document_flagged_via_app_alias(tmp_path):
    root = _make_tree(tmp_path, {
        "adapters/bad.py": "import FreeCAD as App\nApp.setActiveDocument('n')\n",
    })
    v = check_imports.check_tree(root)
    assert v, "App.setActiveDocument must be flagged"
    assert "setActiveDocument" in _rules(v)


def test_active_document_flagged_in_hosts_too(tmp_path):
    # The ban is process-wide; even the outer host ring must use explicit handles.
    root = _make_tree(tmp_path, {
        "hosts/bad.py": "import FreeCAD\nx = FreeCAD.ActiveDocument\n",
    })
    v = check_imports.check_tree(root)
    assert v, "ActiveDocument in hosts must still be flagged"
    assert "ActiveDocument" in _rules(v)


def test_active_document_attr_on_other_object_not_flagged(tmp_path):
    # ``registry.ActiveDocument`` (not a FreeCAD module binding) is not the banned form.
    root = _make_tree(tmp_path, {
        "usecases/ok.py": "import FreeCAD\nd = FreeCAD.getDocument('h')\nx = registry.ActiveDocument\n",
    })
    assert check_imports.check_tree(root) == []
