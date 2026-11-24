import FreeCADGui as Gui
names = ["Body", "Sketch1", "Pad1", "Sketch2", "Pad2", "Body001", "Pad3", "VS"]
out = {}
for n in names:
    o = doc.getObject(n)
    if o is None:
        out[n] = None; continue
    vo = Gui.getDocument(doc.Name).getObject(n)
    out[n] = {"Visibility": o.Visibility, "vp_visible": vo.Visibility if vo else None,
              "valid_shape": (not o.Shape.isNull()) if hasattr(o, "Shape") else None}
b = doc.getObject("Body")
result = {"vis": out, "tip": b.Tip.Name if b.Tip else None, "UndoCount": doc.UndoCount, "RedoCount": doc.RedoCount}
