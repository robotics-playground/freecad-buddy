---
title: 'Story 3.1: Entry Gate G2.E — Command Benchmark & Mutation Fault Suites'
type: 'story'
epic: 3
story: '3-1-entry-gate-g2e-benchmark-fault-suites'
created: '2026-07-31'
status: 'done'
final_revision: '8853c00'
review_loop_iteration: 0
followup_review_recommended: true
---

# Story 3.1: Entry Gate G2.E — Command Benchmark & Mutation Fault Suites

> **As** a project owner, **I want** the 40-command benchmark with per-command geometry
> assertions and the mutation fault suites landed before any mutation tool exists, **so that**
> Phase 2 code is born graded (AD-19).

## Acceptance Criteria

1. **Given** `benchmarks/g2/` **When** inspected **Then** 40 commands × 8 op types with
   assertions authored independently of implementation, dev/held-out split sealed, and fault
   cases covering wrong-parameter runs, the 5 TNP-provoking scenarios, the dress-up silent-drop
   trap, coincidental-hash, and #6031 rollback-boundary patterns
2. **Given** the stub bridge **When** `gate run g2 --stub` executes **Then** every criterion
   fails honestly

## What shipped

`benchmarks/g2/gate.yaml` mirrors the six G2 criteria from `phase-gates.md`; the runner reads it
and never hardcodes them. `KNOWN_GATES` gains `G2`, and `seal_command` is generalised from
G1-only to `_SEALABLE_GATES = {G1, G2}`.

**dev/** — 40 command cases partitioned 5-per-type across the eight op types of decision 013.
**heldout/** — 8 cases, one per op type, with no command text shared with the dev split.
**fault-injection/** — 28 cases in five suites: `tnp/` (5 scenarios + 3 controls),
`dressup-drop/` (1 + 2), `coincidental-hash/` (1 + 1), `rollback-boundary/` (2 + 2),
`wrong-parameter/` (8 + 3). 17 planted defects, 11 clean controls.

Every expected value is derived analytically from the target G0 golden model's known geometry and
carries its derivation inline; nothing was captured from a verify tool (AD-13/AD-19). Commands
are dimensioned to fit their model.

Four fault cases declare `must_not_be_caught_by`, pinning the layer that must *not* detect them,
so a Layer-0-only guard cannot score 100 % on the TNP suite.

`tests/external/test_g2_benchmark.py` is the structural self-check (161 assertions).

## Decisions taken

- **decision 013** — the eight op types (`sketch`, `pad`, `pocket`, `revolve`, `hole`, `dressup`,
  `pattern`, `mirror`). "40 commands × 8 op types" is asserted by `phase-gates.md`, `epics.md`,
  `intent.md` and `SPEC.md` and enumerated by none of them; 013 is the enumeration.
- **TNP scenarios live in `fault-injection/`**, resolving the disagreement between
  `validation-harness-design.md:29` and `phase-gates.md:65`, so planted faults never contaminate
  the G2.1 pass rate.
- **`check_provenance` gains two exemptions**, both requiring the state to be *declared*:
  `fixture: pending` and a case reusing a committed golden model via `inputs.document`. A case
  that merely omits its fixture is still flagged.

## Verification

- `uv run pytest tests/external` — `621 passed`
- `python scripts/check_imports.py` — `check_imports OK`
- `uv run python scripts/check_provenance.py` — `check_provenance OK`
- `uv run python -m benchmarks.runner run G2 --run <id>` — 6/6 `FAIL (verdict=INVALID_INPUT)`,
  which is AC 2
- Falsification: unbalancing an op type, removing a TNP scenario, and undeclaring a pending
  fixture each fail exactly one check and no others.

## Residual risk

- The held-out split is authored but **not yet sealed**: `seal` requires
  `FREECAD_BUDDY_UNSEAL_KEY`, a human-held key. Sealing is an operator action before the G2 exit
  run (Story 3.8), tracked there.
- Fault fixtures are declared `pending`: the mutation runtime that can plant them lands in Story
  3.2. Each case specifies the fault precisely enough to build the fixture against.
- **Assertion vocabulary is split and declared.** Five `fn` names are `verification-design.md`
  §7.2 primitives (`is_valid_solid`, `count_cylindrical_holes`, `hole_spacing`, `hole_through`,
  `expect_volume`). Three are a declared G2 extension with no §7.2 equivalent
  (`expect_solid_count`, `expect_sketch_fully_constrained`, `expect_sketch_geometry_count`) —
  documented in `benchmarks/g2/README.md` and pinned by `test_assertion_fns_are_declared`.
  Whoever implements the grader must add those three to the vocabulary or reconcile the cases.
  Two earlier near-miss renames (`expect_is_valid_solid`, `expect_through`) were corrected to the
  real primitive names before commit.
- **`gate.yaml` cites `benchmarks/harness/assertions.py`, which does not exist yet.** It is
  marked `# planned, Story 3.2+` — the path is where the grader must land, not a claim that it is
  present. This is why every criterion currently fails `INVALID_INPUT`.
- **The lifecycle-op exemption from the preview/confirm gate is an interpretation, not a ratified
  decision** (`mcp-tools-design.md` §7 flags it for spine-owner confirmation). Story 3.2 codifies
  it, so it should be confirmed rather than inherited.
- `followup_review_recommended: true` — this story was authored directly rather than through the
  bmad-loop dev/review pair, so it has had no independent adversarial review.
