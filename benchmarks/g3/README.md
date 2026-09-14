# G3 — Phase 3 Designer benchmark (entry gate G3.E)

Landed by Story 4.1 **before any designer code exists** (AD-19): the machinery is born graded, so
Phase-3 code is measured by assertions authored independently of it.

```
g3/
  gate.yaml            declarative mirror of the phase-gates.md G3.1-G3.7 criteria table
  judge.py             the visual-judge seam — verdict schema + fail-closed stub (story 4.4 replaces it)
  dev/                 20 written specs with compiled assertions and declared anchor frames
  heldout/             7 held-out specs — SEALED before their first commit (DW-99)
  fault-injection/     validates the validators; never counts toward the G3.1 pass rate
    corrupted-plan/      10 planted corrupted plans + 4 discriminating clean controls
    visual-judge/        5 planted visually-wrong parts + 3 discriminating clean controls
    assertions/          4 planted assertion faults + 3 discriminating clean controls
    score_g3_validators.py
```

## The 20 specs and their provenance

Every spec derives from a documented real part — a stock fastener, a catalogue bearing component,
a standards-dimensioned section, or a named workshop/machine part. Each carries a manifest under
`benchmarks/_registry/provenance/g3-dev-*.yaml` declaring `source.kind: hand-authored` and a
`real_world_basis` naming the part. **No DeepCAD, ABC, Text2CAD or Fusion 360 Gallery lineage is
shipped**, and no spec was reverse-engineered from what the agent already does well.

A spec ships no `.FCStd`. The designer *builds* the part from the written requirement, so there is
no input document to carry: each case declares `fixture: none-spec-to-part` and its manifest
declares `kind: part-spec`, which `scripts/check_provenance.py` resolves against the case file
rather than a geometry file.

The **fault cases carry no manifest**, because they ship no artifact, and they name the spec they
corrupt in `spec_ref`, whose manifest already records the provenance. Each declares its fixture
state explicitly, and two states are legal:

- `driven-by-designer-loop` + a `planted_op` — the fixture IS the plan that op returns, driven
  through `run_designer_loop`, so the deviant part is produced by the production mutation path
  rather than carved into a saved document. 21 of the 29 cases.
- `pending` — still undriveable. The 8 `visual-judge` cases, whose geometry is buildable but whose
  verdict needs a credentialed vision call.

`check_provenance.py` exempts both, and only while the state is explicitly declared — a case
claiming to be driven while naming no `planted_op` is still flagged.

## Assertions are hand-derived, never captured

Every `expect` value is computed analytically from the spec's own stated geometry, and each case
carries its derivation as a comment — for example, on `g3-dev-001-mounting-plate`:

```
# volume = 80*60*6 - 4*pi*2.75^2*6 = 28800 - 570.199 = 28229.801 mm^3
```

Nothing here was read off a verify tool. An assertion captured from an implementation cannot
falsify that implementation (AD-13/AD-19), and the implementation does not exist yet.

## Assertion vocabulary — no extension needed

All 20 specs compile to the **closed `verification-design.md` §7.2 vocabulary**, and the 20 cases
between them exercise **all eleven** primitives:

`is_valid_solid` · `count_cylindrical_holes` · `hole_diameter` · `hole_position` ·
`hole_spacing` · `hole_through` · `distance_between` · `angle_between` · `expect_bbox` ·
`expect_extent` · `expect_volume`

**G3 declares no vocabulary extension.** G2 needed three (`expect_solid_count`,
`expect_sketch_fully_constrained`, `expect_sketch_geometry_count`) because it graded mutations and
sketch state; G3 grades finished parts against written specs, which is what §7.2 was designed for.
A fn outside the eleven appearing in a G3 case is a fork, not a case, and
`tests/external/test_g3_gate.py::test_every_assertion_fn_is_a_closed_vocabulary_primitive` fails
on it.

`benchmarks/harness/assertions.py` implements **all 11** as of story 4.2, alongside the three G2
extensions. `tests/external/test_mutation_contract.py::test_assertions_module_imports_without_
freecad_and_declares_the_closed_vocabulary` pins the set as a literal, so a fifteenth name is a
deliberate edit rather than a side effect.

### The two primitives the specs declare without a selector

