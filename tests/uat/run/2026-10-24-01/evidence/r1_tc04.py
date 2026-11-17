"""TC-04 agent-driven scenarios for phase R1 (copy of 2026-10-23-02 r1_tc04.py), one function per step group: p3_tc04.py <name> [doc].
The visual steps (fit, capture, read) run separately through r1_gui1.py / r1_gui2.py."""

import sys

from r1_p3_lib import Run, q


def pre():
    with Run("tc-04-pre") as run:
        run.call("query_capabilities", {}, "freecad_version")
        doc = run.doc("ProbeDoc")
        run.call("feature_body_create", {"doc": doc, "name": "ProbeBody"}, "PartDesign available")
        run.call("document_close", {"doc": doc}, "cleanup")


def tc04_04():
    with Run("tc-04-04") as run:
        doc = run.doc("PadOptions")
        for body, profile, x0 in (("RevBody", "RevProfile", 0), ("TwoBody", "TwoProfile", 40),
                                  ("TaperBody", "TaperProfile", 80)):
            run.call("feature_body_create", {"doc": doc, "name": body}, "given body")
            run.rect(doc, body, profile, x0, 0, 20, 30)
            run.call("verify_sketch", {"doc": doc, "sketch": profile}, "given dof")
        run.call("feature_pad", {"doc": doc, "body": "RevBody", "profile": "RevProfile", "name": "RevPad",
                                 "length": q(10), "reversed": True}, "when reversed")
        run.call("feature_pad", {"doc": doc, "body": "TwoBody", "profile": "TwoProfile", "name": "TwoPad",
                                 "length": q(10), "second_length": q(4)}, "when second_length")
        run.call("feature_pad", {"doc": doc, "body": "TaperBody", "profile": "TaperProfile", "name": "TaperPad",
                                 "length": q(10), "taper_angle": q(5, "deg")}, "when taper")
        for name in ("RevPad", "TwoPad", "TaperPad"):
            run.call("query_mass_properties", {"doc": doc, "object": name}, f"then mass {name}")
            run.call("query_object", {"doc": doc, "object": name}, f"then object {name}")
            run.call("verify_shape", {"doc": doc, "object": name}, f"then verify {name}")
        run.call("feature_pad", {"doc": doc, "body": "TaperBody", "profile": "TaperProfile", "name": "TaperBad",
                                 "length": q(10), "taper_angle": q(120, "deg")}, "then taper 120")
        print("DOC", doc)


TOP = {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face6"}
BBOX = ("o = doc.getObject({!r}); b = o.Shape.BoundBox; "
        "result = [round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]")


def tc04_05():
    with Run("tc-04-05") as run:
        doc = run.doc("PocketPlate")
        run.plate(doc)
        run.faces(doc, "PlatePad")
        run.rect(doc, "PlateBody", "SlotProfile", 10, 10, 10, 10, face=TOP)
        run.rect(doc, "PlateBody", "ThroughProfile", 40, 15, 10, 10, face=TOP)
        for sketch in ("SlotProfile", "ThroughProfile"):
            run.call("verify_sketch", {"doc": doc, "sketch": sketch}, "given dof")
            run.py(doc, BBOX.format(sketch), f"oracle bbox {sketch}")
        run.call("feature_pocket", {"doc": doc, "body": "PlateBody", "profile": "SlotProfile", "name": "SlotPocket",
                                    "length": q(2)}, "when slot")
        run.call("feature_pocket", {"doc": doc, "body": "PlateBody", "profile": "ThroughProfile",
                                    "name": "ThroughPocket", "up_to": "ThroughAll"}, "when through")
        run.call("query_mass_properties", {"doc": doc, "object": "SlotPocket"}, "then mass slot")
        run.call("query_mass_properties", {"doc": doc, "object": "ThroughPocket"}, "then mass through")
        run.call("verify_shape", {"doc": doc, "object": "ThroughPocket"}, "then verify")
        run.call("query_object", {"doc": doc, "object": "ThroughPocket"}, "then object")
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "SlotProfile", "name": "ThroughPad",
                                 "up_to": "ThroughAll"}, "then pad ThroughAll")
        print("DOC", doc)


