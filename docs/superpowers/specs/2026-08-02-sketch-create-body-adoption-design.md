# `sketch_create` body adoption — DW-102

## Problem

`sketch_create` adds its sketch with `document.addObject` and never places it in a Body. A sketch
consumed as a pad profile therefore lives outside the Body that pads it, and FreeCAD reports:

```
PartDesign::Pad: Link(s) to object(s) 'Prof' go out of the allowed scope 'Block'.
Instead, the linked object(s) reside within 'N/A'.
```

PartDesign link properties are `LinkScope::Child` (`App/PropertyLinks.cpp`), meaning a link is
expected to resolve inside the owner's group. The profile does not, so the check fires.

## What the defect actually costs

Measured on FreeCAD 1.1.1, comparing two pads that differ only in whether the profile was adopted:

| | not adopted | adopted |
| --- | --- | --- |
| pad `isValid()` / `State` | True / `Up-to-date` | True / `Up-to-date` |
| pad volume | 500.0 | 500.0 |
| body `Tip` | the pad | the pad |
| `body.Group` | `['Block']` | `['Prof', 'Block']` |

Saved and reopened, the unadopted case still recomputes clean, the profile link still resolves,
and the volume is unchanged.

So this is **not** a geometry defect. The cost is structural: the sketch sits at document root
rather than nested in the Body, which is not the tree a user expects. It is worth fixing because
`feature_body_create` made this path reachable by an MCP client for the first time — before it,
no client could obtain a Body at all.

**The warning itself is not assertable, so it is not the acceptance criterion.** Measured on
FreeCAD 1.1.1: it does not reach the addon log, `getStatusString()` or `State` — PartDesign emits
it to the GUI Report View only. Every test here therefore asserts `Body.Group` membership, which
is the observable consequence of the same change.

## Scope

**In:** an optional `body` argument on `sketch_create`. When given, the new sketch is adopted into
that Body. When omitted, behaviour is exactly as today.

**Out:**

- Adoption inside the extrude tools. Considered and rejected: it would reparent an object the
  caller never named, which the preview diff would then have to explain, and it hides where the
  structure came from. The explicit argument mirrors how every `feature_*` tool already names its
  body.
- Moving an existing sketch into a Body after creation. No caller needs it; `YAGNI`.

## Behaviour

```
sketch_create(doc, name, plane=None, face=None, body=None) -> ResultEnvelope
```

`body` is optional. Given, it must name an existing `PartDesign::Body`; the sketch is added to it
with `Body.addObject(sketch)`, which is the same call the in-FreeCAD test fixture's `_sketch`
helper already makes and the same one the GUI makes.

Adoption applies to **both** creation paths — the base-plane branch and the face-attached branch.
Each currently returns early, so the call belongs before those returns, not after one of them.

`Body.addObject` also advances the Body's `Tip` for a solid feature. A sketch is not a solid
feature, so adopting one leaves `Tip` untouched — confirmed by the measurement above, where the
adopted Body's `Tip` is still the pad.

## Failure behaviour

| Input | Result |
| --- | --- |
| `body` names nothing | `INVALID_INPUT`, pre-bracket |
| `body` names a non-Body object | `INVALID_INPUT`, pre-bracket |
| `body` omitted | unchanged: sketch at document root, no error |

Both rejections happen in `precheck`, so no snapshot is written and no transaction opens, matching
every other malformed-input path in the module.

## Structure

`sketches.py` has no Body resolver. It will get a local one rather than importing `features.py`:
that module does not import `sketches`, so there is no cycle today, but taking a dependency on it
for one five-line check would couple two tool families for no reason.

```python
_BODY_TYPE = "PartDesign::Body"

def _resolve_body(document, name):
    """Return the PartDesign Body named ``name``, or raise ValidationError."""
```

This duplicates `features._resolve_body` in shape. That is accepted deliberately: the alternative
is a shared module for one predicate, and the two rings already keep their own resolvers for
sketches and features respectively.

## Testing

In-FreeCAD (`tests/infc/test_sketch_tools.py`), each falsifiable by reverting the change:

1. A sketch created with `body` is in that Body's `Group`; without `body` it is not.
2. A face-attached sketch created with `body` is also adopted — pins that the second branch is
   covered, which a fix applied to only the base-plane path would fail.
3. Adopting a sketch does not change the Body's `Tip`.
4. An unknown `body` is rejected pre-bracket, via `assert_rejected_pre_bracket`.
5. A `body` naming a non-Body object is rejected pre-bracket.

External: `sketch_create`'s input schema carries `body` as an optional string, and `body` is not
in `required`.

## Risks

One more optional argument on an existing tool. The default path is unchanged, so no existing
caller or test is affected — the new argument is additive, and every current call site continues
to produce exactly the tree it produces today.
