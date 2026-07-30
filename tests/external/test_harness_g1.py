"""G1 harness tests (external / pytest). NON-tautological: validate real ValidationReport
objects against the committed schema + real exit codes; the ACTUAL reachable verdict class;
real grader verdicts over the planted suite; and the actor==grader preflight + honest-fail
guards for --gate G1."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
G1 = BENCHMARKS / "g1"
FAULT_DIR = G1 / "fault-injection"
BROKEN_DIR = G1 / "dev" / "broken-docs"
SCHEMA = (
    REPO_ROOT
    / "src"
    / "freecad_buddy"
    / "contracts"
    / "jsonschema"
    / "validation-report.schema.json"
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(G1))
sys.path.insert(0, str(G1 / "fault-injection"))

import check_provenance  # noqa: E402

from benchmarks import runner  # noqa: E402
from grader import DeterministicGrader, GraderClient, GraderVerdict  # noqa: E402

CLOSED_FAULT_KINDS = {"planted_defect", "clean_control"}
CLOSED_EXPECTATIONS = {"DETECT", "PASS_CLEAN"}


def _report_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def _load_fault_cases() -> list[dict]:
    cases = []
    for case_yaml in sorted(FAULT_DIR.rglob("case.yaml")):
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        data["_dir"] = case_yaml.parent
        cases.append(data)
    return cases


def _load_broken_cases() -> list[dict]:
    cases = []
    for case_yaml in sorted(BROKEN_DIR.rglob("case.yaml")):
        cases.append(yaml.safe_load(case_yaml.read_text(encoding="utf-8")))
    return cases


def _run_runner(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), *args],
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# (a) stub G1 run: report per criterion, schema-valid, INVALID_INPUT, exit 1
# --------------------------------------------------------------------------- #


def test_stub_g1_report_per_criterion_schema_valid_invalid_input():
    reports, exit_code = runner.run_gate("G1")
    gate = yaml.safe_load((G1 / "gate.yaml").read_text(encoding="utf-8"))
    assert len(reports) == len(gate["criteria"])
    assert exit_code == 1  # honest FAIL

    validator = _report_validator()
    for report in reports:
        validator.validate(report)  # raises on schema violation
        assert report["verdict"] != "OK"
        assert report["verdict"] == "INVALID_INPUT", report["subject"]
        assert report["subject"]["gate"] == "G1", report["subject"]


def test_stub_g1_file_path_invocation_exits_1():
    result = _run_runner(["--gate", "G1", "--stub"])
    assert result.returncode == 1, result.stderr
    assert "FAILED" in result.stdout


# --------------------------------------------------------------------------- #
# (b) fault inventory: >=10 planted + >=1 control, closed kinds, bound to grader
# --------------------------------------------------------------------------- #


def test_fault_inventory_counts_and_binding():
    cases = _load_fault_cases()
    validators = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )
    assert "grader" in validators
    last_run = validators["grader"]["last_run"]
    assert last_run is not None  # scored by score_grader.py
    assert last_run["sensitivity"] >= 0.95
    assert last_run["false_alarm"] <= 0.05
    assert validators["grader"]["validator_sha"] is not None
    assert validators["grader"]["suite"] == "g1/fault-injection/"

    planted = [c for c in cases if c["fault"]["kind"] == "planted_defect"]
    controls = [c for c in cases if c["fault"]["kind"] == "clean_control"]
    assert len(planted) >= 10, f"need >=10 planted defects, got {len(planted)}"
    assert len(controls) >= 1

    for case in cases:
        kind = case["fault"]["kind"]
        assert kind in CLOSED_FAULT_KINDS, f"{case['id']}: bad fault.kind {kind!r}"
        assert case["targets_validator"] == "grader", case["id"]
        assert case["fault"]["expectation"] in CLOSED_EXPECTATIONS, case["id"]
        assert "candidate_answer" in case, case["id"]
        assert "object" in case["expected_findings"], case["id"]


# --------------------------------------------------------------------------- #
# (c) broken-doc inventory: exactly 30, 10 n10 + 20 n30, each names {object, cause}
# --------------------------------------------------------------------------- #


def test_broken_docs_inventory_tiered_30():
    cases = _load_broken_cases()
    assert len(cases) == 30, f"expected exactly 30 broken-doc cases, got {len(cases)}"
    n10 = [c for c in cases if c["tier"] == "n10"]
    n30 = [c for c in cases if c["tier"] == "n30"]
    assert len(n10) == 10, f"expected 10 n10 cases, got {len(n10)}"
    assert len(n30) == 20, f"expected 20 n30 cases, got {len(n30)}"
    for case in cases:
        assert case["criterion"] == "G1.2", case["id"]
        assert case["expected"]["object"], case["id"]
        assert case["expected"]["cause"], case["id"]
        assert case["expected"]["cause_keywords"], case["id"]

    # The n=10 tier gates Story 2.2's first pass and only a 10/10 escalates to n=30, so the n10
    # slice must span every break kind — an assistant blind to one kind must not sail through on
    # a kind-skewed sample. Break kind is the id prefix (g1-broken-<kind>-...).
    def _kind(case: dict) -> str:
        return case["id"].split("-")[2]

    n10_kinds = {_kind(c) for c in n10}
    all_kinds = {_kind(c) for c in cases}
    assert n10_kinds == all_kinds, (
        f"n10 tier must span all break kinds; n10 covers {sorted(n10_kinds)} "
        f"of {sorted(all_kinds)}"
    )


def test_eval_questions_fifty_with_findings():
    data = yaml.safe_load((G1 / "dev" / "eval-questions.yaml").read_text(encoding="utf-8"))
    questions = data["questions"]
    assert len(questions) == 50, f"expected 50 eval questions, got {len(questions)}"
    categories = {q["category"] for q in questions}
    assert {"tree-explanation", "error-diagnosis", "next-tool-guidance"} <= categories
    for q in questions:
        assert q["expected_findings"], q["id"]


# --------------------------------------------------------------------------- #
# (d) grader determinism + correctness over the real planted suite
# --------------------------------------------------------------------------- #


def test_grader_fails_planted_wrong_passes_correct_over_suite():
    grader = DeterministicGrader()
    assert isinstance(grader, GraderClient)  # implements the seam
    cases = _load_fault_cases()
    rubric = (G1 / "rubric.md").read_text(encoding="utf-8")
    for case in cases:
        verdict = grader.grade(
            case.get("question_ref", ""),
            case["candidate_answer"],
            rubric,
            case["expected_findings"],
        )
        assert isinstance(verdict, GraderVerdict)
        if case["fault"]["expectation"] == "DETECT":
            # A planted confident-wrong answer must FAIL the grader (rejected).
            assert verdict.pass_ is False, f"{case['id']}: grader wrongly PASSed a planted-wrong"
        else:
            # A clean-correct control must PASS the grader.
            assert verdict.pass_ is True, f"{case['id']}: grader false-alarmed a correct answer"


def test_grader_is_deterministic():
    grader = DeterministicGrader()
    expected = {"object": "BracketPlate", "cause_keywords": ["conflicting"]}
    answer = "BracketPlate has conflicting constraints."
    first = grader.grade("q", answer, "", expected)
    second = grader.grade("q", answer, "", expected)
    assert first == second


def test_grader_cause_keyword_is_whole_token_not_substring():
    grader = DeterministicGrader()
    expected = {"object": "HousingBore", "cause_keywords": ["tool"]}
    # "toolbar" must NOT satisfy the "tool" cause keyword (substring false match).
    assert grader.grade(
        "q", "HousingBore: click the toolbar button.", "", expected
    ).pass_ is False
    # The bare token "tool" still matches.
    assert grader.grade("q", "HousingBore lost its tool object.", "", expected).pass_
    # A multi-word cause keyword still matches as a contiguous run.
    phrase = {"object": "HousingBore", "cause_keywords": ["missing tool"]}
    assert grader.grade("q", "HousingBore has a missing tool operand.", "", phrase).pass_


def test_grader_rejects_non_dict_expected():
    grader = DeterministicGrader()
    # G1.1 list-of-strings findings are not gradeable by the deterministic grader.
    with pytest.raises(ValueError):
        grader.grade("q", "any answer", "", ["a finding", "another"])


def test_grader_requires_both_object_and_cause():
    grader = DeterministicGrader()
    expected = {"object": "BracketPlate", "cause_keywords": ["conflicting"]}
    # object only -> FAIL
    assert grader.grade("q", "BracketPlate is broken.", "", expected).pass_ is False
    # cause only -> FAIL
    assert grader.grade("q", "It has conflicting constraints.", "", expected).pass_ is False
    # both -> PASS
    assert grader.grade("q", "BracketPlate has conflicting constraints.", "", expected).pass_


def test_every_break_kind_has_an_and_discriminator_case():
    # An AND-discriminator names the RIGHT object while omitting its own cause keywords: an
    # object-only or OR(object, any-cause) grader PASSes it, only the AND grader FAILs it. A
    # wholesale OR regression is caught by the bars anyway; one confined to a single break kind is
    # not, so every kind needs its own discriminator.
    from grader import _mentions_cause, _mentions_object, _normalize

    def _kind(case_id: str) -> str:
        # Break kind is the id prefix (g1-broken-<kind>-...).
        parts = case_id.split("-")
        assert len(parts) > 2 and parts[2], f"unparseable case id {case_id!r}"
        return parts[2]

    broken = _load_broken_cases()
    broken_ids = {c["id"] for c in broken}
    fault_cases = _load_fault_cases()
    # The OR grader this test models would be keyed on the fault suite's own keyword sets, so the
    # "foreign" universe must come from the suite, not from the broader broken-docs corpus.
    every_cause_keyword = sorted(
        {kw for c in fault_cases for kw in c["expected_findings"]["cause_keywords"]}
    )

    discriminated = set()
    kinds = set()
    for case in fault_cases:
        question_ref = case.get("question_ref")
        assert question_ref, f"{case['id']}: fault case must name its question_ref"
        # A dangling ref would invent a phantom break kind that satisfies the coverage assertion.
        assert question_ref in broken_ids, (
            f"{case['id']}: question_ref {question_ref!r} names no broken-docs case"
        )
        kind = _kind(question_ref)
        kinds.add(kind)
        if case["fault"]["expectation"] != "DETECT":
            continue
        expected = case["expected_findings"]
        answer = _normalize(case["candidate_answer"])
        names_object = _mentions_object(answer, expected["object"])
        own_cause = _mentions_cause(answer, expected["cause_keywords"])
        # A foreign cause is what separates a discriminator from a plain wrong-cause case: only
        # an answer carrying SOME cause keyword is passed by an OR(object, any-cause) grader.
        foreign_cause = _mentions_cause(answer, every_cause_keyword)
        if names_object and not own_cause and foreign_cause:
            discriminated.add(kind)

    broken_kinds = {_kind(c["id"]) for c in broken}
    assert kinds == broken_kinds, (
        f"fault suite covers kinds {sorted(kinds)}, broken-docs has {sorted(broken_kinds)}"
    )
    assert discriminated == kinds, (
        f"break kinds without an AND-discriminator case: {sorted(kinds - discriminated)}"
    )


def test_validator_sha_changes_when_the_fault_suite_is_mutated(tmp_path, monkeypatch):
    # A score-preserving suite edit must stale the committed score, so the suite is part of
    # validator_sha (otherwise --check reports "committed score matches" over a changed suite).
    import score_grader

    suite = tmp_path / "fault-injection"
    shutil.copytree(FAULT_DIR, suite, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(score_grader, "HERE", suite)
    before = score_grader._validator_sha()

    added = suite / "control-extra" / "case.yaml"
    added.parent.mkdir()
    added.write_text(
        (FAULT_DIR / "control-bracket-correct" / "case.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert score_grader._validator_sha() != before

    added.write_text("id: g1-control-extra\n", encoding="utf-8")
    edited = score_grader._validator_sha()
    assert edited != before

    # A rename with byte-identical content is what the hashed path identity exists to catch.
    shutil.move(str(added.parent), str(suite / "control-extra-renamed"))
    assert score_grader._validator_sha() != edited

    shutil.rmtree(suite / "control-extra-renamed")
    assert score_grader._validator_sha() == before

    # A case whose bytes spell the following case's path must not collide with the two-case suite
    # it imitates — the length prefixes are what keep the path+content concatenation unambiguous.
    two = tmp_path / "two"
    (two / "a").mkdir(parents=True)
    (two / "b").mkdir()
    (two / "a" / "case.yaml").write_bytes(b"id: one\n")
    (two / "b" / "case.yaml").write_bytes(b"id: two\n")
    monkeypatch.setattr(score_grader, "HERE", two)
    two_cases = score_grader._validator_sha()

    one = tmp_path / "one"
    (one / "a").mkdir(parents=True)
    (one / "a" / "case.yaml").write_bytes(b"id: one\nb/case.yamlid: two\n")
    monkeypatch.setattr(score_grader, "HERE", one)
    assert score_grader._validator_sha() != two_cases

    monkeypatch.setattr(score_grader, "HERE", suite)

    # An unreadable case must surface as a clean SuiteError, never a raw OSError traceback — the
    # runner reports the same tree stale, so neither entry point crashes on it.
    unreadable = suite / "control-bracket-correct" / "case.yaml"
    kept = unreadable.read_bytes()
    unreadable.unlink()
    unreadable.mkdir()
    with pytest.raises(score_grader.SuiteError):
        score_grader._validator_sha()
    unreadable.rmdir()
    unreadable.write_bytes(kept)

    # An emptied suite must raise rather than fall back to the source-only digest, which is a
    # value the registry has already carried and would read as current over a deleted suite.
    for case_yaml in list(suite.rglob("case.yaml")):
        case_yaml.unlink()
    with pytest.raises(score_grader.SuiteError):
        score_grader._validator_sha()


def test_runner_grader_hash_mirrors_the_scorer_hash():
    # Leg-b compares the committed validator_sha to runner._validator_src_hasher; if the runner's
    # hash does not mirror the scorer's byte for byte the grader is permanently reported stale.
    import score_grader

    committed = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )
    mirrored = runner._validator_src_hasher("grader")
    assert mirrored == score_grader._validator_sha()
    assert mirrored == committed["grader"]["validator_sha"]


def test_runner_grader_hash_is_stale_not_source_only_when_suite_is_missing(tmp_path, monkeypatch):
    # The runner must report stale rather than degrade to the source-only digest: that digest is a
    # value the registry has already carried, so a deleted suite would read as current.
    monkeypatch.setattr(runner, "_GRADER_SUITE_ROOT", tmp_path / "gone")
    assert runner._validator_src_hasher("grader") == ""


def test_score_grader_meets_bars_exit_0():
    # --check verifies the committed score (sha + sensitivity/FA) without writing, so the test is
    # hermetic (a clean tree) AND asserts the committed validators.yaml block is not stale.
    result = subprocess.run(
        [sys.executable, str(FAULT_DIR / "score_grader.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------- #
# (e) actor==grader gate.yaml copy -> runner G1 preflight exit 2
# --------------------------------------------------------------------------- #


def _collide_actor_grader(text: str) -> str:
    return text.replace(
        "model: deterministic-expected-findings", "model: claude-mcp-client"
    ).replace("context: independent-grader", "context: assistant-under-test")


def test_actor_equals_grader_preflight_exits_2(tmp_path, monkeypatch):
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    gate_yaml = copy / "g1" / "gate.yaml"
    collided = _collide_actor_grader(gate_yaml.read_text(encoding="utf-8"))
    gate_yaml.write_text(collided, encoding="utf-8")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G1")
    # main() converts to exit 2, no traceback
    assert runner.main(["--gate", "G1", "--stub"]) == 2


def test_distinct_actor_grader_does_not_preflight_fail():
    # The committed gate.yaml has distinct ids -> preflight passes, stub run reaches exit 1.
    reports, exit_code = runner.run_gate("G1")
    assert exit_code == 1
    assert len(reports) == 6


# --------------------------------------------------------------------------- #
# (f) honest-fail guards for --gate G1
# --------------------------------------------------------------------------- #


def test_g1_unknown_gate_exits_2_no_traceback():
    result = _run_runner(["--gate", "G9", "--stub"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_g1_lowercase_gate_exits_2():
    result = _run_runner(["--gate", "g1", "--stub"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_g1_criterion_matching_nothing_exits_2():
    result = _run_runner(["--gate", "G1", "--stub", "--criterion", "G1.99"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def _patched_g1_gate(tmp_path: Path, contents: str) -> Path:
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    (copy / "g1" / "gate.yaml").write_text(contents, encoding="utf-8")
    return copy


def test_g1_empty_criteria_exits_2(tmp_path, monkeypatch):
    copy = _patched_g1_gate(tmp_path, "gate: G1\ncriteria: []\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G1")


def test_g1_malformed_gate_yaml_exits_2(tmp_path, monkeypatch):
    copy = _patched_g1_gate(tmp_path, "criteria: [unbalanced\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G1")


def test_g1_check_provenance_clean_on_real_tree():
    assert check_provenance.check_tree(BENCHMARKS) == []


def test_faults_g1_routes_to_scorer_exit_0():
    # `faults G1` spawns the scorer, which merge-WRITES the committed validators.yaml. Snapshot
    # and restore it so the routing assertion stays hermetic (no dirtied tracked file, and a
    # future committed drift cannot be silently overwritten by this test).
    registry = BENCHMARKS / "_registry" / "validators.yaml"
    before = registry.read_bytes()
    try:
        result = _run_runner(["faults", "G1"])
    finally:
        registry.write_bytes(before)
    assert result.returncode == 0, result.stderr


def test_score_grader_check_mode_does_not_write(tmp_path, monkeypatch):
    # --check evaluates the bars + committed-score currency without writing (CI keeps a clean
    # tree). The sentinel starts as a byte-copy of the current committed registry (a non-stale
    # block), so --check passes and leaves it untouched.
    import score_grader

    committed = (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    sentinel = tmp_path / "validators.yaml"
    sentinel.write_text(committed, encoding="utf-8")
    monkeypatch.setattr(score_grader, "VALIDATORS_YAML", sentinel)
    assert score_grader.main(["--check"]) == 0
    assert sentinel.read_text(encoding="utf-8") == committed


def test_score_grader_check_flags_stale_committed_score(tmp_path, monkeypatch):
    # --check must FAIL (exit 1) when the committed validators.yaml grader block is stale/garbage,
    # not silently pass on a freshly-recomputed score.
    import score_grader

    stale = tmp_path / "validators.yaml"
    stale.write_text(
        "grader:\n"
        "  suite: g1/fault-injection/\n"
        '  validator_sha: "DEADBEEF"\n'
        "  last_run:\n"
        "    sensitivity: 0.0\n"
        "    false_alarm: 1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(score_grader, "VALIDATORS_YAML", stale)
    assert score_grader.main(["--check"]) == 1


def test_score_grader_rejects_degenerate_suite(tmp_path, monkeypatch):
    # A suite with zero controls must NOT vacuously clear the FA bar — the scorer raises.
    import score_grader

    case_dir = tmp_path / "only-defect"
    case_dir.mkdir()
    (case_dir / "case.yaml").write_text(
        "id: x\n"
        "targets_validator: grader\n"
        "fault: {kind: planted_defect, expectation: DETECT}\n"
        "candidate_answer: wrong\n"
        "expected_findings: {object: A, cause_keywords: [z]}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(score_grader, "HERE", tmp_path)
    with pytest.raises(SystemExit):
        score_grader.score()


def test_g1_heldout_contains_only_placeholder():
    # Design §1.1 / Story 2.4: heldout holds only the sealed pair (heldout.tar.enc + SEAL.json)
    # plus .gitkeep — no unsealed live case file ever lands here.
    heldout = G1 / "heldout"
    allowed = {".gitkeep", "heldout.tar.enc", "SEAL.json"}
    live = [
        p
        for p in heldout.rglob("*")
        if p.is_file() and p.name not in allowed and "__pycache__" not in p.parts
    ]
    assert live == [], f"g1/heldout must contain only the sealed pair; found live files: {live}"
