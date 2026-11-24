"""FreeCAD capability probes.

Version-sensitive capability checks live here so downstream code branches on probe results,
never on version strings. Boolean probes are cached per process. FreeCAD App modules are
imported lazily inside functions so the module stays importable without FreeCAD present. A
probe that cannot run returns a conservative default rather than raising.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Callable, Literal, TypeVar

from freecad_buddy.contracts import DEFAULT_DISPLAY_DECIMALS, CapabilityBanner, round_floats
from freecad_buddy.usecases.operator_settings import PreferenceValues

T = TypeVar("T")

# OCC's ``write.step.schema`` enum names. The bare protocol name is refused: on 1.1.3
# ``setStaticValue("write.step.schema", "AP242")`` raises ``Failed to set 'write.step.schema'``.
_STEP_SCHEMES = {"AP203": "AP203", "AP214": "AP214IS", "AP242": "AP242DIS"}
_STEP_PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Part/STEP"
# ``Part::supportedSTEPSchemes()`` (``ImportStep.h``): the ``Scheme`` values File > Export applies.
_FREECAD_STEP_SCHEMES = frozenset({"AP203", "AP214CD", "AP214DIS", "AP214IS", "AP242DIS"})
_OCC_DEFAULT_STEP_SCHEME = "AP214IS"
_UNITS_PARAM_PATH = "User parameter:BaseApp/Preferences/Units"
# The addon's own preferences, edited on its page in Edit > Preferences.
BUDDY_PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/FreeCADBuddy"
ROUND_TO_DISPLAY_KEY = "RoundToDisplay"
AUTO_APPROVE_KEY = "AutoApprove"
SCRIPT_EXEC_KEY = "ScriptExec"
AUTO_START_MCP_KEY = "AutoStartMcp"
MCP_COMMAND_KEY = "McpCommand"
UV_PATH_KEY = "UvPath"
AUDIT_LOG_PATH_KEY = "AuditLogPath"

# The (type_id, property) pairs the feature tools validate against a live enumeration. A caller
# cannot know the legal set without reading it from the running build.
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


# The console observer the GUI's notification area attaches (``Gui/NotificationArea.cpp``), and
# every message level it listens to.
_NOTIFICATION_OBSERVER = "NotificationAreaObserver"
_NOTIFICATION_LEVELS = ("Err", "Wrn", "Critical", "Notification")


@contextmanager
def notifications_muted() -> Iterator[None]:
    """Keep a throwaway document's console messages out of the human's notification area.

    A recompute that leaves an object in error reports it through ``Base::Console().error``
    (``App/Document.cpp``), and so does an attachment that cannot be placed
    (``AttachExtension.cpp``); the notification area turns each into a badge and a pop-up about
    a document the human never opened. ``Document::IgnoreErrorOnRecompute``, the flag FreeCAD's
    own commands set to suppress that report, has no Python binding, so the observer is switched
    off instead and restored on every path. The Report View and the caller's own reading of the
    object state still carry the error. Without a GUI the observer does not exist: ``GetStatus``
    returns ``None`` and nothing is changed.
    """
    import FreeCAD

    console = FreeCAD.Console
    saved = {
        level: console.GetStatus(_NOTIFICATION_OBSERVER, level) for level in _NOTIFICATION_LEVELS
    }
    for level, status in saved.items():
        if status is not None:
            console.SetStatus(_NOTIFICATION_OBSERVER, level, False)
    try:
        yield
    finally:
        for level, status in saved.items():
            if status is not None:
                console.SetStatus(_NOTIFICATION_OBSERVER, level, status)


@contextmanager
def _scratch_document(name: str) -> Iterator[object]:
    """Open a throwaway probe document and close it on every path.

    ``temp=True`` is what keeps the caller's state: FreeCAD makes every new document active and
    puts the previous one back only for a temporary document, and closing the active document
    leaves none active, so a GUI session would lose its active 3D view. ``hidden=True`` opens no
    view. The notification area stays muted while the document exists, because a probe fails
    objects on purpose. Raises whatever ``FreeCAD.newDocument`` raises.
    """
    import FreeCAD

    with notifications_muted():
        doc = FreeCAD.newDocument(name, hidden=True, temp=True)
        try:
            yield doc
        finally:
            FreeCAD.closeDocument(doc.Name)


@lru_cache(maxsize=1)
def varset_backend() -> Literal["varset", "spreadsheet"]:
    """Driving-dimension backend: ``varset`` when ``App::VarSet`` is usable, else ``spreadsheet``.

    Attempts to add an ``App::VarSet`` on a throwaway document and confirms it materializes.
    """
    try:
        with _scratch_document("FCB_TMP_varset_probe") as doc:
            obj = doc.addObject("App::VarSet", "FCB_TMP_probe")
            return "varset" if obj is not None else "spreadsheet"
    except Exception:  # noqa: BLE001 - FreeCAD missing, or any failure: the backend is unavailable
        return "spreadsheet"


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
        with _scratch_document("FCB_TMP_partdesign_probe") as doc:
            body = doc.addObject("PartDesign::Body", "FCB_TMP_body")
            pad = doc.addObject("PartDesign::Pad", "FCB_TMP_pad")
            return body is not None and pad is not None
    except Exception:  # noqa: BLE001 - FreeCAD missing, or any failure: the workbench is unavailable
        return False


def probe_object(type_id: str, read: Callable[[object], T]) -> T:
    """Create ``type_id`` on a scratch document, run ``read`` against it, and return the result.

    The scratch document is closed on every path, including when ``read`` raises. No document the
    caller owns is written, and the caller's active document stays active throughout.

    :param type_id: the FreeCAD type id to instantiate, such as ``"PartDesign::Pad"``.
    :param read: receives the probe object and returns whatever the caller needs from it.
    :raises RuntimeError: FreeCAD is unavailable, or the scratch document cannot be opened.
    """
    try:
        import FreeCAD  # noqa: F401 - availability check before the scratch document opens
    except ImportError as exc:
        raise RuntimeError("FreeCAD is unavailable; cannot probe object properties") from exc
    with _scratch_document("FCB_TMP_type_probe") as doc:
        return read(doc.addObject(type_id, "FCB_TMP_probe"))


def enum_values(obj: object, prop: str) -> list[str]:
    """Return the live enumeration of ``obj.prop``, or ``[]`` when it exposes none.

    Several PartDesign enumerations carry deprecation tombstones, and ``Hole`` re-populates four
    of them whenever ``ThreadType`` changes, so every value is checked against this reading
    rather than a hardcoded list.
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