def shaft(run, doc, label="given"):
    run.call("feature_body_create", {"doc": doc, "name": "ShaftBody"}, f"{label} body", quiet=True)
    run.rect(doc, "ShaftBody", "ShaftProfile", 0, 0, 5, 20, plane="XZ", label=label)
    run.call("verify_sketch", {"doc": doc, "sketch": "ShaftProfile"}, f"{label} dof")
    return run.call("feature_revolve", {"doc": doc, "body": "ShaftBody", "profile": "ShaftProfile", "name": "ShaftRev",
                                        "axis": {"kind": "mapped_name", "object": "ShaftProfile", "mapped_name": "V_Axis"},
                                        "angle": q(360, "deg")}, f"{label} revolve")


def tc04_06():
    with Run("tc-04-06") as run:
        doc = run.doc("Shaft")
        shaft(run, doc, "when")
        run.call("query_mass_properties", {"doc": doc, "object": "ShaftRev"}, "then mass")
        run.call("query_object", {"doc": doc, "object": "ShaftRev"}, "then object")
        run.call("query_dependencies", {"doc": doc, "object": "ShaftRev"}, "then dependencies")
        run.call("verify_shape", {"doc": doc, "object": "ShaftRev"}, "then verify")
        base = {"doc": doc, "body": "ShaftBody", "profile": "ShaftProfile"}
        v_axis = {"kind": "mapped_name", "object": "ShaftProfile", "mapped_name": "V_Axis"}
        run.call("feature_revolve", {**base, "name": "EdgeRev", "angle": q(360, "deg"),
                                     "axis": {"kind": "mapped_name", "object": "ShaftProfile", "mapped_name": "Edge1"}},
                 "then Edge1 axis")
        run.call("feature_revolve", {**base, "name": "OverRev", "axis": v_axis, "angle": q(400, "deg")}, "then 400 deg")
        run.call("feature_revolve", {**base, "name": "SecondRev", "axis": v_axis, "angle": q(180, "deg"),
                                     "second_angle": q(90, "deg")}, "then second_angle")
        print("DOC", doc)


def point_sketch(run, doc, name, x, y, label="given"):
    run.call("sketch_create", {"doc": doc, "name": name, "face": TOP, "body": "PlateBody"}, f"{label} {name}", quiet=True)
    run.call("sketch_add_geometry", {"doc": doc, "sketch": name, "geometry": [{"kind": "point", "start": [x, y]}],
                                     "constraints": Run.position(x, y)}, f"{label} {name} point", quiet=True)
    run.call("verify_sketch", {"doc": doc, "sketch": name}, f"{label} dof")


def tc04_07():
    with Run("tc-04-07") as run:
        doc = run.doc("HolePlate")
        run.plate(doc)
        point_sketch(run, doc, "HoleProfile", 10, 20)
        run.py(doc, BBOX.format("HoleProfile"), "oracle bbox HoleProfile")
        hole = {"doc": doc, "body": "PlateBody", "profile": "HoleProfile"}
        run.call("feature_hole", {**hole, "name": "ClearanceHole", "diameter": q(5.5), "depth": q(3)}, "when hole")
        run.call("query_mass_properties", {"doc": doc, "object": "ClearanceHole"}, "then mass")
        run.call("query_object", {"doc": doc, "object": "ClearanceHole"}, "then object")
        run.call("verify_shape", {"doc": doc, "object": "ClearanceHole"}, "then verify")
        run.call("feature_hole", {**hole, "name": "NoDepthHole", "diameter": q(5.5)}, "then no depth")
        run.call("feature_hole", {**hole, "name": "ZeroHole", "diameter": q(0), "depth": q(3)}, "then zero diameter")
        other = run.doc("ThroughHolePlate")
        run.plate(other)
        point_sketch(run, other, "HoleProfile", 10, 20)
        run.call("feature_hole", {"doc": other, "body": "PlateBody", "profile": "HoleProfile", "name": "ThroughHole",
                                  "diameter": q(5.5), "depth_type": "ThroughAll"}, "then ThroughAll")
        run.call("query_mass_properties", {"doc": other, "object": "ThroughHole"}, "then ThroughAll mass")
        run.call("document_close", {"doc": other}, "then ThroughAll cleanup")
        print("DOC", doc)


