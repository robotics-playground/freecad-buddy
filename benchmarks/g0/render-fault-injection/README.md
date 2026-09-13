# G0 render fault-injection suite

Planted-defect + clean-control PNGs that bind `verify_render_tone`, the AD-34 render oracle. A
render is a validator like any other: a planted all-white render must be caught mechanically, not
only by a human looking at the image.

## What the oracle measures

`usecases/render_tone.py` decodes the PNG (stdlib only — no Qt, no FreeCAD) and samples the
**non-background pixels inside the middle 80 % of each axis**. The framing leaves a ~20 % margin,
so a mean over the whole image is dominated by background whatever the face does.

A render passes only when **all four** conditions hold:

| Condition | Bar | Catches |
| --- | --- | --- |
| Interior coverage | ≥ 12 % of the interior | face rendered at the background tone |
| Interior samples | ≥ 500 | a render too small to judge |
| Difference from background | ≥ 24/255 on some channel | a face that blends into the background |
| Every channel in band | within `[20, 235]` | a face saturated to black or to white |

**The check is two-sided, and one-sidedness is how the defect shipped.** The previous rig's stated
purpose was "so no face renders black": it closed the black end and opened the white end. A test
asserting only "not black" passes the white-face defect, and one asserting only "not white" would
re-admit the original black-face defect.

**Why coverage, on top of the absolute sample floor.** The white-face defect is not caught by any
absolute condition. Measured on the real `front` render: tone `rgb(99.7, 99.7, 99.7)` (inside the
band), difference from background 155/255 (well over the bar), 1,276 samples (over the 500 floor)
— it passes everything, because the only pixels sampled are the dark anti-aliased outline, and an
outline is dark and separable. The sample count also scales with render size, so no fixed floor
separates "outline only" from "real face" across sizes. Coverage is size-independent: the defect
covers 3.5 % of the interior against 24.3 % for the thinnest correct render (`top`, the box seen
end-on) and 35-69 % for the rest. The 12 % floor sits near the midpoint of that gap.

## Detection rule — cases encode the REFERENCE, not the defect

A planted `case.yaml` asserts nothing case-specific: the oracle's bars are the reference, and each
planted PNG violates one of them. A case is never tuned to the defective value.

## Cases

| id | expectation | defect | caught by |
| --- | --- | --- | --- |
| captured-white-face-front | DETECT | **the real defect**, captured from the renderer with the pre-fix on-axis headlight | coverage |
| all-white-render | DETECT | face at the background tone, only the anti-aliased outline remains | coverage |
| near-white-face | DETECT | face at `rgb(246,248,250)` | ceiling + difference |
| low-contrast-face | DETECT | face at `rgb(243,244,245)` | ceiling + difference |
| all-black-face | DETECT | face at `rgb(6,6,8)` | floor |
| near-black-face | DETECT | face at `rgb(14,15,17)` | floor |
| clean-control-{iso,front,top,bottom,left,right,back,custom} | PASS_CLEAN | none — real renders of the golden 10×20×30 box | — |

`captured-white-face-front` is the case that matters most. A suite of only synthesized defects
proves the oracle rejects images the builder script draws; that one proves it rejects what the
broken renderer actually emitted. It is committed, never regenerated.

The clean controls are **captured renders**, not synthesized images — the false-alarm rate is the
rate at which the oracle rejects output the renderer really produces, so a hand-made "clean" PNG
would measure nothing.

## Running

```bash
# score the suite and update _registry/validators.yaml (external env — no FreeCAD needed)
uv run python benchmarks/g0/render-fault-injection/score_render_tone.py

# rebuild the synthesized planted fixtures (never touches the captured case)
uv run python benchmarks/g0/render-fault-injection/build_render_fault_fixtures.py

# re-capture the clean controls after any lighting change (needs the render stack)
FreeCADCmd benchmarks/g0/render-fault-injection/capture_render_controls.py
```

Last run: sensitivity 1.000, false alarm 0.000 over 6 planted + 8 controls.