`verification-design.md` §7.2 signs `distance_between` and `angle_between` as
`(shape, sel_a, sel_b, expected, tol)`, but **no G3 case declares a selector** — the three cases
that use them (`g3-dev-002`, `g3-dev-015`, `g3-dev-020`) carry only `expect` and `tol`. Story 4.2
reconciled that openly rather than by renaming a case, which is what the epic's story ordering
requires.

The reading: with no selector, each primitive measures the **closed set of values the part
presents** and passes when one of them carries the declared value.

- `distance_between` — the gap between each pair of parallel planar faces (`distToShape`) **and**
  the axis-to-axis distance between each pair of logical holes. Both are needed: `g3-dev-020`'s
  declared 50 mm is a boss-axis spacing, and that part's parallel-face gaps are
  `[10, 12, 22, 30, 36, 80]` — measured, not assumed. A face-only implementation would fail a
  correct part.
- `angle_between` — the unsigned angle between each pair of planar-face normals. Unsigned because
  a normal's sign is an orientation flag: the same two faces would otherwise read 90° or 270°
  depending on which way the kernel wound them, which is not a property of the part.

This reading is total and deterministic, and it never passes a value the part does not carry. It
is **weaker than a selector-bearing assertion**: an L-bracket presents 90° between many face
pairs, so `angle_between: 90` is close to free on any prismatic part. A spec that needs to pin
*which* two entities carry the value needs a geometric selector (radius band, direction, region —
never an index, AD-13), which no case declares yet. Adding one is a case change, not a code
change: the measurers read `expect` and `tol` off the check mapping and would take a selector the
same way.

## Anchor frames

Every case declares its frame from the closed derivation set. The split across the 20:

| `anchor_frame.kind` | Cases | Why the spec needs it |
| --- | --- | --- |
| `base_sketch_plane` | 16 | The part is built from a profile on a named plane; the plane IS the design datum. |
| `largest_planar_face` | 3 | A prismatic block whose spec names "the top face" with no datum. |
| `named_datum` | 1 | An off-centre feature: under a face-centre frame the stated offsets would name a different point, so the spec declares the datum explicitly. |

`g3-dev-019-offset-pivot-plate` exists specifically to make that last row load-bearing — its
`hole_position` of (20, 15) is only meaningful against the named corner datum.

## The corrupted-plan taxonomy

No planning document enumerates what a corrupted plan looks like; Story 4.1 defines it. A **plan**
is the ordered operation list the designer proposes from a spec and the human approves once. A
plan is **corrupt** when executing it faithfully produces a part that violates the spec it came
from. The six classes partition the ways that happens:

| Class | A step... | Cases |
| --- | --- | --- |
| `value` | carries a wrong number (dimension, count, depth, angle) | 4 |
| `topology` | targets the wrong entity (face, plane, datum, sketch) | 2 |
| `omission` | required by the spec is absent from the plan | 1 |
| `insertion` | adds a feature the spec never asked for | 1 |
| `ordering` | is right, but the order produces different geometry | 1 |
| `frame` | is measured from the wrong anchor frame or in the wrong units | 1 |

**Detection must measure the artifact.** A loop that flags a corrupted plan by reading the plan
text would pass this suite while catching nothing a real deviant part does — assertions grade
geometry, never tool success (AD-13). Every corrupted-plan case says so in its own comment.

## Cited validators — every one has a registry row

`gate.yaml`'s `cited_validators` name six validators, and **all six have a row in
`benchmarks/_registry/validators.yaml`**. That is a deliberate invariant, not bookkeeping:
`check_validator_currency` (`benchmarks/harness/verdict.py:126-144`) compares only the stored
`validator_sha` against the working tree — it never asserts the suite exists or contributed any
case. A citation with **no row** reports `not in registry`, a structural failure that would not
resolve when Phase 3 lands, because nothing in 4.5 writes a missing row. A row whose `not_scored`
names the real gap states the truth and is discharged by closing that gap.

