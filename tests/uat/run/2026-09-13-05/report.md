# UAT Run 2026-09-13-05 — Stories 9.3 and 9.4 Regressions

Targeted run. Validates the story 9.3 and 9.4 fixes against the R2-03 and R2-04 reproducers
recorded in run `2026-09-13-02`.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| FreeCAD pid (render run / sweep run) | 31120 / 24584 |
| Start time (render run) | 2026-09-13 20:55:29 |
| `render` | `gui_constructed` |

**Staleness precondition satisfied:** FreeCAD was restarted after the 9.3/9.4 files were written.

## Summary

| Scenario | Verdict | Notes |
| --- | --- | --- |
| R2-03 `front` render tone | **PASS** | Shaded face, 54.6/255 from background; was `rgb(255,255,255)` |
| R2-03 `iso` still correct | **PASS (deviation)** | Passes the band; tone moved — see below |
| R2-04 temp-file location | **PASS** | Renders land in the session workdir, not OS temp |
| R2-04 no orphan growth | **PASS** | OS temp 743 before and after two renders |
| R2-04 session-start sweep | **PASS** | Workdir `tmp/` 2 -> 0 on restart |
| R2-04 sweep scope | **PASS** | OS temp untouched at 743 |

R2-03 and R2-04 are **fixed**. One deviation from the story 9.3 spec is recorded below.

## R2-03 — every camera renders a visible part

A 40 mm cube was built and rendered from `front`, the camera R2-03 measured at `rgb(255,255,255)`
— identical to the background, so the PNG carried no shape information beyond its outline.

Measured with the shipped `usecases/render_tone.verify_render_tone`, which is the same oracle the
in-FreeCAD camera sweep and the fault suite use:

| Camera | Tone | Difference from background | Coverage | Verdict |
| --- | --- | --- | --- | --- |
| `front` | `(200, 207, 213)` | 54.6 | 39.9 % | pass |
| `iso` | `(141, 144, 148)` | 114.3 | 66.2 % | pass |

Both clear the two-sided band: >= 24/255 difference on some channel, and within `[20, 235]` on
every channel.

**Visual:** the `front` PNG was read and judged. The face renders as a distinctly shaded grey-blue
square, clearly separable from the white background, with a visible outline. R2-03's symptom —
a face indistinguishable from the background — does not occur.

### Deviation from the story 9.3 spec, recorded not waived

The spec required `iso` to stay near `rgb(158,165,169)`. It measures `(141, 144, 148)`.

The implementer found the two constraints cannot both hold and documented the measurement in
`adapters/render_probe.py`: ambient and the headlight offset trade against each other, and raising
ambient to bring `iso` back to the live viewport tone raises the axis-aligned views nearly
one-for-one — at 0.95, `right` measured 241.6 on blue, over the 235 ceiling. Light intensity does
not separate them; it is already 1.0.

Choosing the ceiling over the `iso` target is the right call: the band is AD-34's invariant, while
the `iso` value was a fidelity nicety. The cost is that `iso` renders slightly darker than the live
viewport. Recorded here because it contradicts a stated acceptance criterion.

## R2-04 — temp files the sweep can see

**Location.** A render through the bridge returned
`C:\Users\thuan\freecad-buddy-workdir\tmp\FCB_TMP_shot_1_y50uk6.png` — inside the new session
workdir. Under the shipped code `usecases/screenshot.py:172` passed no `dir=` and the file landed
in the OS temp directory.

**No orphan growth.** The OS temp directory held **743** `FCB_TMP_*` files before the run and
**743** after two renders. Under the old code each render added one; R2-04 counted 392 accumulated
that way, and the count had reached 743 by the start of this run.

**Session-start sweep.** The two renders left 2 files in the workdir's `tmp/`. They survived the
session exit — correct, because a caller may still be reading a returned link, so the sweep runs at
session start rather than as an immediate unlink. After restarting FreeCAD, `tmp/` held **0**.

**Sweep scope.** The OS temp directory still held **743** after the sweep ran. The sweep did not
reach outside the workdir, which is the multi-user safety constraint: on a shared host that
directory is another session's territory. The 743 pre-existing strays are operator cleanup and the
bridge correctly leaves them alone.

## Method note

The MCP bridge is the code under test, so its envelope fields are claims, never evidence. The R2-03
verdict rests on reading the rendered PNG and on measuring it with a stdlib oracle outside the
render path; the R2-04 verdict rests on filesystem counts taken outside the bridge entirely.

One caveat worth stating: an MCP render is a constructed scene produced by the actor under test, so
it is weaker evidence than a live-viewport capture. It is the right artifact here because the
render path *is* the subject of R2-03, and the tone was independently measured rather than accepted
from the bridge's own report.

## Cleanup

All documents closed. FreeCAD left running (pid 24584). No files removed from the OS temp
directory.
