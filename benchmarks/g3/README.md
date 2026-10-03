# G3 — Phase 3 spec-to-part benchmark (entry gate G3.E)

Landed by Story 4.1 before any Phase 3 tool exists (AD-19). The benchmark is data plus gate
wiring. It holds no loop, no planner, no judge and no builder script (AD-35). The actor is an
external agent harness that holds its own plan → execute → measure → repair loop. This
repository grades the part that loop leaves behind.

```
g3/
  gate.yaml            G3.1-G3.6, the G3.E entry items with their owning stories, the threat map
  reuse-survey.md      what was reused from the reverted bb42999 commit, what was rejected, why
  dev/                 20 written specs with compiled assertions in a declared anchor frame
  heldout/             7 held-out specs, SEALED (SEAL.json + heldout.tar.enc, no unseal spent)
  fault-injection/     validates the validators; never counts toward the G3.1 pass rate
    corrupted-plan/      10 planted corrupted plans + 4 clean controls
    threat-counters/     2 planted run-evidence cases for the threats no plan can counter
    score_g3_replay.py       operator-run replay scorer: sensitivity, false alarm, frames per leg
    score_g3_validators.py   structural check; reads G3.E.3 and G3.E.4 from stored evidence
    frames-reference.json    the anchor frame of every clean build, from the 1.1.x leg
```

`runner run G3 --run <id>` and `runner --gate G3 --stub` fail all six criteria with
`INVALID_INPUT`: no actor drives a spec and no collector reads a run yet. `runner faults G3` runs
the structural check and computes G3.E.3 and G3.E.4 from stored evidence;
`runner faults G3 --frames-evidence DIR` reads the per-leg frame files from `DIR`.
`runner run G3 --exit` is refused before the unseal.

## Entry gate G3.E

`gate.yaml` `entry:` lists every G3.E item from `phase-gates.md:77` and the story that owns it.
G3.E stays open after Story 4.1. Story 4.2a supplies the assertion primitives and the anchor-frame
resolver that G3.E.3 and G3.E.4 measure with. Story 4.2b owns both items: it replays the corrupted
plans, scores the suite, and checks the frames on both legs.

| Item | Owner | State after 4.2b |
| --- | --- | --- |
| Spec set with compiled assertions, failing honestly against a stub | 4.1 | landed |
| Corrupted-plan fault suite, every threat countered | 4.1 | landed, `fixture: pending` |
| Anchor frames resolve identically on the 1.0.x and 1.1.x legs | 4.2b | computed from leg evidence |
| Corrupted-plan sensitivity ≥95 % / false-alarm ≤5 % with `validator_sha` | 4.2b | computed from `validators.yaml` |
| Render and drawing path at the ≥2048 px review floor | 4.3 | `INVALID_INPUT` |
| `design-loop`, `visual-review`, `spec-to-assertions` skills | 6.5 | `INVALID_INPUT` |
| Recorded reuse survey (`phase-gates.md:3`) | 4.1 | landed, `reuse-survey.md` |

`runner faults G3` reports the 4.1 items from the structural check only. That the stub run fails
honestly is checked by the CI G3 stub step (exit code exactly 1) and
`test_should_fail_all_six_criteria_with_invalid_input_when_run_against_the_stub`.

- **G3.E.4** is `OK` when the `spec_assertions` block in `_registry/validators.yaml` is current
  and meets sensitivity ≥0.95 and false alarm ≤0.05. Its `validator_sha` hashes
  `usecases/assertions.py`, `usecases/verify.py`, `score_g3_replay.py`, every corrupted-plan
  `case.yaml` and each dev spec a corrupted plan names; an edit to any of them reports
  `FAIL (stale)` until `score_g3_replay.py` runs again.
- **G3.E.3** is `OK` when `G3.E.3.1.0.x.json` and `G3.E.3.1.1.x.json` both hold the frames of
  `frames-reference.json`. Without the reference or either leg file it reports `INVALID_INPUT`;
  a leg file measured on another FreeCAD version, or a frame that differs, reports `FAIL` naming
  the file, or the leg, the build and the field. Each CI headless leg runs
  `score_g3_replay.py --check --frames-check` and uploads its run directory. CI proves the legs
  agree only indirectly: each leg is compared with the committed reference, never with the
  other leg. The joined read is `runner faults G3 --frames-evidence <dir>`, with both leg files
  in `<dir>`.