| Validator | Cited by | Row | Why it reads as it does |
| --- | --- | --- | --- |
| `g3_assertions` | G3.1, G3.4 | yes | A separate registry name for the same code as `assertions`, because a digest folds in the suite it was measured over — reusing `assertions` would stale a G2 score nothing about G2 changed. |
| `visual_judge` | G3.1, G3.7 | yes | `not_scored`: the suite exists but every case is `fixture: pending`. |
| `corrupted_plan` | G3.4 | yes | See below. |
| `verify_recompute` | G3.2, G3.3 | yes | `not_scored`: **no fault case targets it at all**. The one suiteless validator; the scorer emits its row anyway rather than leaving it absent. |
| `verify_shape` | G3.2 | yes | Pre-existing G2 row. It reads stale in the working tree; that drift predates this story and is not G3's to fix. |
| `verify_sketch` | G3.2 | yes | Pre-existing G2 row, kept on the G2 suite — nothing in G3 re-measures it. |

**Why `corrupted_plan` stays a validator rather than becoming a bare case population.** It is
reasonable to read it as "just the suite", and G3.4 could have cited `g3_assertions` alone with
the corrupted-plan cases as its population. It is kept separate because the two measure different
things and would otherwise share one sensitivity number. `g3_assertions` measures whether a
*geometry measurement* catches a wrong part; `corrupted_plan` measures whether the *loop* notices
that the part it built violates the spec it was given — a decision the designer loop makes
(`usecases/designer_loop.py`, story 4.5), not one the assertion primitives make. Folding them
together would let a strong assertion layer carry a loop that never checks its own output, which
is precisely the "plausible plan, deviant part" threat G3.4 exists to counter. Story 4.5 landed
that file, so its digest is now a real hash over `usecases/designer_loop.py` plus the
corrupted-plan cases rather than the `""` an unwritten source produced.

## Fault suites

Each suite mixes planted defects with clean controls: sensitivity = detected/planted (bar
**≥95 %**), false_alarm = flagged/controls (bar **≤5 %**). 19 planted defects and 10 controls
across the three suites.

The controls are chosen to be *discriminating*, not decorative:

- `g3-fault-plan-control-equivalent-step-order` reorders the same two operations as
  `g3-fault-plan-pocket-before-pad` and is geometry-preserving. A guard that flags any reorder
  fails it; only measuring the produced part separates the two.
- `g3-fault-assert-control-within-band-spacing` sits 80.04 mm apart against the 0.5 mm-error
  defect's 80.5 mm. A tolerance tightened until the defect is caught but this control is too is
  mis-calibrated — which is exactly what this control measures.
- `g3-fault-visual-control-symmetric-part-either-hand` is a part whose spec is symmetric, so the
  mirrored build IS correct. A judge that flags every mirror fails it.
- `g3-fault-assert-control-stepped-bore-one-hole` presents two coaxial cylindrical faces that
  coaxial grouping (§7.3 rule 2) must merge into one logical hole. An implementation that counts
  faces reports 2 and flags a correct part.

Two cases exist specifically to prove the visual leg is not decorative, and say so in
`must_not_be_caught_by: geometry_assertions_pass`:

- `g3-fault-visual-mirrored-part` — every dimension and hole measures correct, so the geometry
  leg passes; only the judge sees the part is handed the wrong way.
- `g3-fault-visual-wrong-dimension-callout` — the *part* is correct and the *drawing* is wrong.
  This is the case that proves the judge reads callouts rather than re-deriving them from view
  geometry, and it is why dimensioned drawings are in the judge's standard input set at all.

## Running it

```sh
uv run python -m benchmarks.runner run G3 --run <run-id>
uv run python -m benchmarks.runner faults G3
```

Every criterion still fails, and each report names why — but the reasons now differ, and the
report says which kind it is. Six criteria report a **missing actor**: the designer loop landed in
story 4.5, yet nothing PLANS from a written spec, so G3.1 has no way to turn the 20 dev specs into
plans and G3.2/G3.3/G3.5 have no produced parts to read. G3.7 needs a credentialed vision call
that decision 017 keeps out of unattended CI. **No G3 pass rate is quoted anywhere**, because none
has been measured.

**G3.4 is collected.** It reports a measurement rather than a missing actor: 8 of the 10 authored
corrupted plans detected, against a bar of ≥9, so it FAILS on a measured shortfall
(`verdict: SPEC_FAILED`). The two undetected cases are not loop misses — they are excluded as
unscorable against their own spec, and the report names both. See DW-122.

### Driving the fault suites

