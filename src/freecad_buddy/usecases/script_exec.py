"""``script_exec`` handler: Python inside FreeCAD for an operation no typed tool covers.

Raw exec: no bridge transaction, fingerprint or rollback. Registration follows the operator
switches and every call is audit-logged by the dispatch boundary. The reduced namespace is
blast-radius hygiene, not a security boundary. Requires an explicit ``doc`` handle.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_UNSET = object()


def script_exec(registry: DocumentRegistry, doc: str | None, code: str) -> ResultEnvelope:
    """Execute the caller's ``code`` against the document named by ``doc``.

    ``value_repr`` is the repr of a bound ``result`` variable when the code sets one. On an
    exception the captured stdout is preserved on the raised error's message.
    """
    if not code:
        raise ValidationError("script_exec requires 'code'")

    import FreeCAD

    namespace: dict = {"FreeCAD": FreeCAD, "App": FreeCAD}
    try:
        import Part

        namespace["Part"] = Part
    except ImportError:
        pass

    buffer = io.StringIO()

    def _run(handle: str, document: object) -> str:
        namespace["doc"] = document
        try:
            with redirect_stdout(buffer):
                exec(code, namespace)  # noqa: S102 - raw exec is the tool's purpose
        except Exception as exc:
            captured = buffer.getvalue()
            if captured:
                exc.args = (f"{exc}\n--- captured stdout ---\n{captured}", *exc.args[1:])
            raise
        return handle

    # Resolve and run under the registry lock so the handle cannot be closed mid-exec.
    handle = registry.with_document(doc, _run)

    value = namespace.get("result", _UNSET)
    structured = {
        "doc": handle,
        "stdout": buffer.getvalue(),
        "value_repr": repr(value) if value is not _UNSET else None,
        "fingerprint_after": None,
    }
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": mirror_text(structured),
    }