## Replay scoring

`score_g3_replay.py` runs in an interpreter that has FreeCAD and `mcp`. It spawns the headless H1
host over stdio and reaches FreeCAD only through MCP tools: each step goes through
`preview_dry_run` and then the confirmed call (AD-5), and each part is graded by `verify_shape`
with its spec's `checks` and `anchor_frame`. It reads no verdict off the plan (AD-13).

Each planted plan is built twice: planted, and reverted to its faithful build. Each control is
built once. A planted build is a detection only when a check of its `detected_by` fn fails with a
measured value; a check that fails with an `invalid_input.*` code is a miss. A control or
reverted build is a false alarm when its verdict is not `OK`. A step that does not return `OK`,
or a reverted build that does not grade `OK`, makes the case `INVALID_INPUT`: it is listed,
excluded from both rates, and the run exits non-zero. Reverted builds count as clean controls,
so the false-alarm population is 14: the 4 controls and the 10 reverted plans.

The run writes `cases.jsonl` and `G3.E.3.<leg>.json` to `gate-artifacts/g3/<run>/`. It merges
the `spec_assertions` block into `validators.yaml` unless `--check` is passed or a case is
`INVALID_INPUT`. `spec_assertions` is a separate validator id from G2's `assertions`: the same
code measured over a different suite needs its own `validator_sha` and rates.

### Anchor-frame coverage

The frame comparison uses kind, origin and axes rounded to 1e-6 mm, and the entity only for
`base_sketch_plane` and `named_datum`. A `largest_planar_face` entity is a mapped face name whose
hasher tag changes between sessions, so it is never compared.

Frames are proven on the 14 clean builds, which cover 8 specs: `g3-dev-001`, `-003`, `-007`,
`-008`, `-010`, `-011`, `-012` and `-019`. `gate.yaml` lists them under G3.E.3
`proven_on_built_parts`. No plan builds the other 12 specs, so their frames are not proven on a
built part. `CanonicalFrameTest` in `tests/infc/test_assertion_primitives.py` resolves every
declared `(kind, ref)` (`XY_Plane`, `XZ_Plane`, `PlateCornerDatum`, and a symmetric
`largest_planar_face` part) to a hand-derived frame on both legs. That proves the resolver, not
those parts.

## Specs

Each spec derives from a documented real part and carries a manifest under
`_registry/provenance/g3-dev-*.yaml` with `kind: part-spec`. A spec ships no `.FCStd`: the part is
built from the spec text, so the case declares `fixture: none-spec-to-part`, and
`scripts/check_provenance.py` resolves a `part-spec` manifest against the case file.

Every `expect` value is derived from the spec prose and carries its derivation inline, under a
`Derivations:` comment. Nothing was read off a verify tool.

### Assertion vocabulary

Only the eleven closed `verification-design.md` §7.2 functions are legal: `is_valid_solid`,
`count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`,
`distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`. G3
declares no extension. A sub-element index selector (`Face6`) and a feature-metadata reference
(`PartDesign::Hole.Diameter`) are refused in a spec (AD-13). All eleven and the anchor-frame
resolver live in `src/freecad_buddy/usecases/assertions.py`; `harness/assertions.py` and the MCP
`verify_shape` tool both measure through it.

Selectors are geometric queries, never indexes. `usecases/assertions.py` implements them as
written here.

- `select` narrows a hole primitive (`count_cylindrical_holes`, `hole_diameter`,
  `hole_position`, `hole_spacing`) to the logical holes that match. `diameter` is matched within
  the linear band, and matches a logical hole when any of its coaxial cylinders has it (a
  counterbore is part of its hole, §7.3 rule 4). `axis` is a direction in the anchor frame; a
  hole axis is a line, so its sign is ignored.
- `select_a` / `select_b` name the two sides of `distance_between`, `angle_between` and
  `hole_spacing`. `distance_between` and `angle_between` always carry both (§7.2 signs them with
  two selectors); the structural check refuses either one without them. Each is
  `{hole: {diameter, axis}}`, `{face: {normal: [x, y, z]}}` (a planar face whose outward normal
  is that frame direction) or `{face: {diameter: d}}` (a cylindrical face with material inside
  it, an outside diameter). The value is measured for every entity `select_b` matches, against
  its nearest entity `select_a` matches other than itself, and every value must equal `expect`.
  `distance_between` measures `distToShape` between the two faces; `angle_between` the angle
  between their normals or axes; `hole_spacing` axis to axis. A `normal` matches within the
  angle band (±0.1°).
