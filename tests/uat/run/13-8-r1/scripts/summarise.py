import json
import math
import sys

log = json.load(open(sys.argv[1]))
print("fingerprint before", log["fingerprint_before"])
print("fingerprint after ", log["fingerprint_after"], "EQUAL" if log["fingerprint_before"] == log["fingerprint_after"] else "DIFFERENT")


def close(a, b, tol=1e-6):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol * max(1.0, abs(b))


for case in log["cases"]:
    sc, ref, an = case["sc"], case["reference"], case["analytic"]
    area = None if sc.get("area") is None else sc["area"]["value"]
    length = sc["length"]["value"]
    ref_area = ref["area"] if isinstance(ref["area"], float) else None
    if sc["wires"] and area is None:
        ref_cmp = "area null"
    else:
        ref_cmp = "area=" + str(close(area, ref_area if sc["wires"] else 0.0))
    ok_ref = sc["wires"] == ref["wires"] and sc["closed_wires"] == ref["closed"] and close(length, ref["length"])
    an_ok = "-"
    if an:
        an_ok = (sc["wires"] == an[0] and sc["closed_wires"] == an[1] and close(length, an[3], 1e-6)
                 and (close(area, an[2], 1e-6) if an[2] is not None else area is None))
    bb = sc.get("bbox")
    bbs = None if bb is None else [round(bb[k]["value"], 6) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")]
    print(f"{case['label']:38} {case['status']} wires={sc['wires']} closed={sc['closed_wires']} "
          f"len={length:.6f} area={area} | ref wires={ref['wires']} len={ref['length']:.6f} area={ref['area']} "
          f"slice={ref['slice_wires']} | refmatch={ok_ref} {ref_cmp} analytic={an_ok} bbox={bbs} t={case['elapsed_s']}s")
for label, item in log["extra"].items():
    sc = item.get("sc") or {}
    poly = sc.get("polylines")
    extra = ""
    if poly is not None:
        pts = [p for line in poly for p in line]
        radial = [math.hypot(p[0], p[1]) for p in pts]
        extra = (f" polylines={len(poly)} points={len(pts)} truncated={sc.get('truncated')} "
                 f"r=[{min(radial):.5f},{max(radial):.5f}] z=[{min(p[2] for p in pts)},{max(p[2] for p in pts)}]")
    print(f"{label:38} {item['status']} {item.get('detail')}{extra}")
