"""TC-06 agent-driven scenarios for phase P5, one function per step group: p5_tc06.py <name> [arg ...].
The GUI steps (Show All, Fit All, Standard Views, tree, capture) run separately through p1_gui.py /
p2_gui.py / p5_gui.py; the agent reads every capture and render."""

import json
import sys

from p5_lib import Run5, q

SESSION_TMP = ("import os\nfrom freecad_buddy.usecases.documents import temp_dir\n"
               "result = (temp_dir(), sorted(os.listdir(temp_dir())))")
SYSTEM_TMP_SHOTS = ("import glob, os, tempfile\n"
                    "result = sorted(glob.glob(os.path.join(tempfile.gettempdir(), 'FCB_TMP_shot_*.png')))")


def pre():
    with Run5("tc-06-pre") as run:
        caps = run.call("query_capabilities", {}, "freecad_version and render")
        sc = caps.get("structured_content") or {}
        print("RENDER", sc.get("render"), "VERSION", sc.get("freecad_version"))


def plate(run, label):
    doc = run.doc(label)
    run.plate(doc)
    return doc


def l_block(run, label):
    """Asymmetric L-block: 40 x 30 L profile on XY (notch 15 x 12 at the +X+Y corner), padded 10 mm."""
    doc = run.doc(label)
    run.call("feature_body_create", {"doc": doc, "name": "Body"}, "given body", quiet=True)
    run.call("sketch_create", {"doc": doc, "name": "LProfile", "body": "Body", "plane": "XY"}, "given sketch",
             quiet=True)
    pts = [[0, 0], [40, 0], [40, 18], [25, 18], [25, 30], [0, 30]]
    geometry = [{"kind": "line_segment", "start": pts[i], "end": pts[(i + 1) % 6]} for i in range(6)]
    constraints = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 6, "second_pos": 1}
                   for i in range(6)]
    constraints += [{"type": "Horizontal", "first": i} for i in (0, 2, 4)]
    constraints += [{"type": "Vertical", "first": i} for i in (1, 3, 5)]
    constraints += [
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(40)},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(18)},
        {"type": "DistanceX", "first": 2, "first_pos": 2, "second": 2, "second_pos": 1, "value": q(15)},
        {"type": "DistanceY", "first": 3, "first_pos": 1, "second": 3, "second_pos": 2, "value": q(12)},
    ]
    run.call("sketch_add_geometry", {"doc": doc, "sketch": "LProfile", "geometry": geometry,
                                     "constraints": constraints}, "given geometry", quiet=True)
    run.call("feature_pad", {"doc": doc, "body": "Body", "profile": "LProfile", "name": "LPad", "length": q(10)},
             "given pad", quiet=True)
    run.call("query_mass_properties", {"doc": doc, "object": "LPad"}, "given bbox")
    return doc


def tc06_01_given():
    with Run5("tc-06-01") as run:
        doc = run.doc("tc-06-01b")
        run.py(doc, "b = doc.addObject('Part::Box', 'Bracket')\nb.Length = 60\nb.Width = 40\nb.Height = 5\n"
                    "doc.recompute()\nresult = [(o.Name, o.TypeId) for o in doc.Objects]", "given bracket")
        run.call("query_mass_properties", {"doc": doc, "object": "Bracket"}, "given geometry")
        run.call("document_list", {}, "given document_list")
        run.call("query_tree_summary", {"doc": doc}, "given tree")
        print("DOC", doc)


def fit(tag, doc):
    with Run5(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "fit")


def tc06_01_render(doc):
    with Run5("tc-06-01") as run:
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso", "include": ["Bracket"]}}, "when render")
        run.render(r, "tc-06-01-mcp")
        run.call("query_mass_properties", {"doc": doc, "object": "Bracket"}, "then bbox")


def tc06_02_given():
    with Run5("tc-06-02") as run:
        doc = l_block(run, "tc-06-02")
        print("DOC", doc)


