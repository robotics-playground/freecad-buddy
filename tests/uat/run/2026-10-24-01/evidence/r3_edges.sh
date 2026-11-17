# r3_edges.sh <doc>: select the four vertical edges of the plate (iso view, three foreground clicks, camera rotated 180 degrees about Z, fourth click).
cd "$(dirname "$0")"; source r3_env.sh; D=$1
clk(){ echo "{\"pid\":$PID,\"window_id\":$WID,\"x\":$1,\"y\":$2,\"delivery_mode\":\"foreground\"$3}" | cua-driver call click >/dev/null; sleep 0.8; }
uv run python r3_mcp.py tc-12-01 script_exec "{\"doc\":\"$D\",\"code\":\"import FreeCADGui\nFreeCADGui.Selection.clearSelection()\nFreeCADGui.runCommand('Std_ViewIsometric')\nFreeCADGui.ActiveDocument.ActiveView.fitAll()\nresult = 'iso'\"}" camera-setup > /dev/null 2>&1
uv run python r3_gui.py click "Fit All" Button > /dev/null; sleep 2
clk 559 456 ""; clk 968 691 ',"modifier":["ctrl"]'; clk 1242 534 ',"modifier":["ctrl"]'
uv run python r3_mcp.py tc-12-01 script_exec "{\"doc\":\"$D\",\"code\":\"import FreeCAD, FreeCADGui\nv = FreeCADGui.ActiveDocument.ActiveView\nv.setCameraOrientation(FreeCAD.Rotation(FreeCAD.Vector(0,0,1),180) * v.getCameraOrientation())\nv.fitAll()\nresult = 'rot'\"}" camera-rot > /dev/null 2>&1
sleep 1
clk 968 691 ',"modifier":["ctrl"]'
uv run python r3_mcp.py tc-12-01 script_exec "{\"doc\":\"$D\",\"code\":\"import FreeCADGui\nresult = [s.SubElementNames for s in FreeCADGui.Selection.getSelectionEx()]\"}" sel-check 2>&1 | grep -o 'value_repr": "[^}]*' | head -1