def edge(obj, name):
    return {"kind": "mapped_name", "object": obj, "mapped_name": name}


def tc04_10a():
    with Run("tc-04-10") as run:
        doc = run.doc("ChamferPlate")
        run.plate(doc)
        run.edges(doc, "PlatePad")
        run.call("feature_chamfer", {"doc": doc, "body": "PlateBody", "base": "PlatePad", "name": "EqualChamfer",
                                     "edges": [edge("PlatePad", "Edge1")], "size": q(1.5)}, "when equal")
        run.call("query_object", {"doc": doc, "object": "EqualChamfer"}, "given ChamferType enum")
        run.py(doc, "result = doc.getObject('EqualChamfer').getEnumerationsOfProperty('ChamferType')", "oracle enum")
        run.edges(doc, "EqualChamfer")
        print("DOC", doc)


def tc04_10b(doc):
    with Run("tc-04-10") as run:
        run.call("feature_chamfer", {"doc": doc, "body": "PlateBody", "base": "EqualChamfer", "name": "TwoSizeChamfer",
                                     "edges": [edge("EqualChamfer", "Edge3")], "chamfer_type": "Two distances",
                                     "size": q(2), "second_size": q(1)}, "when two sizes")
        run.edges(doc, "TwoSizeChamfer")


def tc04_10c(doc):
    with Run("tc-04-10") as run:
        base = {"doc": doc, "body": "PlateBody"}
        run.call("feature_chamfer", {**base, "base": "TwoSizeChamfer", "name": "AngleChamfer",
                                     "edges": [edge("TwoSizeChamfer", "Edge17")], "chamfer_type": "Distance and Angle",
                                     "size": q(2), "angle": q(30, "deg")}, "when angle")
        run.call("query_mass_properties", {"doc": doc, "object": "EqualChamfer"}, "then mass equal")
        run.call("feature_chamfer", {**base, "base": "AngleChamfer", "name": "BevelChamfer",
                                     "edges": [edge("AngleChamfer", "Edge1")], "chamfer_type": "Bevel",
                                     "size": q(1)}, "then Bevel")
        run.call("feature_chamfer", {**base, "base": "AngleChamfer", "name": "WideAngleChamfer",
                                     "edges": [edge("AngleChamfer", "Edge1")], "chamfer_type": "Distance and Angle",
                                     "size": q(1), "angle": q(200, "deg")}, "then angle 200")
        run.call("feature_chamfer", {**base, "base": "AngleChamfer", "name": "ZeroChamfer",
                                     "edges": [edge("AngleChamfer", "Edge1")], "size": q(0)}, "then size 0")
        run.call("verify_shape", {"doc": doc, "object": "AngleChamfer"}, "then verify")


