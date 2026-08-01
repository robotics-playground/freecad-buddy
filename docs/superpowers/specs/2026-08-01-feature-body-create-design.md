# `feature_body_create` — make the Phase-2 feature surface reachable

## Problem

The ten `feature_*` tools each require a `body` argument naming a `PartDesign::Body`. Nothing in
the 43-tool MCP surface creates one, so an agent holding only MCP access can never invoke any of
them.

Measured on FreeCAD 1.1.1, 2026-08-01:

- `feature_pad` against a fresh document returns `INVALID_INPUT: unknown object in body: Body`.
- All five golden models under `benchmarks/g0/golden-models/` contain only `Part::Feature`; none
  contains a `PartDesign::Body`.
- No tool name across the surface creates one; `features.py:181` `_resolve_body` only resolves.

The G2 dev split hides the gap rather than covering it: its cases open a pre-built fixture, and
those fixtures have no Body either, so **35 of the 40 dev cases** (every one except the five
`sketch` cases) are undriveable for this reason alone — independent of the missing command
resolver that G2.1 already reports.

## Scope

**In:** one new mutation tool, `feature_body_create`, that creates an *empty* `PartDesign::Body`.

**Out, deliberately:**

- Adopting an existing solid as `BaseFeature`. It would unblock the feature tools against the
  existing `Part::Feature` golden models, but it carries its own TNP reference to guard and is
  not needed to close the gap: a sketch plus a pad builds a solid from scratch.
- Repairing the 35 G2 dev cases. Tracked separately, because how they should get a Body (rebuild
  the fixtures, or have each case call this tool) is its own decision.

## Behaviour

```
feature_body_create(doc, name) -> ResultEnvelope
```

`name` is the intent-bearing name, becoming both the object `Name` and its `Label`, matching
every other feature tool.

Measured properties of an empty Body that the design depends on:

| Property | Value | Consequence |
| --- | --- | --- |
| `isValid()` | `True` | `post_verify`'s validity sweep passes it unchanged |
| `State` | `['Up-to-date']` | no recompute error to report |
| `Shape` | null | the fingerprint's existing null-shape skip covers it |
| `Tip` / `Group` | `None` / `[]` | nothing to grade until a feature is added |
| duplicate `name` | FreeCAD returns `Bracket001` | must be rejected, never silently renamed |

The duplicate-name row is the one real hazard: FreeCAD uniquifies rather than raising, so an
unchecked collision hands back a different object than the caller asked for. `_name_available`
already guards this for the sibling tools and is reused here.

Creating a Body also brings `App::Origin` and its `App::Plane`/`App::Line`/`App::Point` children.
Both the fingerprint (`_DATUM_TYPE_PREFIXES`) and the render/tree-summary skip lists already
exclude those types, so **no change is needed there** — recorded so a later reader does not
"fix" a non-problem.

## Structure

The tool goes in `usecases/features.py` beside its siblings and runs the standard bracket through
`_feature_mutation`, so it inherits preview, confirm, snapshot, rollback proof and the audit
record with no new machinery:

- `precheck` — `_name_available(document, name)`; reject a name FreeCAD would rewrite.
- `op` — `document.addObject("PartDesign::Body", name)`, verify `feature.Name == name`, set
  `Label`, return `[name]`.

It does **not** reuse `_add_feature`: that helper calls `body.addObject(feature)` to insert a
feature *into* a Body, which has no meaning when the Body is the thing being created.

Registration follows the existing path: a spec in `hosts/tool_catalog.py` with a hand-authored
input schema (`doc`, `name`, `confirm`), listed as a mutation so the confirm gate applies and it
stays out of the read-only assistant profile.

## Failure behaviour

| Input | Result |
| --- | --- |
| name already in use | `INVALID_INPUT`, pre-bracket, no snapshot |
| name FreeCAD would rewrite (e.g. `1Body`) | `INVALID_INPUT` |
| missing `name` | `INVALID_INPUT` |
| no confirm on a gated host | `INVALID_INPUT`, before any document write |

## Testing

In-FreeCAD (`tests/infc/test_feature_tools.py`), each falsifiable by reverting the change:

1. A created Body has `TypeId == "PartDesign::Body"`, is valid, and reports `Tip is None`.
2. `feature_pad` succeeds against a Body this tool created — the end-to-end proof that the gap is
   closed, and the test that would have caught it originally.
3. A duplicate name is rejected pre-bracket, asserted through the existing
   `assert_rejected_pre_bracket` helper so no snapshot is minted.
4. An unusable name is rejected pre-bracket.
5. The new Body's Origin children do not enter the fingerprint — pins the interaction above.

External: the tool appears in the catalog with a valid input schema and is absent from
`READ_ONLY_PROFILE`, matching the existing per-tool contract tests.

## Risks

The tool surface grows by one, against the standing "no speculative features" rule. Justified by
measurement rather than anticipation: without it ten existing tools are unreachable.

A future `base_feature` argument is additive — an optional property on the same schema — so
deferring it costs no rework.
