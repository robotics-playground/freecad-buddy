---
title: 'Story 13-4: Skill routing to existing typed tools and the full gap list'
type: 'chore'
created: '2026-11-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Skills route bounding box, volume and validity reads to `script_exec`, name only two gaps, and `part-sourcing` points to an import path that does not exist.

**Approach:** Route those reads to `query_mass_properties` and `verify_shape`. Hold the current gap list as a table in `freecad-scripting-idioms/references/gap-list.md`. State STEP import as a gap in `part-sourcing`. Contract: `tool-contracts.md` T-1 step one and T-14; quality bar `quality-bar-13-4.md`.

</frozen-after-approval>

## Implementation Notes

- New `skills/freecad-scripting-idioms/references/gap-list.md`: covered table (7 rows), 18 gap rows, traced outline route.
- `freecad-scripting-idioms/SKILL.md`: the two-gap sentence now points to the gap list and adds the rule to name the missing typed tool. Line 57 unchanged (decision 5).
- `code-cad-conversion/references/verification-kit.md`: part validity, solid count and volume go through `verify_shape` (`is_valid_solid`, `expect_solid_count`, `expect_volume`); scripts keep overlap, the reference volume, and VarSet set and restore. The limit test is split into case script, typed checks, restore script. `SKILL.md` one sentence follows.
- `part-sourcing/SKILL.md`: import path removed; import is `script_exec` in a transaction and listed as a gap.
- `verification-thinking`: no edit; it already routes to typed tools and has 6 words of headroom.
- Body words: scripting-idioms 1292 to 1310, code-cad-conversion 1416 to 1424, part-sourcing 845 to 862, verification-thinking 1494 unchanged.

## Review Triage Log

Lenses: Blind Hunter adde9f60f12d90587 (claude-opus-5-5, high); Edge Case Hunter a4a5f8f3b1cb416a1 (claude-opus-5-5, high); Verification Gap Finder a03bf1cac40ec12c5 (claude-sonnet-5-5, medium, no gaps filed).

- Limit-test cases leave values set between cases (Blind, Edge): high, real. Patched: restore script runs after every case, also on a failed check, before `document_save`.
- Case script restores only to the previous case value; the restore literal came from "first old" (Edge): medium, real. Patched with the per-case restore above; `old` is now always the default.
- `code-cad-conversion/SKILL.md` kept "two cases per call" and "0.000 %" (Blind): medium, real. Patched: one case per call, "below 0.0001 %".
- Gap list rule "no row means typed tool covers it" unsafe; groove, PartDesign primitives and sketch constraint types missing (Blind): medium, real (`tool_catalog.py` has no groove tool, constraint enum has no `Lock`). Patched: rule reworded, three rows added.
- Delete row for a Body feature leaves an orphan (Blind): medium, real (`Body.cpp:338-374` removes from `Group` only). Patched: both calls in order.
- VarSet row and covered row overlap (Blind, Edge): low, real. Patched: covered row says "of a feature"; VarSet row says `feature_set_parameters` targets features. Whether it accepts a VarSet is unverified; the row claims only that it targets features.
- Covered table omits hole, distance, angle checks and `query_placement`, `query_sketch_info`, `query_dependencies`, `verify_recompute` (Blind): medium, real. Patched; the kit's `invalid` list scan now uses `verify_recompute`.
- STEP import gives no usable route, no created Names, no abort (Blind, Edge): medium, real. Patched: import script in `gap-list.md`, `part-sourcing` points to it.
- `expect_solid_count` fixed at 1 loses "or the source count" (Blind, Edge): medium, real. Patched.
- `ref_vol` rounded to 4 places against `rel` 1e-6 (Edge): low, real on parts under 50 mm3. Patched: unrounded.
- `App::Link` part has no `Shape` for `verify_shape` (Edge): low, real. Patched: note to measure a link in the script with `Part.getShape`.
- `script_exec` absent (Edge, two findings): low, real. Patched: gap list and `part-sourcing` say report as blocked.
- Kit routes to `query_mass_properties` but never calls it (Blind): low. Patched: intro says to read the volume with it.
- `query_mass_properties` gives container coordinates (Edge): low, pre-existing behaviour, not caused by this change. Rejected.
- Quantity repr in restore literal (Edge): low. Rejected; `Params` floats are unitless and JSON floats round-trip.

## Round 2

Verifier D1-D5, red team RT1-RT3 and RT-L1..L3 closed in 0f1d1f6, 14c2e7b. Lenses round 2: blind a5b7b74ceff167b25 (8), edge a46291ebf16e62109 (14), gap abd787c4709a4b5ec (none).

- Constraint gap row deleted instead of fixed (blind, edge): medium, real. Patched: row restored with `InternalAlignment`, `TangentViaPoint`; covered row limited to the enum types.
- `code-cad-conversion/SKILL.md:31` still said "no typed tool writes a VarSet" and "stop" (blind, edge): medium, real. Patched to the shared script-off rule.
- VarSet row scope, string and link values, expression-driven write, units (blind, edge): low, real. Patched in the covered row and one gap row.
- D5 wording (Origin objects, container is the sum of leaves), Import preferences (blind, edge): low, real. Patched.
- Fence parser: tilde fence, nested shorter fence (blind, edge, gap): low, real. Patched in e9cf5bd with two tests; unclosed fence still fails loudly through the missing sections, so no extra check.
- Docstring, link sentence placement, no-shell wording, `document_open` before the check (blind, edge): low, real. Patched.
- Link array or unloaded target (edge): low, rare. Rejected.
