"""Render capability probe and the offscreen render port (the AD-1 render carve-out).

``render_capability()`` runs the detection ladder once per process (cached) and reports
``"gui_constructed" | "offscreen" | "none"`` plus a reason. ``OffscreenRenderPort`` implements
the ``RenderPort`` protocol: it builds a fresh Coin scene from ``subgraphFromObject`` per object,
renders it offscreen with ``FreeCADGui.SoQtOffscreenRenderer``, and writes a PNG.

Every ``FreeCADGui``/``pivy.coin``/Qt import is function-local so the module stays importable
without a GUI stack; this is the only ring outside ``hosts/`` allowed those imports.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache

from freecad_buddy.contracts.render import FocusSpec, RenderResult, SceneSpec

_PROBE_SIZE = 8

_ACCENT_COLOR = (1.0, 0.55, 0.0)

# A sketch draws its lines in the ``SketchEdgeColor`` preference, whose default is white
# (ViewProviderSketch.cpp:390-396) — invisible on the white render background. Screenshots draw
# every unstyled sketch in this fixed dark #212529 instead, so the image never depends on the
# operator's profile.
_SKETCH_LINE_COLOR = (0x21 / 255.0, 0x25 / 255.0, 0x29 / 255.0)

# Focus framing: the bbox spans 1/_FRAME_GROW of the frame's binding axis, leaving ~20% margin.
# _MIN_FRAME_EXTENT floors every derived extent so a bbox degenerate on a projected axis still
# yields a valid view volume.
_FRAME_GROW = 1.2
_MIN_FRAME_EXTENT = 1e-3

# Headlight aim, as an offset from the camera's default -Z look axis, its intensity, and the
# ambient fill. All three are measured against a 10x20x30 box rendered at 240x240 from every named
# camera plus `custom`, sampling the non-background pixels inside the middle 80% of each axis:
#
#   * The offscreen renderer honors exactly ONE SoDirectionalLight. A second light — any
#     direction, intensity, or child order — puts every axis-aligned camera back at pure white.
#     That is why this is one offset light rather than an on-axis key plus an angled fill.
#   * Offset magnitude has a cliff, not a falloff: (0.25, 0.18) still renders `front` white at
#     ~1,276 edge-only samples, while (0.30, 0.20) lights the face at ~13,000 samples. The value
#     below sits well past that cliff so a renderer or driver that shifts the threshold slightly
#     does not silently reopen the white end.
#   * The ceiling is set by the brightest default material, FreeCAD's stock diffuse
#     (0.8, 0.8, 0.9) (App/Material.cpp). A profile with no `DefaultShapeColor` preference — every
#     fresh install and CI — renders with it, and its blue channel is what reaches 235 first.
#   * The headlight intensity, not ambient, holds that ceiling. An axis-aligned view takes most of
#     its tone from the headlight (~183/255 of `right`'s blue at full intensity) and `iso` only
#     ~85/255, while ambient lifts every camera by the same amount. Dimming the light therefore
#     pulls the brightest views down about twice as fast as `iso`. Measured on llvmpipe, FreeCAD
#     1.1.3, stock material: at intensity 1.0 `right` reads blue 242.7 and `front` 236.0, both
#     out of band; at 0.80 the brightest camera (`right`) reads 205.3, `iso` reads
#     rgb(127,127,136) and the darkest (`custom`) 113.9. Holding the ceiling with ambient alone
#     needs 0.30 and leaves `iso` at 112; widening the offset instead saturates one `iso` face to
#     pure white once ambient reaches 0.65.
#   * The darker steel-blue diffuse (0.68, 0.71, 0.74) a customised profile can carry renders every
#     camera between 105 and 179 at these values, so both ends keep a wide margin.
_HEADLIGHT_OFFSET = (0.55, 0.38, -1.0)
_HEADLIGHT_INTENSITY = 0.80
_AMBIENT_INTENSITY = 0.70

# FreeCAD stores the 3D-view anti-aliasing choice as the ``AntiAliasing`` enum value under this
# preference group/key (Gui/Multisample.h). The enum is NOT sequential — MSAA6x=5 and MSAA8x=4 —
# so map each stored value to its true multisample count, matching the live viewport instead of a
# hard-coded value.
_AA_PREF_GROUP = "User parameter:BaseApp/Preferences/View"
_AA_PREF_KEY = "AntiAliasing"
_AA_ENUM_TO_SAMPLES = {0: 0, 1: 1, 2: 2, 3: 4, 4: 8, 5: 6}

# Without this Coin couples the diffuse and transparency overrides, so a style that overrides only
# transparency also replaces the object's color (measured: a red box with transparency 0.5 rendered
# grey rgb(143,143,143); with the variable set, rgb(143,117,117)). In GUI mode FreeCAD's own 3D
# view sets it (``View3DInventorSelection.cpp:60``). A headless process never builds one, and Coin
# reads the variable once, at the first override it traverses, so a headless render must set it
# before that traversal. The write is idempotent, so ``render()`` makes it on every call.
_SEPARATE_OVERRIDE_ENV = "COIN_SEPARATE_DIFFUSE_TRANSPARENCY_OVERRIDE"


def _no_display_reason() -> str | None:
    """Why Qt cannot open a platform plugin here, or ``None`` when it can.

    On Linux, creating a ``QGuiApplication`` with no X11 or Wayland display and no explicit
    ``QT_QPA_PLATFORM`` makes Qt abort the whole process ("no Qt platform plugin could be
    initialized"). An abort cannot be caught, so the probe must refuse before it reaches Qt.
    """
    if not sys.platform.startswith("linux"):
        return None
    if any(os.environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")):
        return None
    return "no display server: DISPLAY, WAYLAND_DISPLAY and QT_QPA_PLATFORM are all unset"


class RenderError(RuntimeError):
    """Raised when the offscreen render pipeline fails to produce an image."""


@lru_cache(maxsize=1)
def render_capability() -> tuple[str, str | None]:
    """Detect the render capability once per process: ``(mode, reason)``.

    Ladder (detection-mcp-freecad §6): a live GUI is ``gui_constructed``; else a lazy
    ``FreeCADGui`` import, a display check (no display on Linux is ``none``, since Qt would abort
    the process), then ``setupWithoutGUI()``, a ``QGuiApplication``, and a successful 8x8 probe
    render is ``offscreen``; any import/GL/probe failure is ``none``
    with the reason. ``reason`` is set only for ``none``.
    """
    try:
        import FreeCAD
    except Exception as exc:  # noqa: BLE001 - no FreeCAD means no render context
        return "none", f"FreeCAD not importable: {exc}"

    if getattr(FreeCAD, "GuiUp", False):
        return "gui_constructed", None

    try:
        import FreeCADGui
    except Exception as exc:  # noqa: BLE001 - no Gui module means no offscreen path
        return "none", f"FreeCADGui not importable: {exc}"

    no_display = _no_display_reason()
    if no_display:
        return "none", no_display

    try:
        FreeCADGui.setupWithoutGUI()
        from pivy import coin

        _ensure_qgui_application()
        renderer = FreeCADGui.SoQtOffscreenRenderer(_PROBE_SIZE, _PROBE_SIZE)
        renderer.render(coin.SoSeparator())
    except Exception as exc:  # noqa: BLE001 - any probe failure means no usable GL context
        return "none", f"offscreen probe render failed: {exc}"
    return "offscreen", None


def render_capability_flag() -> str:
    """The render capability mode alone (``gui_constructed`` / ``offscreen`` / ``none``)."""
    return render_capability()[0]


def _add_lighting(coin, root, orientation) -> None:
    """Add an off-axis headlight plus ambient fill so every camera renders a separable face tone.

    FreeCAD's live viewport lights the scene with a headlight that follows the camera, and that
    headlight is not exactly camera-parallel — which is why the viewport shades an axis-aligned
    view correctly. The invariant here is two-sided: a face must render neither black nor white,
    but at a tone the eye and an assertion can both separate from the background. A headlight aimed
    exactly along the view axis fails the white end on an axis-aligned camera: the visible face's
    normal is anti-parallel to the light, the diffuse term degenerates, and the ambient term alone
    saturates the near-white default material to pure white, leaving a PNG with no shape
    information beyond its outline.

    The headlight is therefore offset off the pure view axis by ``_HEADLIGHT_OFFSET`` before the
    orientation is applied, so an anti-parallel face still receives a diffuse term.
    """
    offset = coin.SbVec3f(*_HEADLIGHT_OFFSET)
    offset.normalize()
    headlight = coin.SoDirectionalLight()
    headlight.direction.setValue(coin.SbRotation(*orientation).multVec(offset))
    headlight.intensity.setValue(_HEADLIGHT_INTENSITY)
    environment = coin.SoEnvironment()
    environment.ambientIntensity.setValue(_AMBIENT_INTENSITY)
    root.addChild(environment)
    root.addChild(headlight)


def _configured_msaa_samples() -> int:
    """Return the multisample count from FreeCAD's 3D-view anti-aliasing preference (0 if unset)."""
    import FreeCAD

    group = FreeCAD.ParamGet(_AA_PREF_GROUP)
    enum_value = int(group.GetInt(_AA_PREF_KEY, 0))
    return _AA_ENUM_TO_SAMPLES.get(enum_value, 0)


def _apply_configured_msaa(renderer: object) -> None:
    """Set the renderer's multisample count from FreeCAD's preference, if the build supports it."""
    setter = getattr(renderer, "setNumPasses", None)
    if setter is None:
        return
    samples = _configured_msaa_samples()
    if samples > 1:
        setter(samples)


def _ensure_qgui_application() -> None:
    """Ensure a ``QGuiApplication`` exists so the offscreen renderer has a GL context."""
    from PySide import QtGui

    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])


