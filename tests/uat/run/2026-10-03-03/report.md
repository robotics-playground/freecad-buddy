# Assertion primitives live run 2026-10-03-03

Story 4.2a (`spec-4-2-assertion-primitives.md`), acceptance criterion 3 and the spec's manual
check. Replays recorded G3 plans through the MCP mutation tools, grades each built part with its
spec's `checks` and `anchor_frame` through `verify_shape`, and compares the result with the real
FreeCAD window.

## Build banner

| Field | Value |
|-------|-------|
| Git | `806955a` on `feat/epic-4-spec-to-part`, Story 4.2a working tree (uncommitted) |
| FreeCAD | 1.1.1 GUI, add-on installed as a junction to `src` |
| Bridge | FreeCAD pid 29400 → proxy pid 7504 → `:8765` |
| Replayer | `evidence/replay_verify.py`: every mutation runs `preview_dry_run`, then the tool with the `preview_id` (AD-5); then `verify_shape` with the spec's `checks` and `anchor_frame` |
| Code under test | every report carries `banner.anchor_frame`, which only the Story 4.2a source writes |

A headless run of the same plans through the in-process MCP server (`evidence/00-headless-replay.jsonl`)
gave the same verdicts.

## Questions and verdicts

| # | Question | Verdict | Evidence |
|---|----------|---------|----------|
| Q1 | Do the 4 clean controls pass every spec check in their declared frame? | PASS | `01-gui-replay.jsonl`: equivalent-step-order 5/5 (`largest_planar_face`), faithful-mounting-plate 11/11 (`XY_Plane`), named-datum-honoured 9/9 (`PlateCornerDatum`), tolerance-edge-hole 11/11 (`XY_Plane`) |
| Q2 | Does `wrong-hole-diameter` fail `hole_diameter`? | PASS | `hole_diameter` measured `[8.0, 8.0, 8.0, 8.0]` against 5.5; `expect_volume` 27593.63 against 28229.80. The four `distance_between` checks select `hole: {diameter: 5.5}`, match nothing and fail `invalid_input.unsupported_assertion`, so the envelope status is `INVALID_INPUT` (empty-match rule, `benchmarks/g3/README.md`) |
| Q3 | Does a faithful `g3-dev-011` part place the 12 mm bore at the origin and the 8 mm hole at +60 X? | PASS | No 011 control exists; the `mirrored-hole-pattern` plan was replayed with its planted step replaced by the spec placement (in the replayer only, no case data edited): OK 8/8, `hole_position` `[0, 0]` and `[60, 0]` |
| Q4 | Does the planted `mirrored-hole-pattern` fail the placement checks? | PASS | `SPEC_FAILED` 6/8; `hole_position` measured `[60, 0]` against `[0, 0]` and `[0, 0]` against `[60, 0]` |
| Q5 | Does the real window agree with the measurements? | PASS | See the visual check below |

## Visual check

Each screenshot is a top view after FreeCAD's own Fit all, read by the agent.

| Screenshot | Observation | Agrees with |
|------------|-------------|-------------|
| `02-faithful-011-top.png` | Large bore near the −X end, small hole toward +X, both on the plate's centre line | `hole_position` `[0, 0]` and `[60, 0]` |
| `03-mirrored-011.png` | The two holes are swapped end for end | Q4 |
| `04-wrong-hole-diameter.png` | Four corner holes, each wider than the 5.5 mm sketch circle drawn inside it | `hole_diameter` 8.0 |
| `05-faithful-plate.png` | Four corner holes at the sketch size | Q1 |
| `06-named-datum.png` | Datum axes on the lower-left plate corner; hole centre 219 px and 164 px from it on a 60 mm plate 659 px wide (10.98 px/mm) = 19.9 mm, 14.9 mm | `hole_position` `[20, 15]` in the `PlateCornerDatum` frame |

Human interventions: **0**. All 7 test documents were closed, then File > Exit; 0 FreeCAD
processes remained and `:8765` was free.

## Findings

- `view_fit_viewport` on the named-datum document returned `OK` with framing ratio 0.95 while the
  live view showed 1.81 mm × 0.86 mm; FreeCAD's own Fit all framed the plate. Already logged in
  `deferred-work.md`.
- The `largest_planar_face` frame resolved to `#78:1;:H453,F` headless and `#78:1;:H1306,F` in
  the GUI for the same plan. The face is the same; the mapped name's tag part differs. Logged in
  `deferred-work.md` for Story 4.2b.
