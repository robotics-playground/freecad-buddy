# Mutation-block contract honesty — DW-78 and DW-79

Two defects in the same four contract blocks, fixed in one pass because both change
`contracts/mutation.py` and its generated schema.

## Problem 1 (DW-78): unmeasured values presented as measurements

`post_verify` short-circuits on the first failure. On those paths it still fills every field of
`PostVerifyBlock`, with values nothing measured:

| path (`transaction.py`) | what it reports | truth |
| --- | --- | --- |
| `verify_shape` raised or failed (227, 231) | `fully_constrained=None` | the contract reads `None` as *no sketch involved*, but the sketch loop never ran — a touched sketch is indistinguishable from an absent one |
| `verify_sketch` raised (239) | `is_valid=True` | no shape was graded; the value is asserted, not measured |

The module docstring says it never presents unmeasured values as measurements. These paths do.

No verdict changes: every affected block already carries `passed=false` and a naming
`explanation`. The cost is that a consumer reading the block cannot tell an unmeasured field from
a measured one. Nothing outside `transaction.py` branches on either field today, so the encoding
is free to change.

## Problem 2 (DW-79): the type checker and the schema disagree

`MutationBlock`, `PostVerifyBlock`, `TnpAuditBlock` and `RefFinding` are all `total=False`, so
every field is optional to the type checker, while the generated schema marks six of
`MutationBlock`'s required. Which fields are mandatory lives in a `# required` comment — prose the
type checker cannot read.

Measured rather than argued:

```
empty MutationBlock accepted by the type system : True
schema rejects it: 'transaction_id' is a required property
additionalProperties: absent
```

So a producer omitting `rollback_proven` type-checks clean and fails at wire validation, in front
of a client. This is how `params_digest` stayed unpopulated while a test pinned it. And with
`additionalProperties` absent, a misspelled field validates while the real one silently defaults.

**The operator's FreeCAD-parity principle does not apply here.** These four blocks have no FreeCAD
counterpart — `transaction_id`, `rollback_proven` and `params_digest` are bridge-invented — so by
that principle they are ours to decide, and the required set stays exactly as the schema already
declares it. The 17 tool-input `required` lists that *do* mirror FreeCAD are audited separately by
DW-104.

## Solution

### DW-78 — an explicit not-measured value

`fully_constrained` and `is_valid` gain `"not_measured"` as a third state, distinct from `None`:

| value | meaning |
| --- | --- |
| `True` / `False` | measured |
| `None` | measured as inapplicable — no sketch was involved |
| `"not_measured"` | the step never ran, so nothing was measured |

Applied at the three short-circuit sites: `fully_constrained="not_measured"` where the sketch loop
had not run, and `is_valid="not_measured"` where the shape loop had not graded anything.

`is_valid` keeps `bool` on every path that did grade. The `recompute_clean=False` path at line 220
is unaffected — that value *is* measured.

### DW-79 — required keys in a `total=True` base

Each of the four blocks splits into a `total=True` base carrying its required keys and a
`total=False` subclass carrying the optional ones:

```python
class _MutationRequired(TypedDict):
    transaction_id: str
    fingerprint_before: FingerprintRecord
    fingerprint_after: FingerprintRecord | None
    post_verify: PostVerifyBlock
    rolled_back: bool
    rollback_proven: RollbackProof | None


class MutationBlock(_MutationRequired, total=False):
    schema: Literal["fcb.mutation/1"]
    snapshot_path: str | None
    ...
```

The `# required` comments go away: the type is now the statement.

`additionalProperties: false` is set on these four objects so a misspelled field is rejected
rather than silently defaulted.

**The generator has no support for this today** — `additionalProperties` appears nowhere in
`gen_schemas.py`, and `_register_def` emits `{"type": "object", "properties": ..., "required": ...}`
with no closure. So this half needs a small generator change: a `CLOSED_TYPES` manifest naming the
types to close, read by `_register_def` and by the wire-root builder.

A manifest rather than closing every type by default. Closing a type is a breaking wire change for
any producer sending an extra field, and the other contract types have not been audited for that;
an explicit list keeps each closure a deliberate act, matching how `REQUIRED_FIELDS` and
`CONDITIONALS` already work.

## Interaction between the two

`REQUIRED_FIELDS` is currently the only statement of what is mandatory. After the split, the
TypedDict states it too, and the two can drift. `test_capability_banner_annotations_match_manifest`
already guards that agreement for the capability banner; the same guard is extended to these four
blocks — `__required_keys__` must equal the manifest entry.

That guard is what makes the split worth doing rather than merely tidy.

## Failure behaviour

| input | result |
| --- | --- |
| a block missing a required key | rejected by the type checker AND by the schema |
| a block with a misspelled field | rejected by the schema (`additionalProperties: false`) |
| `fully_constrained` on a short-circuit path | `"not_measured"`, never a fabricated `None` |

## Testing

External (`tests/external/test_contracts.py`):

1. `MutationBlock.__required_keys__` equals `REQUIRED_FIELDS["MutationBlock"]`, and the same for
   the other three blocks — the anti-drift guard.
2. The generated schema carries `additionalProperties: false` for all four.
3. A block with a misspelled field is rejected by the schema.
4. `"not_measured"` validates for `fully_constrained` and `is_valid`; a nonsense string does not.

In-FreeCAD (`tests/infc/test_mutation_protocol.py`):

5. A mutation whose `verify_shape` fails while a sketch was touched reports
   `fully_constrained: "not_measured"`, not `None`.
6. A mutation whose `verify_sketch` raises reports `is_valid: "not_measured"`, not `True`.
7. A fully successful mutation still reports real booleans on both fields.

Test 7 matters as much as 5 and 6: it pins that the new encoding did not leak onto the paths that
do measure.

## Risks

`"not_measured"` widens two field types from `bool | None` to `bool | None | Literal["not_measured"]`.
A consumer doing `assertFalse(...)` or `if not value:` reads `None` as false but the string as
**truthy**, so any such check on a newly-`"not_measured"` path would silently invert.

Three tests read `fully_constrained` — `test_mutation_protocol.py:330`,
`test_sketch_tools.py:420` and `:1601` — and two use `assertFalse`. All three were checked
against the code paths they drive: each exercises the `verify_sketch` **failure** path at line 253,
where `fully_constrained` is the measured conjunction and stays a real `False`. None touches a
path this change converts, so all three keep passing unchanged.

That is the boundary to hold while implementing: `"not_measured"` belongs only where the loop
never ran. If a test that currently asserts `False` starts seeing the string, the value was
applied to a path that did measure — a defect, not an expected update.
