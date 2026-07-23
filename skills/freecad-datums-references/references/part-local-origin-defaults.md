# Part-local origin defaults

Load this when choosing a part's origin and orientation, or when picking the frame
to re-anchor a broken reference to. The origin you choose is the frame every later
measurement and reference lives in, so choose it from the part's function, not from
convenience.

## Default origins by part type

| Part type | Origin | Orientation |
| --- | --- | --- |
| Symmetric standalone part | body center | main symmetry axes on X/Y/Z |
| Plate | footprint center | thickness along +Z |
| Enclosure | footprint center | base/lid mating surfaces controlled by Z parameters |
| Shaft / knob / axisymmetric part | on the rotational axis | axis along Z |
| Mating adapter plate | primary mounting datum, or the bolt-pattern center | mounting face on XY |

When nothing better applies, use the center of the main part.

## Why the functional datum

Model on the mating interface, mounting plane, or symmetry axis because:

- a hole pattern placed symmetrically about a centered origin stays symmetric under
  a size edit, whereas one dimensioned from an edge drifts;
- a mating face on a known plane makes an alignment check a single measurement, not
  a frame conversion;
- a downstream assembly reuses the part's origin as its attach frame, so a
  functional origin is one less transform to get wrong.

## Anchoring a reference so it survives recompute

A reference is durable when it points at something that does not move or re-label
when the tree recomputes. In order of preference:

1. **A datum plane, axis, or point** created early, anchored to the base solid or
   the origin — a named object the recompute does not renumber.
2. **A local coordinate system** for a sub-group that needs its own frame.
3. **A geometric-query selector** (surface type + axis/radius/position) resolved at
   call time — stable because it describes the geometry, not an index.
4. **A mapped-name selector** — the topological-naming mapped name, which the bridge
   tracks across recompute.

Never persist a bare indexed name (`Face6`, `Edge3`): the index is valid only until
the next recompute reshuffles it. If a caller supplies one, resolve it to a mapped
name or geometric query immediately and store that.

## Frames are distinct

The part's origin, the frame a feature attaches at, and the frame a value is
measured in are three separate things that often — but not always — coincide. State
which frame every placement value is expressed in. A coordinate with no stated frame
is the most common silent placement error: the numbers look right and the geometry
lands somewhere else.

## Repairing a broken reference

When `verify_references` flags a re-pointed or dropped reference, do not re-pick
another bare index — it will break again on the next recompute. Re-resolve against
the most durable anchor available from the list above (datum first), then recompute
and re-audit. If `verify_references` reports `UNSUPPORTED`, the audit could not run
(no element map) — treat the reference as unverified, never as clean.