class OffscreenRenderPort:
    """Constructed-scene offscreen renderer implementing the ``RenderPort`` protocol.

    Serves both hosts: GUI mode runs it on the Qt main thread via the marshal, headless runs it
    inline. The scene is composed per call and never mutates the document, object ``Visibility``,
    or the live viewport.
    """

    def available(self) -> tuple[bool, str | None]:
        """Whether a render context exists; ``(False, reason)`` when the ladder reports none."""
        mode, reason = render_capability()
        return (mode != "none", reason)

    def render(self, document: object, scene: SceneSpec, out_path: str) -> RenderResult:
        """Render ``scene`` for ``document`` to ``out_path``; return the rendered set + focus flag.

        Renders the passed ``document``'s objects only — never ``FreeCAD.ActiveDocument`` (AD-20).
        Gates ``setupWithoutGUI()`` on ``offscreen`` mode so a live GUI process is never torn into
        no-GUI mode to take a screenshot.
        """
        import FreeCADGui
        from pivy import coin

        mode, reason = render_capability()
        if mode == "none":
            raise RenderError(reason or "render unavailable")
        os.environ[_SEPARATE_OVERRIDE_ENV] = "1"
        if mode == "offscreen":
            FreeCADGui.setupWithoutGUI()
            _ensure_qgui_application()

        root = coin.SoSeparator()
        camera = coin.SoOrthographicCamera()
        camera.orientation.setValue(coin.SbRotation(*scene.orientation))
        root.addChild(camera)
        _add_lighting(coin, root, scene.orientation)
        viewport = coin.SbViewportRegion(scene.width, scene.height)

        live = _LiveState(FreeCADGui, document, mode)
        try:
            rendered = _add_subgraphs(FreeCADGui, coin, root, document, scene, viewport, live)
        finally:
            live.restore()

        if not rendered:
            # Nothing drawable was added, so the only thing left to frame is the camera and the
            # light. Rendering that writes a blank PNG the caller cannot distinguish from a real
            # one; report the empty scene instead and write no image at all.
            return RenderResult(rendered_objects=[], focused=False, empty_scene=True)

        focused = _aim_camera(coin, camera, document, scene.focus, rendered, root, viewport)

        renderer = FreeCADGui.SoQtOffscreenRenderer(scene.width, scene.height)
        renderer.setBackgroundColor(1.0, 1.0, 1.0)
        _apply_configured_msaa(renderer)
        renderer.render(root)
        # writeToImage returns None on success on some builds (it does not return a bool), so the
        # written file is the success signal: a non-empty PNG on disk means the render succeeded.
        renderer.writeToImage(out_path)
        if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
            raise RenderError(f"offscreen render produced no image at {out_path}")
        return RenderResult(rendered_objects=rendered, focused=focused)


