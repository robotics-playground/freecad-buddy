"""``view_fit_viewport`` tests: the live-camera fit and its audit line (no FreeCAD).

Covers every story 8.3 I/O matrix row against a scripted fake view and a recording audit sink.
The fake view records each ``fitAll`` call, so "no fit occurred" is asserted on the recording
rather than inferred from the envelope, and the sink keeps whole records, so ``camera_before``
can be checked to be present **and** absent from ``params_digest`` at the same time.
"""

from __future__ import annotations

import ast
import inspect
import json

import pytest

from freecad_buddy.adapters.audit_log import AuditSink, _digest
from freecad_buddy.usecases import view_fit
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.view_fit import view_fit_viewport

HANDLE = "fcb-doc:fake"
CAMERA = "#Inventor V2.1 ascii\nOrthographicCamera { position 0 0 87 height 52 }\n"

# ---- fakes -----------------------------------------------------------------------------------


class _FakeDocument:
    def __init__(self, name="Part"):
        self.Name = name


class _FakeGuiDocument:
    """The ``View3DInventor.Document`` hop: a Gui document wrapping its App document."""

    def __init__(self, document):
        self.Document = document


class _FakeView:
    """A live 3D view whose camera string and ``fitAll`` outcome are scripted per test.

    ``fit_calls`` counts the fits that actually reached the view, which is how the wrong-document
    and unavailable rows prove no camera moved.
    """

    def __init__(self, document=None, camera=CAMERA, raises=None):
        self._camera = camera
        self._raises = raises
        self.fit_calls = 0
        if document is not None:
            self.Document = _FakeGuiDocument(document)

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "getCamera":
            raise RuntimeError("no camera node on this view")
        return self._camera

    def fitAll(self):  # noqa: N802 - FreeCAD API name
        if self._raises == "fitAll":
            raise RuntimeError("the scene graph is empty")
        self.fit_calls += 1


class _FakeViewportPort:
    def __init__(self, view, available=True, reason=None):
        self._view = view
        self._available = available
        self._reason = reason

    def available(self, document):  # noqa: ARG002 - the fake answers the same for any document
        return (self._available, self._reason)

    def view(self, document):  # noqa: ARG002 - the fake holds one view
        return self._view


class _FakeRegistry:
    """Minimal ``with_document`` stand-in that binds one handle to one document."""

    def __init__(self, document, handle=HANDLE):
        self._document = document
        self._handle = handle

    def with_document(self, doc, fn):
        if not doc:
            raise ValidationError("missing required 'doc' handle")
        if doc != self._handle:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(self._handle, self._document)


class _RecordingSink:
    """An audit sink keeping whole records, so a field's presence and absence are both checkable."""

    def __init__(self):
        self.records = []

    def camera(self, tool, doc, params, camera_before):
        self.records.append(
            {
                "tool": tool,
                "doc": doc,
                "params": dict(params),
                "camera_before": camera_before,
            }
        )


@pytest.fixture(autouse=True)
def _no_host_sink():
    """Keep a host-installed sink from leaking between tests; every test passes its own."""
    previous = view_fit.set_audit_sink(None)
    yield
    view_fit.set_audit_sink(previous)


# ---- successful fit --------------------------------------------------------------------------


def test_should_fit_the_view_and_audit_the_prior_camera_when_the_document_has_a_live_view():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document)
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"]["fitted"] is True
    assert view.fit_calls == 1
    assert sink.records[0]["camera_before"] == CAMERA
    assert sink.records[0]["tool"] == "view_fit_viewport"
    assert sink.records[0]["doc"] == HANDLE


def test_should_write_through_the_host_installed_sink_when_the_caller_passes_none():
    # Arrange
    document = _FakeDocument("Part")
    sink = _RecordingSink()
    view_fit.set_audit_sink(sink)

    # Act
    view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(_FakeView(document)), HANDLE)

    # Assert
    assert sink.records[0]["camera_before"] == CAMERA


def test_should_not_abort_the_fit_when_the_audit_sink_cannot_write():
    # Arrange
    class _BrokenSink:
        def camera(self, *_args):
            raise OSError("no space left on device")

    document = _FakeDocument("Part")
    view = _FakeView(document)

    # Act
    envelope = view_fit_viewport(
        _FakeRegistry(document), _FakeViewportPort(view), HANDLE, _BrokenSink()
    )

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1


# ---- the camera never enters the digest ------------------------------------------------------


def test_should_keep_the_camera_out_of_params_digest_when_the_real_sink_writes_the_record(tmp_path):
    """AD-31: ``camera_before`` rides its own field, never the irreversible argument digest.

    Checked against the real ``AuditSink`` rather than a fake, because the field placement that
    keeps the camera out of the digest is the sink's own, and the digest of the tool arguments
    alone is what an auditor joins this line to the dispatch bracket's lines with.
    """
    # Arrange
    path = tmp_path / "audit.jsonl"
    document = _FakeDocument("Part")
    params = {"doc": HANDLE}

    # Act
    view_fit_viewport(
        _FakeRegistry(document),
        _FakeViewportPort(_FakeView(document)),
        HANDLE,
        AuditSink(path, actor="test"),
    )
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    # Assert
    assert record["camera_before"] == CAMERA
    assert record["params_digest"] == _digest(params)
    assert CAMERA not in json.dumps({k: v for k, v in record.items() if k != "camera_before"})


# ---- wrong document --------------------------------------------------------------------------


