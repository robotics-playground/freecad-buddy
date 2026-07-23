# 008 — G1.2 / GS.4 Error-Diagnosis Eval: Tiered n=10 → n=30

## Decision

The Phase-1 error-diagnosis gates (G1.2, and its skill-loaded re-run GS.4) use a **two-tier
eval over a 30-case fixture set**:

1. Author a full **30-case** broken-recompute fixture set (each case naming *the* failing
   object + cause, provenance-manifested like every other benchmark fixture).
2. The gate grades the **first n=10** cases. Pass threshold: **≥ 8/10** for G1.2, **≥ 9/10** for
   GS.4 (skill loaded).
3. **Only a perfect n=10 (10/10)** escalates the gate to the full **n=30** run; the Wilson CI is
   reported on the n=30 result.
4. If n=10 is **below 10/10**, the gate concludes at n=10 with the n=10 Wilson CI, flagged
   low-confidence per AD-14. The remaining 20 cases are not spent.

## Rationale

n=10 alone is statistically weak: an 8/10 point estimate carries a Wilson 95% CI of roughly
49–94%, so a passing gate cannot distinguish a genuinely-good assistant from a lucky-coinflip
one. Enlarging every run to n≈20–30 fixes the confidence but pays 2–3× the grading cost on
every gate execution, including the common case where the assistant is nowhere near the bar.

The tiered rule keeps the cheap path cheap and spends the extra 20 cases only when the assistant
has *earned* statistical scrutiny — a 10/10 at n=10 is the signal that a tighter CI is worth
measuring. Below-perfect runs get a fast, honest low-confidence verdict instead of a full
expensive run they were never going to clear at high confidence.

## Surveyed alternatives

- **Keep n=10 as a flat soft-target (CI attached).** The prior spine posture. Rejected as the
  ceiling: it never produces a high-confidence pass even for a strong assistant, so a genuinely
  good result stays permanently flagged low-confidence.
- **Flat n=30 on every run.** Real confidence, but pays the full grading cost unconditionally —
  most of it wasted on runs that fail the first 10. Rejected as the default; it is exactly the
  escalated tier, gated behind the 10/10 signal.

## Drives

- `benchmarks/g1/` fixture count (author 30, not 10) — story 2-1
  (`2-1-entry-gate-g1e-eval-rubric-grader`).
- The G1.2 / GS.4 gate-runner escalation logic (grade 10, escalate on 10/10, report Wilson CI).
- Resolves the SPEC.md open question ("n=10 enlarged to n≈20–30, or kept soft-target?").
- Consistent across `docs/intent.md` (Phase-1 exit + Skills SMART goal),
  `_bmad-output/specs/spec-freecad-buddy/{SPEC.md, phase-gates.md}`, and
  `_bmad-output/planning-artifacts/epics.md` (Story 2.1 / 2.2 acceptance).
