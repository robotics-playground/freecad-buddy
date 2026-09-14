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
import time
from functools import lru_cache

from freecad_buddy.contracts.render import FocusSpec, RenderResult, SceneSpec

_PROBE_SIZE = 8

_ACCENT_COLOR = (1.0, 0.55, 0.0)

# Focus framing: the bbox spans 1/_FRAME_GROW of the frame's binding axis, leaving ~20% margin.
# _MIN_FRAME_EXTENT floors every derived extent so a bbox degenerate on a projected axis still
# yields a valid view volume.
_FRAME_GROW = 1.2
_MIN_FRAME_EXTENT = 1e-3

# Headlight aim, as an offset from the camera's default -Z look axis, and the ambient fill.
# Both are measured against a 10x20x30 box rendered at 240x240 from every named camera plus
# `custom`, sampling the non-background pixels inside the middle 80% of each axis:
#
#   * The offscreen renderer honors exactly ONE SoDirectionalLight. A second light — any
#     direction, intensity, or child order — puts every axis-aligned camera back at pure white.
#     That is why this is one offset light rather than an on-axis key plus an angled fill.
#   * Offset magnitude has a cliff, not a falloff: (0.25, 0.18) still renders `front` white at
#     ~1,276 edge-only samples, while (0.30, 0.20) lights the face at ~13,000 samples. The value
#     below sits well past that cliff so a renderer or driver that shifts the threshold slightly
#     does not silently reopen the white end.
#   * Ambient and the offset trade against each other and cannot both be satisfied. An
#     axis-aligned view is lit almost entirely by ambient plus a grazing diffuse term, while `iso`
#     also gets a head-on diffuse term. Raising ambient to bring `iso` up to the live viewport's
#     rgb(158,165,169) raises the axis-aligned views nearly one-for-one, and at 0.95 they overshoot
#     the 235 ceiling (`right` measured 241.6 on blue). Light intensity does not separate them —
#     it is already 1.0. So ambient is set for the ceiling, not for `iso`: at these values every
#     camera holds >=24/255 of headroom below 235 and clears the background by >=57/255, while
#     `iso` reads rgb(131,135,138) — darker than the viewport, which is the cost of keeping the
#     axis-aligned views inside the band.
_HEADLIGHT_OFFSET = (0.55, 0.38, -1.0)
_AMBIENT_INTENSITY = 0.70

# FreeCAD stores the 3D-view anti-aliasing choice as the ``AntiAliasing`` enum value under this
# preference group/key (Gui/Multisample.h). The enum is NOT sequential — MSAA6x=5 and MSAA8x=4 —
# so map each stored value to its true multisample count, matching the live viewport instead of a
# hard-coded value.
_AA_PREF_GROUP = "User parameter:BaseApp/Preferences/View"
_AA_PREF_KEY = "AntiAliasing"
_AA_ENUM_TO_SAMPLES = {0: 0, 1: 1, 2: 2, 3: 4, 4: 8, 5: 6}


class RenderError(RuntimeError):
    """Raised when the offscreen render pipeline fails to produce an image."""