def test_should_refuse_naming_both_documents_when_the_viewport_shows_another_document():
    # Arrange
    target = _FakeDocument("DocA")
    view = _FakeView(_FakeDocument("DocB"))
    sink = _RecordingSink()

    # Act
    def act():
        return view_fit_viewport(_FakeRegistry(target), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    with pytest.raises(ValidationError) as caught:
        act()
    message = str(caught.value)
    assert "DocA" in message
    assert "DocB" in message
    assert view.fit_calls == 0
    assert sink.records == []


def test_should_fit_when_the_view_reports_no_document_of_its_own():
    """An unreadable view document is not evidence of a mismatch, so it must not refuse.

    The port already resolved the view through ``getDocument(<Name>)``, so the view belongs to the
    targeted document; refusing on a missing attribute would make the tool unusable against any
    build whose view does not expose one.
    """
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document=None)

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1


# ---- handle errors ---------------------------------------------------------------------------


def test_should_raise_naming_the_handle_when_the_handle_is_unknown():
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))
    port = _FakeViewportPort(_FakeView())

    # Act
    def act():
        return view_fit_viewport(registry, port, "fcb-doc:stale")

    # Assert
    with pytest.raises(ValidationError, match="fcb-doc:stale"):
        act()


def test_should_raise_when_the_handle_is_missing():
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))
    port = _FakeViewportPort(_FakeView())

    # Act
    def act():
        return view_fit_viewport(registry, port)

    # Assert
    with pytest.raises(ValidationError, match="doc"):
        act()


def test_should_resolve_the_handle_before_the_port_when_the_host_has_no_viewport():
    """A stale handle on a headless host is still INVALID_INPUT, not "no viewport"."""
    # Arrange
    registry = _FakeRegistry(_FakeDocument("Part"))

    # Act
    def act():
        return view_fit_viewport(registry, None, "fcb-doc:stale")

    # Assert
    with pytest.raises(ValidationError, match="fcb-doc:stale"):
        act()


# ---- no viewport -----------------------------------------------------------------------------


def test_should_degrade_honestly_when_no_viewport_port_is_injected():
    # Arrange
    document = _FakeDocument("Part")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), None, HANDLE, sink)

    # Assert
    assert envelope["status"] != "OK"
    assert envelope["structured_content"]["fitted"] is False
    assert "no live viewport" in envelope["detail"]["message"]
    assert sink.records == []


def test_should_name_the_missing_view_when_the_port_reports_unavailable():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document)
    port = _FakeViewportPort(view, available=False, reason="document 'Part' has no open 3D view")

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), port, HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert "no open 3D view" in envelope["detail"]["message"]
    assert view.fit_calls == 0


def test_should_degrade_honestly_when_the_port_reports_available_but_hands_back_no_view():
    # Arrange
    document = _FakeDocument("Part")

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(None), HANDLE)

    # Assert
    assert envelope["status"] != "OK"
    assert "Part" in envelope["detail"]["message"]


# ---- degraded camera and fit -----------------------------------------------------------------


def test_should_fit_and_omit_the_camera_when_getcamera_is_unavailable():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="getCamera")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert view.fit_calls == 1
    assert sink.records[0]["camera_before"] is None
    assert envelope["structured_content"]["camera_recorded"] is False


def test_should_omit_the_camera_field_entirely_when_the_camera_was_unreadable(tmp_path):
    """An unreadable camera omits the field rather than persisting a fabricated null string."""
    # Arrange
    path = tmp_path / "audit.jsonl"
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="getCamera")

    # Act
    view_fit_viewport(
        _FakeRegistry(document), _FakeViewportPort(view), HANDLE, AuditSink(path, actor="test")
    )
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    # Assert
    assert "camera_before" not in record


def test_should_report_a_non_ok_status_naming_the_failure_when_fitall_raises():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, raises="fitAll")
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] != "OK"
    assert "RuntimeError" in envelope["detail"]["message"]
    assert view.fit_calls == 0
    assert sink.records == []


def test_should_ignore_a_camera_that_is_not_a_string():
    # Arrange
    document = _FakeDocument("Part")
    view = _FakeView(document, camera=object())
    sink = _RecordingSink()

    # Act
    envelope = view_fit_viewport(_FakeRegistry(document), _FakeViewportPort(view), HANDLE, sink)

    # Assert
    assert envelope["status"] == "OK"
    assert sink.records[0]["camera_before"] is None


# ---- AD-31: Gui-free, gate-free --------------------------------------------------------------


def test_should_import_no_gui_qt_or_pivy_module():
    """The view arrives as an opaque object from the port; ``usecases/`` stays Gui-free."""
    # Arrange
    tree = ast.parse(inspect.getsource(view_fit))
    banned = {"FreeCADGui", "PySide", "PySide2", "PySide6", "PyQt5", "PyQt6", "pivy"}

    # Act
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    # Assert
    assert imported & banned == set()


def test_should_name_neither_preview_id_nor_run_mutation():
    """The camera move must not route through the confirm gate or the mutation bracket.

    Both would demand a ``preview_id`` for an operation that has no geometry to preview, which is
    exactly the failure AD-31 spells the tool's own literal spec out to avoid.
    """
    # Arrange
    source = inspect.getsource(view_fit)
    banned = ("preview_id", "run_mutation", "gate_mutation")

    # Act
    present = [name for name in banned if name in source]

    # Assert
    assert present == []
