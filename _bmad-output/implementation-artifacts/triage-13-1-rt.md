# Story 13-1 triage: red team

Base: bd122f2 + `patch-13-1-r1.diff` (sha256 904e6edad4b3). Source: `redteam-13-1.md`.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-2 | redteam-13-1 | Treat every line boundary that `str.splitlines()` recognises (`\n`, `\r`, `\v`, `\f`, `\x1c`-`\x1e`, `\x85`, ` `, ` `) as a line break: a value with any of them renders `key: <N chars>`. Add one parametrised test over those characters. Regression risk: a short value with no break must still render inline — keep the 80-char inline test green. |
| RT-4 | redteam-13-1 | Add a test where character length and byte length differ (for example 80 non-ASCII characters stay inline; 81 render `<81 chars>`), so a byte-length mutant goes red. |
| RT-5 | redteam-13-1 | In the new tests, `target` names the system under test only (CLAUDE.md section 9). Rename variables that hold the output to `result` (or `actual`). |

## Not fixed, with the reason

- RT-1: no code change. T-13 table (`tool-contracts.md:23`) keeps a string of ≤80 characters inline; the "once" in the Done line refers to the long values measured in `usage-evidence.md`. Quality bar Q4 was worded too broadly; the leader corrected Q4 to long values.
- RT-3: addon/proxy version skew is outside this Story. The release build ships both from one wheel; dev skew is an operator setup state. Low, recorded in the ledger only.

## After the fixes

Run `uv run pytest tests/external -q` and ruff on the changed files. Report counts. Refresh `patch-13-1-r2.diff` is done by the leader; do not create it.
