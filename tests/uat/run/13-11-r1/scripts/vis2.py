import FreeCADGui as Gui
g = Gui.getDocument(doc.Name)
b = doc.getObject("Body")
result = {"objects": {o.Name: o.Visibility for o in doc.Objects if o.TypeId.startswith(("PartDesign::Pad", "Sketcher"))},
          "tip": b.Tip.Name if b.Tip else None, "UndoCount": doc.UndoCount, "RedoCount": doc.RedoCount}
