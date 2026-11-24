# Story 13-14 triage: round 2 (verifier F1 + red team)

Base: 9a9a3e7b on `story/13-14-verify-shape-schema`. Sources (this folder): `verify-13-14.md` (F1), `redteam-13-14.md` (RT-1 .. RT-4).

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (medium) | red team | None of the five validator source lists hashes `contracts/assertions.py` (`benchmarks/runner.py:103`, `score_verify_shape.py:50`, `score_g2_infc.py:82`, `score_g2_validators.py:39`, `score_g3_replay.py:72`), so a table edit changes verdicts while `validator_sha` stays current. Add the file to every list that hashes `usecases/assertions.py` or `verify.py`; refresh the hashes by running the scorers (as before); add a test that a table edit changes the hash. |
| F1 + RT-2 (medium) | verifier, red team | UAT drift: scripted scenario `tests/uat/scenarios/tc-07-01.json:182-190`, and the case text `TC-07-verification-and-export-pairing.md:69` and `TC-09-error-contract-and-fault-injection.md:415-441` still expect handler refusals that the schema now pre-empts. Update them to the new behaviour (the schema's "Input validation error", or move the probe to an input the schema accepts and the handler refuses), keeping each case's intent. |
| RT-3 (low, AD-28) | red team | `expect_solid_count` with `expect: 1.0` worked on base (int()), passes the schema, and is now refused by the use case. A call that validated before must not be refused now: accept an integral float for integer fns (schema and use case agree), test it. |
| RT-4 (low) | red team | `items.description` does not mark required keys, and the AD-13 index-selector hint no longer reaches the agent. Mark required keys and include the AD-13 hint text in the description. |

## After the fixes

Commit on your branch yourself (no trailer). Small changes: no lens round unless the product change grows past about 60 lines. `uv run --extra dev pytest tests/external -q` (Git Bash), infc suite (FREECAD_USER_HOME temp), check_provenance; reply with SHA and counts in at most 6 lines.
