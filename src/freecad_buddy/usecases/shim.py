"""FreeCAD capability probes.

Version-sensitive capability checks live here so downstream code branches on probe results,
never on version strings. Boolean probes are cached per process. FreeCAD App modules are
imported lazily inside functions so the module stays importable without FreeCAD present. A
probe that cannot run returns a conservative default rather than raising.
"""

from __future__ import annotations

from functools import lru_cache


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
def serializer_tag() -> str:
    """Fingerprint serializer tag: ``exportBinary`` when exposed, else ``exportBrep``."""
    return "exportBinary" if export_binary_available() else "exportBrep"


@lru_cache(maxsize=1)
def varset_backend() -> str:
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


@lru_cache(maxsize=1)
def render_available() -> bool:
    """Whether an offscreen GL render context is usable on the running FreeCAD build.

    The headless surface has no render context, so this returns False until the render ladder
    lands with the screenshot story.
    """
    return False


@lru_cache(maxsize=1)
def element_map_available() -> bool:
    """Whether the topological element map is exposed on the running FreeCAD build.

    True when ``TopoShape`` exposes ``getElementHistory`` and a probe box yields a non-empty
    element map.
    """
    try:
        import Part

        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    if not callable(getattr(shape, "getElementHistory", None)):
        return False
    mapper = getattr(shape, "ElementMap", None)
    if mapper is None:
        return False
    try:
        return len(mapper) > 0
    except TypeError:
        return bool(mapper)


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
def freecad_version() -> str:
    """The running FreeCAD version as ``major.minor.patch``, or ``unknown`` when absent."""
    try:
        import FreeCAD
    except ImportError:
        return "unknown"
    version = FreeCAD.Version()
    return ".".join(str(part) for part in version[:3])


def capability_banner() -> dict:
    """Runtime capability payload for the report banner and ``query_capabilities``.

    All fields are live probes. ``render`` is ``"none"`` for the headless surface.
    """
    return {
        "freecad_version": freecad_version(),
        "element_map_available": element_map_available(),
        "serializer": serializer_tag(),
        "varset_backend": varset_backend(),
        "render": "none",
    }
