# Visual judge rubric — G3.7

**Written before any fixture image was rendered or seen.** A rubric authored after looking at the
images is fitted to them, which is the same post-hoc tuning AD-19 forbids for assertions. The
per-case verdicts are recorded separately in `GRADING-<date>.md`; this file is the standing rule.

## The question the judge answers

Given the standard visual set for one part — a 3D iso render plus the dimensioned front/top/right
sheet — and the spec text the part was built from:

> Does the rendered part match what the spec asks for?

Output shape is fixed by `benchmarks/g3/judge.py`:
`{pass: bool, findings: [{view, observation, severity}]}`. `view` ∈ {iso, focus, front, top, right};
`severity` ∈ {blocking, advisory}. A `blocking` finding means `pass: false`.

## Decision rule

**PASS** when every claim the spec makes is visible and correct in the images, and nothing visible
contradicts the spec.

**FAIL** on any of:

- a spec-named feature absent from the part
- a feature present but on the wrong face, edge, or centreline
- proportions that visibly disagree with the spec's stated dimensions
- a handedness that the spec fixes and the part violates
- a dimension callout on the sheet that disagrees with the spec text

## What must NOT cause a failure

These are the false-alarm traps the controls exist to catch. Flagging any of them is a false alarm,
counted against the ≤5 % bar:

- **Camera azimuth, material tone, lighting, background.** The render is a constructed scene; its
  appearance is not the part. Judge geometry against the spec checklist, never pixel similarity to a
  reference image.
- **A mirror on a part whose spec is symmetric.** Handedness is only a defect when the spec fixes a
  hand. A washer mirrored is the same washer.
- **Drawing style** — line weight, label placement, sheet layout, the absence of witness lines and
  arrowheads. The sheet's callouts are drawn by the compositor as `parameter = value` text
  (DW-118); that is the shipped format, not a defect in the part.
- **Tessellation or edge aliasing** in the iso render.
- **A dimension the spec does not state.** Absence of a callout is not a wrong callout.

## Reading callouts (the `wrong-dimension-callout` case)

The judge reads the callout **as printed** and compares it against the **spec text**. It must not
re-derive the value from the view geometry and then compare against itself — a callout that agrees
with the drawing but disagrees with the spec is exactly the spec→assertion mistranslation this leg
exists to catch, and re-deriving would hide it.

Where a callout and the geometry disagree, that is a blocking finding and the geometry assertions
remain authoritative for the *measurement*; the judge's job is to report the disagreement, not to
resolve it.

## Scoring

```
sensitivity = detected_defects / planted_defects     bar >= 0.95
false_alarm = flagged_controls / clean_controls      bar <= 0.05
```

With 5 planted and 3 controls, a single miss puts sensitivity at 0.800 and a single flagged control
puts false alarm at 0.333. **Neither bar is reachable at this n.** The suite is too small to
*demonstrate* the bars; what it can do is falsify a judge that is obviously broken. Any number
produced here must be quoted with its n and its Wilson CI, and must not be presented as clearing the
AD-13 bar. Raising n is separate work.

## Independence caveat

AD-13 requires the judge not be the actor. An agent that also drove the designer loop is not fully
independent. For this suite the exposure is bounded — the parts were authored before any judge
existed, and the grading is of planted defects against this fixed rubric rather than of the agent's
own output — but any score produced this way carries the caveat rather than claiming clean
independence. A fully independent number needs a separate model or a separate context.

## Rubric staleness

Editing this file invalidates every sensitivity run measured against it, the same hash rule that
governs every other validator in `_registry/validators.yaml`.
