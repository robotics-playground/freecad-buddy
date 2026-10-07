# Reading mutation results

Read this when you read the result of a typed mutation (`sketch_*`, `feature_*`,
`document_*`) per feature. Every mutation already ran the shape, sketch, and reference
checks on full data; the result reports what changed and what failed. All paths below
are under `structured_content`.

## Is the feature clean

A feature is clean only when **all** of these hold:

- `mutation.post_verify.passed` is true.
- `mutation.post_verify.tnp_audit.status` is `CLEAN`. `passed` stays true on an
  `UNSUPPORTED` audit, so read the status separately.
- No `post_verify` field reads `"not_measured"`.
- On a sketch tool: `sketch_state.readable` is true, `sketch_state.fully_constrained`
  is true, and `sketch_state.dof` is 0.

## `mutation.post_verify`

| Field | Reading |
| --- | --- |
| `passed` | false → the mutation failed; see "A failed mutation" |
| `explanation` | the failed step and its cause; null on a pass |
| `recompute_clean` | false → the recompute left an object invalid |
| `is_valid` | false → a touched shape failed `verify_shape`. `"not_measured"` → the check did not run: not a pass; call `verify_shape` |
| `fully_constrained` | `null` → no sketch was involved. `"not_measured"` → the check did not run: not a pass; call `verify_sketch` |
| `tnp_audit` | the post-recompute reference audit; see below |

## `post_verify.tnp_audit`

- `status` is one of `CLEAN`, `FLAGGED`, `UNSUPPORTED`.
- `FLAGGED` → at least one `BROKEN`, `REPOINTED`, `DROPPED`, or `UNSUPPORTED` finding.
- `UNSUPPORTED` → no element map; the audit could not run. Not clean, never a pass.
- `RE_BASELINED` findings are informational and can appear under `CLEAN`.
- `counts` holds one count per verdict; `findings` lists the non-PASS findings only.

## `sketch_state`

Sketch tools add `sketch_state` with the `verify_sketch` grade (the AD-8 sketch
signal): `fully_constrained`, `dof`, and the constraint diagnostics. `readable` false
means the sketch could not be graded and the block carries no `dof` or
`fully_constrained`: not a pass; call `verify_sketch`.

## `mutation.changed` and the fingerprints

- `fingerprint_before` and `fingerprint_after` are `{digest, serializer}` objects.
  Compare `fingerprint_before.digest` with `fingerprint_after.digest`: equal digests
  mean no geometry changed. The digest is the equality test.
- `changed` lists the objects whose mass properties (volume, area, center of mass,
  moments, inertia) differ between the two fingerprints.
- In a PartDesign body each feature's `Shape` is cumulative, so an edit also lists
  every later feature and the body. An *earlier* feature in `changed` is a regression.
- Either `fingerprint_*` can be null (the fingerprint failed). Then `changed` is empty
  and proves nothing: report the regression check as unverified and re-measure.

## A failed mutation

- `passed` false, `rolled_back` true, and `rollback_proven` set → the change is not in
  the model. Read `explanation`, fix the cause, and send the call again.
- `passed` false with `rolled_back` false or `rollback_proven` null → the model
  state is unproven. Stop and report; do not build on it. `changed` then carries
  `before` and `after` mass properties per object to show what was left.
