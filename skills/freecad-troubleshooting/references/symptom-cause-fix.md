# Symptom → cause → fix catalog

Load this when a failure doesn't match an obvious class, or you need the full list
of likely causes and the smallest fix for each. Work the loop for every entry:
read the failing output, classify it against a row below, make the smallest
responsible change, rerun the failed operation, rerun dependent checks, report
residual risk.

## Recompute / execution error

Likely causes: an upstream object in error (dependents cascade); a missing or
dropped reference; an invalid sketch feeding a feature; a boolean that produced a
null shape.

Fix: find the *first* object in error (not the last to report), repair it, then
recompute so dependents re-evaluate. Never start from the last error in the
cascade.

## Invalid or missing geometry

Likely causes: an open sketch profile (no face); a subtractive profile outside the
target; zero thickness; a failed boolean; construction geometry used as real
geometry.

Fix: close profiles meant to become faces; confirm dimensions are positive; make
through-cuts pass fully through (overshoot or a through-all/up-to mode); simplify
the failing feature and rebuild incrementally.

## Fillet or chamfer failure

Likely causes: radius/size exceeds the local geometry; the selection includes tiny
or unintended edges; a prior boolean created complex edge topology; edges were
re-labelled or dropped by a later feature.

Fix, in order: reduce the radius/size below the local dimension; narrow the edge
selection; apply the dress-up later in the chain; split the edge group by feature
intent. A dress-up (fillet/chamfer) silently drops edges that lose two adjacent
faces — compare the edge count, not just the error state.

## Wrong scale or bounding box

Likely causes: a units mismatch; a diameter entered as a radius (or vice versa);
wrong extrusion direction or amount; the part not centred as assumed; an imported
file in unexpected units.

Fix: check parameter values and units first; inspect the tree and mass properties;
measure the critical extents with `query_mass_properties`/`query_placement`;
correct the source dimension or the import handling.

## Missing feature

Likely causes: wrong add/subtract mode; the feature profile not inside the target;
a blind cut too shallow; a selector that changed after a prior operation.

Fix: confirm the feature mode; increase the cut length for through-cuts; inspect
the tree and object properties; regenerate and measure the feature-specific
result.

## Broken or fragile reference (TNP)

Likely causes: an arbitrary index selection; topology changed after a fillet or
boolean; similar faces/edges are indistinguishable by index; an external reference
was dropped and marked with `?`.

Fix: re-select by axis, plane, position, normal, or an inspected mapped-name/
geometric-query reference; use `query_tree_summary` + `query_object` to rediscover
stable references; add a construction datum or simplify the operation so the
reference has something durable to attach to. A `verify_references` result of
`UNSUPPORTED` means the audit could not run (no element map) — treat it as
not-clean, never as a pass.

## Positioning or datum mismatch

Likely causes: a wrong part-local origin or datum; a sign error in symmetric
placement; a placement not recomputed after a parameter change; a reference defined
in world coordinates when a part-local datum was intended.

Fix: inspect placement with `query_placement`; verify the datum and the intended
frame; apply the smallest source correction; regenerate and rerun the failed check.

## Export failure

Likely causes: a null or invalid shape reaching the exporter; an unclosed solid;
the wrong object set selected; an ambient unit assumed instead of pinned.

Fix: verify the shape is valid and closed first (`verify_shape`); pin the export
unit per call; then re-run the export and its paired `verify_export_*` re-import
check — an export is done only when the re-import matches.

## Reporting an unrepairable failure

State: what failed; what was tried; which artifact (if any) is still usable; which
validation claims cannot be made; and the next source-level correction to attempt.
An honest failure report is a result; a silent one is a hidden defect.
