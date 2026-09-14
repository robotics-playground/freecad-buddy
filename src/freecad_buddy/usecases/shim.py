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

# The (type_id, property) pairs the feature tools validate against a live enumeration. The
# spellings differ between supported builds, so a caller cannot know the legal set without
# reading it from the running one.
_ENUM_PROPERTIES = (
    ("PartDesign::Pad", "Type"),
    ("PartDesign::Pocket", "Type"),
    ("PartDesign::Revolution", "Type"),
    ("PartDesign::Hole", "ThreadType"),
    ("PartDesign::Hole", "HoleCutType"),
    ("PartDesign::Hole", "DepthType"),
    ("PartDesign::Chamfer", "ChamferType"),
    ("PartDesign::LinearPattern", "Mode"),
    ("PartDesign::LinearPattern", "TransformMode"),
    ("PartDesign::PolarPattern", "Mode"),
)

_sketcher_probed_ok = False


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
def varset_probe() -> tuple[Literal["varset", "spreadsheet"], str | None]:
    """The driving-dimension backend and, when it fell back, why.

    Adds an ``App::VarSet`` on a throwaway document and writes one property to it. Creating the
    object is not enough on its own: decision 004's open question is whether VarSet's *Python*
    surface is exposed (upstream #12531), and a build that hands back an object whose
    ``addProperty`` raises would hold no parameter the facade could write. The probe therefore
    exercises the write the facade actually performs.

    The reason is kept rather than discarded because the Spreadsheet fallback is currently
    unexercised — VarSet is the measured path on both supported legs — so the only way a silent
    switch becomes visible is for the fallback to name what it could not do.
    """
    try:
        import FreeCAD
    except ImportError:
        return "spreadsheet", "FreeCAD is unavailable"
    try:
        doc = FreeCAD.newDocument("FCB_TMP_varset_probe")
    except Exception as exc:  # noqa: BLE001 - cannot open a probe document; assume unavailable
        return "spreadsheet", f"probe document could not be opened: {exc}"
    try:
        obj = doc.addObject("App::VarSet", "FCB_TMP_probe")
        if obj is None:
            return "spreadsheet", "App::VarSet is not a type this build creates"
        obj.addProperty("App::PropertyLength", "FCB_TMP_probe_length", "Driving", "")
        obj.FCB_TMP_probe_length = 1.0
        return "varset", None
    except Exception as exc:  # noqa: BLE001 - any failure means the backend is unavailable
        return "spreadsheet", f"App::VarSet is not writable from Python: {exc}"
    finally:
        FreeCAD.closeDocument(doc.Name)


@lru_cache(maxsize=1)
def varset_backend() -> Literal["varset", "spreadsheet"]:
    """Driving-dimension backend: ``varset`` when ``App::VarSet`` is usable, else the fallback."""
    return varset_probe()[0]


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
def element_map_version_string() -> str | None:
    """The topological element-map version verbatim, or ``None`` when unexposed.

    Probes ``TopoShape.ElementMapVersion`` on a box and returns whatever the build reports
    without narrowing it; the value is a dotted string such as ``"15.70200.5"``.
    """
    try:
        import Part

        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return None
    raw = getattr(shape, "ElementMapVersion", None)
    return None if raw is None else str(raw)


@lru_cache(maxsize=1)
def element_map_version() -> int | None:
    """The topological element-map version as an int, or ``None`` when unexposed.

    Narrows ``element_map_version_string`` to its leading dotted component, so a build
    reporting ``"15.70200.5"`` yields ``15``. Returns ``None`` when the build exposes no
    version or its leading component is not integral.
    """
    raw = element_map_version_string()
    if raw is None:
        return None
    try:
        return int(raw.split(".")[0])
    except (TypeError, ValueError):
        return None


def sketcher_available() -> bool:
    """Whether the Sketcher module exposes the constraint constructor the sketch tools drive.

    True when ``Sketcher`` imports and ``Sketcher.Constraint`` accepts the verified
    ``(type, geoId, value)`` form; a build without a usable constructor cannot run any sketch
    mutation.

    Only a success is cached. A failure is re-probed on the next call, because the import can
    fail while the workbench is still loading and succeed once it has settled; caching that
    first answer would disable every sketch tool for the life of the process.
    """
    global _sketcher_probed_ok
    if _sketcher_probed_ok:
        return True
    try:
        import Sketcher

        Sketcher.Constraint("Radius", 0, 1.0)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    _sketcher_probed_ok = True
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


# The headless ``TechDraw`` App-module surface decision 016 rests on
# (``AppTechDrawPy.cpp:138-170``). Probed as a set rather than by importing the module alone,
# because a build can expose ``TechDraw`` while missing a helper, and discovering that halfway
# through a TempDoc build leaks the document. The set is the whole measured boundary, not only
# what the drawing generator calls today: a build that lost any of the four has moved the boundary
# decision 016 records, and reporting that as "available" would hide the move.
_TECHDRAW_ENTRY_POINTS = ("projectToSVG", "viewPartAsSvg", "makeExtentDim", "makeDistanceDim")


@lru_cache(maxsize=1)
def techdraw_available() -> bool:
    """Whether the headless ``TechDraw`` App module exposes every entry point 4.3 drives.

    Never probes ``TechDrawGui``. Page export lives there and is unreachable from a console
    process, and a *second* import of it after ``FreeCADGui.setupWithoutGUI()`` terminates the
    interpreter with no traceback (decision 016, DW-116) — so a probe that reached for it could
    take the whole process down instead of returning ``False``.
    """
    try:
        import TechDraw
    except Exception:  # noqa: BLE001 - a module that will not import means the feature is absent
        return False
    return all(hasattr(TechDraw, name) for name in _TECHDRAW_ENTRY_POINTS)


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


