| Case | Spec | Build | verify_shape | Checks passed | detected_by check (measured vs expected, code) | Outcome | Capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| control-faithful-mounting-plate | 001-mounting-plate | control | OK | 11/11 |  | **PASS_CLEAN** | `g3-control-faithful-mounting-plate-control.png` |
| blind-hole-made-through | 007-jig-block-blind-bore | planted | SPEC_FAILED | 6/8 | `hole_through`: true vs false, code `None` | **DETECTED** | `g3-blind-hole-made-through-planted.png` |
| blind-hole-made-through | 007-jig-block-blind-bore | reverted | OK | 8/8 |  | **PASS_CLEAN** | `g3-blind-hole-made-through-reverted.png` |
| control-equivalent-step-order | 012-clamp-pad-slot | control | OK | 5/5 |  | **PASS_CLEAN** | `g3-control-equivalent-step-order-control.png` |
| control-named-datum-honoured | 019-offset-pivot-plate | control | OK | 9/9 |  | **PASS_CLEAN** | `g3-control-named-datum-honoured-control.png` |
| control-tolerance-edge-hole | 001-mounting-plate | control | OK | 11/11 |  | **PASS_CLEAN** | `g3-control-tolerance-edge-hole-control.png` |
| datum-origin-swapped | 019-offset-pivot-plate | planted | SPEC_FAILED | 6/9 | `hole_position`: [50.0, 45.0] vs [20.0, 15.0], code `None` | **DETECTED** | `g3-datum-origin-swapped-planted.png` |
| datum-origin-swapped | 019-offset-pivot-plate | reverted | OK | 9/9 |  | **PASS_CLEAN** | `g3-datum-origin-swapped-reverted.png` |
| extra-unrequested-pocket | 010-cover-panel-window | planted | SPEC_FAILED | 3/6 | `expect_volume`: 22800.000000000004 vs 23400.0, code `None` | **DETECTED** | `g3-extra-unrequested-pocket-planted.png` |
| extra-unrequested-pocket | 010-cover-panel-window | reverted | OK | 6/6 |  | **PASS_CLEAN** | `g3-extra-unrequested-pocket-reverted.png` |
| hole-on-wrong-face | 007-jig-block-blind-bore | planted | INVALID_INPUT | 6/8 | `angle_between`: 89.99999999999999 vs 0.0, code `None` | **DETECTED** | `g3-hole-on-wrong-face-planted.png` |
| hole-on-wrong-face | 007-jig-block-blind-bore | reverted | OK | 8/8 |  | **PASS_CLEAN** | `g3-hole-on-wrong-face-reverted.png` |
| mirrored-hole-pattern | 011-lever-arm | planted | SPEC_FAILED | 6/8 | `hole_position`: [60.0, 0.0] vs [0.0, 0.0], code `None` | **DETECTED** | `g3-mirrored-hole-pattern-planted.png` |
| mirrored-hole-pattern | 011-lever-arm | reverted | OK | 8/8 |  | **PASS_CLEAN** | `g3-mirrored-hole-pattern-reverted.png` |
| missing-bolt-holes | 008-flange-gasket | planted | INVALID_INPUT | 5/10 | `count_cylindrical_holes`: 1 vs 7, code `None` | **DETECTED** | `g3-missing-bolt-holes-planted.png` |
| missing-bolt-holes | 008-flange-gasket | reverted | OK | 10/10 |  | **PASS_CLEAN** | `g3-missing-bolt-holes-reverted.png` |
| pocket-before-pad | 012-clamp-pad-slot | planted | SPEC_FAILED | 3/5 | `expect_volume`: 31999.999999999993 vs 24000.0, code `None` | **DETECTED** | `g3-pocket-before-pad-planted.png` |
| pocket-before-pad | 012-clamp-pad-slot | reverted | OK | 5/5 |  | **PASS_CLEAN** | `g3-pocket-before-pad-reverted.png` |
| radius-for-diameter | 003-shaft-collar | planted | INVALID_INPUT | 4/7 | `hole_diameter`: 32.0 vs 16.0, code `None` | **DETECTED** | `g3-radius-for-diameter-planted.png` |
| radius-for-diameter | 003-shaft-collar | reverted | OK | 7/7 |  | **PASS_CLEAN** | `g3-radius-for-diameter-reverted.png` |
| wrong-hole-diameter | 001-mounting-plate | planted | INVALID_INPUT | 5/11 | `hole_diameter`: [8.0, 8.0, 8.0, 8.0] vs 5.5, code `None` | **DETECTED** | `g3-wrong-hole-diameter-planted.png` |
| wrong-hole-diameter | 001-mounting-plate | reverted | OK | 11/11 |  | **PASS_CLEAN** | `g3-wrong-hole-diameter-reverted.png` |
| wrong-plate-thickness | 001-mounting-plate | planted | SPEC_FAILED | 9/11 | `expect_bbox`: [80.0, 60.0, 8.0] vs [80.0, 60.0, 6.0], code `None` | **DETECTED** | `g3-wrong-plate-thickness-planted.png` |
| wrong-plate-thickness | 001-mounting-plate | reverted | OK | 11/11 |  | **PASS_CLEAN** | `g3-wrong-plate-thickness-reverted.png` |
