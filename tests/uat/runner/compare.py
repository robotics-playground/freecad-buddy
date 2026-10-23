"""Compare a scripted replay with the verdicts of a past agent-run UAT report.

    uv run python tests/uat/runner/compare.py <old run dir> <replay run dir> [--testcases DIR]

The old verdicts of TC-01..TC-14 come from ``<old run dir>/evidence/tc-NN-results.json`` when that
file exists, else from the per-test-case tables of ``<old run dir>/report.md``. The runner
verdicts come from ``<replay run dir>/results.json``. The current scenario ids are the
``### TC-xx-yy:`` headings of the test-case markdown. ``<replay run dir>/replay-notes.json``,
written by the agent, explains what the script cannot decide::

    {"TC-02-05": {"coverage": "GUI action", "explanation": "..."},
     "TC-04-08": {"coverage": "not encoded", "explanation": "..."},
     "TC-03-05": {"class": "product fixed (F-04, 10.2)", "explanation": "..."},
     "TC-02-01": {"left_out": [{"then": "the saved file exists", "reason": "file check"}]}}

``coverage`` is a not-covered reason from ``NOT_COVERED_REASONS`` or ``not encoded``; it applies
to an id the replay did not run. ``class`` is a difference class from ``DIFFERENCE_CLASSES``; it
applies to a ``differs`` row. ``left_out`` names the deterministic Thens a scenario file does not
encode, each with a not-covered reason, so a ``same`` row never claims more than was checked.

Writes ``<replay run dir>/replay.md``: one row per id, old or current, with the row kind
``same | differs | not covered | not encoded | new | removed``. Exit codes: 0 every row is
explained; 1 a row is ``unexplained``; 2 an input could not be read (a report row the parser
cannot read, a missing file, or a note outside the closed sets).
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTCASE_DIR = REPO_ROOT / "tests" / "uat" / "testcases"
TEST_CASES = [f"TC-{number:02d}" for number in range(1, 15)]
NOT_COVERED_REASONS = (
    "H1 host",
    "raw RPC or second client",
    "process kill or relaunch",
    "log or audit read",
    "file check",
    "GUI action",
    "timing bound",
    "comparison op",
)
NOT_ENCODED = "not encoded"
DIFFERENCE_CLASSES = (
    re.compile(r"product fixed \(F-\d\d, \d+\.\d+\w*\)"),
    re.compile(r"test case changed \(10\.7 edit\)"),
    re.compile(r"runner limit"),
    re.compile(r"harness"),
)
UNEXPLAINED = "unexplained"
REMOVED_DEFAULT = (
    "no scenario with this id in the current test cases; see "
    "_bmad-output/implementation-artifacts/spec-10-7-edit-inventory.md"
)
NO_COMPARISON = ("BLOCKED", "SKIP")
SCENARIO_ID = re.compile(r"TC-\d\d-\d\d")
REPORT_ROW = re.compile(r"\| (TC-\d\d-\d\d) \| [^|]+ \| \*\*([A-Z-]+)\*\* \|")
HEADING = re.compile(r"^### (TC-\d\d-\d\d):", re.MULTILINE)


class CompareError(Exception):
    pass


def _in_scope(scenario_id):
    return scenario_id[:5] in TEST_CASES


def old_verdicts(run_dir):
    """``{id: verdict word}`` for TC-01..TC-14 of a past run; JSON per test case, else report."""
    run_dir = Path(run_dir)
    verdicts, from_report = {}, []
    for tc in TEST_CASES:
        results = run_dir / "evidence" / f"{tc.lower()}-results.json"
        if results.is_file():
            for row in json.loads(results.read_text(encoding="utf-8")):
                if SCENARIO_ID.fullmatch(row["id"]):
                    verdicts[row["id"]] = row["verdict"]
        else:
            from_report.append(tc)
    if from_report:
        verdicts.update(_report_verdicts(run_dir / "report.md", from_report))
    return verdicts


def _report_verdicts(report, test_cases):
    if not report.is_file():
        raise CompareError(f"{report}: missing; needed for {', '.join(test_cases)}")
    verdicts = {}
    for number, line in enumerate(report.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| TC-") or line[2:7] not in test_cases:
            continue
        if not SCENARIO_ID.fullmatch(line[2:10]):
            continue
        match = REPORT_ROW.match(line)
        if match is None:
            raise CompareError(f"{report}:{number}: scenario row not parsed: {line[:120]}")
        verdicts[match.group(1)] = match.group(2)
    return verdicts


def current_ids(testcase_dir):
    ids = []
    for path in sorted(Path(testcase_dir).glob("TC-*.md")):
        ids += [i for i in HEADING.findall(path.read_text(encoding="utf-8")) if _in_scope(i)]
    if not ids:
        raise CompareError(f"{testcase_dir}: no '### TC-xx-yy:' heading of TC-01..TC-14 found")
    return ids


def _agent_check_only(record):
    return (
        record["verdict"] == "ESCALATE"
        and bool(record.get("agent_check"))
        and record.get("capture") is not None
        and not record.get("errors")
        and not record.get("disagreements")
        and not record.get("findings")
    )


def same_verdict(old, record):
    """Apply the verdict map: PASS and PARTIAL match PASS or an ``agent_check``-only ESCALATE."""
    if old in ("PASS", "PARTIAL"):
        return record["verdict"] == "PASS" or _agent_check_only(record)
    return old == "FAIL" and record["verdict"] == "FAIL"


def _check_note(scenario_id, note):
    coverage, kind = note.get("coverage"), note.get("class")
    if coverage is not None and coverage not in (*NOT_COVERED_REASONS, NOT_ENCODED):
        raise CompareError(f"replay-notes {scenario_id}: coverage {coverage!r} is not in the set")
    if kind is not None and not any(pattern.fullmatch(kind) for pattern in DIFFERENCE_CLASSES):
        raise CompareError(f"replay-notes {scenario_id}: class {kind!r} is not in the set")
    for then in note.get("left_out", []):
        if then.get("reason") not in NOT_COVERED_REASONS or not then.get("then"):
            raise CompareError(f"replay-notes {scenario_id}: left_out entry {then!r} is invalid")


def _explanation(note):
    left_out = "; ".join(f"{then['then']} ({then['reason']})" for then in note.get("left_out", []))
    parts = [note.get("explanation", ""), f"Not checked: {left_out}." if left_out else ""]
    return " ".join(part for part in parts if part)


def rows(old, records, current, notes):
    """One row per id: ``{id, old, runner, row, class, explanation}``."""
    for scenario_id, note in notes.items():
        _check_note(scenario_id, note)
    by_id = {record["id"]: record for record in records if _in_scope(record["id"])}
    table = []
    for scenario_id in sorted(set(old) | set(current) | set(by_id)):
        note = notes.get(scenario_id, {})
        record = by_id.get(scenario_id)
        row = {
            "id": scenario_id,
            "old": old.get(scenario_id),
            "runner": record["verdict"] if record else None,
            "class": "-",
            "explanation": _explanation(note),
        }
        if scenario_id not in current and record is None:
            row["row"] = "removed"
            row["explanation"] = row["explanation"] or REMOVED_DEFAULT
        elif scenario_id not in old or old[scenario_id] in NO_COMPARISON:
            row["row"] = "new"
            if record is None:
                row["class"] = note.get("coverage", UNEXPLAINED)
        elif record is None:
            coverage = note.get("coverage")
            row["row"] = NOT_ENCODED if coverage == NOT_ENCODED else "not covered"
            row["class"] = coverage or UNEXPLAINED
        elif same_verdict(old[scenario_id], record):
            row["row"] = "same"
        else:
            row["row"] = "differs"
            row["class"] = note.get("class", UNEXPLAINED)
        table.append(row)
    return table


def _cell(text):
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render(table, old_dir, replay_dir, metadata):
    kinds = ("same", "differs", "not covered", "not encoded", "new", "removed")
    counts = {kind: sum(row["row"] == kind for row in table) for kind in kinds}
    unexplained = sum(row["class"] == UNEXPLAINED for row in table)
    lines = [
        "# Replay comparison",
        "",
        f"Old run: `{old_dir.as_posix()}`. Replay: `{replay_dir.as_posix()}` (commit "
        f"`{metadata.get('git_commit')}`, `git_dirty: {json.dumps(metadata.get('git_dirty'))}`, "
        f"FreeCAD {metadata.get('freecad_version')}).",
        "",
        "Verdict map: old `PASS` and `PARTIAL` match runner `PASS`, or `ESCALATE` whose only "
        "reason is an `agent_check`; old `FAIL` matches runner `FAIL`; old `BLOCKED` and `SKIP` "
        "are not compared (row `new`).",
        "",
        f"{len(table)} rows: "
        + ", ".join(f"{counts[kind]} {kind}" for kind in kinds)
        + f". Unexplained: {unexplained}.",
        "",
        "| Scenario | Old verdict | Runner verdict | Row | Class or reason | Explanation |",
        "|----------|-------------|----------------|-----|-----------------|-------------|",
    ]
    for row in table:
        cells = [
            row["id"],
            row["old"] or "-",
            row["runner"] or "-",
            row["row"],
            row["class"],
            row["explanation"] or "-",
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CompareError(f"{path}: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare a replay with a past UAT report.")
    parser.add_argument("old", type=Path, help="past run folder (report.md, evidence/)")
    parser.add_argument("replay", type=Path, help="runner run folder (results.json)")
    parser.add_argument("--testcases", type=Path, default=TESTCASE_DIR)
    args = parser.parse_args(argv)
    try:
        old = old_verdicts(args.old)
        results = _read_json(args.replay / "results.json")
        notes_file = args.replay / "replay-notes.json"
        notes = _read_json(notes_file) if notes_file.is_file() else {}
        table = rows(old, results["scenarios"], current_ids(args.testcases), notes)
    except CompareError as exc:
        print(f"compare refused: {exc}")
        return 2
    (args.replay / "replay.md").write_text(
        render(table, args.old, args.replay, results.get("run", {})),
        encoding="utf-8",
        newline="\n",
    )
    unexplained = [row["id"] for row in table if row["class"] == UNEXPLAINED]
    print(f"{len(table)} rows, {len(unexplained)} unexplained: {' '.join(unexplained) or '-'}")
    print(f"replay: {args.replay / 'replay.md'}")
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
