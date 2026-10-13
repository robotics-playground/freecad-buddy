"""Read-only snapshot of FreeCAD kernel and GUI state for the UAT probe.

Every function takes FreeCAD modules or objects as arguments and only reads them. The kernel
part (``read_document`` and below) runs under FreeCADCmd for the offline reader; the GUI part
(``take_snapshot``, ``read_view``) needs ``FreeCADGui``. Tests pass fake objects.
"""

CLIP_SLACK_PX = 1


def freecad_version(app):
    return ".".join(app.Version()[:3])


def read_shape(obj):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return None
    box = shape.BoundBox
    return {
        "valid": shape.isValid(),
        "volume": shape.Volume,
        "bbox": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
    }


def read_object(obj):
    return {
        "name": obj.Name,
        "type": obj.TypeId,
        "visibility": obj.Visibility,
        "shape": read_shape(obj),
    }


def read_document(doc):
    return {
        "name": doc.Name,
        "label": doc.Label,
        "objects": [read_object(obj) for obj in doc.Objects],
    }


def read_view(view):
    """Camera, size and screen rectangle of a 3D view, and whether its parent clips part of it.

    ``getSize()`` is the render area in device pixels and stays the full widget when the MDI
    area hides part of it; ``visibleRegion()`` is in logical pixels and shrinks. Scaling the
    visible rectangle by the device pixel ratio puts both in the same unit. The scale truncates
    as FreeCAD does: on FreeCAD 1.1.4 at ratio 1.25, a 1534 x 799 widget reports 1917 x 998.
    Only ratio 1.25 was measured, so a difference of up to ``CLIP_SLACK_PX`` per dimension
    counts as not clipped. A hidden or minimized view has an empty region and says nothing
    about clipping: ``visible_size`` and ``clipped`` are then ``None``.

    ``rect`` is ``[x, y, width, height]`` of the render area in global device pixels, the unit
    a window capture of a single monitor uses: the widget's global origin times the ratio, and
    ``getSize()``.
    """
    graphics_view = view.graphicsView()
    region = graphics_view.visibleRegion()
    ratio = graphics_view.devicePixelRatioF()
    size = list(view.getSize())
    origin = graphics_view.mapToGlobal(graphics_view.rect().topLeft())
    visible_size = clipped = None
    if graphics_view.isVisible() and not region.isEmpty():
        visible = region.boundingRect()
        visible_size = [int(visible.width() * ratio), int(visible.height() * ratio)]
        clipped = any(abs(s - v) > CLIP_SLACK_PX for s, v in zip(size, visible_size))
    return {
        "camera": view.getCamera(),
        "size": size,
        "visible_size": visible_size,
        "clipped": clipped,
        "rect": [round(origin.x() * ratio), round(origin.y() * ratio), *size],
    }


def screen_point(view, rect, point):
    """Project a 3D point to global device pixels.

    ``getPointOnViewport`` answers in device pixels of the render area with the origin at the
    bottom left (Coin), so Y is flipped against the top-left origin of ``rect``.
    """
    x, y = view.getPointOnViewport(point)
    return [rect[0] + x, rect[1] + rect[3] - 1 - y]


def _read_gui_document(gui, doc, view, view_rect):
    """``read_document`` plus ``modified`` and, per object, ``screen_center`` of its bbox.

    ``screen_center`` is ``None`` for an object with no shape or when ``view`` is ``None``.
    """
    record = {"modified": gui.getDocument(doc.Name).Modified, **read_document(doc)}
    for obj, entry in zip(doc.Objects, record["objects"]):
        entry["screen_center"] = None
        if view is not None and entry["shape"] is not None:
            entry["screen_center"] = screen_point(view, view_rect, obj.Shape.BoundBox.Center)
    return record


def take_snapshot(app, gui):
    """Snapshot of every open document and the active 3D view.

    Only the active document is drawn in the active view, so only its objects get a
    ``screen_center``.
    """
    active = app.ActiveDocument
    active_view = None
    if active is not None:
        candidate = gui.getDocument(active.Name).ActiveView
        if hasattr(candidate, "graphicsView"):
            active_view = candidate
    view = read_view(active_view) if active_view is not None else None
    documents = []
    for doc in app.listDocuments().values():
        is_active = active is not None and doc.Name == active.Name
        shown_in = active_view if is_active else None
        documents.append(_read_gui_document(gui, doc, shown_in, view and view["rect"]))
    return {
        "freecad_version": freecad_version(app),
        "active_document": active.Name if active is not None else None,
        "documents": documents,
        "view": view,
    }
