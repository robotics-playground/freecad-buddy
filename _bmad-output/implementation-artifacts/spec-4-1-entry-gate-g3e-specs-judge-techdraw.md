---
title: 'Story 4.1 — Entry Gate G3.E: Specs, Assertions, Judge & TechDraw Spike'
type: 'feature'
created: '2026-09-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '273413a46692d95c17c1e2f613ec3b3f57bbbd16'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
  - '{project-root}/benchmarks/g2/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Phase 3 has no definition of done. `benchmarks/g3/` does not exist, no spec compiles to
assertions, the visual judge has no fault suite, and the headless TechDraw question is open — so any
designer code written now would be graded by measures authored after it, which AD-19 forbids.

**Approach:** Land the G3 entry gate before any designer code: the `benchmarks/g3/` tree with 20
provenance-backed specs compiled to AD-13 assertions, a sealed held-out split, 10 corrupted-plan
cases, the visual-judge fault suite with a stub judge that fails honestly, and an executable answer
to the headless TechDraw spike. The machinery is born graded and fails honestly against the absent
Phase 3 implementation, exactly as `g1/` and `g2/` did.

## Boundaries & Constraints

**Always:**
- Assertions are hand-derived analytically from each spec's stated geometry, and each carries its
  derivation as a comment. Nothing is captured from a verify tool — an assertion read off an
  implementation cannot falsify that implementation (AD-13/AD-19).
- Every `fn` in a case comes from the closed `verification-design.md` §7.2 vocabulary. A name outside
  it is a declared extension documented in `benchmarks/g3/README.md` with its reason, never a silent
  fork — the `benchmarks/g2/README.md` "Assertion vocabulary" table is the precedent.
- Every case declares its `anchor_frame` from the closed derivation set: `named_datum`,
  `base_sketch_plane`, or `largest_planar_face`.
- Every `.FCStd` artifact carries a provenance manifest under `benchmarks/_registry/provenance/`
  with `source.kind` in the closed set (`freecad-parts-library`, `freecad-wiki-tutorial`,
  `hand-authored`, `hf-verified-permissive`). Non-`hand-authored` kinds also need non-empty
  `source.url`, `source.license` and `source.attribution`; `hand-authored` needs `real_world_basis`.
- The held-out split is sealed with an **operator-held key before its cases are ever committed**.
  This is the DW-99 correction: G2's first split was burned by committing plaintext.
- Fault suites live beside the dev/heldout split, never inside it, and never count toward a pass rate.
- A validator with no measurable score records an explicit `not_scored` reason in
  `validators.yaml` rather than a fabricated `0.0`.
- **UAT is executed for this story** with the `manual-testing` skill and `cua-driver` driving the
  real FreeCAD GUI [operator decision]. Shut down every FreeCAD process and close all documents
  first, use absolute paths, and have the agent perform the visual check itself — an automated
  verdict or an MCP result is never sufficient on its own.

**Never:**
- No designer-loop, assertion-primitive, drawing-generator or `verify_visual` implementation. Those
  are stories 4.2–4.6. This story lands the measures and the stubs only.
- Never raise `_MAX_DIM` or the tool-catalog cap in this story. The ≥2048 px judge path is 4.3/4.4 work;
  this story only records the constraint.
- Never commit held-out case content as plaintext, at any point, even briefly.
- Never quote a G3 pass rate. Every criterion must fail honestly until Phase 3 code exists.
- No DeepCAD / ABC / Text2CAD / Fusion 360 Gallery lineage shipped as a spec or golden model.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Gate runs with no Phase 3 code | `run G3` | Every criterion fails honestly; report names the missing actor | `INVALID_INPUT`, exit 1 |
| Dev run touches held-out | `run G3` (no `--exit`) | `g3/heldout/` never read; only the sealed pair present | Exit 2 if readable `case.yaml` found |
| Exit run without key | `run G3 --exit`, `FREECAD_BUDDY_UNSEAL_KEY` unset | Refuses to unseal | `UsageError`, exit 2 |
| Unsupported `fn` in a case | case declares an unknown assertion name | Failing check, never a silent pass | `INVALID_INPUT` check |
| Judge unreachable | stub judge, no vision backend | `visual.unavailable`; part not done | Recorded `not_scored`, never a pass |
| Headless TechDraw probe | `TechDrawGui` import under `FreeCADCmd` | Probe records absence; view-level API works | Capability recorded, not a crash |