class _LiveState:
    """The live ``Visibility`` flags and GUI ``Modified`` flag a render must leave as it found them.

    ``subgraphFromObject`` builds a fresh view provider and attaches it, and ``attach`` copies that
    provider's default ``Visibility=true`` onto the live object
    (``ViewProviderDocumentObject.cpp:360-363``). Building the subgraph of a hidden object therefore
    un-hides it in the human's document and, in the GUI, marks the document modified. Each flag is
    recorded before its subgraph is built and written back only when it changed. ``Modified`` is
    restored last, because writing a ``Visibility`` back can set it again.
    """

    def __init__(self, gui, document, mode: str) -> None:
        self._visibility: list[tuple[object, bool]] = []
        self._gui_document = gui.getDocument(document.Name) if mode == "gui_constructed" else None
        self._modified = self._gui_document.Modified if self._gui_document is not None else None

    def record(self, obj) -> None:
        self._visibility.append((obj, bool(obj.Visibility)))

    def restore(self) -> None:
        # Reversed, so an object recorded twice ends at its first, untouched value.
        for obj, visible in reversed(self._visibility):
            if bool(obj.Visibility) != visible:
                obj.Visibility = visible
        if self._gui_document is not None and self._gui_document.Modified != self._modified:
            self._gui_document.Modified = self._modified