- `hole_position` reports where each matched hole's axis meets the anchor frame's XY plane, in
  frame coordinates.
- `expect_bbox` compares the sorted extents measured in the anchor frame, so the order of the
  three `expect` values does not matter. `expect_extent` measures along its frame `direction`.
- `hole_diameter` on a logical hole with several coaxial cylinders (`g3-dev-017`: a 6.5 mm bore
  under an 11 mm counterbore) returns the smallest of them, the through bore. A counterbore is
  asserted through `select.diameter`, never through `hole_diameter`.
- A selector that matches nothing makes its check fail with `INVALID_INPUT`. It is never a pass,
  never a silent skip, and never counted as a DETECT. The same holds for a corrupted-plan step
  that errors on replay: the case reports a failing `INVALID_INPUT` check and is not counted as
  a detection.

### Anchor frames

| `anchor_frame.kind` | Specs |
| --- | --- |
| `base_sketch_plane` | 16 |
| `largest_planar_face` | 3 (007, 012, 017) |
| `named_datum` | 1 (019) |

The specs assume a `largest_planar_face` frame has its origin at that face's centroid and its
+Z pointing from the face into the part. `g3-dev-007`, `g3-dev-012` and `g3-dev-017` rely on
it, and the `g3-dev-019` comment states the origin rule. The resolver fixes that rule. Its
in-plane X is document X projected onto the face, or document Y when the face is normal to X. A
tie on area goes to the lowest centroid Z, then the lowest mapped face name; without mapped
names, to the lowest centroid X, then Y. A tie that survives every rule leaves the frame
unresolved, and every frame-dependent check fails with `INVALID_INPUT`. `base_sketch_plane` and
`named_datum` resolve `ref` by object `Name`, then by unique `Label`, to that object's global
placement. The report banner records the resolved frame and the entity it came from.

## Corrupted plans

A corrupted plan is a recorded plan, in the `harness/scripted_backend.py` `PlanStep` shape: an
ordered list of `{tool, args}` steps that build `spec_ref` through the MCP mutation tools.
`$doc` stands for the handle the `document_create` step returns. A planted case marks its one
defect step in `planted_step` (0-based); a clean control marks none. Every case targets
`spec_assertions@usecases.assertions.evaluate_checks`: `score_g3_replay.py` replays the plan, and
the spec's own assertions grade the part it produces. Detection comes from measuring that part,
never from reading the plan. Every case declares `fixture: pending`: no `.FCStd` ships, and the
part exists only as the replay builds it.

A planted case also carries the faithful build its replay is reverted to. Seven cases carry
`faithful_args`, the args the spec states for the planted step. Three cases carry
`faithful_steps`, a map from step index to the step the spec asks for, or to null to drop that
step, because their defect spans more than the one marked step:

- `pocket-before-pad` is an ordering defect. A pocket at step 9 is filled by the upper pad at
  step 10 whatever its args, so the revert swaps the two steps.
- `hole-on-wrong-face` places the block, sketches the bore on XZ and centres it for that face
  (steps 3, 5 and 6). With only step 5 changed, the bore misses the block. The revert takes the
  three steps from `blind-hole-made-through`.
- `extra-unrequested-pocket` is an insertion. The revert drops step 7; the unused sketch stays.

The plans use base planes only. A plate is padded `reversed`, so it sits below the XY plane and
its top face lies on it; a top-face feature is sketched on XY and cuts downwards. A sketch on the
XZ plane has its normal along −Y and maps sketch `(u, v)` to global `(u, 0, v)`.

The two `g3-dev-012` plans are the exception. The block is padded in two halves either side of
the XY plane (the upper half forward, the lower half `reversed`), and the slot pocket is
`reversed: true`, so it cuts upwards from the XY plane into the upper half.