def tc06_02_renders(doc):
    with Run5("tc-06-02", limit=700) as run:
        for camera in ("iso", "front", "top", "right", "left", "back", "bottom"):
            r = run.call("query_screenshot", {"doc": doc, "view": {"camera": camera}}, f"when {camera}")
            run.render(r, f"tc-06-02-{camera}")
        run.call("query_screenshot", {"doc": doc, "view": {"camera": "oblique"}}, "then oblique refused")


def tc06_06_given():
    with Run5("tc-06-06") as run:
        doc = run.doc("tc-06-06")
        run.py(doc, "a = doc.addObject('Part::Box', 'BoxA')\na.Length = 20\na.Width = 20\na.Height = 20\n"
                    "b = doc.addObject('Part::Box', 'BoxB')\nb.Length = 10\nb.Width = 10\nb.Height = 30\n"
                    "b.Placement.Base = FreeCAD.Vector(40, 0, 0)\ndoc.recompute()\n"
                    "result = [(o.Name, o.Visibility) for o in doc.Objects]", "given two boxes")
        run.call("query_tree_summary", {"doc": doc}, "given tree")
        print("DOC", doc)


def tc06_06(doc, step):
    with Run5("tc-06-06") as run:
        if step == "render1":
            r = run.call("query_screenshot", {"doc": doc}, "when default render 1")
            run.render(r, "tc-06-06-default1")
        elif step == "tree":
            run.call("query_tree_summary", {"doc": doc}, "then tree")
        elif step == "render2":
            r = run.call("query_screenshot", {"doc": doc}, "when default render after hide")
            run.render(r, "tc-06-06-default-hidden")
            r = run.call("query_screenshot", {"doc": doc, "view": {"include": ["BoxB"]}}, "when explicit include BoxB")
            run.render(r, "tc-06-06-includeB")
        elif step == "render3":
            r = run.call("query_screenshot", {"doc": doc}, "then default render after restore")
            run.render(r, "tc-06-06-default-restored")


def tc06_08_given():
    with Run5("tc-06-08") as run:
        doc = plate(run, "tc-06-08")
        run.call("document_list", {}, "given document_list")
        print("DOC", doc)


def tc06_08(doc):
    with Run5("tc-06-08") as run:
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, "when default size")
        run.render(r, "tc-06-08-default")
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso", "width": 640, "height": 480}},
                     "when 640x480")
        run.render(r, "tc-06-08-640x480")
        run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso", "width": 4096, "height": 4096}},
                 "when 4096 above cap")
        run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso", "width": 0}}, "when width 0")
        r = run.call("query_screenshot", {"doc": doc, "view": {"width": 1920, "height": 1920}}, "then exactly 1920")
        run.render(r, "tc-06-08-1920")
        r = run.call("query_screenshot", {"doc": doc, "view": {"width": 800}}, "then width only 800")
        run.render(r, "tc-06-08-w800")


def tc06_09_given(path):
    with Run5("tc-06-09") as run:
        doc = run.call("document_open", {"path": path}, "given open")["structured_content"]["doc"]
        print("DOC", doc)