def _add_subgraphs(gui, coin, root, document, scene, viewport, live: _LiveState) -> list[str]:
    """Add each scene object's subgraph to ``root``; return the names that drew something.

    A subgraph with an empty bounding box draws nothing, so it is left out and its name does not
    count as rendered: a scene of only such subgraphs is an empty scene, never a blank PNG. Styles
    and the highlight key on the name the caller gave, so a style on a Body reaches its Tip.
    """
    styles = {style.object: style for style in scene.styles}
    rendered: list[str] = []
    for name in scene.objects:
        source = _subgraph_source(document.getObject(name))
        if source is None:
            continue
        live.record(source)
        sub = gui.subgraphFromObject(source)
        if sub is None or _is_empty(coin, sub, viewport):
            continue
        base_color = _SKETCH_LINE_COLOR if _is_sketch(source) else None
        root.addChild(_wrap_style(coin, sub, styles.get(name), scene.highlight == name, base_color))
        rendered.append(name)
    return rendered


def _is_sketch(obj) -> bool:
    is_derived_from = getattr(obj, "isDerivedFrom", None)
    return is_derived_from is not None and bool(is_derived_from("Sketcher::SketchObject"))


def _subgraph_source(obj):
    """The object whose subgraph draws ``obj``: a ``PartDesign::Body``'s Tip, else ``obj`` itself.

    A Body's own view provider is never built: its subgraph faults the headless Coin library and
    leaves it unusable for every later object, and it does not draw the Body's features. The Tip is
    the Body's result shape. A Body with no Tip, or a missing object, draws nothing (``None``).
    """
    is_derived_from = getattr(obj, "isDerivedFrom", None)
    if is_derived_from is not None and is_derived_from("PartDesign::Body"):
        return obj.Tip
    return obj


def _is_empty(coin, subgraph, viewport) -> bool:
    action = coin.SoGetBoundingBoxAction(viewport)
    action.apply(subgraph)
    return bool(action.getBoundingBox().isEmpty())


# Every field of a ``SoMaterial``; ``_wrap_style`` marks the ones it does not write as ignored.
_MATERIAL_FIELDS = (
    "ambientColor",
    "diffuseColor",
    "specularColor",
    "emissiveColor",
    "shininess",
    "transparency",
)


def _wrap_style(coin, subgraph, style, is_highlight, base_color=None):
    """Wrap ``subgraph`` in a separator with a prepended overriding material.

    A highlight sets the diffuse color to ``_ACCENT_COLOR``, taking precedence over ``style.color``,
    which in turn takes precedence over ``base_color``; ``style.transparency`` is applied whether
    or not the object is highlighted. Returns the raw subgraph unchanged when there is no color and
    no transparency to apply.

    The material always overrides, because the object's own material sits deeper in the subgraph
    and would otherwise win. Every field it does not write is marked ignored, so only the written
    fields override: a transparency-only style keeps the object's own color, and a color-only
    style keeps its own transparency.
    """
    style_color = style.color if style is not None else None
    transparency = style.transparency if style is not None else None
    if is_highlight:
        color = _ACCENT_COLOR
    else:
        color = style_color if style_color is not None else base_color
    if color is None and transparency is None:
        return subgraph
    separator = coin.SoSeparator()
    material = coin.SoMaterial()
    written = set()
    if color is not None:
        material.diffuseColor.setValue(*color)
        written.add("diffuseColor")
    if transparency is not None:
        material.transparency.setValue(transparency)
        written.add("transparency")
    for field_name in _MATERIAL_FIELDS:
        if field_name not in written:
            getattr(material, field_name).setIgnored(True)
    material.setOverride(True)
    separator.addChild(material)
    separator.addChild(subgraph)
    return separator


def _aim_camera(coin, camera, document, focus, rendered, root, viewport):
    """Aim ``camera`` at the focus target's bbox, or ``viewAll`` the scene; return the focus flag.

    Returns ``True`` only when a sub-element bbox was actually framed. A whole-object focus, an
    unresolved sub-element, or no focus all fall back to ``viewAll`` and return ``False`` so the
    usecase echoes object-only (or drops the echo entirely).
    """
    if focus is not None:
        bbox = _focus_bbox(document, focus, rendered)
        if bbox is not None:
            _frame_bbox(coin, camera, bbox, viewport)
            return _is_sub_element(focus)
    camera.viewAll(root, viewport)
    return False