def tc04_13():
    with Run("tc-04-13") as run:
        doc = run.doc("DatumPlate")
        run.plate(doc)
        run.faces(doc, "PlatePad")
        run.edges(doc, "PlatePad")
        run.py(doc, "result = [(i + 1, [round(v, 3) for v in (p.X, p.Y, p.Z)]) for i, p in "
                    "enumerate(doc.getObject('PlatePad').Shape.Vertexes)]", "oracle vertices PlatePad")
        base = {"doc": doc, "body": "PlateBody"}
        run.call("feature_datum", {**base, "name": "RaisedPlane", "kind": "plane",
                                   "attachment": edge("PlatePad", "Face6"), "offset": q(10)}, "when plane")
        run.call("feature_datum", {**base, "name": "EdgeAxis", "kind": "axis",
                                   "attachment": edge("PlatePad", "Edge1"), "map_mode": "TwoPointLine"}, "when axis")
        run.call("feature_datum", {**base, "name": "CornerPoint", "kind": "point",
                                   "attachment": edge("PlatePad", "Vertex1"), "map_mode": "Vertex"}, "when point")
        run.call("feature_datum", {**base, "name": "FaceCS", "kind": "cs",
                                   "attachment": edge("PlatePad", "Face6")}, "when cs")
        run.call("query_placement", {"doc": doc, "object": "RaisedPlane"}, "then placement")
        run.call("query_object", {"doc": doc, "object": "RaisedPlane"}, "then object")
        run.call("query_dependencies", {"doc": doc, "object": "RaisedPlane"}, "then dependencies")
        run.call("query_mass_properties", {"doc": doc, "object": "RaisedPlane"}, "then mass datum")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("feature_datum", {**base, "name": "CurveDatum", "kind": "curve",
                                   "attachment": edge("PlatePad", "Edge1")}, "then kind curve")
        run.call("feature_datum", {**base, "name": "BadModePoint", "kind": "point",
                                   "attachment": edge("PlatePad", "Edge1"), "map_mode": "TwoPointLine"}, "then bad map_mode")
        run.call("query_mass_properties", {"doc": doc, "object": "PlatePad"}, "then plate unchanged")
        print("DOC", doc)


def tc04_15a():
    with Run("tc-04-15") as run:
        doc = run.doc("UpToFace")
        run.call("feature_body_create", {"doc": doc, "name": "PlateBody"}, "given body", quiet=True)
        run.rect(doc, "PlateBody", "BaseProfile", 0, 20, 60, 5, plane="XZ")
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "BaseProfile", "name": "BasePad",
                                 "length": q(40), "midplane": True}, "given base pad")
        run.call("verify_shape", {"doc": doc, "object": "BasePad"}, "given verify")
        run.call("query_mass_properties", {"doc": doc, "object": "BasePad"}, "given volume")
        run.rect(doc, "PlateBody", "RiserProfile", 25, -5, 10, 10)
        run.call("verify_sketch", {"doc": doc, "sketch": "RiserProfile"}, "given dof")
        run.py(doc, BBOX.format("RiserProfile"), "oracle bbox RiserProfile")
        run.faces(doc, "BasePad")
        print("DOC", doc)


def tc04_15b(doc):
    with Run("tc-04-15") as run:
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "RiserProfile", "name": "RiserPad",
                                 "up_to": "UpToFace", "up_to_face": edge("BasePad", "Face1")}, "when up to face")
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "RiserProfile", "name": "BadTypePad",
                                 "up_to": "UpToInfinity"}, "when bad enum")
        run.call("query_mass_properties", {"doc": doc, "object": "RiserPad"}, "then mass")
        run.call("query_object", {"doc": doc, "object": "RiserPad"}, "then object")
        run.call("query_dependencies", {"doc": doc, "object": "RiserPad"}, "then dependencies")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("verify_shape", {"doc": doc, "object": "RiserPad"}, "then verify")


def tc04_16a():
    with Run("tc-04-16") as run:
        doc = run.doc("BigFillet")
        run.plate(doc)
        run.edges(doc, "PlatePad")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_16b(doc):
    with Run("tc-04-16") as run:
        run.call("feature_fillet", {"doc": doc, "body": "PlateBody", "base": "PlatePad", "name": "TooBigFillet",
                                    "edges": [edge("PlatePad", "Edge3")], "radius": q(20)}, "when fillet 20")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("query_mass_properties", {"doc": doc, "object": "PlatePad"}, "then plate volume")
        run.snaps(doc, "then snaps")
        run.call("verify_recompute", {"doc": doc}, "then recompute")


