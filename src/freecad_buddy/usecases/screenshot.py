"""View-controlled screenshot use case (Gui-free).

``query_screenshot`` resolves a document handle under the registry lock, fingerprints it,
assembles a ``SceneSpec`` from the ``view`` options (include/exclude object list, per-object
style overrides, camera orientation, focus/highlight targets), and hands it to a host-injected
``RenderPort``. It owns the temp-PNG lifecycle (removed on every non-OK path, including a
raising post-render fingerprint/compare) and asserts the document ``fingerprint()`` before ==
after, so the render is provably read-only.

Contains no ``FreeCADGui``/``pivy``/Qt import — all Gui/Coin work lives behind the ``RenderPort``
in ``adapters/render_probe.py``. The FreeCAD App API is used only through the passed document
handle and the fingerprint oracle.
"""

from __future__ import annotations

import math
import os
import tempfile

from freecad_buddy.contracts import (
    FocusSpec,
    ImageRef,
    RenderPort,
    ResultEnvelope,
    SceneSpec,
    StyleSpec,
    massprops_equal,
    mirror_text,
)
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

_MAX_DIM = 1920
_DEFAULT_WIDTH = 1920
_DEFAULT_HEIGHT = 1920

_ELEMENT_TYPES = frozenset({"face", "edge", "vertex"})

# Types skipped by a default (no ``include``) render. Datum/origin features are construction
# geometry, not model shape; a ``Sketcher::SketchObject`` has a non-null wire Shape but is a
# profile, not model shape, so it leaks into the scene otherwise; a ``PartDesign::Body`` is a
# container whose Coin subgraph aggregates its children through view-provider machinery that
# faults in a headless (no-GUI) renderer and leaves the Coin library unusable for every later
# object. An explicit ``include`` still renders any of them — the skip only shapes the automatic
# set to the shape-bearing leaf features.
_NON_RENDER_TYPE_PREFIXES = ("App::Origin", "App::Line", "App::Plane", "App::Point")
_NON_RENDER_TYPES = frozenset({"PartDesign::Body", "Sketcher::SketchObject"})


def _is_default_renderable(obj: object) -> bool:
    """Whether ``obj`` is in the automatic render set: visible, has a shape, not a datum/container.

    The default (no-``include``) set mirrors the live viewport — an object hidden via its
    ``Visibility`` flag is omitted. An explicit ``include`` bypasses this and renders the object.
    """
    type_id = str(getattr(obj, "TypeId", ""))
    if type_id in _NON_RENDER_TYPES or type_id.startswith(_NON_RENDER_TYPE_PREFIXES):
        return False
    if not bool(getattr(obj, "Visibility", True)):
        return False
    return _has_shape(obj)

# Fixed camera orientations (x, y, z, w quaternions). ``iso`` is FreeCAD's axonometric preset.
_CAMERA_QUATS: dict[str, tuple[float, float, float, float]] = {
    "iso": (0.424708, 0.17591, 0.339851, 0.820473),
    "front": (0.5, 0.5, 0.5, 0.5),
    "top": (0.0, 0.0, 0.0, 1.0),
    "bottom": (1.0, 0.0, 0.0, 0.0),
    "right": (0.5, 0.5, 0.5, 0.5),
    "left": (0.5, -0.5, -0.5, 0.5),
    "back": (0.0, 0.707107, 0.707107, 0.0),
}


