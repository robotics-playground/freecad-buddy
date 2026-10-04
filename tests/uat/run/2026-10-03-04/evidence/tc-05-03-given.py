from tc05lib import *


async def body(m, log):
    doc = await body_sketch(m, "TC0503")
    log.note(f"fully constrained 20x20 Sketch built via MCP in TC0503 doc={doc}; next: delete its DistanceX, DistanceY and root Coincident in FreeCAD's Python console (fixture only, MCP cannot leave dof>0)")
    log.write({"doc": doc})


go("tc-05-03-given", body)