def tc04_17a():
    with Run("tc-04-17") as run:
        doc = run.doc("SeamFillet")
        shaft(run, doc)
        run.edges(doc, "ShaftRev")
        run.call("query_mass_properties", {"doc": doc, "object": "ShaftRev"}, "given volume")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_17b(doc):
    with Run("tc-04-17") as run:
        base = {"doc": doc, "body": "ShaftBody", "base": "ShaftRev", "radius": q(1)}
        run.call("feature_fillet", {**base, "name": "DropFillet", "edges": [edge("ShaftRev", "Edge3")]}, "when seam")
        run.call("feature_fillet", {**base, "name": "MixedFillet",
                                    "edges": [edge("ShaftRev", "Edge1"), edge("ShaftRev", "Edge3")]}, "when mixed")
        run.snaps(doc, "then snaps")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("query_mass_properties", {"doc": doc, "object": "ShaftRev"}, "then volume")


def tc04_19a():
    with Run("tc-04-19") as run:
        doc = run.doc("BadLength")
        run.call("feature_body_create", {"doc": doc, "name": "BlockBody"}, "given body", quiet=True)
        run.rect(doc, "BlockBody", "BlockProfile", 0, 0, 20, 30)
        run.call("verify_sketch", {"doc": doc, "sketch": "BlockProfile"}, "given dof")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_19b(doc):
    with Run("tc-04-19") as run:
        base = {"doc": doc, "body": "BlockBody", "profile": "BlockProfile"}
        run.call("feature_pad", {**base, "name": "ZeroPad", "length": q(0)}, "when zero")
        run.call("feature_pad", {**base, "name": "NegPad", "length": q(-10)}, "when negative")
        run.call("feature_pad", {**base, "name": "NoLenPad"}, "when no length")
        run.snaps(doc, "then snaps")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("query_object", {"doc": doc, "object": "BlockBody"}, "then body tip")


def block(run, doc, label="given"):
    run.call("feature_body_create", {"doc": doc, "name": "BlockBody"}, f"{label} body", quiet=True)
    run.rect(doc, "BlockBody", "BlockProfile", 0, 0, 20, 30, label=label)
    run.call("feature_pad", {"doc": doc, "body": "BlockBody", "profile": "BlockProfile", "name": "BlockPad",
                             "length": q(10)}, f"{label} pad", quiet=True)
    return run.call("query_mass_properties", {"doc": doc, "object": "BlockPad"}, f"{label} volume")


def tc04_21a():
    with Run("tc-04-21") as run:
        doc = run.doc("ReadOnly")
        block(run, doc)
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_21b(doc):
    with Run("tc-04-21") as run:
        sp = {"doc": doc, "feature": "BlockPad"}
        run.call("feature_set_parameters", {**sp, "parameters": {"Thickness": q(3)}}, "when unknown")
        run.call("feature_set_parameters", {**sp, "parameters": {"Shape": 1}}, "when read-only Shape")
        run.call("feature_set_parameters", {**sp, "parameters": {"Length": q(25, "deg")}}, "when wrong unit")
        run.call("feature_set_parameters", {**sp, "parameters": {"Length": [25]}}, "when list value")
        run.snaps(doc, "then snaps")
        run.call("query_mass_properties", {"doc": doc, "object": "BlockPad"}, "then volume")
        run.call("feature_set_parameters", {**sp, "parameters": {"Length": q(12), "Thickness": 3}}, "then batch")
        run.call("query_object", {"doc": doc, "object": "BlockPad"}, "then Length")
        other = run.doc("ReadOnlyShaft")
        shaft(run, other)
        run.call("feature_set_parameters", {"doc": other, "feature": "ShaftRev",
                                            "parameters": {"Base": q(1)}}, "then revolution Base")
        run.call("document_close", {"doc": other}, "then Base cleanup")


