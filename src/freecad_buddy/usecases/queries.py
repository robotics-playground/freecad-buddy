"""Read-only introspection use cases.

Exposes ``query_capabilities``: runtime capability probes assembled from the shim plus the
operator ``exec_enabled`` flag. No mutation and no ``doc`` handle.
"""

from __future__ import annotations

from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.usecases import shim


def query_capabilities(exec_enabled: bool = False) -> ResultEnvelope:
    """Report runtime capabilities: FreeCAD version, element-map, serializer, VarSet, render, exec.

    Every field is a live probe. ``render`` is ``"none"`` on the headless surface and
    ``exec_enabled`` reflects whether the exec tool is reachable.
    """
    structured = dict(shim.capability_banner())
    structured["exec_enabled"] = exec_enabled
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": mirror_text(structured),
    }