def _is_sub_element(focus: FocusSpec) -> bool:
    """Whether ``focus`` names a sub-element (element_type+index or mapped_name)."""
    return focus.mapped_name is not None or (
        focus.element_type is not None and focus.index is not None
    )


def _focus_bbox(document, focus: FocusSpec, rendered):
    """Resolve the focus target to a FreeCAD ``BoundBox``, or ``None`` when it cannot sub-frame.

    Returns ``None`` (whole-scene fallback) when the focus object is not in the rendered set, has
    no ``Shape``, or names a sub-element/mapped_name that does not resolve.
    """
    if focus.object not in rendered:
        return None
    obj = document.getObject(focus.object)
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        return None
    sub = _sub_shape(shape, focus)
    if sub is None:
        return None
    try:
        return sub.BoundBox
    except Exception:  # noqa: BLE001 - a degenerate sub-shape has no usable bbox
        return None


def _sub_shape(shape, focus: FocusSpec):
    """Return the ``focus`` sub-shape, the whole shape for a whole-object focus, or None."""
    if focus.mapped_name is not None:
        return _mapped_sub_shape(shape, focus.mapped_name)
    if focus.element_type is not None and focus.index is not None:
        return _indexed_sub_shape(shape, focus.element_type, focus.index)
    return shape


def _indexed_sub_shape(shape, element_type: str, index: int):
    """Return the 0-based ``index`` sub-shape of ``element_type`` on ``shape``, or ``None``."""
    collection = {
        "face": getattr(shape, "Faces", None),
        "edge": getattr(shape, "Edges", None),
        "vertex": getattr(shape, "Vertexes", None),
    }.get(element_type)
    if not collection or index < 0 or index >= len(collection):
        return None
    return collection[index]


def _mapped_sub_shape(shape, mapped_name: str):
    """Return the sub-shape for a TNP ``mapped_name`` via the element map, or ``None``."""
    getter = getattr(shape, "getElement", None)
    if getter is None:
        return None
    try:
        return getter(mapped_name)
    except Exception:  # noqa: BLE001 - an unresolved mapped name frames the whole object
        return None


def _frame_bbox(coin, camera, bbox, viewport):
    """Aim ``camera`` at ``bbox`` so it spans ``1 / _FRAME_GROW`` of the frame's binding axis.

    The bbox corners are rotated into the camera's own frame, and the height comes from the extents
    measured there. Framing via ``viewAll`` over a proxy cube cannot do this: ``viewAll``
    circumscribes a *sphere*, so the resulting height is the bbox space diagonal regardless of
    orientation — loose on most views and clipping on others.

    ``camera.height`` is the world height and the world width is ``height * aspect``, so the
    horizontal extent only constrains the framing on a viewport taller than it is wide.
    """
    inverse = camera.orientation.getValue().inverse()
    local = [
        inverse.multVec(coin.SbVec3f(x, y, z)).getValue()
        for x in (bbox.XMin, bbox.XMax)
        for y in (bbox.YMin, bbox.YMax)
        for z in (bbox.ZMin, bbox.ZMax)
    ]
    span_x, span_y, span_z = (
        max(axis) - min(axis) for axis in ([point[i] for point in local] for i in range(3))
    )

    size = viewport.getViewportSizePixels()
    aspect = size[0] / size[1]
    # A bbox degenerate on a projected axis (an edge seen end-on) would give a zero height and an
    # undefined view volume; the floor keeps the camera valid and the render non-blank.
    height = max(span_y * _FRAME_GROW, span_x * _FRAME_GROW / aspect, _MIN_FRAME_EXTENT)

    view_direction = camera.orientation.getValue().multVec(coin.SbVec3f(0.0, 0.0, -1.0))
    center = coin.SbVec3f(bbox.Center.x, bbox.Center.y, bbox.Center.z)
    # Stand off by the full frame height beyond the geometry's own depth so the near plane clears
    # the bbox for any orientation. The depth is floored too: a bbox flat along the view axis would
    # otherwise collapse near onto far, leaving a zero-thickness view volume that renders nothing.
    depth = max(span_z, _MIN_FRAME_EXTENT)
    distance = depth * 0.5 + height
    camera.height.setValue(height)
    camera.position.setValue(center - view_direction * distance)
    camera.nearDistance.setValue(max(distance - depth, _MIN_FRAME_EXTENT))
    camera.farDistance.setValue(distance + depth)
    camera.focalDistance.setValue(distance)


__all__ = [
    "OffscreenRenderPort",
    "RenderError",
    "render_capability",
    "render_capability_flag",
]
