"""The shared-sentence rule, enforced rather than assumed.

``text`` is hand-written per tool — roughly forty ``summarize_*`` f-strings — so "one shared
helper renders the sentence" is convention until something fails when it is broken. These tests
are that something. They prove the sentence exists in exactly one module of ``src/``, that every
registered tool goes through the one attachment point, and that a ``fits: false`` verdict puts
the shared sentence in the rendered text whatever the tool.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from freecad_buddy.contracts import envelope as envelope_contract
from freecad_buddy.contracts.envelope import framing_warning, with_framing_text
from freecad_buddy.hosts import tool_catalog
from freecad_buddy.usecases import framing
from freecad_buddy.usecases.documents import ValidationError

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "freecad_buddy"
_CONTRACT_MODULE = SRC_ROOT / "contracts" / "envelope.py"
_HANDLE = "fcb-doc:fake"

# The sentence is not spelled out here: a literal copy in the test would be a second source of
# the text, which is the very thing under test. It is read from the helper.
SENTENCE = framing_warning(
    {"fits": False, "ratio": 2.0, "checked": "computed", "stale_reason": None}
)


def _python_sources() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


# ---- the sentence exists in exactly one place --------------------------------------------------


def test_should_spell_the_warning_sentence_in_exactly_one_module_of_src():
    """A second copy is how two tools end up warning in two wordings an agent must both learn."""
    # Arrange
    probe = SENTENCE[:60]

    # Act
    carriers = [path for path in _python_sources() if probe in path.read_text(encoding="utf-8")]

    # Assert
    assert carriers == [_CONTRACT_MODULE]


def test_should_name_the_fit_tool_in_the_sentence_so_the_agent_knows_what_to_call():
    # Act
    sentence = framing_warning(
        {"fits": False, "ratio": None, "checked": "computed", "stale_reason": None}
    )

    # Assert
    assert "view_fit_viewport" in sentence


def test_should_keep_every_usecase_summary_free_of_the_fit_tool_name():
    """No ``summarize_*`` may point at the fit tool: that is the wrapper's job, not a tool's.

    ``view_fit.py`` is the one legitimate carrier — it *is* the tool, and its own refusal text
    names itself.
    """
    # Arrange
    usecases = [p for p in (SRC_ROOT / "usecases").rglob("*.py") if p.name != "view_fit.py"]

    # Act
    carriers = [p.name for p in usecases if "view_fit_viewport" in p.read_text(encoding="utf-8")]

    # Assert
    assert carriers == []


# ---- the helper's own contract ------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict",
    [
        None,
        {"fits": True, "ratio": 0.5, "checked": "computed", "stale_reason": None},
        {"fits": None, "ratio": None, "checked": "unavailable", "stale_reason": "no view"},
    ],
    ids=["absent", "fits", "unavailable"],
)
def test_should_render_no_sentence_when_the_verdict_is_not_a_miss(verdict):
    """Only ``fits: False`` earns a sentence. ``unavailable`` is a measurement failure, not a
    framing problem, and rendering it as prose would read as one."""
    # Act
    result = framing_warning(verdict)

    # Assert
    assert result is None


def test_should_leave_the_text_byte_identical_when_no_sentence_is_earned():
    # Arrange
    text = "pad created; volume 1000.0 mm^3"

    # Act
    result = with_framing_text(
        text, {"fits": True, "ratio": 0.5, "checked": "computed", "stale_reason": None}
    )

    # Assert
    assert result == text


def test_should_append_rather_than_regenerate_when_a_sentence_is_earned():
    """Every real tool hand-writes ``text``; regenerating it from ``structured_content`` would
    replace that summary with the generic mirror."""
    # Arrange
    text = "pad created; volume 1000.0 mm^3"
    verdict = {"fits": False, "ratio": 2.0, "checked": "computed", "stale_reason": None}

    # Act
    result = with_framing_text(text, verdict)

    # Assert
    assert result.startswith(text)
    assert result.endswith(SENTENCE)


def test_should_render_the_same_sentence_for_a_cached_miss_as_for_a_computed_one():
    """Freshness lives in ``checked``, not in the prose: two wordings would be two rules."""
    # Arrange
    computed = {"fits": False, "ratio": 2.0, "checked": "computed", "stale_reason": None}
    cached = {"fits": False, "ratio": 2.0, "checked": "cached", "stale_reason": "geometry"}

    # Act
    from_computed = framing_warning(computed)
    from_cached = framing_warning(cached)

    # Assert
    assert from_computed == from_cached


# ---- every registered tool goes through the one attachment point --------------------------------


class _FakeBoundBox:
    def __init__(self, *values):
        self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = values


class _FakeShape:
    def __init__(self):
        self.BoundBox = _FakeBoundBox(0, 0, 0, 10, 10, 10)

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False


class _FakeObject:
    Name = "Box"
    TypeId = "Part::Feature"
    Visibility = True

    def __init__(self):
        self.Shape = _FakeShape()


class _FakeDocument:
    Name = "Part"
    Objects = [_FakeObject()]


class _FakeRegistry:
    def with_document(self, doc, fn):
        if doc != _HANDLE:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(_HANDLE, _FakeDocument())


class _OverflowView:
    """A view every corner of whose model lands past the right edge."""

    def getSize(self):  # noqa: N802 - FreeCAD API name
        return (800, 600)

    def getCamera(self):  # noqa: N802 - FreeCAD API name
        return "cam"

    def getPointOnViewport(self, x, y, z):  # noqa: N802 - FreeCAD API name
        return (1700.0, 300.0)


class _OverflowPort:
    def available(self, document):
        return (True, None)

    def view(self, document):
        return _OverflowView()


@pytest.fixture(autouse=True)
def _empty_cache():
    framing.reset_cache()
    yield
    framing.reset_cache()


def _tool_texts() -> dict[str, str]:
    """Every registered tool's ``text``, run through the wrapper with an overflowing viewport.

    The tool bodies are replaced by one stub envelope: what is under test is the wrapper the
    catalog wires around every spec, not any tool's own behavior.
    """
    stub = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"ok": True},
        "text": "tool summary",
    }
    texts = {}
    for spec in tool_catalog.tool_specs():
        handler = tool_catalog.with_framing(
            lambda **_p: dict(stub), _FakeRegistry(), _OverflowPort()
        )
        texts[spec.name] = handler(doc=_HANDLE)["text"]
        framing.reset_cache()
    return texts


def test_should_put_the_shared_sentence_in_every_tools_text_when_the_model_does_not_fit():
    # Act
    texts = _tool_texts()

    # Assert
    assert texts, "the catalog registered no tools"
    missing = sorted(name for name, text in texts.items() if not text.endswith(SENTENCE))
    assert missing == []


def test_should_wrap_every_registered_method_in_the_framing_wrapper():
    """A spec added later must not be able to opt out: the wrapper is applied in the loop, so a
    tool that carries no framing block is a tool the loop skipped."""
    # Arrange
    source = inspect.getsource(tool_catalog.build_inline_handlers)

    # Act
    wrapped = "with_framing(raw, doc_registry, viewport_port)" in source

    # Assert
    assert wrapped, "build_inline_handlers no longer applies with_framing to every spec"


def test_should_run_the_framing_read_inside_the_marshal_wrapper():
    """Marshal ordering is load-bearing: the framing read touches Qt, so it must execute on the
    FreeCAD main thread with the tool body. ``wrap(with_framing(raw))`` does; the inverse would
    pass the external test leg and fail only in the live GUI."""
    # Arrange
    source = inspect.getsource(tool_catalog.build_inline_handlers)

    # Act
    framed_then_wrapped = "wrap(framed, spec.timeout_s)" in source
    wrapped_then_framed = "with_framing(wrap(" in source

    # Assert
    assert framed_then_wrapped
    assert not wrapped_then_framed


def test_should_declare_the_framing_key_on_the_result_envelope_contract():
    # Act
    hints = envelope_contract.ResultEnvelope.__annotations__

    # Assert
    assert "framing" in hints
    assert envelope_contract.ResultEnvelope.__total__ is False, (
        "the key must be optional: an envelope without a viewport carries no framing block"
    )


# ---- the calibrated near-miss tolerance ---------------------------------------------------------


def test_should_keep_the_near_miss_tolerance_at_zero_so_every_miss_warns():
    """AD-32 reserved this knob against "a hair-trigger warning on every call". Calibration found
    nothing for it to suppress: ``fitAll`` frames the bounding *sphere* of the bbox
    (``View3DInventorViewer.cpp:4571-4573``), so a fitted model lands at
    ``largest_extent / space_diagonal`` — 0.58 for a cube, 0.99 for a 100x10x10 bar — and never
    overflows. The only other candidate is one pixel of ``short`` rounding, and suppressing that
    would also suppress a genuine one-pixel overflow, which AD-30 requires stay a miss."""
    # Act
    tolerance = envelope_contract.NEAR_MISS_TOLERANCE

    # Assert
    assert tolerance == 0.0


def test_should_warn_on_a_miss_that_only_just_overflows_while_the_tolerance_is_zero():
    # Arrange: ratio 1.001 — a hair over the viewport, and still a miss worth a sentence.
    verdict = {"fits": False, "ratio": 1.001, "checked": "computed", "stale_reason": None}

    # Act
    sentence = framing_warning(verdict)

    # Assert
    assert sentence == SENTENCE


def test_should_warn_when_the_ratio_is_unmeasurable_because_a_corner_was_discarded():
    """``ratio: None`` means a coordinate wrapped the ``short`` cast — a gross overflow, the last
    thing a tolerance should ever silence."""
    # Arrange
    verdict = {"fits": False, "ratio": None, "checked": "computed", "stale_reason": None}

    # Act
    sentence = framing_warning(verdict)

    # Assert
    assert sentence == SENTENCE
