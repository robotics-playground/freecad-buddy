"""FreeCAD capability probes.

Version-sensitive capability checks live here so downstream code branches on probe results,
never on version strings. Boolean probes are cached per process. FreeCAD App modules are
imported lazily inside functions so the module stays importable without FreeCAD present. A
probe that cannot run returns a conservative default rather than raising.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Literal, TypeVar

from freecad_buddy.contracts import CapabilityBanner

T = TypeVar("T")

_STEP_PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Part/STEP"
_STEP_SCHEMES = frozenset({"AP203", "AP214", "AP242"})


@lru_cache(maxsize=1)
def export_binary_available() -> bool:
    """Whether ``TopoShape.exportBinary`` is exposed on the running FreeCAD build."""
    try:
        import Part

        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    return callable(getattr(shape, "exportBinary", None))


@lru_cache(maxsize=1)
def serializer_tag() -> Literal["exportBinary", "exportBrep"]:
    """Fingerprint serializer tag: ``exportBinary`` when exposed, else ``exportBrep``."""
    return "exportBinary" if export_binary_available() else "exportBrep"


@lru_cache(maxsize=1)
def varset_backend() -> Literal["varset", "spreadsheet"]:
    """Driving-dimension backend: ``varset`` when ``App::VarSet`` is usable, else ``spreadsheet``.

    Attempts to add an ``App::VarSet`` on a throwaway document and confirms it materializes.
    """
    try:
        import FreeCAD
    except ImportError:
        return "spreadsheet"
    try:
        doc = FreeCAD.newDocument("FCB_TMP_varset_probe")
    except Exception:  # noqa: BLE001 - cannot open a probe document; assume unavailable
        return "spreadsheet"
    try:
        obj = doc.addObject("App::VarSet", "FCB_TMP_probe")
        return "varset" if obj is not None else "spreadsheet"
    except Exception:  # noqa: BLE001 - any failure means the backend is unavailable
        return "spreadsheet"
    finally:
        FreeCAD.closeDocument(doc.Name)


@lru_cache(maxsize=1)
def varset_available() -> bool:
    """Whether ``App::VarSet`` is usable from Python on the running FreeCAD build."""
    return varset_backend() == "varset"


def render_available(render: str = "none") -> bool:
    """Whether a render context is usable, given the host-probed ladder mode ``render``.

    The ladder itself lives in ``adapters/render_probe.py`` (the Gui carve-out); the resolved
    mode (``gui_constructed`` / ``offscreen`` / ``none``) is threaded in so this stays Gui-free.
    """
    return render != "none"


@lru_cache(maxsize=1)
def element_map_available() -> bool:
    """Whether the topological element-map API is exposed on the running FreeCAD build.

    True when a probe box exposes the ``getElementHistory`` method and the ``ElementMapSize``
    and ``ElementMap`` attributes.
    """
    try:
        import Part

        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    if not callable(getattr(shape, "getElementHistory", None)):
        return False
    return hasattr(shape, "ElementMapSize") and hasattr(shape, "ElementMap")


@lru_cache(maxsize=1)
def element_map_version() -> int | None:
    """The topological element-map version as an int, or ``None`` when unexposed.

    Probes ``TopoShape.ElementMapVersion`` on a box; returns the integer version where the
    build cleanly exposes one, else ``None``. This is the report-banner value; the coarser
    availability bool stays in ``element_map_available``.
    """
    try:
        import Part

        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return None
    raw = getattr(shape, "ElementMapVersion", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def sketcher_available() -> bool:
    """Whether the Sketcher module exposes the constraint constructor the sketch tools drive.

    True when ``Sketcher`` imports and ``Sketcher.Constraint`` accepts the verified
    ``(type, geoId, value)`` form; a build without a usable constructor cannot run any sketch
    mutation.
    """
    try:
        import Sketcher

        Sketcher.Constraint("Radius", 0, 1.0)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    return True


@lru_cache(maxsize=1)
def partdesign_available() -> bool:
    """Whether the running build can create the PartDesign objects the feature tools drive.

    True when a throwaway document accepts a ``PartDesign::Body`` and a ``PartDesign::Pad``;
    a build without either cannot run any feature mutation.
    """
    try:
        import FreeCAD
    except ImportError:
        return False
    try:
        doc = FreeCAD.newDocument("FCB_TMP_partdesign_probe")
    except Exception:  # noqa: BLE001 - cannot open a probe document; assume unavailable
        return False
    try:
        body = doc.addObject("PartDesign::Body", "FCB_TMP_body")
        pad = doc.addObject("PartDesign::Pad", "FCB_TMP_pad")
        return body is not None and pad is not None
    except Exception:  # noqa: BLE001 - any failure means the workbench is unavailable
        return False
    finally:
        FreeCAD.closeDocument(doc.Name)


def probe_object(type_id: str, read: Callable[[object], T]) -> T:
    """Create ``type_id`` on a scratch document, run ``read`` against it, and return the result.

    The scratch document is closed on every path, including when ``read`` raises. No document the
    caller owns is written.

    :param type_id: the FreeCAD type id to instantiate, such as ``"PartDesign::Pad"``.
    :param read: receives the probe object and returns whatever the caller needs from it.
    :raises RuntimeError: FreeCAD is unavailable, or the scratch document cannot be opened.
    """
    try:
        import FreeCAD
    except ImportError as exc:
        raise RuntimeError("FreeCAD is unavailable; cannot probe object properties") from exc
    doc = FreeCAD.newDocument("FCB_TMP_type_probe")
    try:
        return read(doc.addObject(type_id, "FCB_TMP_probe"))
    finally:
        FreeCAD.closeDocument(doc.Name)


def enum_values(obj: object, prop: str) -> list[str]:
    """Return the live enumeration of ``obj.prop``, or ``[]`` when it exposes none.

    Several PartDesign enumerations differ in spelling, ordering and length between the
    supported FreeCAD builds, and ``Hole`` re-populates four of them whenever ``ThreadType``
    changes, so every value is checked against this reading rather than a hardcoded list.
    """
    getter = getattr(obj, "getEnumerationsOfProperty", None)
    if not callable(getter):
        return []
    try:
        return [str(value) for value in getter(prop)]
    except Exception:  # noqa: BLE001 - a property with no enumeration offers no values
        return []


def extrude_symmetric(obj: object, on: bool) -> None:
    """Make an extrude straddle its profile plane by writing ``Midplane``.

    A freshly created extrude already extrudes to one side, so only ``on=True`` writes the
    property.

    :raises AttributeError: the build does not expose the ``Midplane`` property.
    """
    if on:
        obj.Midplane = True


# SketchObject::execute() returns this exact message prefix, and only it, when solve() reports
# -2 (redundant constraints) — a code distinct from conflicting (-3), over-constrained (-4) and
# malformed (-5). It is therefore a reliable discriminator for redundancy alone.
_REDUNDANT_SKETCH_STATUS = "Sketch with redundant constraints"


def redundant_only_sketch(obj: object) -> bool:
    """Whether ``obj`` is a sketch whose sole invalidity is redundant constraints.

    FreeCAD marks such a sketch invalid and gives it no shape, while redundancy is only a
    warning; the generic validity sweeps use this to leave the verdict to the sketch grader.
    """
    if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
        return False
    getter = getattr(obj, "getStatusString", None)
    if not callable(getter):
        return False
    return str(getter()).startswith(_REDUNDANT_SKETCH_STATUS)


def set_attachment(obj: object, support: list, map_mode: str) -> None:
    """Attach ``obj`` to ``support`` under ``map_mode``.

    ``support`` is a ``PropertyLinkSubList`` value: a list of ``(object, [subelement])`` pairs.
    ``map_mode`` is an ``AttachEngine`` mode name such as ``"FlatFace"`` or ``"ObjectXY"``.

    :raises AttributeError: the build does not expose the ``AttachmentSupport`` property.
    """
    obj.AttachmentSupport = support
    obj.MapMode = map_mode


def enable_undo(doc: object) -> bool:
    """Turn on ``doc``'s undo stack when the build honours the switch; report whether it is on.

    ``Document.UndoMode`` is ``0`` (no undo) on a headless document, so ``abortTransaction`` would
    silently restore nothing. Some builds hardcode the getter to ``1`` and ignore the setter, so
    the result is read back rather than assumed: the return value is what the document reports
    after the write, never what was requested.
    """
    try:
        doc.UndoMode = 1
    except Exception:  # noqa: BLE001 - a build that rejects the write leaves undo as it was
        pass
    return bool(getattr(doc, "UndoMode", 0))


@lru_cache(maxsize=1)
def freecad_version() -> str:
    """The running FreeCAD version as ``major.minor.patch``, or ``unknown`` when absent."""
    try:
        import FreeCAD
    except ImportError:
        return "unknown"
    version = FreeCAD.Version()
    return ".".join(str(part) for part in version[:3])


def warm_capability_probes() -> None:
    """Force-evaluate every cached capability probe once so their work runs at a controlled point.

    Must run on the FreeCAD execution thread before the host serves requests, so the
    ``varset_backend`` probe's temp-document churn cannot interleave with a registry mutation.
    Each probe returns its conservative default when it cannot run; a probe whose teardown
    fails may still propagate, so callers warm defensively.
    """
    export_binary_available()
    serializer_tag()
    varset_backend()
    varset_available()
    element_map_available()
    element_map_version()
    sketcher_available()
    partdesign_available()
    freecad_version()


def pin_step_config(ap: str) -> None:
    """Pin the STEP write unit to millimetres and the schema to ``ap`` for the next export.

    ``ap`` is the STEP application protocol (``"AP242"`` or ``"AP214"``). The unit is set
    through ``Part.setStaticValue("write.step.unit", "MM")``. The schema is set through the
    ``Mod/Part/STEP`` ``Scheme`` preference string, because ``setStaticValue`` raises on
    ``write.step.schema`` on the 1.0/1.1 builds. Raises ``ValueError`` for an unknown ``ap``.
    """
    if ap not in _STEP_SCHEMES:
        raise ValueError(f"unknown STEP application protocol: {ap!r}")
    import FreeCAD
    import Part

    Part.setStaticValue("write.step.unit", "MM")
    FreeCAD.ParamGet(_STEP_PARAM_PATH).SetString("Scheme", ap)


def step_schema() -> str:
    """Return the STEP schema currently pinned in the ``Mod/Part/STEP`` ``Scheme`` preference."""
    import FreeCAD

    return FreeCAD.ParamGet(_STEP_PARAM_PATH).GetString("Scheme")


def capability_banner(
    render: Literal["gui_constructed", "offscreen", "none"] = "none",
) -> CapabilityBanner:
    """Runtime capability payload for the report banner and ``query_capabilities``.

    Every field is a live probe except ``render``, whose ladder mode is host-probed in
    ``adapters/render_probe.py`` and threaded in (keeping the shim Gui-free).
    """
    return {
        "freecad_version": freecad_version(),
        "element_map_available": element_map_available(),
        "serializer": serializer_tag(),
        "varset_backend": varset_backend(),
        "render": render,
        "sketcher_available": sketcher_available(),
        "partdesign_available": partdesign_available(),
    }
