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
from functools import lru_cache

from freecad_buddy.contracts.render import FocusSpec, RenderResult, SceneSpec

_PROBE_SIZE = 8

_ACCENT_COLOR = (1.0, 0.55, 0.0)

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
    """Add a camera-aligned headlight plus ambient fill so no face renders black.

    FreeCAD's live viewport lights the scene with a headlight that follows the camera (it lights
    whatever the camera sees). A single fixed ``SoDirectionalLight`` leaves every face angled away
    from its world-space direction near-black — the divergence a viewport comparison exposes. This
    aims the light along the camera's view direction (the orientation quaternion applied to the
    camera's default -Z look axis) and adds a modest ambient term via ``SoEnvironment`` so grazing
    faces keep some tone, matching the viewport's softer shading.
    """
    view_dir = coin.SbRotation(*orientation).multVec(coin.SbVec3f(0.0, 0.0, -1.0))
    headlight = coin.SoDirectionalLight()
    headlight.direction.setValue(view_dir)
    environment = coin.SoEnvironment()
    # 0.7 matches FreeCAD's live viewport tone: measured against a PrintWindow capture, a lit face
    # reads RGB ~(158,165,169), which this ambient reproduces (~159,164,169). A lower value renders
    # the model visibly darker than the viewport while keeping the headlight's angular gradient.
    environment.ambientIntensity.setValue(0.7)
    root.addChild(environment)
    root.addChild(headlight)


def _configured_msaa_samples() -> int:
    """Return the multisample count from FreeCAD's 3D-view anti-aliasing preference (0 if unset)."""
    import FreeCAD

    group = FreeCAD.ParamGet(_AA_PREF_GROUP)
    enum_value = int(group.GetInt(_AA_PREF_KEY, 0))
    return _AA_ENUM_TO_SAMPLES.get(enum_value, 0)


def _apply_configured_msaa(renderer: object) -> None:
    """Set the renderer's multisample count from FreeCAD's preference, when the build supports it."""
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
    """Wrap ``subgraph`` in a separator with a prepended material for style/highlight overrides.

    A highlight accent takes precedence over a plain style override on the same object. Returns
    the raw subgraph unchanged when neither a style nor a highlight applies.
    """
    if style is None and not is_highlight:
        return subgraph
    separator = coin.SoSeparator()
    material = coin.SoMaterial()
    if is_highlight:
        material.diffuseColor.setValue(*_ACCENT_COLOR)
    else:
        if style.color is not None:
            material.diffuseColor.setValue(*style.color)
        if style.transparency is not None:
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
    """Aim ``camera`` at ``bbox`` (grown ~20%) by framing a proxy cube of the grown extent."""
    proxy = coin.SoSeparator()
    cube = coin.SoCube()
    grow = 1.2
    cube.width.setValue(max(bbox.XLength, 1e-3) * grow)
    cube.height.setValue(max(bbox.YLength, 1e-3) * grow)
    cube.depth.setValue(max(bbox.ZLength, 1e-3) * grow)
    transform = coin.SoTransform()
    transform.translation.setValue(bbox.Center.x, bbox.Center.y, bbox.Center.z)
    proxy.addChild(transform)
    proxy.addChild(cube)
    camera.viewAll(proxy, viewport)


__all__ = [
    "OffscreenRenderPort",
    "RenderError",
    "render_capability",
    "render_capability_flag",
]
