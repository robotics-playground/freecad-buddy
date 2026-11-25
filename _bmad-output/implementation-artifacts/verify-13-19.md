# Verify Story 13-19: skill routing to Part, loft, sweep and placement tools

Verifier: verifier-13-19 (opus, effort medium). Worktree `D:/Work/Personal/Sources/freecad-buddy-wt-13-19`, head `f151a456` (merge of the integration branch at `135fd94c`). Base `6e15f063`. Story commits: `ba41f0be` (skills), `f42cde8a` (MCP server instructions), `f151a456` (gap-list).

Scratch scripts (verifier's own, not the builder's): `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\verifier-13-19\` — `payload_check.py`, `fence_check.py`, `run_example.py`; outputs `gates.txt`, `pytest.txt`, `payload.txt`, `example.txt`.

Verdict: **PASS**. No high or medium finding. Four low notes (L-1 to L-4).

## 1. Gates at f151a456

| Gate | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | exit 0, "All checks passed!" |
| `scripts/check_imports.py` | exit 0, OK |
| `scripts/check_status_vocab.py` | exit 0, OK |
| `scripts/gen_schemas.py --check` | exit 0, OK |
| `scripts/check_skill_shape.py` | exit 0 |
| `scripts/check_provenance.py` | exit 0, OK |
| `pytest tests/external -q` (Git Bash) | 2,121 passed, 6 skipped, 1 failed. Failed: `test_rpc_listener.py::test_should_log_one_info_line_when_the_client_closes_its_connection_cleanly` (one extra "client closed the connection" record). Re-run alone 3 times: 3 passed. Its file alone: 44 passed. Timing flake; the story changes no `src/` file under `adapters/rpc_listener.py`. |

Body word counts (`check_skill_shape._body`, limit 1,500): code-cad-conversion 1,491 · design-decomposition 1,392 · design-intent 881 · freecad-datums-references 800 · freecad-fundamentals 907 · freecad-partdesign 959 · freecad-scripting-idioms 1,405 · freecad-sketcher 963 · freecad-troubleshooting 996 · parametric-patterns 1,107 · part-sourcing 872 · sdf-export 874 · sketch-strategy 840 · tool-selection 967 · urdf-export 908 · verification-thinking 1,499.

## 2. Independent payload check

Files: the 12 skill files in `git diff --name-only 6e15f063..f151a456 -- skills`. Schemas: `tool_specs()` imported from the worktree `src` (55 tools), validated with `jsonschema` Draft 2020-12; a missing `doc` is filled (skills omit the handle).

| Check | Count | Result |
| --- | --- | --- |
| Backticked tool names in changed files | 170 mentions | every name is a `tool_specs()` name (regex built from the spec list) |
| Inline JSON payloads after a tool name | 10 | 9 valid; 1 fragment (L-1) |
| JSON lines in fenced blocks (`code-cad-conversion/SKILL.md:125-128`) | 4 | 4 valid (2 × `feature_part_primitive`, `feature_set_expression`, `feature_part_boolean`) |
| `verify_shape` check arrays (`verification-kit.md:88-90`, `:212-214`) | 2 | 2 valid |
| Parameter names and enum values in the parenthesis after a tool | all | all in the schema. Non-schema tokens are nested paths or outputs: `placement.rotation` (nested property), `com` (output field), `App::Part`, `SKILL.md`, `_stl`/`_3mf` suffixes |
| Enum values stated in prose | — | `kind` box/cylinder/cone/sphere/torus, `operation` cut/fuse/common, sweep `mode` standard/frenet, parameter types length/angle/float/integer/bool/string: all match |
| Refusal codes named (`x.y`) | 18 tool codes | every one exists in `src/` as a quoted string: `part_boolean.{not_top_level,untrusted_shape,too_complex,empty_result,invalid_result,invalid_input}`, `loft.{too_complex,invalid_result,wire_count_mismatch}`, `sweep.{too_complex,invalid_result,degenerate_spine}`, `parameters.value_overwritten`, `delete.has_dependents`, `interference.too_complex`, `section.plane_on_face`, `exec.python_error`. Wildcards `part_primitive.*` (fields, dimension), `loft.*`, `sweep.invalid_*` (invalid_mode, invalid_spine) resolve to existing codes |
| Limits stated | — | 3,000 faces = `features.py:4178` `_PART_BOOLEAN_MAX_FACES = 3000`; 1,000 pairs = `:4179`; 1 to 20 tools = `:4158` and schema `maxItems: 20`; 100 items = `feature_set_expression` / `feature_parameters_define` `maxItems: 100`; 1 to 50 names = `query_mass_properties` `maxItems: 50`; 30 s = `script_exec` `timeout_s=30.0` (`tool_catalog.py:1579`). 1e9 mm, 1e6 deg, ±2147483647: no changed skill states them (no mismatch possible) |
| Object types named in `build123d-mapping.md:41-43` | — | `Part::MultiFuse`, `Part::Cut` with `<name>_tools`, `Part::MultiCommon` match `features.py:4395-4407` |

Mismatches: none in this story's lines. L-1 below is pre-existing.

## 3. Route check (Q1)

Grep of every skill for `Part::Box|Cylinder|Cone|Sphere|Torus|Cut|Fuse|Common|MultiFuse|MultiCommon|Loft|Sweep`, primitive, boolean, loft, sweep, `Placement`, `AttachmentOffset`, `Label`, in the same line or paragraph as `script_exec`, `setattr`, `addObject`, ".Placement =", ".Label =", "is a gap", "no typed tool".

No line sends a covered operation to `script_exec`. Remaining script uses, each out of the typed scope:

- `generator-kit.md:150-250` primitive and boolean helpers: the headless route only (`generator-kit.md:48`, `:312` "Headless, with no typed tools"); the live route is typed (`generator-kit.md:1-8`, `SKILL.md:45-63`).
- `verification-kit.md:78`, `:154-169` `Shape.common(ref)`: overlap with a reference STEP, which no typed tool reads (`verification-kit.md:7`).
- `verification-kit.md:197`, `gap-list.md:35`: fused-volume overlap of touching parts (gap row).
- `switches-and-fit.md:12`, `parametric-patterns/SKILL.md:55`: enumeration property (gap row `gap-list.md:36`).
- `verification-thinking/SKILL.md:110` now routes the pose write to `feature_set_parameters` on the Body's `Placement`.

## 4. Worked example under freecadcmd

`run_example.py` under `freecadcmd.exe -u/-s` private cfg, `FREECAD_USER_HOME` temp; package loaded from `D:\Work\Personal\Sources\freecad-buddy-wt-13-19\src` (no addon shadow). It reads the four JSON lines of `code-cad-conversion/SKILL.md:125-128` verbatim and calls them through `tool_specs()[name].make_handler(registry, ...)`, after `feature_parameters_define` of `L 60, PLATE_W 40, PLATE_T 5, HOLE_R 2, EDGE 10` (the skill leaves `EDGE` open). All 12 tool calls returned `status` OK.

Objects: `Params` (App::VarSet), `bracket_plate` (Part::Box), `bracket_hole` (Part::Cylinder), `bracket` (Part::Cut).

| Case | Volume | Analytic `L*W*T - pi*R^2*T` | Overlap with analytic shape | Result |
| --- | --- | --- | --- | --- |
| default | 11,937.1681 | 11,937.1681 | 100.0000 % | PASS |
| `PLATE_T` 3 | 7,162.3009 | 7,162.3009 | 100.0000 % | PASS |
| `PLATE_T` 8 | 19,099.4690 | 19,099.4690 | 100.0000 % | PASS |
| `EDGE` 4 | 11,937.1681 | 11,937.1681 | 100.0000 % (hole moved) | PASS |
| restored | 11,937.1681 | 11,937.1681 | 100.0000 % | PASS |

Each case: one valid solid, `State` Up-to-date. The overlap uses `Part.makeBox(L,W,T).cut(Part.makeCylinder(R,T,(EDGE,EDGE,0)))`, so a misplaced hole fails it. The skill text states no number; the analytic value matches the triage log (11,937.168 and 19,099.469).

## 5. AC map

| Q | Verdict | Evidence |
| --- | --- | --- |
| Q1 | PASS | `gap-list.md:25-27` covered rows; `tool-selection/SKILL.md:43-48`, `:68-75`; `design-decomposition/SKILL.md:64-73`; `freecad-partdesign/SKILL.md:63-67`; `code-cad-conversion/SKILL.md:45-63`; `freecad-scripting-idioms/SKILL.md:79-85`; `mcp_server.py:69-71` instructions name loft, sweep, Part primitives and booleans. Section 3 grep: no covered operation sent to `script_exec` |
| Q2 | PASS | Section 2: 15 payloads/arrays valid, 18 refusal codes exist, limits match constants |
| Q3 | PASS | Generator boundary: `code-cad-conversion/SKILL.md:56-63` (Wedge `taper_z`, other Part type, `App::Link`, tilted primitive; enumeration switch), `generator-kit.md:1-8`, `:300-313`; traced outline kept `gap-list.md:88-95`; >20 tools chain `SKILL.md:53-54`, `build123d-mapping.md:44` |
| Q4 | PASS | `code-cad-conversion/SKILL.md:64-65`; `gap-list.md:49-66` (each code with its repair, "A script that repeats a call skips the guard"); `design-decomposition/SKILL.md:71-73` (`empty_result`: "do not script around it"); `tool-selection/SKILL.md:46-48` |
| Q5 | PASS | Covered rows `gap-list.md:25-27`; placement, `Label`, Part primitive/boolean rows gone from Gaps (`:32-47`); remaining gaps `:37` (Wedge, Prism, Ellipsoid, Offset2D, Extrusion, Fillet, Chamfer, Compound, Reverse), `:38` (Helix, thickness, sweep modes Fixed/Auxiliary/Binormal, `SpineTangent`, `Transition`, auxiliary spine, `Part::Loft`, `Part::Sweep`), `:41` narrowed to link, file, vector, list, colour; `value_overwritten` and attached-`Placement` rule `:27` match `features.py:2672-2731` |
| Q6 | PASS | `deferred-work.md:1657` (Part::Common) and `:2358` (13-16 gap-list entry) have resolution lines (wording note L-3) |
| Q7 | PASS | `check_skill_shape.py` exit 0; counts in section 1 (max 1,499) |
| Q8 | PASS | Section 1; one timing flake, passes alone |
| Q9 | NOT RUN | Live routing check runs at epic close |

## Low notes

- **L-1** (pre-existing, `8cd54a01e`): `freecad-scripting-idioms/SKILL.md:148` shows `feature_set_parameters` `{"Visibility": true}`, which is the `parameters` value, not a call payload (fails the schema: `feature`, `parameters` required). Not in this story's diff.
- **L-2**: `generator-kit.md:15` clear example lists `["Params", "Box", "Box001", "Cut"]` (generator default Names), while the typed worked example in `SKILL.md:125-128` makes `bracket_plate`, `bracket_hole`, `bracket` in the same `bracket` document. A reader who copies step 1 after the typed example names objects that do not exist. Schema-valid.
- **L-3**: `deferred-work.md:2358` resolution says "link, file, vector and list"; the row `gap-list.md:41` also lists colour.
- **L-4**: `code-cad-conversion/SKILL.md:124-129` fenced block does not name the tool per line; the reader infers it from the keys and from the rule order (`:45-55`). `freecad-scripting-idioms/SKILL.md:80-81` says placements are written "on any object", while `gap-list.md:27` states the attached / in-Body refusal (wording from 13-16). `part-sourcing/SKILL.md` names no tool for writing the placement of a placed part (unchanged skill, outside the Q1 file list). `verification-thinking` body is 1,499 of 1,500 words: no room for further text.

Nothing left running: no `freecadcmd` process after the runs.

## Round 2

Head: the leader named `22e96c4d` (red-team doc fixes). The worktree was already at `3a993adf` when the checks ran, so every check below covers both commits. `3a993adf` is one gap-list sentence (`gap-list.md:63-67`: tools that exceed the time budget or are refused → split the call). Triage: `triage-13-19-rt.md` T1-T8. Scripts: `scratchpad\verifier-13-19\r2\run_r2.py` (my own, through `tool_specs()` handlers and `SCRIPT_EXEC_SPEC`); output `r2\r2.txt`, `r2\pytest.txt`, `r2\payload.txt`.

Verdict: **PASS**. All T1-T8 fixes hold. No new finding above low.

### Gates

| Gate | Result |
| --- | --- |
| ruff check, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance | all exit 0 |
| pytest tests/external (Git Bash) | 2,122 passed, 6 skipped, 0 failed |

Body words: code-cad-conversion 1,495 · design-decomposition 1,399 · freecad-scripting-idioms 1,407 · verification-thinking 1,499 · tool-selection 967 · freecad-partdesign 959 · others unchanged (max 1,107).

### Payload and link checks

- 12 changed skill files (`6e15f063..3a993adf`): 170 tool mentions, every name valid. 9 inline payloads valid, 0 invalid. 4 fenced JSON lines (`code-cad-conversion/SKILL.md:122-125`) valid. The `"<fcb-doc handle>"` placeholder is a string and passes the schema (T7). The `{"Visibility": true}` fragment now reads "with `parameters` `{...}`" (`freecad-scripting-idioms/SKILL.md:148`, T8).
- Links: scanned every `*.md` reference in all skills against the skill folder, its `references/` and any skill named just before it. No dangling file. `code-cad-conversion/SKILL.md:64-65` now reads (`freecad-scripting-idioms`, `references/gap-list.md`), and that file exists (T1). The `build123d-mapping.md` "Placement" heading that `SKILL.md:87-88` points to exists (`:46`) and keeps the frame formula that was moved there. The `mcp-tools-design.md` pointer is gone from gap-list.

### Worked example and coverage script (T2, T7)

Ran the 4 JSON lines of `code-cad-conversion/SKILL.md:122-125` word for word (the placeholder replaced by the real handle) after `feature_parameters_define` (`L 60, PLATE_W 40, PLATE_T 5, HOLE_R 2, EDGE 10`). All calls returned OK.

| Case | Volume | Analytic | Overlap | Result |
| --- | --- | --- | --- | --- |
| default | 11,937.1681 | 11,937.1681 | 100.0000 % | PASS |
| `PLATE_T` 3 / 8 | 7,162.3009 / 19,099.4690 | same | 100.0000 % | PASS |
| `EDGE` 4 | 11,937.1681 | same | 100.0000 % (hole moved) | PASS |
| `L` 80, `PLATE_W` 30 | 11,937.1681 | same | 100.0000 % | PASS |
| restored | 11,937.1681 | same | 100.0000 % | PASS |

Coverage script extracted word for word from `verification-kit.md` ("Expression coverage" fence) and run through `script_exec`: `value_repr` = `[]` (PASS; red team got `[('bracket_plate', [x, y, z]), ('bracket_hole', [z])]` at f151a456).

### Fix probes

| T | Text | Probe (tool handlers, freecadcmd) | Result |
| --- | --- | --- | --- |
| T3 | `switches-and-fit.md:20-22`: additive tool kept inside the base, `rib` `Height` `FITS ? 10 : 5` on a 5 mm base | body 20×20×5, rib 2×20 at the origin with that binding, `fuse` | FITS false: 1 solid / 2,000.0000; FITS true: 1 solid / 2,200.0000. With the parked vent cut as well: 1 / 2,000.0000 and 1 / 2,137.1681 (= 2,200 − π·4·5). PASS |
| T5 | `design-decomposition/SKILL.md:68-70`: delete the piece and its region boxes, then create both again | Master Body (100×40×20) ∩ region1 → `split1` 40,000; `document_object_delete` `["split1", "region1"]` OK; re-create `region1` and `split1` with the same names | both OK; `split1` 1 solid / 40,000.0000. `Visibility` true on the Master after the common: OK. PASS |
| T6 | `code-cad-conversion/SKILL.md:53-54`: 1 to 20 tools, chain a longer cut, fuse or common | 21 cylinders on a 300×5×5 box | `fuse` 21 and `common` 21 refused (`tools must be a list of 1 to 20 object Names`); `fuse` 20 then `fuse` 1 chained: 1 solid / 7,829.8672 = 7,500 + 21·π·5. PASS |
| T4 | `gap-list.md:27`: a read-only `Placement` (attached sketch, PartDesign feature such as a Pad) refused; write the Body's or `AttachmentOffset` | Body over a Part box | `BaseFeature` Placement write OK; Body Placement OK; Pad Placement refused (`Pad.Placement is read-only ...`); attached sketch refused (`... write AttachmentOffset instead`). Text matches. PASS |
| T8 | `generator-kit.md:15` clear list, `deferred-work.md:2358` | read | `["Params", "bracket_plate", "bracket_hole", "bracket"]` matches the worked example's Names; resolution line lists colour. PASS |

### Low notes (round 2)

- **L-5**: `build123d-mapping.md:44` still says "at most 20; chain further cuts" for the hole-loop row only; the fuse row (`:41`) and common row (`:43`) give no limit. `SKILL.md:53-54` states the rule for all three, so an agent that reads the skill has it.
- **L-6** (older text, not changed by this story): `build123d-mapping.md:53` "start from a non-zero rotation about z to fix the axis". The round-1 triage probe showed a bound `Placement.Rotation.Angle` on an identity rotation keeps axis (0,0,1), so the advice is not needed, but it does no harm.

Q1-Q8 PASS (round 1 map stands; T1-T8 lines above). Q9 NOT RUN (epic close). Nothing left running.