@lru_cache(maxsize=1)
def render_capability() -> tuple[str, str | None]:
    """Detect the render capability once per process: ``(mode, reason)``.

    Ladder (detection-mcp-freecad §6): a live GUI is ``gui_constructed``; else a lazy
    ``FreeCADGui`` import followed immediately by ``setupWithoutGUI()``, a ``QGuiApplication``,
    and a successful 8x8 probe render is ``offscreen``; any import/GL/probe failure is ``none``
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
        if mode == "offscreen":
            FreeCADGui.setupWithoutGUI()
            _ensure_qgui_application()

        styles = {style.object: style for style in scene.styles}
        root = coin.SoSeparator()
        camera = coin.SoOrthographicCamera()
        camera.orientation.setValue(coin.SbRotation(*scene.orientation))
        root.addChild(camera)
        _add_lighting(coin, root, scene.orientation)

        rendered: list[str] = []
        subgraphs: dict[str, object] = {}
        for name in scene.objects:
            obj = document.getObject(name)
            if obj is None:
                continue
            sub = FreeCADGui.subgraphFromObject(obj)
            if sub is None:
                continue
            styled = _wrap_style(coin, sub, styles.get(name), scene.highlight == name)
            root.addChild(styled)
            rendered.append(name)
            subgraphs[name] = sub

        if not rendered:
            # Nothing drawable was added, so the only thing left to frame is the camera and the
            # light. Rendering that writes a blank PNG the caller cannot distinguish from a real
            # one; report the empty scene instead and write no image at all.
            return RenderResult(rendered_objects=[], focused=False, empty_scene=True)

        viewport = coin.SbViewportRegion(scene.width, scene.height)
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


def _wrap_style(coin, subgraph, style, is_highlight):
    """Wrap ``subgraph`` in a separator with a prepended overriding material.

    A highlight sets the diffuse color to ``_ACCENT_COLOR``, taking precedence over ``style.color``;
    ``style.transparency`` is applied whether or not the object is highlighted. Returns the raw
    subgraph unchanged when there is no highlight and no style field to apply.

    The material is marked as overriding only when a diffuse color is written. ``setOverride`` is
    node-wide rather than per-field, so a material that overrode while carrying an unwritten diffuse
    would force Coin's default grey over the object's own color.
    """
    has_style = style is not None and (style.color is not None or style.transparency is not None)
    if not has_style and not is_highlight:
        return subgraph
    separator = coin.SoSeparator()
    material = coin.SoMaterial()
    color = _ACCENT_COLOR if is_highlight else style.color
    if color is not None:
        material.diffuseColor.setValue(*color)
        material.setOverride(True)
    if style is not None and style.transparency is not None:
        material.transparency.setValue(style.transparency)
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


# Wall-clock yielded per settle attempt. The hidden-line-removal pass runs on a worker thread, so
# the main thread must actually give up the CPU for it to make progress: at 10 ms a measured view
# completed in 2 attempts, while pumping with no sleep took 888. Small enough that the headless
# leg — where the pass is synchronous and never settles at all — pays nothing.
_SETTLE_SLEEP_S = 0.01


class RasterError(RuntimeError):
    """Raised when the SVG rasterizer fails to produce an image."""


class QtSvgRasterPort:
    """Qt-backed SVG-to-PNG rasterizer implementing the ``SvgRasterPort`` protocol.

    Rasterizes the judge sheet ``usecases/techdraw.py`` composes. It lives here rather than in a
    new adapter because Qt is legal in exactly two places — ``hosts/**`` and this file — and AD-29
    pins that carve-out to one adapter (``scripts/check_imports.py`` ``QT_EXEMPT_ADAPTERS``, and
    the test that asserts the set holds only this path).

    **Why Qt rather than a new dependency.** The judge needs a raster on both the headless CI leg
    and the Windows operator machine, and a sheet that rasterizes on only one leg cannot support
    Epic 5's headless service. ``PySide6.QtSvg`` ships inside FreeCAD's own bundle, so it is
    present wherever FreeCAD is, adds nothing to ``pyproject.toml``, and needs no display: measured
    under ``FreeCADCmd`` on FreeCAD 1.1.1 (Libs 1.1.1R20260414) on Windows with no display server,
    a 2048x1024 raster of a sheet carrying stroked paths and text wrote a 26,982-byte PNG with the
    text rendered as real glyphs. ``cairosvg`` was the alternative considered and rejected: it is
    absent from the bundle, so it would be a new third-party dependency that must then be proven
    installable on every leg to buy what Qt already provides.

    Unlike ``OffscreenRenderPort`` this needs no GL context and no Coin scene — ``QSvgRenderer``
    paints into a ``QImage`` through the raster paint engine — so its availability is deliberately
    NOT gated on ``render_capability()``. A leg with no usable GL still rasterizes a sheet.
    """

    def available(self) -> tuple[bool, str | None]:
        """Whether Qt's SVG module can be imported; ``(False, reason)`` naming what is missing."""
        try:
            self._qt()
        except Exception as exc:  # noqa: BLE001 - any import failure means no rasterizer
            return False, f"Qt SVG rasterizer unavailable: {exc}"
        return True, None

    def settle(self) -> None:
        """Give a pending HLR pass one turn to advance: pump Qt's queue, then yield the CPU.

        **Both halves are required, and the sleep is the load-bearing one.** Measured on FreeCAD
        1.1.1 with a ``QApplication`` up, over the same 80x60x6 plate, counting iterations until
        ``viewPartAsSvg`` first returned path geometry:

        * ``processEvents()`` alone — **888** iterations;
        * ``processEvents()`` then ``sleep(0.01)`` — **2** iterations;
        * ``sleep(0.01)`` alone — still nothing after **500**.

        The pass runs on a worker thread, so a bare pump loop spins the main thread hot and starves
        it, while the pump alone is what lets the completion be observed. Sleeping without pumping
        never finishes. Hence pump, then yield.

        A process with no Qt application object has nothing to pump; the sleep then costs one
        ``_SETTLE_SLEEP_S`` per attempt, which the caller never pays because HLR is synchronous
        there and the first read already succeeded.

        Any failure is swallowed. This is a best-effort nudge inside a polling loop whose real
        verdict is whether the SVG arrived; raising here would replace a recoverable wait with an
        error.
        """
        try:
            from PySide import QtGui

            app = QtGui.QGuiApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:  # noqa: BLE001 - a nudge that cannot run leaves the poll to time out
            pass
        time.sleep(_SETTLE_SLEEP_S)

    def rasterize(self, svg: str, out_path: str, width: int, height: int) -> None:
        """Paint ``svg`` into a ``width`` x ``height`` PNG at ``out_path``.

        The image is filled white first: an unfilled ``QImage`` starts with undefined contents, and
        the composed sheet draws unfilled strokes, so painting onto it directly would hand the
        judge line art over noise.

        :raises RasterError: Qt is unavailable, the SVG does not parse, or the write fails.
        """
        try:
            qtsvg, qtgui = self._qt()
        except Exception as exc:  # noqa: BLE001 - surfaced as the port's own failure type
            raise RasterError(f"Qt SVG rasterizer unavailable: {exc}") from exc

        _ensure_qgui_application()
        renderer = qtsvg.QSvgRenderer(bytearray(svg.encode("utf-8")))
        if not renderer.isValid():
            raise RasterError("composed sheet is not parseable SVG")

        image = qtgui.QImage(width, height, qtgui.QImage.Format_RGB32)
        image.fill(qtgui.QColor(255, 255, 255))
        painter = qtgui.QPainter(image)
        try:
            renderer.render(painter)
        finally:
            # A QPainter still active when its QImage is saved leaves the paint device locked and
            # the file empty, so the end() must survive a failing render.
            painter.end()
        if not image.save(out_path, "PNG"):
            raise RasterError(f"could not write the rasterized sheet to {out_path}")

    @staticmethod
    def _qt():
        """Return the ``(QtSvg, QtGui)`` module pair, raising when either is unavailable."""
        from PySide import QtGui, QtSvg

        return QtSvg, QtGui


__all__ = [
    "OffscreenRenderPort",
    "QtSvgRasterPort",
    "RasterError",
    "RenderError",
    "render_capability",
    "render_capability_flag",
]
