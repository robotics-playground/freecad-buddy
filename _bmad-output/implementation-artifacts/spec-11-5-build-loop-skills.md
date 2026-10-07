---
title: 'Build-loop skills'
type: 'feature'
created: '2026-10-07'
status: 'done'
baseline_commit: 'f3be4b76cd53201d0e7fd89e03d90d405b41a1ee'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/skills-structure-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Skills make the agent verify per feature: `verification-thinking/SKILL.md:68` asks a screenshot for "every part whose geometry changed", and 19 references in 8 skill files send the agent to `verify_references` and `verify_fingerprint`, tools that do not exist. Session `0320ba38` took 44 screenshots, 21 `verify_sketch` and 11 `verify_shape` calls that repeated checks the mutation result already reported, and edited the live model through headless scripts 31 times.

**Approach:** Rewrite skill text so the agent reads the mutation result per feature and verifies per milestone. Point every stale reference to the shipped result fields. Add plan-shape, live-model and derived-piece rules. Set an 800 px default screenshot size.

## Boundaries & Constraints

**Always:**
- Field names match the shipped wire: `structured_content.mutation.{post_verify, changed, fingerprint_before, fingerprint_after, rolled_back}`; `post_verify.{passed, explanation, recompute_clean, is_valid, fully_constrained, tnp_audit}`; `tnp_audit.{status: CLEAN|FLAGGED|UNSUPPORTED, counts, findings}` (findings non-PASS only: `BROKEN`, `REPOINTED`, `DROPPED`, `UNSUPPORTED`, `RE_BASELINED`); sketch tools add `structured_content.sketch_state.{fully_constrained, dof, ...}`.
- `UNSUPPORTED` stays "not clean" everywhere it is said today.
- Every `SKILL.md` keeps its 4 H2 sections in order and ≤ 1,500 words (front matter excluded).
- Worked examples match FreeCAD behavior: in a PartDesign body each feature's `Shape` is cumulative, so a change also lists every later feature and the body in `changed`.

**Never:**
- No change to `src/`, schemas or tool behavior. No new MCP tool.
- No AI workflow in code: rules live in skill text only.
- Never open `benchmarks/*/heldout`.
- No Story 6.1 rules in the shape check (front matter, description, cross-skill links).

**Decisions (human, 2026-10-07):**
- Build `scripts/check_skill_shape.py` with the AC8 subset only: exactly the H2s `## Scope`, `## Decision Rules`, `## Worked Examples`, `## Anti-Patterns`, in that order, each non-empty; ≤ 1,500 words with front matter excluded. Add a pytest and a CI step. Story 6.1 extends it.
- "One commit per milestone" = `document_save`, then a version-control commit of the `.FCStd` and the plan file, when the user's project uses version control.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean tree | 15 current skills | exit 0, no output | N/A |
| Missing / extra / reordered H2 | `SKILL.md` with `## Examples` | exit 1; line names file, rule, found headings | N/A |
| Empty section | H2 followed by next H2 | exit 1; names file and section | N/A |
| Too long | body 1,501 words | exit 1; names file and measured count | N/A |
| Front matter long | 400-word front matter, body ≤ 1,500 | exit 0 | N/A |

</frozen-after-approval>

## Code Map

- `skills/verification-thinking/SKILL.md` -- `:56-60` `verify_fingerprint` rule; `:65-67` `verify_references` rule; `:68-72` screenshot rule (AC1 text edit); worked examples `:104`, `:110`; anti-pattern `:131`. 1,254 words now.
- `skills/verification-thinking/references/snapshot-packet-sizing.md` -- no size today. `query_screenshot` input `view.width` / `view.height` default 1920, max 1920 (`hosts/tool_catalog.py:202-203`). AD-21 review floor ≥ 2048 px (spine `:118`, `:200`) applies to review-directed images (TechDraw / visual-judge set), not to `query_screenshot`.
- `skills/freecad-sketcher/SKILL.md` -- `:35-38` `verify_sketch` done-rule; `:65`, `:110` stale refs; examples `:82`, `:91`.
- `skills/freecad-scripting-idioms/SKILL.md` -- `:72-80` headless fallback "on the closed document"; add the live-model ban next to it.
- `skills/design-decomposition/SKILL.md` -- add plan-shape and derived-piece rules; stale ref `:122`. 1,185 words now.
- Stale refs, rest: `freecad-datums-references/SKILL.md:54,72,87`, `freecad-datums-references/references/part-local-origin-defaults.md:58,61`, `freecad-troubleshooting/SKILL.md:53,66`, `freecad-troubleshooting/references/symptom-cause-fix.md:68`, `parametric-patterns/SKILL.md:54,58,79`. AC5 says 9 files; the tree has 8.
- Verify tools that exist: `verify_shape`, `verify_sketch`, `verify_recompute`, `verify_export_step`, `verify_export_stl`.
- Script test style: `tests/external/test_check_imports.py` (`sys.path` insert of `scripts/`, fixture trees in `tmp_path`).

## Tasks & Acceptance