def query_screenshot(
    registry: DocumentRegistry,
    render_port: RenderPort,
    doc: str | None = None,
    view: dict | None = None,
) -> ResultEnvelope:
    """Render a constructed, read-only screenshot of ``doc`` honoring the ``view`` options.

    Returns an ``OK`` envelope with the rendered PNG as an ``ImageRef`` ``resource_link`` and the
    §3.9 ``{render, scene}`` structured content. When the render ladder reports no capability the
    envelope is still ``OK`` with ``render.available:false`` and a reason (unavailability is not
    an error). Every invalid input (unknown object name, bad color/transparency/orientation,
    incoherent selector) raises ``ValidationError`` (``INVALID_INPUT``).
    """
    options = view or {}

    def read(_handle: str, document: object) -> ResultEnvelope:
        available, reason = render_port.available()
        if not available:
            return _unavailable_envelope(reason)

        scene, focus_echo = _build_scene(document, options)
        # A document with a pending or broken recompute (a Touched, Invalid, or Error object) is
        # self-unstable: reading .Shape while fingerprinting re-triggers the failing recompute, so
        # the render's before==after mutation guard cannot distinguish "render mutated geometry"
        # from that pre-existing churn. When the document is dirty the guard is skipped and the
        # render proceeds with a dirty_document note; a clean document keeps the strict read-only
        # assertion. A broken object with a null shape never enters the fingerprint, so State — not
        # a mass-property diff — is the signal that catches it.
        dirty = _document_is_dirty(document)
        before = fingerprint(document)
        result, out_path = _render_with_lifecycle(render_port, document, scene, before, dirty)
        image: ImageRef = {
            "kind": "resource_link",
            "uri": out_path,
            "mime_type": "image/png",
            "audience": ["user"],
        }
        structured = {
            "render": {
                "available": True,
                "resource_link": out_path,
                "reason": None,
                "dirty_document": dirty,
            },
            "scene": {
                "rendered_objects": result.rendered_objects,
                "focused_on": _focused_on(focus_echo, result.focused),
            },
        }
        return _ok_envelope(structured, image, summarize_screenshot(structured))

    return registry.with_document(doc, read)


# An object still carrying one of these in ``State`` did not recompute cleanly — either a failure
# ("Invalid"/"Error") or a silently-skipped pending recompute ("Touched"). Same vocabulary the
# verify_recompute use case keys on.
_DIRTY_STATES = frozenset({"Invalid", "Error", "Touched"})


def _document_is_dirty(document: object) -> bool:
    """Whether any object has a pending or failed recompute (Touched/Invalid/Error in ``State``)."""
    return any(
        token in _DIRTY_STATES
        for obj in document.Objects
        for token in (getattr(obj, "State", None) or [])
    )


def _render_with_lifecycle(render_port, document, scene, before, dirty):
    """Render into a temp PNG, verifying read-only + a non-empty file; clean up on any failure.

    The temp PNG is removed on EVERY non-OK path: ``render()`` raising, a fingerprint mismatch,
    an empty/absent output file, AND a raising post-render ``fingerprint()``/``fingerprints_equal``
    (a serializer-tag mismatch raises ``ValueError``). No path returns or propagates with the temp
    file orphaned.

    When ``dirty`` is set the document is already self-unstable (a pending or broken recompute), so
    the before==after mutation guard is meaningless and skipped; the non-empty-PNG check still runs.
    """
    fd, out_path = tempfile.mkstemp(prefix="FCB_TMP_shot_", suffix=".png")
    os.close(fd)
    try:
        result = render_port.render(document, scene, out_path)
        # Compare geometry (mass-properties), not raw BRep bytes: OCCT re-lays-out a freshly
        # loaded shape's serialization the first time a render touches it, so the byte digest
        # changes while the geometry is identical. A real mutation still changes the mass-props.
        if not dirty and not massprops_equal(before, fingerprint(document)):
            raise ValidationError("screenshot mutated the document (geometry changed)")
        if not os.path.exists(out_path) or os.path.getsize(out_path) <= 0:
            raise _RenderProduceError("render produced an empty or missing PNG")
    except BaseException:
        _remove(out_path)
        raise
    return result, out_path


class _RenderProduceError(RuntimeError):
    """A render call that returned without writing a usable (non-empty) PNG."""


def _remove(path: str) -> None:
    """Remove ``path`` if present, swallowing an already-gone file."""
    try:
        os.remove(path)
    except OSError:
        pass