def extrude_second_side(obj: object, length: float) -> None:
    """Give an extrude a second, length-driven side of ``length`` mm opposite the first.

    FreeCAD 1.1 reads ``Type2`` and ``Length2`` only when ``SideType`` is ``"Two sides"``
    (``FeatureExtrude.cpp:333-342``), so the side type is written first.

    :raises AttributeError: the build does not expose the ``SideType`` property.
    """
    obj.SideType = "Two sides"
    obj.Type2 = "Length"
    obj.Length2 = length


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
        with _scratch_document("fcb_mapmode_probe") as doc:
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
        with _scratch_document("fcb_enum_probe") as document:
            found: dict[str, dict[str, list[str]]] = {}
            for index, (type_id, prop) in enumerate(_ENUM_PROPERTIES):
                obj = document.addObject(type_id, f"Probe{index}")
                values = enum_values(obj, prop)
                if values:
                    found.setdefault(type_id, {})[prop] = values
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


def display_decimals() -> int | None:
    """FreeCAD's display precision: the ``Decimals`` unit preference, read on every call.

    ``None`` when the addon's ``RoundToDisplay`` preference (default on) is off, so results and
    verdicts stay raw. Not cached: FreeCAD applies a change to either preference at once
    (``DlgSettingsGeneral.cpp:209``), so the next tool result follows it. No FreeCAD, a missing
    preference or a negative value gives ``DEFAULT_DISPLAY_DECIMALS``.

    FreeCAD is read only when this process has already loaded it; this function never loads it.
    """
    freecad = sys.modules.get("FreeCAD")
    if freecad is None:
        return DEFAULT_DISPLAY_DECIMALS
    try:
        if not freecad.ParamGet(BUDDY_PARAM_PATH).GetBool(ROUND_TO_DISPLAY_KEY, True):
            return None
        decimals = freecad.ParamGet(_UNITS_PARAM_PATH).GetInt("Decimals", DEFAULT_DISPLAY_DECIMALS)
    except Exception:  # noqa: BLE001 - a preference that cannot be read falls back to the default
        return DEFAULT_DISPLAY_DECIMALS
    return decimals if decimals >= 0 else DEFAULT_DISPLAY_DECIMALS


def read_operator_preferences() -> PreferenceValues:
    """The operator settings from the addon's preference page; the defaults without FreeCAD.

    Read once at bridge start. Unlike ``RoundToDisplay``, a change applies after a restart.
    """
    defaults = PreferenceValues()
    try:
        import FreeCAD

        preferences = FreeCAD.ParamGet(BUDDY_PARAM_PATH)
        return PreferenceValues(
            auto_approve=preferences.GetBool(AUTO_APPROVE_KEY, defaults.auto_approve),
            script_exec=preferences.GetBool(SCRIPT_EXEC_KEY, defaults.script_exec),
            auto_start_mcp=preferences.GetBool(AUTO_START_MCP_KEY, defaults.auto_start_mcp),
            mcp_command=preferences.GetString(MCP_COMMAND_KEY, defaults.mcp_command),
            uv_path=preferences.GetString(UV_PATH_KEY, defaults.uv_path),
            audit_log_path=preferences.GetString(AUDIT_LOG_PATH_KEY, defaults.audit_log_path),
        )
    except Exception:  # noqa: BLE001 - no FreeCAD or an unreadable group: run on the defaults
        return defaults


def displayed(value):
    """``value`` with every float at ``display_decimals`` places, as a tool result shows it.

    A message string built from ``displayed`` values states the same numbers as the rounded JSON.
    """
    return round_floats(value, display_decimals())


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
    element_map_version_string()
    element_map_version()
    sketcher_available()
    partdesign_available()
    freecad_version()


