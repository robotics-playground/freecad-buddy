# Run 13-16-r1: findings

## B1 — TC-20 Given builds an under-constrained sketch (test-case defect, fixed)

- Request: `feature_set_parameters { feature: "Block", parameters: { Label: "Profile" } }` and `feature_set_parameters { feature: "Profile", parameters: { AttachmentOffset: { base: { z: {value: 5, unit: "mm"} } } } }` on the TC-20 build.
- Output: `SPEC_FAILED`, message `verify_sketch failed on Profile (dof=8): sketch.fully_constrained` (`evidence/out-tc20-02-given-v1.json`). The writes rolled back, so the first `document_undo` then undid the build itself.
- Cause: the build call added only four `Coincident` constraints (DoF 8). The AD-5 post-verify checks every sketch the op touches or a touched feature consumes, `src/freecad_buddy/usecases/transaction.py:177` `_involved_sketches` and `:301-321`; the TC-20-01 write touched only the Body, so it passed.
- Cause class: test-case defect. The product behaves as the bracket is designed.
- Fix: the TC build now adds Horizontal, Vertical and four distance constraints and returns `('built', sk.FullyConstrained)`; the Given checks `('built', True)`. The TC-20-02 visual Then no longer fits the view before the after capture (a fit hides a uniform move) and names how to expand `Body` in the tree.
- Product note (not a defect of this Story): a `Label`-only rename of a feature whose sketch is under-constrained fails `SPEC_FAILED`. Same rule for every bracketed write.
