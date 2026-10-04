from tc08lib import *  # noqa
from tc04lib import point_profile

DOC = "fcb-doc:3C8p0yHytbnEukTTjZeiTA"


async def body(m, log):
    log.note("3rd sample feature_set_parameters Pad Length 35 was AUTHORIZED but returned RECOMPUTE_ERROR (Fillet edge link broke, rolled back; preview predicted it). Extra sample: sketch_add_geometry on Sketch2.")
    g, c = point_profile(5, 5)
    p, a = await apply(m, DOC, "sketch_add_geometry", {"sketch": "Sketch2", "geometry": g, "constraints": c})
    log.check("extra sample sketch_add_geometry (Sketch2, fully constrained point): preview + token -> OK",
              p.get("status") == "OK" and a.get("status") == "OK", {"preview": p.get("status"), "apply": short(a)})


go("tc-08-17b", body)
