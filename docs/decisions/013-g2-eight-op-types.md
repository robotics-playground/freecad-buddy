# 013 — G2.1 Command Benchmark: The Eight Op Types

## Decision

The G2.1 command benchmark is partitioned into these **eight op types**, five commands each,
for the specified 40:

| # | Op type | Covers | Shipped tools exercised |
| --- | --- | --- | --- |
| 1 | `sketch` | create a sketch, add geometry, add constraints | `sketch_create`, `sketch_add_geometry`, `sketch_add_constraint`, `sketch_set_datum` |
| 2 | `pad` | extrude a profile into material | `feature_pad` |
| 3 | `pocket` | extrude a profile as a cut | `feature_pocket` |
| 4 | `revolve` | revolve a profile about an axis | `feature_revolve` |
| 5 | `hole` | parametric hole features | `feature_hole` |
| 6 | `dressup` | fillet and chamfer | `feature_fillet`, `feature_chamfer` |
| 7 | `pattern` | linear/polar/rectangular repetition | `feature_pattern` |
| 8 | `mirror` | mirrored features | `feature_mirror` |

Each case declares its type in `op_type`, a required field of the G2 case schema. The gate
runner asserts all eight are present and that the 40 cases distribute 5 per type.

## Rationale

`phase-gates.md:62`, `epics.md:526`, `docs/intent.md:238`, and `SPEC.md:28` all assert
"40 commands × 8 op types", but **no document enumerates the eight**. The count appears four
times; the list appears zero times. Story 3.1 cannot author 40 cases without resolving it.

Two candidate lists exist in the repo and neither is 8:

- `mcp-tools-design.md:171-180` ships **10** `feature_*` tools (`pad`, `pocket`, `revolve`,
  `hole`, `fillet`, `chamfer`, `pattern`, `mirror`, `datum`, `set_parameters`) and separately
  **8** `sketch_*` tools. The sketch count coinciding with 8 is not an equivalence any document
  asserts.
- `docs/intent.md:235` names the Phase-2 surface as "create sketch, add geometry + constraints,
  pad, pocket, fillet, chamfer, hole, mirror, pattern" — 8 or 9 depending on whether the two
  sketch clauses are one type, and it predates the architecture (it omits `revolve`, which the
  shipped catalog has).

This decision reconciles the two by treating the taxonomy as **op types, not tools**: a type is a
kind of modeling intent a command expresses, which is what a natural-language command benchmark
grades. Sketch creation/geometry/constraints collapse to one type because a single NL command
("sketch a 40×20 rectangle on the XY plane and fully constrain it") exercises all three, and
G2.5 already grades sketch constraint state separately. `fillet` and `chamfer` collapse to
`dressup` because they are the same `FeatureDressUp` code path — the path carrying the
silent-drop trap (`verification-design.md:164`) — so grading them as one type keeps the
benchmark aligned with the failure mode. `revolve` is restored from the shipped catalog because
dropping it would leave a shipped tool ungraded.

`feature_datum` and `feature_set_parameters` are deliberately excluded: a datum is a reference
construct rather than a geometric result, and `set_parameters` re-parameterises an existing
feature rather than expressing a new modeling intent. Both are still exercised incidentally as
setup within other types' cases, and both remain covered by the AD-5 mutation protocol.

## Consequences

- The eight names are a **contract**: `op_type` values are validated against this closed set, so
  a typo fails the case loader rather than silently creating a ninth type.
- The 5-per-type split is even by construction, so G2.1's ≥85 % first-attempt pass rate cannot be
  reached by over-weighting easy types.
- If a later phase adds a genuinely new mutation kind, this note is amended and the benchmark
  re-partitioned rather than the count being quietly grown.
- `phase-gates.md`, `epics.md`, `intent.md`, and `SPEC.md` continue to say "8 op types" without
  enumerating them; this note is the enumeration they refer to.

## Alternatives considered

**Split `fillet` and `chamfer`, drop `revolve`.** Keeps the two dress-up ops distinct, which has
some appeal since they differ in parameters. Rejected because it leaves a shipped tool
(`feature_revolve`) entirely ungraded by the command benchmark, and because the TNP failure mode
that matters is shared by both dress-up ops rather than specific to either.

**One type per `feature_*` tool, taking 8 of 10.** Closest to the implemented catalog, but it
excludes sketch commands from G2.1 even though sketches are the substrate every other feature
builds on, and it forces an arbitrary choice of which two `feature_*` tools to drop.
