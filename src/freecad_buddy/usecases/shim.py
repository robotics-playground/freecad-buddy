"""Capability probes (AD-11).

All version-sensitive FreeCAD capability checks live here so downstream code never
branches on version strings. Phase-0 stubs return conservative defaults (False); the
real probes land in later stories and are confirmed at runtime on the CI legs.

FreeCAD App modules are imported lazily inside functions (never at module top) so this
module stays importable FreeCAD-free for static analysis and the external test suite.
"""


def export_binary_available() -> bool:
    """Whether ``TopoShape.exportBinary`` is Python-exposed on the running FreeCAD build.

    Drives the fingerprint serializer choice (docs/decisions/001-serializer-exportbinary.md,
    story 1.6). Conservative default False → callers fall back to the ``exportBrep`` stream.
    """
    return False


def varset_available() -> bool:
    """Whether ``App::VarSet`` is usable from Python on the running FreeCAD build.

    Drives the driving-dimension facade (docs/decisions/004-dimension-facade-varset.md,
    story 4.6). Conservative default False → callers fall back to Spreadsheet.
    """
    return False


def render_available() -> bool:
    """Whether an offscreen GL render context is usable on the running FreeCAD build.

    Drives the screenshot render ladder (docs/decisions/003-render-ladder.md, story 1.9).
    Conservative default False → screenshot features stay disabled until confirmed.
    """
    return False


def element_map_available() -> bool:
    """Whether the topological element map (TNP guard) is exposed on the running build.

    Drives the TNP snapshot/audit guard (AD-7). Conservative default False → guard degrades
    gracefully until confirmed.
    """
    return False