def tc04_22a():
    with Run("tc-04-22") as run:
        doc = run.doc("Orphans")
        run.plate(doc)
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "given tree")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_22b(doc):
    with Run("tc-04-22") as run:
        run.call("feature_pad", {"doc": doc, "body": "NoSuchBody", "profile": "PlateProfile", "name": "OrphanPad",
                                 "length": q(5)}, "when no body")
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "NoSuchSketch", "name": "OrphanPad",
                                 "length": q(5)}, "when no profile")
        run.call("feature_fillet", {"doc": doc, "body": "PlateBody", "base": "NoSuchPad", "name": "OrphanFillet",
                                    "edges": [edge("NoSuchPad", "Edge1")]}, "when no base")
        run.call("feature_pad", {"doc": doc, "body": "PlateProfile", "profile": "PlateProfile", "name": "WrongTypePad",
                                 "length": q(5)}, "when wrong type")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.snaps(doc, "then snaps")
        run.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "PlateProfile", "name": "PlatePad",
                                 "length": q(5)}, "then taken name")


LOOSEN = ("s = doc.getObject('LooseProfile'); [s.delConstraint(i) for i in sorted((i for i, c in "
          "enumerate(s.Constraints) if c.Name in ('PosX', 'PosY')), reverse=True)]; doc.recompute(); s.solve(); "
          "result = s.DoF")


def tc04_23a():
    with Run("tc-04-23") as run:
        doc = run.doc("Loose")
        run.call("feature_body_create", {"doc": doc, "name": "LooseBody"}, "given body", quiet=True)
        run.rect(doc, "LooseBody", "LooseProfile", 5, 5, 20, 30, names=("PosX", "PosY"))
        run.call("verify_sketch", {"doc": doc, "sketch": "LooseProfile"}, "given dof before")
        run.py(doc, LOOSEN, "given script_exec delete PosX PosY")
        run.call("verify_sketch", {"doc": doc, "sketch": "LooseProfile"}, "given dof after")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_23b(doc):
    with Run("tc-04-23", limit=1600) as run:
        run.call("feature_pad", {"doc": doc, "body": "LooseBody", "profile": "LooseProfile", "name": "LoosePad",
                                 "length": q(10)}, "when pad")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")
        run.call("query_object", {"doc": doc, "object": "LooseBody"}, "then body tip")
        run.snaps(doc, "then snaps")


def tc04_24a():
    with Run("tc-04-24") as run:
        doc = run.doc("RecomputeError")
        run.plate(doc)
        run.edges(doc, "PlatePad")
        run.call("feature_fillet", {"doc": doc, "body": "PlateBody", "base": "PlatePad", "name": "EdgeFillet",
                                    "edges": [edge("PlatePad", "Edge3")], "radius": q(1)}, "given fillet 1 mm")
        run.call("verify_recompute", {"doc": doc}, "given recompute")
        run.snaps(doc, "given snaps")
        run.call("view_fit_viewport", {"doc": doc}, "given fit")
        print("DOC", doc)


def tc04_24b(doc):
    with Run("tc-04-24", limit=1600) as run:
        run.call("feature_set_parameters", {"doc": doc, "feature": "EdgeFillet",
                                            "parameters": {"Radius": q(20)}}, "when radius 20")
        run.call("verify_recompute", {"doc": doc}, "when recompute after")
        run.call("query_object", {"doc": doc, "object": "EdgeFillet"}, "then radius")
        run.snaps(doc, "then snaps")
        run.call("query_tree_summary", {"doc": doc, "depth": 3}, "then tree")


def fit(tag, doc):
    with Run(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "visual fit")


def close(tag, doc):
    with Run(tag) as run:
        run.call("document_close", {"doc": doc}, "cleanup")


if __name__ == "__main__":
    globals()[sys.argv[1]](*sys.argv[2:])