def _constraint_indices(obj: object, prop: str) -> list | None:
    """Read one of ``SketchObject``'s solver-diagnostic index lists, or ``None`` when unexposed."""
    raw = getattr(obj, prop, None)
    if raw is None:
        return None
    try:
        return list(raw)
    except TypeError:
        return None


def redundant_only_sketch(obj: object) -> bool:
    """Whether ``obj`` is a sketch whose sole invalidity is redundant constraints.

    FreeCAD marks such a sketch invalid and gives it no shape, while redundancy is only a
    warning; the generic validity sweeps use this to leave the verdict to the sketch grader.

    The verdict comes from the sketch's own solver diagnostics rather than ``getStatusString``,
    which reports the recompute log and so can still name a fault the sketch no longer has.
    True requires ``RedundantConstraints`` to be non-empty with ``ConflictingConstraints`` and
    ``MalformedConstraints`` both empty and ``DoF`` non-negative, matching the priority order in
    ``SketchObject::solve`` where over-constraint, conflict and malformation each outrank
    redundancy. A build exposing none of the diagnostics reports ``False``.
    """
    if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
        return False
    redundant = _constraint_indices(obj, "RedundantConstraints")
    conflicting = _constraint_indices(obj, "ConflictingConstraints")
    malformed = _constraint_indices(obj, "MalformedConstraints")
    if redundant is None or conflicting is None or malformed is None:
        return False
    dof = getattr(obj, "DoF", None)
    if not isinstance(dof, int) or dof < 0:
        return False
    return bool(redundant) and not conflicting and not malformed


def set_attachment(obj: object, support: list, map_mode: str) -> None:
    """Attach ``obj`` to ``support`` under ``map_mode``.

    ``support`` is a ``PropertyLinkSubList`` value: a list of ``(object, [subelement])`` pairs.
    ``map_mode`` is an ``AttachEngine`` mode name such as ``"FlatFace"`` or ``"ObjectXY"``.

    :raises AttributeError: the build does not expose the ``AttachmentSupport`` property.
    """
    obj.AttachmentSupport = support
    obj.MapMode = map_mode


_NOT_IMPLEMENTED_SUFFIX = " is not implemented."


@lru_cache(maxsize=8)
def implemented_map_modes(type_id: str) -> frozenset[str] | None:
    """The ``MapMode`` values ``type_id``'s attach engine implements, or ``None`` when unprobeable.

    ``MapMode``'s enumeration is the union across every ``AttachEngine``, so a mode a datum
    advertises is not necessarily one its own engine implements: ``PartDesign::Line`` advertises
    all 55 and implements 18. The engine reports an unimplemented one through
    ``AttachEngine::throwWrongMode`` (``Attacher.cpp:1074-1090``), whose message this probe
    matches, and it does so only once the datum has references — an unreferenced datum never
    evaluates its mode and recomputes clean — so the probe attaches each mode to a throwaway box
    face before reading the verdict.

    A mode the engine implements but that this probe's single face reference cannot satisfy
    reports a different message from ``calculateAttachedPlacement`` and is counted as
    implemented, because the fault is the reference rather than the kind. The result is therefore
    the set that is not excluded *by kind alone*, which is exactly what a caller can be told
    before its own references are resolved.
    """
    try:
        import FreeCAD

        doc = FreeCAD.newDocument("fcb_mapmode_probe", hidden=True)
        try:
            box = doc.addObject("Part::Box", "ProbeBox")
            doc.recompute()
            obj = doc.addObject(type_id, "Probe")
            implemented = set()
            for mode in obj.getEnumerationsOfProperty("MapMode"):
                obj.AttachmentSupport = [(box, ["Face1"])]
                obj.MapMode = mode
                doc.recompute()
                if not str(obj.getStatusString()).endswith(_NOT_IMPLEMENTED_SUFFIX):
                    implemented.add(mode)
        finally:
            FreeCAD.closeDocument(doc.Name)
    except Exception:  # noqa: BLE001 - a probe that cannot run leaves the mode unchecked
        return None
    return frozenset(implemented)


@lru_cache(maxsize=1)
def property_enums() -> dict[str, dict[str, list[str]]]:
    """The live enumeration of every property the feature tools validate, by type and property.

    Values are reported verbatim in FreeCAD's own order. A ``?``-prefixed member is kept: it is
    assignable and reads back unchanged, so filtering it would hide a value a caller may use.

    A pair the build cannot probe is omitted rather than reported empty, so a consumer can tell
    an absent enumeration from one offering no values. A build that cannot run the probe at all
    reports an empty mapping.
    """
    try:
        import FreeCAD

        document = FreeCAD.newDocument("fcb_enum_probe", hidden=True)
        try:
            found: dict[str, dict[str, list[str]]] = {}
            for index, (type_id, prop) in enumerate(_ENUM_PROPERTIES):
                obj = document.addObject(type_id, f"Probe{index}")
                values = enum_values(obj, prop)
                if values:
                    found.setdefault(type_id, {})[prop] = values
        finally:
            FreeCAD.closeDocument(document.Name)
    except Exception:  # noqa: BLE001 - a probe that cannot run reports nothing
        return {}
    return found


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
    varset_probe()
    varset_backend()
    varset_available()
    element_map_available()
    element_map_version_string()
    element_map_version()
    sketcher_available()
    partdesign_available()
    techdraw_available()
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
        "enums": property_enums(),
    }
