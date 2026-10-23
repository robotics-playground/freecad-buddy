"""Prove the scripted pixel check detects each planted capture fault (AD-13).

    uv run python tests/uat/runner/pixel_faults.py

Builds synthetic window captures in memory and runs ``run.check_pixel`` unchanged on each, with
one probe snapshot: a 3D view rectangle and one object's projected ``screen_center``. A fault is
detected when the check reports its named finding. A control is a false alarm when the check
reports any finding. Exit 0 only when every fault is detected and no control is flagged.

The set covers what the pixel check measures: the view is empty, the part is clipped at a view
edge, the part moved off its sample point, the part is too small. It does not see dialogs, a
wrong shape or a wrong colour (``tests/uat/test-plan.md`` §9).
"""

import sys

import png
import run

WINDOW = {"x": 0, "y": 0, "width": 200, "height": 150}
VIEW_RECT = [20, 10, 160, 120]
SAMPLE = "box.Box"
SCREEN_CENTER = [100, 70]
CONFIG = {"samples": [SAMPLE], "extent": {"min_fraction": 0.5, "inside": True}}
SNAPSHOT = {
    "documents": [{"name": "box", "objects": [{"name": "Box", "screen_center": SCREEN_CENTER}]}],
    "view": {"clipped": False, "rect": VIEW_RECT},
}
# FreeCAD 1.1.4 paints a flat 247 background; the gradient control covers the vertical gradient
# of other settings.
BACKGROUND = 247
MODEL = (110, 110, 120)
# Part rectangles ``((x0, y0), (x1, y1))`` in capture pixels; the view spans x 20-180, y 10-130.
FRAMED = ((50, 35), (150, 105))

CASES = [
    {"id": "empty-view", "kind": "fault", "field": f"samples.{SAMPLE}", "part": None},
    {
        "id": "clipped-at-edge",
        "kind": "fault",
        "field": "extent.touches_edge",
        "part": ((60, 35), (180, 105)),
    },
    {
        "id": "moved-off-sample",
        "kind": "fault",
        "field": f"samples.{SAMPLE}",
        "part": ((115, 80), (175, 125)),
    },
    {"id": "too-small", "kind": "fault", "field": "extent.fraction", "part": ((88, 60), (112, 80))},
    {"id": "flat-background", "kind": "control", "part": FRAMED},
    {"id": "gradient-background", "kind": "control", "part": FRAMED, "gradient": True},
]


def synthetic_capture(part, gradient=False):
    """A capture of ``WINDOW`` size: background, plus the part rectangle when there is one."""
    rows = []
    for y in range(WINDOW["height"]):
        shade = 190 + y * 57 // WINDOW["height"] if gradient else BACKGROUND
        row = [(shade, shade, shade)] * WINDOW["width"]
        if part is not None:
            (x0, y0), (x1, y1) = part
            if y0 <= y < y1:
                row[x0:x1] = [MODEL] * (x1 - x0)
        rows.append(bytes(value for pixel in row for value in pixel))
    return png.Image(WINDOW["width"], WINDOW["height"], 3, rows)


def judge(case):
    """Return ``(flagged, detail)``: whether the check reported a bad capture, and why."""
    image = synthetic_capture(case["part"], case.get("gradient", False))
    _, findings = run.check_pixel(CONFIG, SNAPSHOT, image, WINDOW)
    if case["kind"] == "fault":
        named = [f for f in findings if f["field"] == case["field"]]
        return bool(named), "; ".join(f["reason"] for f in named or findings) or "no finding"
    return bool(findings), "; ".join(f["reason"] for f in findings) or "no finding"


def main():
    detected = false_alarms = 0
    faults = [case for case in CASES if case["kind"] == "fault"]
    controls = [case for case in CASES if case["kind"] == "control"]
    for case in CASES:
        flagged, detail = judge(case)
        if case["kind"] == "fault":
            detected += flagged
            verdict = "DETECTED" if flagged else "MISSED"
        else:
            false_alarms += flagged
            verdict = "FALSE ALARM" if flagged else "CLEAN"
        print(f"{verdict:<11} {case['id']}: {detail}")
    print(f"detected {detected}/{len(faults)}")
    print(f"false alarms {false_alarms}/{len(controls)}")
    return 0 if detected == len(faults) and false_alarms == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
