# 014 — TNP Guard: "Intended Target" Means What the Op Wrote

## Decision

The Layer-1 exemption that spares a reference from a non-PASS verdict is keyed to **the value the
op assigned**, not to the object that owns the reference.

`run_mutation` captures each snapshotted reference's value immediately after the op callable
returns and before `recompute()`. A reference is exempt only when its post-op value equals the one
the op wrote. The `op` callable's return contract is unchanged — it still reports touched object
names, and those names are still used for reporting, but they are no longer the exemption test.

## Rationale

`verification-design.md` §3.2 granted PASS when "the reference was not the mutation's intended
target" without defining the granularity of "target". Story 3.5 implemented it the only way the
available data allowed — `record["owner"] in touched` — and `touched` carries object names only
(`features.py:1571-1574` returns `[target.Name, body.Name]`).

That makes the exemption object-level while the check it guards is property-level, and the
mismatch disables the guard's headline detector:

- `feature_fillet` always reports `Fillet` in `touched`, because it created it.
- `Fillet.Base` — the LinkSubList whose entry count is the *only* detector for the
  `FeatureDressUp.getContinuousEdges` silent edge drop — is owned by `Fillet`.
- So the exemption fires on every fillet, and the count comparison never runs on the one operation
  that produces the defect. Not intermittently: never.

`feature_set_parameters` has the same shape — it exempts every reference the edited feature owns,
so a `Profile` or `UpToFace` that silently re-points during the forced re-solve grades PASS.

The op wrote `Fillet.Base` with four entries. If four entries come back, the op's intent is
satisfied and the reference is genuinely exempt. If three come back, FreeCAD dropped one after the
op wrote it — which is exactly the defect, and comparing against the written value catches it
while an owner check cannot.

## Alternatives considered

**Ops declare `(owner, prop)` pairs.** Change `touched` from names to property pairs so the
exemption is precise by construction. The most explicit fix, and rejected only on cost: it changes
the `op` callable contract in `run_mutation` and touches all ten `feature_*` and eight `sketch_*`
tools, reopening Stories 3.3 and 3.4 after both shipped and passed review. The correctness gain
over the chosen approach is small, because comparing against the written value is already exact.

**Exempt nothing from the DROPPED count check.** Keep the owner-level exemption for re-point
detection but make the entry-count comparison unconditional. Smallest possible change and it does
restore the trap, but a deliberate edge removal — the `dressup-intended-edge-removal` control case
in `benchmarks/g2/fault-injection/dressup-drop/` — would then be reported as a defect, so the
false-positive it creates needs its own discriminator. That is the same granularity problem in a
new place rather than a resolution of it.

## Consequences

- The guard must observe the post-op, pre-recompute state. `run_mutation` gains one capture point;
  no code outside the mutation runtime changes.
- The exemption is now falsifiable: a test can write a known value, mutate the reference behind the
  guard's back, and assert the verdict is not PASS. An owner-level exemption could not be tested
  this way, which is part of why the defect survived a green suite.
- `verification-design.md` §3.2 carries the definition inline, so the next implementer cannot
  re-derive the object-level reading from the same text.

## Provenance

Found by the two blind reviewers of Story 3.5 independently, each ranking it their most severe
finding. Verified before acting: `features.py:1571-1574` confirms the object-level `touched`, and
`verification-design.md:163` confirms the undefined granularity. The reverted Story 3.5
implementation was fully green (339 infc tests, 722 external, all six `RefVerdict` members
covered) — it matched the specification exactly. The specification was wrong.