**Execution:**
- [x] `skills/verification-thinking/SKILL.md` -- build-loop rule (per feature / per milestone / after outside change); `:68-72` "every milestone"; replace stale refs -- AC1, AC5.
- [x] `skills/verification-thinking/references/snapshot-packet-sizing.md` -- "Size" section: `view.width`/`view.height` 800 by default; larger only for a review-directed image under the AD-21 floor -- AC6.
- [x] `skills/freecad-sketcher/SKILL.md` -- `sketch_state` is the AD-8 signal; `verify_sketch` for a sketch changed outside the typed tools -- AC2, AC5.
- [x] `skills/freecad-scripting-idioms/SKILL.md` -- live-model ban -- AC3.
- [x] `skills/design-decomposition/SKILL.md` -- plan shape; derived pieces with the drawer evidence -- AC4, AC7, AC5.
- [x] Other 5 files in Code Map -- stale refs -- AC5.
- [x] `skills/design-decomposition/SKILL.md` -- milestone close = `document_save` + version-control commit when the project has one -- AC4.
- [x] `scripts/check_skill_shape.py` -- stdlib; `check_tree(skills_dir) -> list[str]` + `main()`; word = whitespace-split token of the body after the closing `---` -- AC8.
- [x] `tests/external/test_check_skill_shape.py` -- I/O matrix cases in `tmp_path`, plus real tree clean -- AC8.
- [x] `.github/workflows/ci.yml` -- step "Skill shape (AD-15)" after "Provenance gate" -- AC8.

**Acceptance Criteria:**
- Given `grep -rn "verify_references\|verify_fingerprint" skills`, then no match.
- Given the edited skills, then each Story 11.5 AC1-AC7 statement is present, with the field paths above.
- Given every `SKILL.md`, then the shape check passes (4 sections, ≤ 1,500 words).

## Implementation Notes

## Spec Change Log

## Review Triage Log

- Pass 1: `tnp_audit` text wrong — `RE_BASELINED` listed as flagging, status `UNSUPPORTED` missing, and `post_verify.passed` stays true on an `UNSUPPORTED` audit (blind, edge-case) -- medium, patch: `tnp_guard.py:452` excludes `RE_BASELINED` from `failing`; `transaction.py:301-310` returns `passed` True when status is `UNSUPPORTED`.
- Pass 1: empty `changed` read as proof; `fingerprint_*` are `{digest, serializer}` objects and can be null (verification-gap, edge-case, blind) -- medium, patch: `result_projection.py:79` returns `[]` when either record is `None`; `contracts/mutation.py:90`.
- Pass 1: `post_verify.is_valid` / `fully_constrained` may be `"not_measured"` or `None`; `sketch_state.readable` false has no `dof` (verification-gap, edge-case, blind) -- low, patch: `contracts/mutation.py:28-31,57-61`, `sketches.py:502`.
- Pass 1: sketcher DoF = 2 example teaches reading `dof` across typed calls; a typed sketch call with `dof > 0` fails `verify_sketch` and rolls back, so the state is an outside change (blind, edge-case) -- medium, patch: `verify.py:320` hard-fails `dof > 0`.
- Pass 1: no rule for a failed mutation (`rolled_back`, `rollback_proven`) (blind) -- medium, patch: per-feature rule names only success fields.
- Pass 1: "after an outside change call `verify_*` again" — no tool re-runs the reference audit or the before/after comparison (edge-case, blind) -- medium, patch: tool catalog has no such tool; text must say those stay unverified.
- Pass 1: 800 px section points to a ≥ 2048 px floor `query_screenshot` cannot produce (max 1920) (edge-case, blind) -- medium, patch: `tool_catalog.py:202-203`.
- Pass 1: `sketch-strategy/SKILL.md:60,76` still says verify with `verify_sketch` after building, contradicting the sketcher rule (blind) -- medium, patch.
- Pass 1: derived-pieces rule gives no executable path; no typed tool makes `Part::Common`, and the live-model ban forbids a script on the open document (blind) -- medium, patch: point to the closed-document fallback.
- Pass 1: skill `version` not bumped although `skills-structure-design.md:103` requires it on any body change (implementer note) -- medium, patch: ablation results cite skill versions.
- Pass 1: design docs still say `check_skill_shape.py` is not built (implementer note) -- low, patch: `skills-structure-design.md:51,166`, spine AD-15, `project-structure.md`.
- Pass 1: "`changed` names every object whose geometry moved" overclaims; it compares mass properties only (blind) -- low, patch: `contracts/fingerprint.py:103-108`.
- Pass 1: `verification-thinking` description triggers "after a mutation" (blind) -- low, patch: contradicts the per-milestone rule.
- Pass 1: milestone close does not require its checks to pass first (blind) -- low, patch.
- Pass 1: no test for the missing-root exit 1 or for a deleted section (verification-gap, blind) -- low, patch: two direct tests.
- Pass 1: test module docstring cites the story; fixture directories named `target` (blind) -- low, patch: `commenting.md` forbids provenance; `target` is reserved for the system under test.
- Pass 1: `## ` inside a code fence read as H2 (edge-case, blind) -- low, rejected: no `SKILL.md` has a fence; fix adds a branch.
- Pass 1: unclosed front matter or UTF-8 BOM counts front matter as body (edge-case, blind) -- low, rejected: no skill file has either; fix adds a branch.
- Pass 1: skill directory without `SKILL.md`, or a root with no skills, exits 0 (edge-case, blind) -- low, rejected: CI uses the repo root, and the real-tree test pins it; front-matter and layout rules belong to Story 6.1.
- Pass 1: section holding only a `###` heading or a comment counts as non-empty (edge-case) -- low, rejected: unlikely; fix adds a branch.

## Verification

**Commands:**
- `grep -rn "verify_references\|verify_fingerprint" skills` -- expected: no output.
- `uv run python scripts/check_skill_shape.py` -- expected: exit 0.
- `uv run pytest tests/external` -- expected: green.
- `uv run ruff check .` -- expected: clean.