def tc06_09(doc):
    with Run5("tc-06-09", limit=1500) as run:
        run.call("verify_recompute", {"doc": doc}, "given verify_recompute")
        run.py(doc, SESSION_TMP, "given session temp listing")
        run.py(doc, SYSTEM_TMP_SHOTS, "given system temp shots")
        before_mass = run.call("query_mass_properties", {"doc": doc, "object": "Box"}, "when before mass")
        before_tree = run.call("query_tree_summary", {"doc": doc, "depth": 2}, "when before tree")
        links = []
        for label, view, stem in (("iso", {"camera": "iso"}, "tc-06-09-iso"),
                                  ("top styled", {"camera": "top", "styles": [{"object": "Box", "color": [0, 1, 0],
                                                                               "transparency": 50}]},
                                   "tc-06-09-top-styled"),
                                  ("front focus", {"camera": "front", "focus": {"object": "Box", "element_type": "face",
                                                                               "index": 2}}, "tc-06-09-front-focus")):
            r = run.call("query_screenshot", {"doc": doc, "view": view}, f"when render {label}")
            links.append(((r.get("structured_content") or {}).get("render") or {}).get("resource_link"))
            run.render(r, stem)
        after_mass = run.call("query_mass_properties", {"doc": doc, "object": "Box"}, "when after mass")
        after_tree = run.call("query_tree_summary", {"doc": doc, "depth": 2}, "when after tree")
        run.py(doc, "result = [o.Name for o in doc.Objects if 'Touched' in o.State]", "then touched")
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, "then unstyled after styled")
        run.render(r, "tc-06-09-unstyled-after")
        links.append(((r.get("structured_content") or {}).get("render") or {}).get("resource_link"))
        run.py(doc, SESSION_TMP, "then session temp listing")
        run.py(doc, SYSTEM_TMP_SHOTS, "then system temp shots")
        bm, am = before_mass.get("structured_content"), after_mass.get("structured_content")
        print("CHECK mass equal:", bm == am)
        print("CHECK volume/com before:", json.dumps({k: bm.get(k) for k in ("volume", "com")}),
              "after:", json.dumps({k: am.get(k) for k in ("volume", "com")}))
        print("CHECK tree equal:", before_tree == after_tree)
        print("LINKS", json.dumps(links))


def tc06_10_given():
    with Run5("tc-06-10") as run:
        doc = run.doc("tc-06-10")
        run.call("feature_body_create", {"doc": doc, "name": "Body"}, "given body", quiet=True)
        run.rect(doc, "Body", "BoxSketch", 0, 0, 20, 10)
        run.call("verify_sketch", {"doc": doc, "sketch": "BoxSketch"}, "given verify_sketch")
        run.call("feature_pad", {"doc": doc, "body": "Body", "profile": "BoxSketch", "name": "BoxPad",
                                 "length": q(10)}, "given pad")
        run.call("query_mass_properties", {"doc": doc, "object": "BoxPad"}, "given volume")
        r = run.call("query_screenshot", {"doc": doc}, "given clean render")
        run.render(r, "tc-06-10-given-clean")
        print("DOC", doc)


def tc06_10(doc):
    with Run5("tc-06-10", limit=2000) as run:
        run.py(doc, "doc.getObject('BoxPad').Length = 25\nresult = doc.getObject('BoxPad').State", "when set Length")
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, "when dirty render")
        run.render(r, "tc-06-10-dirty")
        print("TEXT", json.dumps(r.get("text")))
        run.call("document_recompute", {"doc": doc}, "when recompute")
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, "when clean render")
        run.render(r, "tc-06-10-recomputed")
        run.call("query_mass_properties", {"doc": doc, "object": "BoxPad"}, "then volume")


def tc06_12_given():
    with Run5("tc-06-12") as run:
        doc = plate(run, "tc-06-12")
        run.call("query_capabilities", {}, "given render mode")
        print("DOC", doc)


def tc06_12(doc, stem):
    with Run5("tc-06-12") as run:
        r = run.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}, f"when render {stem}")
        run.render(r, stem)


def tc06_12_pref(doc, value):
    with Run5("tc-06-12") as run:
        run.py(doc, "p = FreeCAD.ParamGet('User parameter:BaseApp/Preferences/View')\nresult = p.GetInt('AntiAliasing')\n"
                    f"p.SetInt('AntiAliasing', {int(value)})", f"when set AntiAliasing {value}")


def close(tag, *docs):
    with Run5(tag) as run:
        for doc in docs:
            run.call("document_close", {"doc": doc}, "cleanup close")


if __name__ == "__main__":
    globals()[sys.argv[1]](*sys.argv[2:])
