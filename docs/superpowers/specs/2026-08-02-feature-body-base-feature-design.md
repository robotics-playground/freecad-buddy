# `feature_body_create` base-feature adoption — DW-103

## Problem

35 of the 40 G2 dev cases (every op type except the five `sketch` cases) name a `body` their
fixture does not contain. All five golden models hold a single `Part::Feature` and no
`PartDesign::Body`, so those cases cannot be driven even once a command resolver exists.

`feature_body_create` does not resolve this on its own: it creates an **empty** Body, while these
cases operate on the fixture's existing solid. The arithmetic in the case files proves it —
`g2-dev-006-pad` expects `6640.0`, which is the box's `6000.0` plus the pad's `640.0`. Every
volume-asserting case follows the same shape:

| case | fixture | fixture volume | expected |
| --- | --- | --- | --- |
| `g2-dev-006-pad` | box-10-20-30 | 6000.0 | 6640.0 |
| `g2-dev-015-pocket` | box-10-20-30 | 6000.0 | 5784.0 |
| `g2-dev-009-pad` | cylinder-r5-h20 | 1570.8 | 1617.5617 |
| `g2-dev-008-pad` | box40-hole-r5 | 15214.6 | 21786.2833 |

## Solution

Add the optional `base_feature` argument that the original `feature_body_create` design
deliberately deferred. Given, the new Body adopts that object as its `BaseFeature`, so subsequent
features modify the adopted solid.

Verified on FreeCAD 1.1.1 before designing: a Body with `BaseFeature = Box` reports the fixture's
6000.0, its `Tip` is the `BaseFeature`, and a 6×12×5 pad on it yields exactly **6360.0** — the
fixture-plus-feature arithmetic the cases encode.

## Scope

**In:** an optional `base_feature` argument on `feature_body_create`.

**Out:** rebuilding the golden models to contain a Body. Investigated and rejected on cost:
`tests/infc/test_golden_models.py:73` asserts each fixture holds **exactly one object**, and a
Body brings eleven (Body, Origin, three axes, three planes, the origin point, and the
`PartDesign::FeatureBase`). Six files consume those fixtures, including the E2E sweep, which reads
the document root positionally. `base_feature` unblocks all 35 cases without touching any of it,
and it is also the answer a real agent needs when handed an imported STEP to modify.

## Behaviour

```
feature_body_create(doc, name, base_feature=None) -> ResultEnvelope
```

Omitted, behaviour is exactly as today: an empty Body. Given, it must name an object that carries
a non-null shape and is not already adopted by another Body.

## Failure behaviour — FreeCAD validates none of this

Measured: FreeCAD accepts every malformed target **silently**, with no raise and no error status.
The precheck must therefore own all of it.

| `base_feature` names | FreeCAD's own behaviour | this tool |
| --- | --- | --- |
| a solid (`Part::Feature`) | Body reports the solid's volume, `Tip` = `BaseFeature` | accept |
| a sketch | accepted; Body shape **null**, status `Touched` | `INVALID_INPUT` |
| a shapeless object | accepted; Body shape **null**, status `Touched` | `INVALID_INPUT` |
| an object another Body already adopted | accepted; **both** Bodies report the same volume | `INVALID_INPUT` |
| nothing (unknown name) | — | `INVALID_INPUT` |

The already-adopted row is the one worth stating plainly: adopting one solid into two Bodies
leaves two Bodies each claiming the same geometry, which no later check in this bridge would
catch. It is rejected here because nothing else will reject it.

All rejections happen in `precheck`, so no snapshot is written and no transaction opens.

## Structure

`features.py` already has `_resolve_object`. The new check needs two additions beside
`feature_body_create`:

```python
def _resolve_base_feature(document, name):
    """Return the object ``name`` for adoption as a Body's BaseFeature.

    :raises ValidationError: unknown, carries no usable shape, or already adopted by a Body.
    """
```

"Already adopted" is read from the candidate's `InList`: an adopted object gains its owning Body
and a `PartDesign::FeatureBase` entry there. "Carries a shape" is `Shape` present and not null,
which is what distinguishes a solid from a sketch or a shapeless feature.

In `op`, the assignment is `body.BaseFeature = target` before returning, and the recompute the
bracket already performs materialises it.

## Testing

In-FreeCAD (`tests/infc/test_feature_tools.py`), each falsifiable:

1. A Body created with `base_feature` reports the source solid's volume and has `Tip` set.
2. A pad on such a Body yields fixture-plus-feature volume — the case arithmetic, driven for real.
3. Omitting `base_feature` still yields an empty Body with a null shape and `Tip is None`.
4. A sketch as `base_feature` is rejected pre-bracket.
5. A shapeless object as `base_feature` is rejected pre-bracket.
6. An already-adopted solid is rejected pre-bracket.
7. An unknown name is rejected pre-bracket.

External: `base_feature` is an optional string on the input schema and absent from `required`.

## What this does not do

It does not make the 35 cases run. They still need the command resolver G2.1 reports as its
blocker, and their `case.yaml` files carry no `tool`/`args` for a driver to execute (DW-96). This
removes the *fixture* blocker only — one of the two, and the one nothing else was tracking.
