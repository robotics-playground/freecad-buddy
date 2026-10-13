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
    """Camera and size of a 3D view, and whether its parent clips part of it.

    ``getSize()`` is the render area in device pixels and stays the full widget when the MDI
    area hides part of it; ``visibleRegion()`` is in logical pixels and shrinks. Scaling the
    visible rectangle by the device pixel ratio puts both in the same unit. The scale truncates
    as FreeCAD does: on FreeCAD 1.1.4 at ratio 1.25, a 1534 x 799 widget reports 1917 x 998.
    Only ratio 1.25 was measured, so a difference of up to ``CLIP_SLACK_PX`` per dimension
    counts as not clipped. A hidden or minimized view has an empty region and says nothing
    about clipping: ``visible_size`` and ``clipped`` are then ``None``.
    """
    graphics_view = view.graphicsView()
    region = graphics_view.visibleRegion()
    size = list(view.getSize())
    visible_size = clipped = None
    if graphics_view.isVisible() and not region.isEmpty():
        visible = region.boundingRect()
        ratio = graphics_view.devicePixelRatioF()
        visible_size = [int(visible.width() * ratio), int(visible.height() * ratio)]
        clipped = any(abs(s - v) > CLIP_SLACK_PX for s, v in zip(size, visible_size))
    return {
        "camera": view.getCamera(),
        "size": size,
        "visible_size": visible_size,
        "clipped": clipped,
    }


def take_snapshot(app, gui):
    documents = [
        {"modified": gui.getDocument(doc.Name).Modified, **read_document(doc)}
        for doc in app.listDocuments().values()
    ]
    active = app.ActiveDocument
    view = None
    if active is not None:
        active_view = gui.getDocument(active.Name).ActiveView
        if hasattr(active_view, "graphicsView"):
            view = read_view(active_view)
    return {
        "freecad_version": freecad_version(app),
        "active_document": active.Name if active is not None else None,
        "documents": documents,
        "view": view,
    }