def pin_step_config(ap: str) -> str:
    """Pin the STEP write unit to millimetres and the schema to ``ap``; return the prior unit.

    ``ap`` is the STEP application protocol (``"AP242"``, ``"AP214"`` or ``"AP203"``). Both are
    OCC statics, because ``TopoShape::exportStep`` (``TopoShape.cpp:891``) reads only the statics
    and never the ``Mod/Part/STEP`` preferences. The statics are process-global and File > Export
    does not re-apply the ``Unit`` preference (FreeCAD applies it only at Part load and when the
    STEP preferences are saved), so the caller passes the returned unit to ``restore_step_config``
    after the export. Raises ``ValueError`` for an unknown ``ap``.
    """
    if ap not in _STEP_SCHEMES:
        raise ValueError(f"unknown STEP application protocol: {ap!r}")
    import Part

    previous_unit = Part.exportUnits()["write.step.unit"]
    Part.setStaticValue("write.step.schema", _STEP_SCHEMES[ap])
    Part.setStaticValue("write.step.unit", "MM")
    return previous_unit


def restore_step_config(unit: str) -> None:
    """Set ``write.step.unit`` back to ``unit`` and ``write.step.schema`` to FreeCAD's own choice.

    The unit has a getter (``Part.exportUnits``), so ``pin_step_config`` saved it and it comes
    back exactly. The schema has none: it becomes the ``Mod/Part/STEP`` ``Scheme`` preference when
    that is a scheme File > Export applies, else the OCC default ``AP214IS``; a schema a macro set
    directly on the static is overwritten. The preferences are only read, never written.
    """
    import FreeCAD
    import Part

    Part.setStaticValue("write.step.unit", unit)
    scheme = FreeCAD.ParamGet(_STEP_PARAM_PATH).GetString("Scheme")
    if scheme not in _FREECAD_STEP_SCHEMES:
        scheme = _OCC_DEFAULT_STEP_SCHEME
    Part.setStaticValue("write.step.schema", scheme)


def export_step_objects(
    items: list[tuple[str, object]], document_name: str, path: str
) -> list[str]:
    """Write ``(label, shape)`` pairs to one STEP file, one product per pair named by its label.

    Each shape is copied into a scratch ``Part::Feature`` carrying the label, and ``Import.export``
    writes those features. The OCAF writer shares one product between objects whose shapes share
    their geometry (a simple copy, a link), which would give two objects one product name; the
    copy gives every object its own geometry and so its own product. It also writes exactly the
    shape the caller recorded, whatever a group holds that is hidden. The multi-solid shape of one
    pair may become several products. The writer reads the same ``write.step.*`` statics
    ``pin_step_config`` sets, so the caller pins and restores them. Writer options that otherwise
    come from the operator's ``Mod/Import`` preferences are passed explicitly. Returns the label
    each feature ended with, which FreeCAD makes unique within the scratch document. The writer
    names the root product after the document's internal name, so the scratch document is named
    ``<document_name>_export`` (FreeCAD adds a number when that name is taken). A feature has no
    colours of its own, so the file carries none.
    """
    import Import

    with _scratch_document(f"{document_name}_export") as doc:
        features = []
        for label, shape in items:
            feature = doc.addObject("Part::Feature", "Part")
            feature.Label = label
            feature.Shape = shape.copy()
            features.append(feature)
        Import.export(features, path, exportHidden=True, legacy=False, keepPlacement=False)
        return [feature.Label for feature in features]


def read_step_leaves(path: str) -> list[dict]:
    """Re-import a STEP file into a scratch document and return one fact record per product.

    Each record holds the shape's ``volume``, ``valid``, ``faces``, ``edges`` and ``solids``, in
    the order FreeCAD created the objects. A product that holds
    several solids is split by FreeCAD into one leaf per solid. The reader options that otherwise
    come from the operator's ``Mod/Import`` preferences (merge, hidden objects, link groups,
    one document per assembly) are passed explicitly. The scratch document is closed before
    return.
    """
    import Import

    with _scratch_document("FCB_TMP_step_read") as doc:
        Import.insert(path, doc.Name, importHidden=True, merge=False, useLinkGroup=False, mode=0)
        leaves = []
        for obj in doc.Objects:
            if obj.TypeId != "Part::Feature":
                continue
            shape = obj.Shape
            leaves.append(
                {
                    "volume": float(shape.Volume),
                    "valid": bool(shape.isValid()),
                    "faces": len(shape.Faces),
                    "edges": len(shape.Edges),
                    "solids": len(shape.Solids),
                }
            )
        return leaves


def export_meshes(meshes: list, path: str) -> None:
    """Write each mesh as its own object of one mesh file (the format follows the extension).

    ``Mesh.export`` takes document objects, so the meshes go into a scratch document as
    ``Mesh::Feature`` objects first.
    """
    import Mesh

    with _scratch_document("FCB_TMP_mesh_write") as doc:
        features = []
        for mesh in meshes:
            feature = doc.addObject("Mesh::Feature", "Mesh")
            feature.Mesh = mesh
            features.append(feature)
        Mesh.export(features, path)


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
