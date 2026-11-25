# 017 — TNP Guard: A Witness Move Is Excused Only When the Same Element Rides Its Support

## Decision

Layer 1 does not grade a moved witness `REPOINTED` when all of these hold:

- FreeCAD calls it the same element: the mapped name is equal and the history source
  `(sourceTag, sourceName)` is equal on both sides, and neither side is unreadable.
- The support changed: the whole target shape's witness differs beyond the element tolerance
  from the baseline. The baseline is the snapshot, or the op-written reading when the record's
  value equals what the op wrote (the path `run_mutation` takes for an unchanged reference).
- The element moved no farther than the support, in the support's direction: per axis, each signed
  shift of the element's two bounding-box faces lies in the range spanned by zero and both of the
  support's face shifts.

The excused entry still goes to Layer 2. Every other witness move stays `REPOINTED`.

`RefRecord` carries `target_witness`, the witness of the whole target shape. One mechanism covers
every sub-element link (datum `AttachmentSupport`, sketch attachment, `ExternalGeometry`,
`Fillet.Base`, `Pad.Profile`); there is no property-name list.

## Rationale

The witness is the absolute bounding box of the element. A datum attached to a Pad face moves
when `Pad.Length` or a sketch width changes, although the reference did not change. The old
rule graded that `REPOINTED`, `post_verify` rolled the typed mutation back, and the agent fell
back to `script_exec`.

"Same support, same name, therefore `PASS`" would disable the witness check, which is the only
Layer-1 detector of a re-point that keeps the mapped name. The distance bound keeps it: a planted
witness shift larger than the support move stays `REPOINTED`
(`test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record`).

The bound is per axis and signed, so a witness shifted along an axis the support did not move on,
or outside the range the support's shifts span, stays `REPOINTED`. A single maximum over all axes would
excuse a 5 mm shift in X beside a support that grew 5 mm in Z.

## Accepted residual

An element that moves farther than its whole support (a pocket floor moves while the support box
is unchanged) stays `REPOINTED`. This is strictly fewer false positives than before, and the user
accepted it on 2026-11-25. Dropping the bound would also pass a witness tamper on a record whose
support really changed.

A second residual runs the other way: when the support moves a long way, a tampered witness that
keeps the mapped name and the history source and moves inside that range is excused. The history
source is decoded from the mapped name (`ElementMap.cpp`), so the two are one identity signal,
not two; the excuse rests on FreeCAD reporting the same mapped name.

The range joins both support faces, because a face must be able to follow the support's other
face when a midplane pad grows. A tampered shift opposite to its own face but inside that range
is therefore excused too.

These cases stay `REPOINTED` although the element is the same (false positives on the safe side,
measured in review round 3): a support that rotates or is reflected (`Pad.Reversed` toggled); an
inward-tapered pad (`TaperAngle` -10, the top face shrinks while the support box does not move
on x and y); a revolution whose `Angle` changes (the end face turns while the support z extent
does not move); and a pocket floor that moves inside an unchanged support box. In each the
element moves in a way the support bounding box does not show. A vertical edge also grades
`REPOINTED`, from the mapped-name check: its hashed `#id` segment changes while the edge does
not. That is outside this rule.

## Alternatives considered

- **Exempt by owner, or by "same support and same mapped name".** Rejected: it disables the
  witness check, the only Layer-1 detector of a re-point that keeps the mapped name (see 014 for
  the same granularity mistake on the entry-count check).
- **Whitelist `AttachmentSupport` only.** Rejected by epic decision 40
  (`epic-13-decisions.md`): it needs a property-name list and leaves the `Fillet.Base` false
  positive.
- **One maximum over all six bounding-box components, or per-axis magnitudes.** Replaced by the
  signed per-axis bound after review: they ignore direction.

## Related

Decision 014; `verification-design.md` §3.2 Layer 1; spec
`_bmad-output/implementation-artifacts/spec-13-15-tnp-expected-reattachment.md`; epic decision 40.

## Consequences

- `snapshot_references` reads the target's `BoundBox` once per target per walk.
- `Fillet.Base` entries that FreeCAD renumbers after a Pad change (`Edge1`, `Edge2`) still grade
  `BROKEN`; only the entries that keep their element identity pass.
- An entry with no readable history or no mapped name keeps today's verdict: no history, no excuse.
