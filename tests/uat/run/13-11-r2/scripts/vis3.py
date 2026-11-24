b = doc.getObject("Body")
result = {"vis": {o.Name: o.Visibility for o in doc.Objects if o.TypeId.startswith(("PartDesign::Pad", "PartDesign::Boolean", "PartDesign::Body"))},
          "tip": b.Tip.Name if b.Tip else None, "body_volume": round(b.Shape.Volume, 3), "UndoCount": doc.UndoCount, "RedoCount": doc.RedoCount,
          "objects": len(doc.Objects), "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]}
