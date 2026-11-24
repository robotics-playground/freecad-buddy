# Story 13-20 triage: round 2 (verifier + red team)

Base: 27d75a93 on `story/13-20-usage-report`. Sources (this folder): `verify-13-20.md` (D-1, G-1), `redteam-13-20.md` (RT-1 .. RT-6). Use their reproductions as failing tests first.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 = D-1 (medium) | red team, verifier | Loft/sweep/helix/thickness class: match the PartDesign type ids (`AdditiveLoft`, `SubtractiveLoft`, `AdditivePipe`, `SubtractivePipe`, `AdditiveHelix`, `SubtractiveHelix`, `Thickness`) and the Part equivalents (`Part::Loft`, `Part::Sweep`, `Part::Thickness`, `makeLoft`, `makeHelix`, `makePipeShell`). Test with real code shapes. Report the new count on the evidence range in your reply. |
| RT-2 (medium) | red team | "script_exec timeout" failure class counts timeouts of every tool. Restrict it to `script_exec`; add a generic timeout class per tool if the evidence table has one, else count other timeouts in their tool's own row. Test. |
| RT-3 (medium) | red team | Calls to a server named `mcp__freecad-buddy-docker__*` (or any `mcp__<name containing freecad-buddy>__*`) count as 0 with no warning. Match every server whose name contains `freecad-buddy`, as the docstring says, and print the server names found. Test with the docker name. |
| RT-4 (medium) | red team | A deeply nested `rpc-*.json` raises `RecursionError` in the sweep, so the bridge does not start. The sweep must never stop bridge start: catch every exception per file (keep the file on doubt) and log one line. Test with a nested file. |
| RT-5 (low) | red team | A mutation written after `;` on the same line is counted read-only. Fix the read-only/mutating classification to scan every statement. Test. |
| RT-6 (low) | red team | A result in a file that sorts before its call's file is lost. Pair results with calls across files regardless of order. Test. |
| G-1 (low) | verifier | The date-filter test checks only the count. Assert which calls are counted, so a UTC+7 filter mutant goes red. |

## Not fixed, with the reason

- The remaining evidence gap (1,221 vs 897 calls in range; isValid 163 vs 122): transcripts deleted from disk (verifier: first present call 2026-10-26; 12 of 18 files left). Not a code defect. The acceptance text goes to the user as question 4.

## After the fixes

1. Commit on your branch yourself (decision 13 allows it; no trailer).
2. Product change spans the report and the sweep: run `bmad-build`'s three lenses again as fresh subagents (round 2) on 27d75a93..HEAD with `quality-bar-13-20.md`. Patch high/medium; commit.
3. Re-run the report on 2026-10-18..2026-11-18 over the two evidence folders; reply with SHA, lens ids, counts and the new class counts in at most 10 lines.
