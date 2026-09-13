"""Framing on the tool result: the envelope key, the sentence, and the cache (no FreeCAD).

Every story 8.4 I/O matrix row is driven through ``tool_catalog.with_framing`` — the single
attachment point — against a scripted fake view, so the rules under test are the wired ones and
not a re-statement of them. The non-``OK`` omission rule is proven across several statuses
because "omit on failure" is the rule a future tool is most likely to erode one status at a time.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy.contracts.envelope import framing_warning
from freecad_buddy.hosts import tool_catalog
from freecad_buddy.usecases import framing
from freecad_buddy.usecases.documents import ValidationError

_HANDLE = "fcb-doc:fake"
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "freecad_buddy"
    / "contracts"
    / "jsonschema"
    / "result-envelope.schema.json"
)

# ---- fakes -----------------------------------------------------------------------------------


class _FakeBoundBox:
    def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
        self.XMin, self.YMin, self.ZMin = xmin, ymin, zmin
        self.XMax, self.YMax, self.ZMax = xmax, ymax, zmax


class _FakeShape:
    def __init__(self, bbox):
        self.BoundBox = bbox

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False


class _FakeObject:
    def __init__(self, name, bounds, visibility=True):
        self.Name = name
        self.TypeId = "Part::Feature"
        self.Visibility = visibility
        self.Shape = _FakeShape(_FakeBoundBox(*bounds))


class _FakeDocument:
    def __init__(self, objects, name="Part"):
        self.Name = name
        self._objects = list(objects)

    @property
    def Objects(self):  # noqa: N802 - FreeCAD API name
        return list(self._objects)


class _FakeRegistry:
    def __init__(self, document, handle=_HANDLE):
        self._document = document
        self._handle = handle

    def with_document(self, doc, fn):
        if doc != self._handle:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(self._handle, self._document)


class _FakeView:
    """A live view whose camera, size, viewer identity and projection are all scripted.

    ``projections`` counts how many corners were projected, which is how a cache hit is proven:
    a served verdict costs zero projections.
    """

    def __init__(self, size=(800, 600), point=(400.0, 300.0), camera="cam-1"):
        self.size = size
        self.point = point
        self.camera = camera
        self.projections = 0

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return self.size

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        return self.camera

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        self.projections += 1
        return self.point


class _FakeViewportPort:
    def __init__(self, view, available=True):
        self._view = view
        self._available = available

    def available(self, document):
        return (self._available, None if self._available else "no 3D view")

    def view(self, document):
        return self._view


# ---- helpers ---------------------------------------------------------------------------------


def _document(bounds=(0.0, 0.0, 0.0, 10.0, 10.0, 10.0)):
    return _FakeDocument([_FakeObject("Box", bounds)])


def _envelope(status="OK", text="pad created", structured=None):
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,
        "detail": None if status == "OK" else {"code": "x", "message": "boom"},
        "structured_content": structured if structured is not None else {"ok": True},
        "text": text,
    }


def _wired(view, document=None, available=True, result=None):
    """``with_framing`` around a handler returning ``result``, wired to ``view``."""
    registry = _FakeRegistry(document if document is not None else _document())
    port = _FakeViewportPort(view, available=available)
    raw = lambda **_params: dict(result if result is not None else _envelope())  # noqa: E731
    return tool_catalog.with_framing(raw, registry, port)


@pytest.fixture(autouse=True)
def _empty_cache():
    """The cache is process-global, so every test starts and leaves it empty."""
    framing.reset_cache()
    yield
    framing.reset_cache()


# ---- the block rides the envelope, never structured_content -----------------------------------


def test_should_attach_framing_as_a_top_level_key_when_the_status_is_ok():
    # Arrange
    handler = _wired(_FakeView())

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["framing"]["fits"] is True
    assert result["framing"]["checked"] == "computed"
    assert "framing" not in result["structured_content"]


def test_should_leave_the_text_untouched_when_the_model_fits():
    # Arrange
    handler = _wired(_FakeView())

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["text"] == "pad created"


def test_should_end_the_text_with_the_shared_sentence_when_the_model_overflows():
    # Arrange: every corner projects past the right edge.
    handler = _wired(_FakeView(point=(1700.0, 300.0)))

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["framing"]["fits"] is False
    assert result["text"].startswith("pad created")
    assert result["text"].endswith(framing_warning(result["framing"]))
    assert "view_fit_viewport" in result["text"]


def test_should_validate_against_the_regenerated_envelope_schema_when_framing_is_attached():
    # Arrange
    handler = _wired(_FakeView(point=(1700.0, 300.0)))

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=result, schema=schema)


# ---- the non-OK omission rule ------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["TIMEOUT", "INVALID_INPUT", "RECOMPUTE_ERROR", "SPEC_FAILED", "OOM_KILLED", "WORKER_CRASHED"],
)
def test_should_omit_framing_entirely_on_any_non_ok_terminal_status(status):
    """One rule, no either/or: a verdict on a failed call invites a reader to treat it as current.

    The view here would happily answer ``fits: False`` — the omission must come from the status,
    not from the read being impossible.
    """
    # Arrange
    handler = _wired(_FakeView(point=(1700.0, 300.0)), result=_envelope(status=status))

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert "framing" not in result
    assert result["text"] == "pad created"


def test_should_leave_a_usecase_attached_framing_block_intact_on_a_non_ok_envelope():
    """AD-32's single carve-out: ``view_fit_viewport``'s post-fit ``SPEC_FAILED`` carries its own
    freshly-computed verdict, and the wrapper must not strip it.

    ``with_framing`` short-circuits on non-``OK`` today, so the carve-out costs the wrapper
    nothing — but that is the property the carve-out depends on, so it is pinned rather than read.
    If the wrapper is ever changed to strip unknown keys, this story's contract breaks silently.
    """
    # Arrange
    verdict = {"fits": False, "ratio": 1.1, "checked": "computed", "stale_reason": None}
    fit_failure = {**_envelope(status="SPEC_FAILED", text="the fit ran"), "framing": verdict}
    handler = _wired(_FakeView(), result=fit_failure)

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["framing"] == verdict
    assert result["text"] == "the fit ran", "the wrapper appends no sentence to a failed call"


def test_should_attach_no_framing_block_to_any_other_non_ok_tool():
    """The carve-out extends to exactly one site: a tool that attached nothing still gets nothing,
    whatever the view would have answered."""
    # Arrange
    handler = _wired(_FakeView(point=(1700.0, 300.0)), result=_envelope(status="SPEC_FAILED"))

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert "framing" not in result


def test_should_not_project_at_all_when_the_status_is_not_ok():
    # Arrange
    view = _FakeView()
    handler = _wired(view, result=_envelope(status="TIMEOUT"))

    # Act
    handler(doc=_HANDLE)

    # Assert
    assert view.projections == 0


# ---- the three no-verdict states ---------------------------------------------------------------


def test_should_omit_framing_when_the_document_has_no_viewport():
    # Arrange
    handler = _wired(_FakeView(), available=False)

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert "framing" not in result


def test_should_omit_framing_when_no_viewport_port_is_injected():
    # Arrange
    raw = lambda **_params: _envelope()  # noqa: E731
    handler = tool_catalog.with_framing(raw, _FakeRegistry(_document()), None)

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert "framing" not in result
    assert handler is raw, "a host with no viewport must not pay for a wrapper that cannot answer"


def test_should_attach_unavailable_without_a_sentence_when_the_projection_fails():
    # Arrange
    view = _FakeView()
    view.getPointOnViewport = _raiser  # the projection is the only thing that fails

    handler = _wired(view)

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["framing"]["fits"] is None
    assert result["framing"]["checked"] == "unavailable"
    assert "projection failed" in result["framing"]["stale_reason"]
    assert result["text"] == "pad created", "an unmeasurable verdict is not a framing warning"


def _raiser(*_args, **_kwargs):
    raise RuntimeError("no render manager")


# ---- the verdict describes the targeted document -----------------------------------------------


def test_should_omit_framing_when_the_targeted_document_is_not_the_one_on_screen():
    """Two-document session: ``DocA`` is targeted, the viewport shows ``DocB``.

    ``ViewportPort`` is per document, so ``DocA`` simply has no view — the block is omitted. A
    warning about ``DocB``'s framing on a call that targeted ``DocA`` would be a lie.
    """
    # Arrange
    handler = _wired(
        _FakeView(point=(1700.0, 300.0)), document=_FakeDocument([], "DocA"), available=False
    )

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert "framing" not in result


def test_should_omit_framing_rather_than_fail_the_call_when_the_handle_is_unknown():
    # Arrange
    handler = _wired(_FakeView())

    # Act
    result = handler(doc="fcb-doc:stale")

    # Assert
    assert "framing" not in result
    assert result["status"] == "OK", "an advisory verdict must never fail a completed call"


def test_should_omit_framing_when_the_call_named_no_document():
    # Arrange
    handler = _wired(_FakeView())

    # Act
    result = handler()

    # Assert
    assert "framing" not in result


# ---- the cache ---------------------------------------------------------------------------------


def test_should_serve_a_cached_verdict_without_re_projecting_when_nothing_changed():
    # Arrange
    view = _FakeView()
    handler = _wired(view)

    # Act
    first = handler(doc=_HANDLE)
    projections_after_first = view.projections
    second = handler(doc=_HANDLE)

    # Assert
    assert first["framing"]["checked"] == "computed"
    assert second["framing"]["checked"] == "cached"
    assert second["framing"]["fits"] == first["framing"]["fits"]
    assert view.projections == projections_after_first, "a cache hit must re-project nothing"


def test_should_name_geometry_as_unverified_when_a_query_serves_a_cached_verdict():
    """The pure-query path has no cheap geometry digest, so freshness cannot be proven.

    AD-32's escape clause: report cached with a stated reason rather than claim a freshness the
    bridge cannot prove. ``fingerprint()`` is never called for a cache key.
    """
    # Arrange
    handler = _wired(_FakeView())

    # Act
    handler(doc=_HANDLE)
    second = handler(doc=_HANDLE)

    # Assert
    assert second["framing"]["checked"] == "cached"
    assert "geometry" in second["framing"]["stale_reason"]


def test_should_claim_no_unverified_component_when_the_mutation_supplied_its_own_digest():
    # Arrange: the digest run_mutation already computed, read out of the envelope for free.
    mutation = {"mutation": {"fingerprint_after": {"digest": "abc123"}}}
    handler = _wired(_FakeView(), result=_envelope(structured=mutation))

    # Act
    handler(doc=_HANDLE)
    second = handler(doc=_HANDLE)

    # Assert
    assert second["framing"]["checked"] == "cached"
    assert second["framing"]["stale_reason"] is None


def test_should_not_serve_a_stale_verdict_when_only_the_window_was_resized():
    """A window resize moves ``getSize()`` while the camera node is untouched.

    A geometry-only staleness trigger would answer ``fits: true, stale_reason: null`` for a
    viewport that now clips the model. The size is a key component, so the verdict moves with it.

    The rule is "never fresh for a viewport that moved", which the size being re-read satisfies by
    recomputing. The alternative the matrix allows — serving the stored verdict as ``cached`` with
    ``viewport_size`` named — applies only when the size cannot be re-read, which is the case the
    unreadable-component test covers.
    """
    # Arrange: the model fits an 800x600 viewport and overflows a 200x150 one.
    view = _FakeView(size=(800, 600), point=(400.0, 300.0))
    handler = _wired(view)

    # Act
    first = handler(doc=_HANDLE)
    view.size = (200, 150)
    second = handler(doc=_HANDLE)

    # Assert
    assert first["framing"]["fits"] is True
    assert second["framing"]["fits"] is False, "the resize must not be served from the cache"
    assert second["framing"]["checked"] == "computed"


def test_should_never_report_a_verdict_as_fresh_when_the_viewport_size_cannot_be_read():
    """AD-32's escape clause on the size component.

    ``getSize`` feeds both the cache key and the projection, so a size the process cannot read
    leaves nothing to measure at all: the verdict is ``unavailable`` with the failure named, never
    a ``computed`` answer that a reader would take as current.
    """
    # Arrange
    view = _FakeView()
    view.getSize = _raiser
    handler = _wired(view)

    # Act
    first = handler(doc=_HANDLE)
    second = handler(doc=_HANDLE)

    # Assert
    assert first["framing"]["checked"] == "unavailable"
    assert "viewport size unreadable" in first["framing"]["stale_reason"]
    assert second["framing"]["checked"] == "unavailable", (
        "a verdict that measured nothing has no stored measurement to serve as cached"
    )


def test_should_not_serve_a_stale_verdict_when_the_camera_moved():
    # Arrange
    view = _FakeView()
    handler = _wired(view)

    # Act
    handler(doc=_HANDLE)
    view.camera = "cam-2"
    view.point = (1700.0, 300.0)
    second = handler(doc=_HANDLE)

    # Assert
    assert second["framing"]["fits"] is False
    assert second["framing"]["checked"] == "computed"


def test_should_not_serve_a_stale_verdict_when_the_active_view_changed():
    """A view switch hands back a different view object with the same camera and size.

    Identity is the fourth key component, so the cache must miss even though every readable
    component matches. An id-derived key would be unsound here: a dead view's address is reused.
    """
    # Arrange
    document = _document()
    registry = _FakeRegistry(document)
    first_view = _FakeView()
    second_view = _FakeView(point=(1700.0, 300.0))
    port = _FakeViewportPort(first_view)
    raw = lambda **_params: _envelope()  # noqa: E731
    handler = tool_catalog.with_framing(raw, registry, port)

    # Act
    handler(doc=_HANDLE)
    port._view = second_view
    second = handler(doc=_HANDLE)

    # Assert
    assert second_view.camera == first_view.camera
    assert second_view.size == first_view.size
    assert second["framing"]["fits"] is False
    assert second["framing"]["checked"] == "computed"


def test_should_report_cached_naming_the_camera_when_the_camera_cannot_be_read():
    """AD-32's escape clause: a key component that cannot be read is never treated as fresh."""
    # Arrange
    view = _FakeView()
    view.getCamera = _raiser
    handler = _wired(view)

    # Act
    handler(doc=_HANDLE)
    second = handler(doc=_HANDLE)

    # Assert
    assert second["framing"]["checked"] == "cached"
    assert "camera" in second["framing"]["stale_reason"]


