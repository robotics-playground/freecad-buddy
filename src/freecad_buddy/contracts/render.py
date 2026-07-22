"""Render scene contract: the stdlib-only spec a ``RenderPort`` consumes.

A ``SceneSpec`` is the per-call description of what to render — which objects, per-object
style overrides, camera orientation, and an optional focus target — assembled by
``usecases/screenshot.py`` (Gui-free) and handed to a host-injected ``RenderPort``. The port
owns all Coin/Gui machinery; this module carries no FreeCAD, Gui, or Qt import (stdlib only),
so it stays in the innermost ring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StyleSpec:
    """A per-object material override applied to that object's subgraph only.

    ``transparency`` is 0.0-1.0 (opaque..transparent); ``color`` is an optional RGB triple in
    0.0-1.0. Neither touches the document — the override wraps a transient subgraph copy.
    """

    object: str
    transparency: float | None = None
    color: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class FocusSpec:
    """A resolved focus target the camera frames instead of the whole scene.

    ``object`` names the whole object to frame; ``element_type``/``index`` (or ``mapped_name``)
    name a direct sub-element. The renderer signals back through ``RenderResult.focused`` whether
    it actually sub-framed, so the usecase never echoes a granularity the camera did not frame.
    """

    object: str
    element_type: str | None = None
    index: int | None = None
    mapped_name: str | None = None


@dataclass(frozen=True)
class SceneSpec:
    """The full per-call render description handed to a ``RenderPort``.

    ``objects`` is the ordered list of object Names to add to the scene; ``styles`` are the
    per-object overrides; ``highlight`` is the whole-object accent target (a Name) or ``None``;
    ``orientation`` is the 4-float camera quaternion; ``focus`` is the resolved focus target or
    ``None``; ``width``/``height`` are the PNG dimensions (already capped).
    """

    objects: list[str]
    orientation: tuple[float, float, float, float]
    width: int
    height: int
    styles: list[StyleSpec] = field(default_factory=list)
    highlight: str | None = None
    focus: FocusSpec | None = None


@dataclass(frozen=True)
class RenderResult:
    """What a ``RenderPort.render`` returns.

    ``rendered_objects`` is the ordered list of object Names actually added to the scene;
    ``focused`` is ``True`` iff the camera sub-framed the focus element (``False`` means it fell
    back to whole-object/whole-scene framing, so the usecase echoes object-only).
    """

    rendered_objects: list[str]
    focused: bool = False


@runtime_checkable
class RenderPort(Protocol):
    """The render capability the host injects; the usecase depends only on this shape."""

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``; ``reason`` is set only when unavailable."""

    def render(self, document: object, scene: SceneSpec, out_path: str) -> RenderResult:
        """Render ``scene`` for ``document`` (the resolved handle) to ``out_path`` as a PNG.

        The port renders the passed ``document``'s objects; it must never read
        ``FreeCAD.ActiveDocument`` (a screenshot of a handle renders that handle's doc even when
        a different or no document is active).
        """


__all__ = [
    "FocusSpec",
    "RenderPort",
    "RenderResult",
    "SceneSpec",
    "StyleSpec",
]