</frozen-after-approval>

## Code Map

- `benchmarks/g2/` -- the direct structural template for `g3/`: `gate.yaml` + `dev/` +
  `heldout/` + `fault-injection/` + `README.md`. Copy the shape, not the content.
- `benchmarks/g2/gate.yaml` -- declarative criteria mirror. `actor:`/`grader:` blocks,
  `required_tokens`, `verdict.heldout: sealed`, and one entry per criterion with `pass_rule` and
  `cited_validators`. G3's adds a `visual_judge:` block alongside `actor:`.
- `benchmarks/g2/dev/g2-dev-001-sketch/case.yaml` -- exact case schema to follow:
  `id`, `gate`, `criterion`, `spec`, `inputs.document`, `assertions.anchor_frame`,
  `assertions.checks[]`.
- `benchmarks/harness/assertions.py` -- **already implements 5 of the 11 §7.2 primitives**
  (`is_valid_solid`, `count_cylindrical_holes`, `hole_spacing`, `hole_through`, `expect_volume`)
  plus 3 declared G2 extensions. Reuse; do not fork. The other 6 primitives are story 4.2 — G3 cases
  may cite them, and the grader reports `INVALID_INPUT` for them until 4.2 lands.
- `benchmarks/harness/seal.py` -- `ARCHIVE_NAME = "heldout.tar.enc"`, `MANIFEST_NAME = "SEAL.json"`,
  stdlib SHA-256 keystream XOR (decision 012). Reuse verbatim; no new crypto.
- `benchmarks/runner.py:55` -- `KNOWN_GATES = {"G0": "g0", "G1": "g1", "G2": "g2"}`; add `"G3": "g3"`.
- `benchmarks/runner.py:57` -- `_SEALABLE_GATES = frozenset({"G1", "G2"})`; add `"G3"`.
- `benchmarks/runner.py:75-78` -- `_FAULT_SCORERS`; add a `"G3"` entry pointing at the new scorer.
- `benchmarks/runner.py:96-118` -- `_VALIDATOR_SOURCES`; add rows for the G3 validators.
- `benchmarks/runner.py:68` -- `_UNSEAL_KEY_ENV = "FREECAD_BUDDY_UNSEAL_KEY"`; the only key source.
- `benchmarks/_registry/validators.yaml` -- registry row shape: `suite`, `validator_sha`,
  `last_run{run_id, sensitivity, false_alarm, date, wilson_ci}`, optional `not_scored`.
- `scripts/check_provenance.py:31-38` -- `CLOSED_SOURCE_KINDS`; CI fails on any artifact without a
  manifest. `heldout/` is excluded from the walk (already sealed).
- `usecases/screenshot.py:34` -- `_MAX_DIM = 1920`, enforced by `_clamp_dim` at :373-384.
- `hosts/tool_catalog.py:202-203` -- `"width"/"height": {"maximum": 1920}`. The second cap.
  `contracts/` holds no third — verified. Record both; change neither here.
- `docs/references/FreeCAD/src/Mod/TechDraw/Gui/AppTechDrawGuiPy.cpp:56,59` -- `exportPageAsPdf` /
  `exportPageAsSvg` registered in the **Gui** module: page export is GUI-only.
- `docs/references/FreeCAD/src/Mod/TechDraw/App/AppTechDrawPy.cpp:126-190` -- headless App module:
  `viewPartAsSvg`, `projectToSVG`, `writeDXFPage`, `makeExtentDim`, `makeDistanceDim`. This is the
  headless path the spike verdict rests on.
- `tests/infc/` -- runs under `FreeCADCmd` with stdlib `unittest` via `run_tests.py`. The TechDraw
  probe belongs here. `tests/external/` is pytest and cannot import FreeCAD.
- `docs/decisions/` -- decision-note location; `013-g2-eight-op-types.md` is the format precedent.

## Tasks & Acceptance

**Execution:**
- [ ] `docs/decisions/0NN-headless-techdraw-export.md` -- record the spike verdict: page export is
      GUI-registered (`AppTechDrawGuiPy.cpp:56,59`), headless offers view-level SVG only
      (`viewPartAsSvg`, `projectToSVG`) plus `makeExtentDim`/`makeDistanceDim` -- so 4.3 must compose
      a page from view-level SVG rather than call a page exporter. Cite file:line for every claim.