def test_should_keep_an_unavailable_verdict_unavailable_rather_than_restamp_it_cached():
    # Arrange: an empty document can never be measured, so there is no stored measurement to cache.
    view = _FakeView()
    handler = _wired(view, document=_FakeDocument([]))

    # Act
    handler(doc=_HANDLE)
    second = handler(doc=_HANDLE)

    # Assert
    assert second["framing"]["checked"] == "unavailable"
    assert second["framing"]["fits"] is None


def test_should_key_the_cache_per_document_handle():
    # Arrange: two handles, two documents, one view — the second must not read the first's verdict.
    wide = _FakeRegistry(_document(), handle="fcb-doc:wide")
    view = _FakeView()
    port = _FakeViewportPort(view)
    raw = lambda **_params: _envelope()  # noqa: E731

    # Act
    tool_catalog.with_framing(raw, _FakeRegistry(_document()), port)(doc=_HANDLE)
    projections_after_first = view.projections
    tool_catalog.with_framing(raw, wide, port)(doc="fcb-doc:wide")

    # Assert
    assert view.projections > projections_after_first, (
        "a second handle must be measured, not served the first handle's verdict"
    )


# ---- the mutation path measures its own effect --------------------------------------------------


def test_should_warn_on_the_very_call_whose_mutation_overflowed_the_viewport():
    """The read runs after the handler returns — outside the AD-5 bracket, past ``commit``.

    The handler grows the model as its own effect; the verdict on that same result must already
    see the grown model, not the pre-call one.
    """
    # Arrange
    document = _document()
    view = _FakeView()
    registry = _FakeRegistry(document)

    def pad(**_params):
        document._objects[0].Shape.BoundBox = _FakeBoundBox(0, 0, 0, 500, 500, 500)
        view.point = (1700.0, 300.0)
        return _envelope(text="pad created", structured={"mutation": {"fingerprint_after": {}}})

    handler = tool_catalog.with_framing(pad, registry, _FakeViewportPort(view))

    # Act
    result = handler(doc=_HANDLE)

    # Assert
    assert result["framing"]["fits"] is False
    assert result["text"].endswith(framing_warning(result["framing"]))


# ---- geometry proxy: both envelope shapes carry the digest --------------------------------


def test_should_read_the_digest_when_a_lifecycle_tool_publishes_it_at_the_top_level():
    # Arrange: document_recompute/document_undo change geometry but publish the digest as a bare
    # top-level string, not as a nested mutation block. Reading only the nested form made them
    # contribute None, so two in a row under a static camera shared a cache key and the second
    # was served the first's stale `fits: true` with the warning suppressed.
    lifecycle = {"structured_content": {"fingerprint_after": "abc123def456", "recomputed": 1}}
    mutation = {
        "structured_content": {"mutation": {"fingerprint_after": {"digest": "abc123def456"}}}
    }

    # Act
    from_lifecycle = tool_catalog._geometry_proxy(lifecycle)
    from_mutation = tool_catalog._geometry_proxy(mutation)

    # Assert
    assert from_lifecycle == "abc123def456"
    assert from_mutation == "abc123def456"


def test_should_report_no_digest_when_the_envelope_carries_none():
    # Arrange
    query = {"structured_content": {"objects": ["Pad"]}}

    # Act
    digest = tool_catalog._geometry_proxy(query)

    # Assert
    assert digest is None