The two `g3-dev-019` plans put `PlateCornerDatum` and the plate at (25, 30), off the global
origin, so a resolver that ignores the named datum measures the hole from the wrong place and
fails the control too. The plans cannot offset a datum in X or Y directly: `feature_datum` only
offsets along the datum's own Z. So each plan sketches a single point at (25, 30) and attaches the
datum to it with `map_mode: Translate`, naming the point `Vertex1`. That name is a sub-element
index, which a spec may not use; here it names the only vertex of a one-point sketch, so it cannot
renumber, and a plan is not graded by it.

| Case | Spec | Class | Detected by |
| --- | --- | --- | --- |
| `blind-hole-made-through` | 007 | value | `hole_through` |
| `datum-origin-swapped` | 019 | frame | `hole_position` |
| `extra-unrequested-pocket` | 010 | insertion | `expect_volume` |
| `hole-on-wrong-face` | 007 | topology | `angle_between` |
| `mirrored-hole-pattern` | 011 | topology | `hole_position` |
| `missing-bolt-holes` | 008 | omission | `count_cylindrical_holes` |
| `pocket-before-pad` | 012 | ordering | `expect_volume` |
| `radius-for-diameter` | 003 | value | `hole_diameter` |
| `wrong-hole-diameter` | 001 | value | `hole_diameter` |
| `wrong-plate-thickness` | 001 | value | `expect_bbox` |
| `control-faithful-mounting-plate` | 001 | control | — |
| `control-tolerance-edge-hole` | 001 | control | — |
| `control-named-datum-honoured` | 019 | control | — |
| `control-equivalent-step-order` | 012 | control | — |

`wrong-hole-diameter`, `wrong-plate-thickness` and `datum-origin-swapped` share every step but
the planted one with their control, so the suite measures the corruption and not the difference
between two plans. `pocket-before-pad` and `control-equivalent-step-order` run the same steps in
different orders: swapping the two pads preserves the part, while running the slot pocket before
the upper pad loses the slot.

## Threats and their counter cases

`gate.yaml` `threats:` maps each `phase-gates.md` G3 threat to the planted cases that counter
it. The structural check fails, naming the threat, when a threat has no existing counter case.

| Threat | Counter case(s) |
| --- | --- |
| Plan looks professional, part deviates | all 10 planted corrupted plans |
| Agent stopped because it ran out of patience | `g3-fault-plan-missing-bolt-holes` |
| Part never looked at | `g3-threat-no-visual-findings` |
| Rate cited for the wrong actor | `g3-threat-banner-actor-mismatch` |

The two threat-counter cases plant run evidence, not geometry. Their part is the build of
`plan_ref` (the faithful mounting-plate control), and `planted_evidence` names what the run
workdir or the report banner carries. The Story 4.5 collectors read that evidence.

## Reused data and known defects

The 20 dev specs, their 20 manifests, the 7-case sealed held-out split and the 14 corrupted-plan
cases come from commit `bb42999`, a designer-loop implementation that was reverted. Only
pure data is reused. No loop, judge, designer or actor code is restored.

