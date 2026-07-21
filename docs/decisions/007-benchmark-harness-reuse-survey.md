# 007 — Benchmark Harness Reuse Survey (G0.E)

## Decision

The G0 entry-gate harness is a **thin stdlib gate runner** (`benchmarks/runner.py` +
`benchmarks/harness/report_build.py`) built over the Story-1.2 contracts, not an adopted
third-party framework. The runner loads a declarative `gate.yaml`, runs each criterion against
a `StubBridge`, and emits one contracts-owned `ValidationReport` per criterion via
`derive_verdict` (AD-17). PyYAML is the only third-party dependency, and it lives in the
external uv process only (AD-12).

## Surveyed alternatives

- **pytest-as-the-gate-runner.** pytest is already the external test runner. Rejected as the
  *gate* mechanism: the gate verdict must be a pure function over stored `ValidationReport`s
  and human-token artifacts (phase-gates Global-protocol 3–4, harness §3.2), re-runnable by an
  auditing agent without re-executing cases. pytest's pass/fail lives in exit codes and
  captured output, not in a stored, schema-valid report set — grading on exit-code-0 is exactly
  the anti-pattern AD-13/AD-19 forbid. pytest remains the runner for the harness's *own* unit
  tests (`tests/external/test_harness_g0.py`).
- **Existing CAD / ML eval frameworks** (DeepCAD/ABC/Text2CAD lineage, Fusion 360 Gallery
  eval sets, generic LLM-eval harnesses). Rejected: (a) their datasets are provenance-blocked
  for shipping (Onshape creator-copyright / non-commercial ceilings — harness §1.2), usable
  only as non-shipped `oracle-geometry`; (b) they score model *output quality*, not a
  deterministic geometry validator against hand-computed references; (c) they carry heavy
  third-party dependency trees that would violate the in-FreeCAD zero-third-party rule if ever
  pulled toward the bridge.

## Why nothing existing fit

The gate's core contract is unusual: a **mechanically reproducible verdict computed from
contracts-owned reports**, honest-failing against a stub before any tool exists (AD-19), with
provenance-gated hand-authored fixtures (AD-16). No surveyed framework produces the
contracts `ValidationReport` shape or the pure-function verdict; adopting one would mean
wrapping it only to discard its scoring and re-emit our own reports — more surface than the
~150-line stdlib runner it would replace. The contracts layer (Story 1.2) is the reused
component; the runner wraps it, and this survey records why the runner itself is from-scratch
(reuse-before-invention, project-context Workflow rule).

## Drives

- G0.E reuse-survey artifact (phase-gates entry-gate requirement: "reuse survey recorded").
- `benchmarks/runner.py` from-scratch justification.
