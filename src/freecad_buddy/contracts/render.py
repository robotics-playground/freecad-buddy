"""Render scene contract: the stdlib-only spec a ``RenderPort`` consumes.

A ``SceneSpec`` is the per-call description of what to render — which objects, per-object
style overrides, camera orientation, and an optional focus target — assembled by
``usecases/screenshot.py`` (Gui-free) and handed to a host-injected ``RenderPort``. The port
owns all Coin/Gui machinery; this module carries no FreeCAD, Gui, or Qt import (stdlib only),
so it stays in the innermost ring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict, runtime_checkable


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
    back to whole-object/whole-scene framing, so the usecase echoes object-only);
    ``empty_scene`` is ``True`` when no drawable geometry was added, in which case no image was
    written and the caller must not expect one.
    """

    rendered_objects: list[str]
    focused: bool = False
    empty_scene: bool = False


class FramingVerdict(TypedDict, total=False):
    """Whether the targeted document's model fits the live viewport, and how fresh that answer is.

    **Three no-verdict states, discriminated by ``checked`` and never by an absent field:**

    1. No viewport for this document (a headless host, or a GUI document with no open 3D view —
       what ``ViewportPort.available`` reports as ``(False, reason)``) → the whole block is
       **omitted**, no ``FramingVerdict`` is built.
    2. Viewport present, projection attempted and failed → ``fits: None`` **always** paired with
       ``checked: "unavailable"``, the failure named in ``stale_reason``.
    3. Viewport present, projection succeeded → ``fits`` is a real bool.

    State 1 vs state 2 is the divergence this spelling exists to prevent: "GUI document with no
    open 3D view" is state 1 (omitted), never state 2.

    ``fits`` is ``None`` only when the verdict could not be computed, never a guess.

    ``ratio`` is the larger of the two extent/viewport-extent quotients over the 2D axis-aligned
    hull of the projected bbox corners, so ``1.0`` exactly fills, ``< 1.0`` leaves margin and
    ``> 1.0`` overflows. **If any corner coordinate was discarded as an implausible magnitude —
    ``|coordinate| > 4 ×`` the corresponding viewport dimension, a stated constant, not a
    per-implementer judgement — then ``ratio`` is ``None`` while ``fits`` is ``False``.** A
    discarded coordinate has no measurable fraction, and fabricating one would report a wildly
    wrong camera as a hair's-breadth miss.

    ``checked`` is a closed enum: adding a fourth value is a schema **major bump** under AD-28,
    not an additive change.
    """

    fits: bool | None  # required
    ratio: float | None  # required
    checked: Literal["computed", "cached", "unavailable"]  # required
    stale_reason: str | None  # required


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


@runtime_checkable
class ViewportPort(Protocol):
    """The live-camera capability the host injects; a host with no viewport injects ``None``.

    Separate from ``RenderPort``: the render port self-frames a constructed scene, so its
    availability answers "can this process render offscreen" — orthogonal to "a live 3D view
    exists for this document". ``available`` and ``view`` answer per document, because one GUI
    session can hold a document with an open 3D view beside one without.
    ``showing_document_name`` is the exception: it is session-wide and takes no document.
    """

    def available(self, document: object) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)`` for ``document``; ``reason`` is set only when False."""

    def view(self, document: object) -> object | None:
        """Return ``document``'s live 3D view handle, or ``None`` when it has none.

        Never falls back to another document's view: a verdict must describe the document the
        call targeted, not whichever document the GUI happens to show.
        """

    def showing_document_name(self) -> str | None:
        """Return the ``Name`` of the one document on screen, or ``None`` when unreadable.

        **Session-wide, and takes no document** — that is the whole point. ``view(document)``
        resolves through the passed handle's own ``Name``, so any guard comparing that view's
        document against the target compares a name with itself and can never fire. The on-screen
        name must come from a source independent of the target handle.

        ``None`` means "could not read the on-screen name" and is **not** a refusal: an unreadable
        name is no evidence of a mismatch, so a caller guarding on it proceeds. ``None``
        deliberately conflates "no viewport" with "name unreadable" and carries **no reason
        string**, unlike ``available``: both are treated identically, and a reason would invite a
        caller to branch on a distinction with no consequence.
        """


__all__ = [
    "FocusSpec",
    "FramingVerdict",
    "RenderPort",
    "RenderResult",
    "SceneSpec",
    "StyleSpec",
    "ViewportPort",
]