Planting a G3 fault means driving a plan through the designer loop and measuring the part it
built, which needs the geometry. Two steps:

```sh
# 1. drive the cases and measure them, inside FreeCAD
FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd benchmarks/g3/fault-injection/score_g3_infc.py

# 2. read those results into the registry, from the uv env
uv run python -m benchmarks.runner faults G3
```

`score_g3_infc.py` resolves each case's `planted_op` in `planted_plans.py`, drives its plan through
`run_designer_loop`, and reads the verdict from `detect_spec_violation` over the checks the case's
`spec_ref` declares. **Detection measures the produced artifact; the plan is never inspected.** A
scorer that read `corruption_class` off the case would report perfect sensitivity while measuring
nothing.

Measured today: `corrupted_plan` 8/8 detected with 0/4 false alarms, `g3_assertions` 4/4 with 0/3.
Both rows carry their Wilson interval and, where a population was narrowed, the excluded case ids
with the reason. `visual_judge` still records `not_scored` — its geometry is buildable but its
verdict needs an operator run with a credential. A zero meaning "the validator missed every defect"
and a zero meaning "no defect was driveable" are different facts; the registry spells them
differently.

## The visual judge is a seam, not a judge

`judge.py` fixes the verdict shape — `{pass, findings: [{view, observation, severity}]}` — the
fail-closed rule, and the validation that rejects a malformed model verdict. It has no vision
client: every call returns `visual.unavailable` with `pass: False`. Story 4.4 replaces it.

The value 4.1 delivers is the fault cases and the schema, authored before the judge exists, which
is the whole point of an entry gate. The judge's independence is declared in `gate.yaml`'s
`visual_judge:` block with a model id distinct from `actor:` — preflight enforces that separation
the same way the Phase 1 grader's is enforced.

**Two render caps block the ≥2048 px judge floor**, recorded here and changed by neither this
story nor this tree: `src/freecad_buddy/usecases/screenshot.py:34` (`_MAX_DIM = 1920`, enforced by
`_clamp_dim`) and `src/freecad_buddy/hosts/tool_catalog.py:202-203`
(`"width"/"height": {"maximum": 1920}`). `contracts/` holds no third — verified. Raising both is
4.3/4.4 work.

## Headless TechDraw

`docs/decisions/016-headless-techdraw-export.md` records the spike verdict: page export is
registered in the **Gui** module and is unreachable headless, so Story 4.3 must compose a sheet
from view-level SVG. `tests/infc/test_techdraw_probe.py` asserts that boundary executably under
`FreeCADCmd`, so a FreeCAD upgrade that moves it breaks a test rather than silently invalidating
a prose claim.

One measured caveat the note records: **`TechDrawGui`'s importability is process-state dependent**.
In a bare `FreeCADCmd` process the import raises; in a process that has already run the rest of
`tests/infc` it succeeds. The probe therefore runs that check in a fresh subprocess, and the
load-bearing assertion is the order-independent one — the headless `TechDraw` module registers no
`exportPage*` name at all.

## Held-out set

`heldout/` holds the sealed pair (`SEAL.json` + `heldout.tar.enc`) and no readable `case.yaml`.
Only `run G3 --exit` unseals it, key-gated on `FREECAD_BUDDY_UNSEAL_KEY`.

**The DW-99 protection is preserved in full.** G2's first held-out split was burned because
plaintext `case.yaml` files were committed and remain readable in git history. The G3 cases were
authored and sealed in one operation, with the staged plaintext deleted before any commit — no
plaintext of them exists in history, and `git log -p benchmarks/g3/heldout/` shows none.

**One limit, stated so it is not read as stronger than it is.** The frozen intent for this story
required an **operator-held** key. The operator approved this story for unattended overnight
execution and was unavailable for a key ceremony, so the split is sealed with a
**machine-generated key written outside the repository** (`~/.freecad-buddy-g3-unseal.key`),
matching G2's replacement mechanism. The set is therefore protected against casual reading and
against the actor that runs the exit, but **not** against whoever holds the key. G1's seal, which
used an operator-held key, is stronger on that axis. A deferred-work entry records that the
operator should re-seal with a human-held key before the G3 exit ceremony.

The key is not in git and not in CI. Losing it makes the sealed set unrecoverable — the cases
exist nowhere else.
