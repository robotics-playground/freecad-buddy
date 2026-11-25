doc.redo()
doc.recompute()
b = doc.getObject("Body"); p2 = doc.getObject("Pad2")
result = {"UndoCount": doc.UndoCount, "RedoCount": doc.RedoCount, "UndoNames": doc.UndoNames, "RedoNames": doc.RedoNames,
          "objects": len(doc.Objects), "tip": b.Tip.Name if b and b.Tip else None,
          "group": [o.Name for o in b.Group] if b else None,
          "pad2": None if p2 is None else {"outlist": [o.Name for o in p2.OutList], "expr": p2.ExpressionEngine,
                  "length": p2.Length.Value, "zmax": p2.Shape.BoundBox.ZMax, "base": p2.BaseFeature.Name if p2.BaseFeature else None,
                  "visible": p2.Visibility},
          "VS_inlist": [o.Name for o in doc.getObject("VS").InList] if doc.getObject("VS") else None,
          "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]}