def _build_scene(document: object, options: dict) -> tuple[SceneSpec, FocusSpec | None]:
    """Assemble the ``SceneSpec`` and the focus-echo from the validated ``view`` options."""
    objects = _object_list(document, options)
    styles = _styles(document, options.get("styles"))
    orientation = _orientation(options)
    focus = _selector(document, options.get("focus"), objects)
    highlight_spec = _selector(document, options.get("highlight"), objects)
    highlight = highlight_spec.object if highlight_spec is not None else None
    width = _clamp_dim(options.get("width"), _DEFAULT_WIDTH)
    height = _clamp_dim(options.get("height"), _DEFAULT_HEIGHT)
    scene = SceneSpec(
        objects=objects,
        orientation=orientation,
        width=width,
        height=height,
        styles=styles,
        highlight=highlight,
        focus=focus,
    )
    return scene, focus


def _object_list(document: object, options: dict) -> list[str]:
    """Resolve the include/exclude object list; every named object must exist (fail-closed).

    ``include`` (when present) is the exact set to render; otherwise all shape-bearing objects
    minus ``exclude``. Any nonexistent name in ``include``/``exclude`` raises ``ValidationError``.
    """
    include = options.get("include")
    exclude = set(options.get("exclude") or [])
    for name in exclude:
        _require_object(document, name)
    if include is not None:
        return [_require_object(document, name).Name for name in include]
    excluded = {_require_object(document, name).Name for name in exclude}
    return [
        obj.Name
        for obj in document.Objects
        if _is_default_renderable(obj) and obj.Name not in excluded
    ]


def _has_shape(obj: object) -> bool:
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    return shape is not None and not (is_null is not None and is_null())


def _styles(document: object, raw: object) -> list[StyleSpec]:
    """Build the per-object ``StyleSpec`` list; every styled object must exist."""
    if not raw:
        return []
    styles: list[StyleSpec] = []
    for entry in raw:
        name = _require_object(document, entry.get("object")).Name
        styles.append(
            StyleSpec(
                object=name,
                transparency=_coerce_transparency(entry.get("transparency")),
                color=_coerce_color(entry.get("color")),
            )
        )
    return styles