- [ ] `tests/infc/test_techdraw_probe.py` -- executable spike proof under `FreeCADCmd`: assert
      `TechDrawGui` is unavailable, that `TechDraw.projectToSVG` / `viewPartAsSvg` produce non-empty
      SVG for a known solid, and that a dimension helper is callable. Makes the verdict falsifiable
      rather than a prose claim.
- [ ] `benchmarks/g3/README.md` -- document the tree, the 20-spec provenance basis, any declared
      assertion-vocabulary extension with its reason, the fault-suite counts, and the seal caveat.
- [ ] `benchmarks/g3/gate.yaml` -- declarative mirror of the G3.1–G3.7 criteria with `pass_rule` and
      `cited_validators` per criterion, `actor:` + `visual_judge:` blocks (distinct model ids),
      `required_tokens: [spot_audit]`, `verdict.heldout: sealed`.
- [ ] `benchmarks/g3/dev/<case>/case.yaml` ×20 -- 20 specs with compiled assertions and declared
      anchor frames. Each `expect` value derived analytically, with its derivation as a comment.
- [ ] `benchmarks/g3/fault-injection/corrupted-plan/` -- 10 corrupted-plan cases plus clean controls,
      each declaring `targets_validator` and its `expectation` (`DETECT` / `PASS_CLEAN`). Define and
      document the corruption taxonomy — no planning document enumerates it.
- [ ] `benchmarks/g3/fault-injection/visual-judge/` -- planted visually-wrong parts (mirrored,
      missing flange, wrong-face feature, wrong proportions, wrong-dimension-callout drawing) plus
      discriminating clean controls.
- [ ] `benchmarks/g3/fault-injection/assertions/` -- planted assertion faults per
      `verification-design.md` §9: missing hole, wrong diameter, mirrored pattern, 0.5 mm spacing error.
- [ ] `benchmarks/g3/judge.py` -- stub judge returning the schema-validated
      `{pass, findings:[{view, observation, severity}]}` verdict shape, failing honestly with
      `visual.unavailable`. The seam 4.4 replaces with a real vision client.
- [ ] `benchmarks/g3/fault-injection/score_g3_validators.py` -- scorer computing sensitivity /
      false-alarm + Wilson CI, writing `not_scored` reasons rather than fabricated zeros.
- [ ] `benchmarks/runner.py` -- register G3 at the four points named in the Code Map.
- [ ] `benchmarks/_registry/provenance/g3-*.yaml` -- one manifest per shipped artifact.
- [ ] `benchmarks/g3/heldout/` -- author, then seal with the operator-held key **before first
      commit**. Only `SEAL.json` + `heldout.tar.enc` may ever be committed.
- [ ] `tests/external/test_g3_gate.py` -- pin the invariants: every `fn` is declared, every case
      names a manifest, `heldout/` holds only the sealed pair, and every criterion fails honestly.
- [ ] `tests/uat/testcases/TC-16-techdraw-capability-boundary.md` -- UAT scenarios in the suite's
      Given/When/Then form, executed by the agent against the live GUI with `cua-driver`: confirm
      `TechDrawGui` IS importable in the GUI process while absent under `FreeCADCmd`, and that the
      headless view-level SVG path produces the same projection the GUI shows. The spike verdict is a
      claim about what FreeCAD exposes where, so it must be checked against the running application,
      not only the vendored source. Agent performs the visual check itself; never trust the MCP
      result alone.
- [ ] `tests/uat/APPENDIX-A-deferred-coverage.md` -- update the four Epic 4 rows to state what 4.1
      actually landed (benchmark data + spike verdict, still no shipped tool), so the table keeps
      distinguishing "untested" from "broken".
- [ ] `tests/uat/coverage-matrix.md` -- add the TC-16 row.

**Acceptance Criteria:**
- Given `benchmarks/g3/`, when inspected, then 20 specs carry compiled assertion sets and declared
  anchor frames, dev and held-out are split, held-out is sealed, and 10 corrupted-plan cases exist.
- Given `uv run python -m benchmarks.runner run G3`, when no Phase 3 implementation exists, then
  every criterion fails honestly naming the missing actor, and no pass rate is reported.