- **Byte-identical:** all 20 dev manifests, `heldout/SEAL.json` and `heldout/heldout.tar.enc`
  (`unseal_events: []`; the key is the operator's machine key).
- **Restored, then amended:** all 20 dev specs (see the next three items). Every amendment carries
  its derivation and a disclosure comment in the case file.
- **Rewritten:** the 14 corrupted-plan cases. Their `planted_op` and `driven-by-designer-loop`
  fields named reverted code and are dropped. Each now carries a recorded `plan`, targets
  `spec_assertions@usecases.assertions.evaluate_checks`, declares `fixture: pending`, and has a
  manifest. Five descriptions were rewritten to match the plan that now plants the defect
  (`pocket-before-pad`, `control-equivalent-step-order`, `hole-on-wrong-face`,
  `mirrored-hole-pattern`, `missing-bolt-holes`). The `radius-for-diameter` description said an
  8 mm wall; a 32 mm bore in a 40 mm collar leaves 4 mm, and the text now says so. `id`,
  `corruption_class` and `spec_ref` are unchanged in all 14; `detected_by` is unchanged in 13
  (see the `g3-dev-007` angle check below).
- **DW-122, amended after the reverted code existed:** `g3-dev-007` gained a `hole_position`
  check whose selector pins the bore axis to the frame normal, and `g3-dev-011` gained a placement
  sentence and two `hole_position` checks. Without them `hole-on-wrong-face` and
  `mirrored-hole-pattern` left every declared check passing. The structural check now refuses a
  planted case whose `detected_by` names no check in its spec, which is how DW-122 would read.
- **DW-127 / DW-129, amended inside `bb42999`:** `g3-dev-002` gained its clearance hole so the
  part has a handedness. The case file's comment cites DW-127 (why the hole was needed); the
  amendment itself is recorded as DW-129. That comment also names two visual-judge fault cases
  (`g3-fault-visual-mirrored-part`, `g3-fault-visual-control-symmetric-part-either-hand`) and a
  `visual_judge` validator. None of them was restored: they belonged to the reverted judge.
- **Spec audit, amended after the reverted code existed.** Test applied to every spec: can a part
  that violates a stated requirement pass every check? Each amendment adds a requirement the
  prose states and relaxes none.
  - `g3-dev-019`: the prose names the datum `PlateCornerDatum` and the corner it sits on; two
    edge-distance checks catch a datum placed anywhere else.
  - `g3-dev-002`: a placement sentence and two edge-distance checks for the hole, which catch a
    mirrored build. `hole_position` is not used because the hole axis is parallel to the anchor
    plane.
  - `g3-dev-008`: hole counts by diameter, the bolt-to-bore pitch-circle spacing, the bolt pitch
    and the bore wall.
  - `g3-dev-017`: the through hole's diameter and the hole and counterbore positions on the boss
    axis.
  - Hole-to-edge distances: `g3-dev-001`, `-005`, `-006`, `-014`, `-016`.
  - Concentric walls: `g3-dev-003`, `-004`, `-009`, `-013`, `-018`.
  - Feature placement: `g3-dev-010` (window centred), `-012` (slot depth), `-015` (rib on the
    centreline), `-020` (bosses symmetric, holes on the boss axes).
  - With `g3-dev-007` and `g3-dev-011` (DW-122), every dev spec is amended.
- **Selector amendment, after the reverted code existed.** The reused `angle_between` checks in
  `g3-dev-002` and `g3-dev-015`, and the reused `distance_between` in `g3-dev-020`, carried no
  selectors, so they could not be evaluated and failed a faithful part. Each now carries
  `select_a`/`select_b` from the prose. `g3-dev-020`'s check expected 50, the boss axis spacing;
  face to face the two bosses are 36 mm apart, and the 50 mm spacing is graded by `hole_spacing`.
- **Placement prose.** A spec may state where the part sits in its frame when a stated
  requirement can only be graded there (handedness, position). `g3-dev-011`, `-002` and `-019`
  carry such a sentence, and `g3-dev-014` gained "Model the plate centred on the origin of the
  base sketch plane", so its reused `hole_position (0, 0)` grades a stated requirement. Each is
  disclosed in its case file.
- The reused dev specs say "The designer BUILDS this part". "Designer" is the reverted loop's
  term; read it as "the actor". The sentence is kept unchanged so the reuse stays checkable.
- The 7 held-out specs are sealed and were not re-read. They may carry the same class of gap as
  DW-122, and that cannot be checked before the exit unseals them.
- A `normal` selector already fixes a face's direction, so `angle_between` over two normal
  selectors mostly fails through an empty match (a tilted leg or rib matches no face) rather
  than through a measured angle off by more than 0.1°.
- **Faithful builds, added in Story 4.2b after the suite landed.** All 10 planted cases gained
  `faithful_args` or `faithful_steps` (see Corrupted plans). The data was added after the plans
  existed, and the three `faithful_steps` reverts change more than the planted step. Each
  reverted build grades `OK` on both legs, which ties every detection to the planted defect.
- **`g3-dev-007` angle check, added in Story 4.2b after the suite landed.** `hole-on-wrong-face`
  named `hole_position` in `detected_by`. That check's selector pins the bore axis to the frame
  normal, so a side-face bore matches nothing and the check fails `INVALID_INPUT`, which is never
  a detection. `g3-dev-007` gained `angle_between` from the top face's normal to the 12 mm bore,
  expected 0°, from the prose "into the centre of the top face". It measures 90° on the
  side-face bore and 0° on the faithful one. The case's `detected_by` is now `angle_between`.
  Every other check stays, and nothing is relaxed.
- G3.1 and G3.4 cite `spec_assertions`, scored over this suite. The `assertions` registry row
  is G2's and was measured over the G2 suite.