def _coerce_transparency(raw: object) -> float | None:
    """Convert a 0-100 transparency to a 0.0-1.0 fraction; a bad value raises ValidationError."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid transparency: {raw!r}") from exc
    if not 0.0 <= value <= 100.0:
        raise ValidationError(f"transparency out of range 0-100: {raw!r}")
    return value / 100.0


def _coerce_color(raw: object) -> tuple[float, float, float] | None:
    """Convert an RGB triple to floats; a wrong length or non-numeric element raises."""
    if raw is None:
        return None
    try:
        values = [float(component) for component in raw]
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid color: {raw!r}") from exc
    if len(values) != 3:
        raise ValidationError(f"color must be an RGB triple: {raw!r}")
    return (values[0], values[1], values[2])


def _orientation(options: dict) -> tuple[float, float, float, float]:
    """Resolve the camera quaternion from the ``camera`` preset or a validated ``custom`` quat."""
    camera = options.get("camera", "iso")
    if camera == "custom":
        return _custom_orientation(options.get("custom_orientation"))
    quat = _CAMERA_QUATS.get(camera)
    if quat is None:
        raise ValidationError(f"unknown camera preset: {camera!r}")
    return quat


def _custom_orientation(raw: object) -> tuple[float, float, float, float]:
    """Validate a 4-float quaternion: right length, finite, non-zero norm."""
    if raw is None:
        raise ValidationError("camera 'custom' requires custom_orientation (a 4-float quaternion)")
    try:
        values = [float(component) for component in raw]
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid custom_orientation: {raw!r}") from exc
    if len(values) != 4:
        raise ValidationError(f"custom_orientation must be a 4-float quaternion: {raw!r}")
    if not all(math.isfinite(v) for v in values):
        raise ValidationError(f"custom_orientation has non-finite components: {raw!r}")
    if math.sqrt(sum(v * v for v in values)) == 0.0:
        raise ValidationError(f"custom_orientation is degenerate (zero norm): {raw!r}")
    return (values[0], values[1], values[2], values[3])


def _selector(document: object, raw: object, rendered: list[str]) -> FocusSpec | None:
    """Resolve a focus/highlight selector to a ``FocusSpec``; incoherent selectors fail closed.

    The object must exist. A selector carrying BOTH ``mapped_name`` and ``element_type``/``index``
    is rejected; a non-string ``mapped_name`` is rejected; a partial sub-element selector
    (``element_type`` xor ``index``) is rejected. Returns ``None`` when ``raw`` is absent.
    """
    if not raw:
        return None
    name = _require_object(document, raw.get("object")).Name
    mapped_name = raw.get("mapped_name")
    element_type = raw.get("element_type")
    index = raw.get("index")

    has_mapped = mapped_name is not None
    has_element = element_type is not None or index is not None
    if has_mapped and has_element:
        raise ValidationError("selector cannot carry both mapped_name and element_type/index")
    if has_mapped and not isinstance(mapped_name, str):
        raise ValidationError(f"mapped_name must be a string: {mapped_name!r}")
    if has_element:
        _validate_element(element_type, index)
    return FocusSpec(
        object=name,
        element_type=element_type,
        index=index,
        mapped_name=mapped_name,
    )


def _validate_element(element_type: object, index: object) -> None:
    """Reject a partial or malformed element_type/index sub-element selector."""
    if element_type is None or index is None:
        raise ValidationError("sub-element selector requires both element_type and index")
    if element_type not in _ELEMENT_TYPES:
        raise ValidationError(f"unknown element_type: {element_type!r}")
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValidationError(f"element index must be an integer: {index!r}")


def _require_object(document: object, name: object) -> object:
    """Return the object named ``name`` on ``document``, or raise ``ValidationError``."""
    if not name or not isinstance(name, str):
        raise ValidationError(f"selector/style requires an object name: {name!r}")
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object: {name}")
    return obj


def _clamp_dim(raw: object, default: int) -> int:
    """Coerce a dimension to a 1.._MAX_DIM int; a bad value raises ``ValidationError``."""
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid image dimension: {raw!r}") from exc
    if value <= 0:
        raise ValidationError(f"image dimension must be positive: {raw!r}")
    return min(value, _MAX_DIM)


def _focused_on(focus: FocusSpec | None, sub_framed: bool) -> dict | None:
    """Echo the focus resolution, dropping the sub-element part when the camera did not sub-frame.

    On any fallback (``sub_framed`` false) the echo is object-only, so the response never claims a
    sub-element framing that did not happen.
    """
    if focus is None:
        return None
    echo: dict = {"object": focus.object}
    if sub_framed:
        if focus.mapped_name is not None:
            echo["mapped_name"] = focus.mapped_name
        else:
            echo["element_type"] = focus.element_type
            echo["index"] = focus.index
    return echo


def summarize_screenshot(sc: dict) -> str:
    """One-line screenshot summary: render count + dirty flag."""
    render = sc.get("render", {})
    scene = sc.get("scene", {})
    n = len(scene.get("rendered_objects", []))
    if not render.get("available", False):
        return f"Render unavailable: {render.get('reason')}."
    dirty = " Document dirty (pending/broken recompute)." if render.get("dirty_document") else ""
    return f"Rendered {n} objects.{dirty}"


def _ok_envelope(structured: dict, image: ImageRef, summary: str | None = None) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summary if summary is not None else mirror_text(structured),
        "images": [image],
    }


def _unavailable_envelope(reason: str | None) -> ResultEnvelope:
    """Render unavailable: ``OK`` with ``render.available:false`` and no ``resource_link``."""
    structured = {
        "render": {"available": False, "reason": reason},
        "scene": {"rendered_objects": [], "focused_on": None},
    }
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": mirror_text(structured),
    }


__all__ = ["query_screenshot"]
