import json, sys
F = 'from freecad_buddy.usecases.fingerprint import fingerprint\nresult = fingerprint(doc, fresh=True)["digest"]'
def shot(name):
    return ("cd D:/Work/Personal/Sources/freecad-buddy-wt-13-fu && export PROJECT_ROOT=$PWD RUN_DIR=$PWD/tests/uat/run/13-fu-r1 && "
            "echo '{\"pid\":1202,\"window_id\":41943133,\"screenshot_out_file\":\"$RUN_DIR/evidence/" + name + ".png\"}' "
            "| scripts/automation/fcb_cua.sh get_window_state | head -c 300")
BUILD = ("import Part, FreeCAD as App\nV = App.Vector\ndef add(n, s):\n    o = doc.addObject('Part::Feature', n); o.Shape = s\n"
         "add('A', Part.makeBox(10, 10, 10))\nadd('Face', Part.makeBox(10, 10, 10, V(10, 0, 0)))\n"
         "add('Edge', Part.makeBox(10, 10, 10, V(10, 10, 0)))\nadd('Vertex', Part.makeBox(10, 10, 10, V(10, 10, 10)))\n"
         "add('Big1', Part.makeBox(100, 100, 100, V(0, 100, 0)))\nadd('Big2', Part.makeBox(100, 100, 100, V(100 - 1e-7, 100, 0)))\n"
         "doc.recompute()\nresult = 'built'")
calls = [
 {"tool":"document_list","args":{}},
 {"tool":"document_create","args":{"label":"tc17_touch"}},
 {"tool":"script_exec","args":{"doc":"$DOC","code":BUILD}},
 {"tool":"query_tree_summary","args":{"doc":"$DOC"}},
 {"tool":"script_exec","args":{"doc":"$DOC","code":"a = doc.A.Shape\nresult = [round(a.Volume + doc.getObject(n).Shape.Volume - a.fuse(doc.getObject(n).Shape).Volume, 9) for n in ('Face', 'Edge', 'Vertex')]"}},
 {"tool":"script_exec","args":{"doc":"$DOC","code":"c = doc.Big1.Shape.common(doc.Big2.Shape)\nresult = c.isNull() or not c.Volume"}},
 {"tool":"view_fit_viewport","args":{"doc":"$DOC"}},
 {"shell":shot("tc-17-01-before")},
 {"tool":"script_exec","args":{"doc":"$DOC","code":F}},
 {"tool":"query_interference","args":{"doc":"$DOC","pairs":[["A","Face"],["A","Edge"],["A","Vertex"],["Big1","Big2"]]}},
 {"tool":"script_exec","args":{"doc":"$DOC","code":F}},
 {"tool":"query_tree_summary","args":{"doc":"$DOC"}},
 {"shell":shot("tc-17-01-after")},
]
json.dump(calls, open(sys.argv[1], "w"), indent=1)
