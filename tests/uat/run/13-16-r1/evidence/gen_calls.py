"""Write the TC-20 call lists for mcpcall.py."""
import json

import re

TC = open("/".join(__file__.replace("\\", "/").split("/")[:-4]) + "/testcases/TC-20-set-parameters-placement-strings.md", encoding="utf-8").read()
# The build call is the first fenced `mcp script_exec` block of TC-20-01, taken verbatim.
BUILD = json.loads('"' + re.search(r'mcp script_exec \{ doc: <handle>, code: "(.*?)" \}\n```', TC).group(1) + '"')
SETPL = ("import FreeCAD as App\ndoc.Body.Placement = App.Placement(App.Vector(1, 2, 3), App.Rotation(App.Vector(0, 0, 1), 90))\n"
         "doc.recompute()\nresult = [tuple(doc.Body.Placement.Base), round(doc.Body.Placement.Rotation.Angle * 57.29577951308232, 6)]")
READPL = "result = [tuple(doc.Body.Placement.Base), round(doc.Body.Placement.Rotation.Angle * 57.29577951308232, 6)]"
CUA = ("export MSYS_NO_PATHCONV=1; echo '{\"pid\":%d,\"window_id\":%d,\"screenshot_out_file\":\"/repo/tests/uat/run/13-16-r1/evidence/%s\"}' "
       "| docker exec -i -u cua fcb-desktop bash -c 'eval \"$(fcb-session-env)\"; /usr/local/bin/cua-driver call get_window_state' "
       "| grep -o '\"screenshot_file_path\"[^,]*'")
PID, WID = 559, 41943133


def shot(name):
    return {"shell": CUA % (PID, WID, name)}


MOVE = {"doc": "$DOC", "feature": "Body", "parameters": {"Placement": {"base": {"x": {"value": 10, "unit": "mm"}}}}}
tc01 = [
    {"tool": "document_list", "args": {}},
    {"tool": "document_create", "args": {"label": "tc20_place"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": BUILD}},
    {"tool": "query_tree_summary", "args": {"doc": "$DOC"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": SETPL}},
    {"tool": "view_fit_viewport", "args": {"doc": "$DOC"}},
    shot("tc-20-01-before.png"),
    {"tool": "feature_set_parameters", "args": MOVE},
    {"tool": "query_placement", "args": {"doc": "$DOC", "object": "Body"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": READPL}},
    {"tool": "feature_set_parameters", "args": MOVE},
    shot("tc-20-01-after.png"),
    {"tool": "document_undo", "args": {"doc": "$DOC"}},
    {"tool": "query_placement", "args": {"doc": "$DOC", "object": "Body"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": READPL}},
]
tc01_cleanup = [{"tool": "document_list", "args": {}}]

z = {"value": 5, "unit": "mm"}
tc02 = [
    {"tool": "document_list", "args": {}},
    {"tool": "document_create", "args": {"label": "tc20_label"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": BUILD}},
    {"tool": "query_tree_summary", "args": {"doc": "$DOC"}},
    {"tool": "view_fit_viewport", "args": {"doc": "$DOC"}},
    shot("tc-20-02-before.png"),
    {"tool": "feature_set_parameters", "args": {"doc": "$DOC", "feature": "Block", "parameters": {"Label": "Profile"}}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": "result = doc.Block.Label"}},
    {"tool": "feature_set_parameters", "args": {"doc": "$DOC", "feature": "Profile", "parameters": {"Placement": {"base": {"z": z}}}}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": "result = doc.Profile.Placement.Base.z"}},
    {"tool": "feature_set_parameters", "args": {"doc": "$DOC", "feature": "Profile", "parameters": {"AttachmentOffset": {"base": {"z": z}}}}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": "result = doc.Profile.Placement.Base.z"}},
    shot("tc-20-02-after.png"),
    {"tool": "query_tree_summary", "args": {"doc": "$DOC"}},
    {"tool": "document_undo", "args": {"doc": "$DOC"}},
    {"tool": "document_undo", "args": {"doc": "$DOC"}},
    {"tool": "script_exec", "args": {"doc": "$DOC", "code": "result = [doc.Block.Label, doc.Profile.Placement.Base.z]"}},
]
for name, calls in {"calls-tc20-01.json": tc01, "calls-tc20-02.json": tc02}.items():
    json.dump(calls, open(name, "w", encoding="utf-8"), indent=1)
