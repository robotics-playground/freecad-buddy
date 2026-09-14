# 018 — The G3.3 Editability Test: Selection, Magnitude, and the Pass Condition

## Decision

G3.3 changes **one** driving parameter per passing part and grades the result on **three
conjunctive legs**. All three are measured; none is assumed.

### 1. Which parameter is selected

The **first parameter in the part's surface order**, where the surface is
`usecases.parameters.read_surface` and the order is the one FreeCAD reports on the holder object.
FreeCAD returns `PropertiesList` sorted by name, so in practice this is the alphabetically first
parameter.

The rule is deliberately not "the parameter most likely to succeed". A selection that read the
part and picked a safe dimension would grade the selector rather than the part, and the ≥90 %
number would mean "≥90 % of parts have at least one parameter that works", which is a different
and much weaker claim than the gate states.

A part exposing **no** parameter fails the criterion as `no_parameter`. It is not skipped: a part
with no driving dimensions is exactly a part that is not editable, and excluding it would let the
rate be raised by shipping blobs.

### 2. What change is applied

**+10 % of the current value**, with a **0.5 mm floor** on the absolute step:

```
delta = max(0.10 * abs(value_before), 0.5)
value_after = value_before + delta
```

Relative, so the change is proportionate on both a 6 mm plate thickness and an 80 mm plate
length. Floored, because 10 % of a small dimension can fall inside the measurement tolerance —
the movement leg below asserts against a ±0.05 mm linear band
(`verification-design.md` §8), and a step that cannot clear that band would report "did not move"
for a parameter that moved exactly as asked.

Increasing, never decreasing. A decrease on a part whose feature is already near a limit
(a pocket as deep as its stock, a hole as wide as its boss) turns a size change into a topology
change, and the test would then be measuring whether the part survives losing a face rather than
whether the parameter drives anything.

### 3. What counts as a pass

`editable = recompute_clean ∧ valid_solid ∧ dimension_moved`

| Leg | Measured by | Fails as |
| --- | --- | --- |
| `recompute_clean` | `verify_recompute` — no object left in an error or still-touched state | `recompute_error` |
| `valid_solid` | `verify_shape` — `Shape.isValid()`, `Shape.check()` clean, the result is a solid with volume > 0 | `invalid_solid` |
| `dimension_moved` | the part's **geometry** changed measurably: its bounding-box extents or its volume differ from before the change by more than the ±0.05 mm / 1 % linear-and-volume bands | `ignored` |

**`dimension_moved` is the leg that matters.** A parameter written into a VarSet that no sketch
or feature references recomputes perfectly cleanly forever, so a test reading only the first two
legs would score it as editable. That is the failure mode the G3.3 number is supposed to exclude,
and the only way to exclude it is to measure the produced geometry.

The movement leg reads the **shape**, never the property. A property reads back whatever was
written to it whether or not any feature consumed the value, so comparing `value_after` against
the property is a tautology that always passes.

A change that makes the solid invalid is recorded **with the failing value** and counted as
non-editable. It is not retried at a smaller step: retrying until something passes measures how
hard the harness tried, not whether the part is editable.

### 4. Where the change happens

On a **copy** of the part document, not on the graded artifact. The editability test is a
destructive probe and the part it probes is a G3.1 result that other criteria still read; a test
that mutated it in place would make G3.2's hygiene reading depend on whether G3.3 had run yet.

The write itself goes through `usecases.parameters.set_value`, which goes through
`run_mutation` like every other mutation — so a value that breaks the part rolls back with proof
rather than leaving a broken document for the next case.

## Rationale

`benchmarks/g3/gate.yaml:65-68` states G3.3 as *"Editability: script one driving-parameter
change per passing part; recompute; verify"* with the pass rule *"≥90 % recompute without
errors"*, and `epic-4-context.md:74` records the gap verbatim: *"The parameter-edit-survives test
has no design. Editability is stated as a gate number with the parameter façade named as its
enabler, but no document specifies how a driving-parameter change is chosen, applied, or judged
clean."*

Left undefined, the number would be whatever the implementation happened to measure. Three
choices in particular decide the value of the number and none of them is stated anywhere else:

- **Reading the gate's own words literally gives a broken test.** "≥90 % recompute without
  errors" is satisfied by a part whose parameters drive nothing at all. The spec's own boundary
  is explicit about this — *"Never count a part as editable because the recompute returned
  without raising. Prove the dimension moved."* — so the criterion text is read as the *shape* of
  the test and the movement leg is added as the thing that makes it mean what the gate says.
- **A per-part parameter choice would grade the chooser.** Fixing the rule to "first in surface
  order" makes the selection independent of the part, so the rate measures parts.
- **A fixed absolute step would be wrong on one end of the size range.** The G3 dev set spans a
  6 mm plate thickness and a 90 mm lever arm; one absolute step cannot be both a real change and
  a safe one.

## Consequences

- G3.3's denominator is the set of parts that **passed G3.1**, every one of them, including parts
  that expose no parameter. Neither the selection rule nor the failure classes can shrink it.
- A part can pass G3.2 (its dimensions are exposed as named parameters) and still fail G3.3 (one
  of them does not drive anything). The two criteria are not redundant: G3.2 reads the surface,
  G3.3 reads what the surface does.
- Because `usecases.parameters.declare` refuses to declare a parameter that drives nothing, the
  `ignored` class should be unreachable for a part this repository's facade built. It is measured
  anyway, because a part can lose the binding later — an expression broken by a topological-naming
  drift leaves the property writable and the geometry unmoved, and that is precisely a part that
  stopped being editable.
- The +10 % / 0.5 mm step and the ±0.05 mm band move together. Changing the tolerance policy in
  `verification-design.md` §8 without revisiting the floor here would let a step disappear into
  the band.

## Alternatives considered

**Change every parameter, not one.** Grades more of the surface, and it is what a user editing a
part actually does. Rejected for this gate because a multi-parameter change that fails names no
single cause — the discrepancy vector would say "the part broke" and not which dimension broke
it — and because the gate criterion says "one driving-parameter change per passing part".

**Select the parameter with the largest value.** Tempting as a proxy for "the most structural
dimension", and it would avoid the small-dimension band problem without the floor. Rejected
because it is a measurement of the part deciding what the part is graded on, which is the same
circularity as letting the actor pick its own test case.

**Judge movement by re-reading the property.** Cheapest possible check, and it is what "the
dimension actually changed" sounds like it means. Rejected because it cannot fail: FreeCAD stores
the written value on the holder regardless of whether anything consumes it, so the leg would pass
on exactly the parts it exists to catch.
