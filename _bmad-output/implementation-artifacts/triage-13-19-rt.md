# Story 13-19 red-team round: leader triage

Base: f151a456 (story/13-19-skill-routing-part-loft-placement). Reports: `redteam-13-19.md` (RT-1..RT-7), `verify-13-19.md` (L-1..L-4). Probes: scratchpad `redteam-13-19\probes\` (read-only).
Doc fixes; where a skill states a tool behaviour, re-run the red team's probe or your own to prove the new text.

| # | Source | Finding | Required fix |
| --- | --- | --- | --- |
| T1 | RT-1 (medium) | `code-cad-conversion/SKILL.md:64` points to `references/gap-list.md`, which is not in this skill | Point to `skills/freecad-scripting-idioms/references/gap-list.md` with the form other skills use for cross-skill links; grep every changed skill for links to files that do not exist and fix them all. |
| T2 | RT-2 (medium) | Worked example (SKILL.md:125-128) leaves the plate's `Placement.Base.x/y/z` and the hole's `Placement.Base.z` unbound; the skill's own coverage script (:155) returns `[('bracket_plate',[x,y,z]),('bracket_hole',[z])]`, not `[]` | Bind every placement the rule at :51-53 requires in the worked example (or state the exact exception the rule allows and make the coverage script agree); run the coverage script on the result and show `[]`. Keep within the 1,500-word budget (move detail to references if needed). |
| T3 | RT-3 (medium) | `switches-and-fit.md:17-20` parks an additive fit tool; a fuse with the parked rib gives 2 solids / 2400 where the source has 1 solid / 2000; no repair given | State the repair for an additive switch (remove or zero-size the tool instead of parking it away, or whatever the probe shows gives the source's 1 solid / 2000), and prove it with a probe. |
| T4 | RT-4 (low) | `gap-list.md:27` says a Placement write on a feature in a Body is refused; probe: a write on `BaseFeature` returned OK and moved the Body | Make the row state what the tool does (read-only placements refused: attached Sketch, PartDesign features; Body placement writable), matching 13-16 / decision 50. |
| T5 | RT-5 (low) | `design-decomposition:68` "delete, then the tools again": recreating the region box is refused (name exists) | Say to delete the result AND its tool objects (or use new names) before rebuilding; name the delete tool. |
| T6 | RT-6 (low) | Chaining rule stated for cuts only; a 21-tool fuse is refused | State the 20-tool limit for every operation and the chaining for fuse/common too. |
| T7 | RT-7 (low) | Example payloads use `"doc": "bracket"`; the field needs the `fcb-doc:` handle from `document_create` | Use a placeholder that shows the handle (e.g. `"doc": "<fcb-doc handle from document_create>"`) consistently. |
| T8 | verifier L-1..L-3 (low) | `freecad-scripting-idioms/SKILL.md:148` `{"Visibility": true}` fragment (pre-existing); `generator-kit.md:15` clears `Box/Box001/Cut` while the typed example makes `bracket_*`; `deferred-work.md:2358` omits colour | Show the full `parameters` call or label the fragment as the `parameters` value; align the clear example with the `bracket_*` names; add colour to the resolution line. |

## After the fixes
Gates: check_skill_shape (word counts), ruff, tests/external. verifier-13-19 re-runs its payload check, the worked example with the coverage script, and the red team's probes for T2-T4.