- Given `uv run python -m benchmarks.runner run G3 --exit` with no `FREECAD_BUDDY_UNSEAL_KEY`, when
  invoked, then it refuses to unseal and exits 2.
- Given `python scripts/check_provenance.py`, when run over the new tree, then it exits 0.
- Given the assertion fault suite, when scored, then sensitivity and false-alarm are computed over the
  cases actually run, and any unmeasurable validator records a `not_scored` reason.
- Given `tests/infc/test_techdraw_probe.py` under `FreeCADCmd`, when run, then the headless TechDraw
  capability boundary is asserted executably and matches the decision note.

## Implementation Notes

**Seal key deviation, recorded not hidden.** The frozen block requires an operator-held key. The
operator approved this story for unattended overnight execution and is unavailable for a key
ceremony, so the held-out split is sealed with a **machine-generated key written outside the
repository** (`~/.freecad-buddy-g3-unseal.key`), matching G2's replacement mechanism. The DW-99
protection that matters is preserved in full: no held-out plaintext is ever committed. The weaker
property is that the set is not protected against whoever holds the key. State this in
`benchmarks/g3/README.md` exactly as `benchmarks/g2/README.md` states its own equivalent limit, and
log a deferred-work entry so the operator can re-seal with a human-held key. Do not silently claim
an operator-held seal.

**No commits.** Leave all work in the working tree. The operator approves every commit.

## Spec Change Log

## Review Triage Log

## Design Notes

**Why the spike verdict is already known.** Read from vendored FreeCAD source rather than guessed:
`exportPageAsSvg` and `exportPageAsPdf` are registered in `AppTechDrawGuiPy.cpp:56,59` — the **Gui**
module — while the headless App module (`AppTechDrawPy.cpp:126-190`) exposes only view- and
shape-level output. The design in `verification-design.md` §7a assumes "export page to PNG/SVG",
which no headless entry point provides. The task is therefore to *prove and record* the boundary, so
4.3 composes a page from `viewPartAsSvg` output instead of discovering this mid-implementation.

**Why the judge is a stub here.** `g1/` landed its gate with a deterministic grader and `g2/` with
deterministic assertions, both before the code they grade existed. No repo code sends an image to a
model API today, so a live vision judge is 4.4's work. The value 4.1 delivers is the fault cases and
the verdict schema — authored before the judge exists, which is the whole point of an entry gate.

**Two render caps, recorded not changed.** `usecases/screenshot.py:34` and
`hosts/tool_catalog.py:202-203` both pin 1920 px; `contracts/` has no third. The judge's ≥2048 px
floor needs both raised, which is 4.3/4.4 work.

**The DW-99 trap.** G2's held-out split was burned because plaintext `case.yaml` files were committed
before sealing and remain readable in git history. Authoring must be followed immediately by sealing,
with no intermediate commit.

## Verification

**Commands:**
- `python scripts/check_provenance.py` -- expected: exit 0, every new artifact has a manifest
- `python scripts/check_imports.py` -- expected: exit 0, no ring violation
- `uv run python -m benchmarks.runner run G3` -- expected: exit 1, every criterion fails honestly
- `uv run python -m benchmarks.runner faults G3` -- expected: runs; scores or explicit `not_scored`
- `uv run python -m benchmarks.runner run G3 --exit` (no key) -- expected: exit 2
- `uv run pytest tests/external/test_g3_gate.py` -- expected: pass
- `python tests/run_tests.py` (under the H1 `fcb` env, with the documented `PYTHONPATH` patch)
  -- expected: TechDraw probe passes; baseline before this story was 614 tests OK (skipped=1)

**Manual checks (if no CLI):**
- `benchmarks/g3/heldout/` contains exactly `SEAL.json` and `heldout.tar.enc` — no readable case file,
  and `git log -p benchmarks/g3/heldout/` shows no plaintext case content in any commit.
- **UAT run** via `manual-testing` + `cua-driver` against the live GUI: execute
  `tests/uat/testcases/TC-16-techdraw-capability-boundary.md`, write results under
  `tests/uat/run/<date>-<nn>/`, and record any defect found in that run's `bugs.md`. Preconditions:
  no FreeCAD process running and no document open at start. The agent inspects the rendered result
  visually and reports what it saw — an MCP response is evidence, not proof.
