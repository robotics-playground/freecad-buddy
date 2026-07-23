"""G1 actor-run tests (external / pytest).

Drive the actor-run harness with a ``ScriptedBackend`` (offline, deterministic) over the real
broken-doc fixtures and the independent Story 2.1 grader. Cover the I/O matrix rows: a correct
answer grades OK, a confident-wrong answer grades SPEC_FAILED, the tiered n10->n30 escalation
fires per decision 008 (8/10 passes without escalating, 10/10 escalates to n=30, 6/10 fails), a
malformed/no-final-answer case grades as a typed fail (not a crash), the live backend is skipped
(not errored) when unwired, and the actor's recorded calls stay on the summarized-tree query.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
G1 = BENCHMARKS / "g1"
BROKEN_DIR = G1 / "dev" / "broken-docs"
SCHEMA = (
    REPO_ROOT
    / "src"
    / "freecad_buddy"
    / "contracts"
    / "jsonschema"
    / "validation-report.schema.json"
)

for _p in (str(REPO_ROOT), str(REPO_ROOT / "src"), str(G1)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.g1 import actor_run  # noqa: E402
from benchmarks.harness.actor import Actor, AnswerResult, ScriptedBackend, ToolCall  # noqa: E402
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod  # noqa: E402
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE  # noqa: E402


def _report_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def _profile_registry() -> MethodRegistry:
    registry = MethodRegistry()
    for name in sorted(READ_ONLY_PROFILE):
        registry.register(
            RpcMethod(
                name=name,
                handler=lambda **_kwargs: {
                    "schema": "fcb.result-envelope/1",
                    "status": "OK",
                    "detail": {"code": "ok", "message": ""},
                    "structured_content": {},
                    "text": "",
                },
            )
        )
    return registry


def _broken_cases() -> list[dict]:
    cases = []
    for case_yaml in sorted(BROKEN_DIR.rglob("case.yaml")):
        cases.append(yaml.safe_load(case_yaml.read_text(encoding="utf-8")))
    return cases


def _correct_entry(case: dict) -> dict:
    expected = case["expected"]
    keyword = expected["cause_keywords"][0]
    return {
        "answer": f"{expected['object']} is in error: {keyword}.",
        "tools": ["query_tree_summary", "verify_recompute"],
    }


def _wrong_entry(case: dict) -> dict:
    return {
        "answer": "SomeOtherObject is fine; nothing is wrong.",
        "tools": ["query_tree_summary"],
    }


def _script_all_correct() -> dict:
    return {c["id"]: _correct_entry(c) for c in _broken_cases()}


def _run(script: dict):
    actor = Actor(_profile_registry())
    backend = ScriptedBackend(script)
    return actor_run.run_actor_eval(actor, backend, repeats=3)


# --------------------------------------------------------------------------- #
# correct -> OK ; confident-wrong -> SPEC_FAILED
# --------------------------------------------------------------------------- #


def test_correct_answer_grades_ok():
    result = _run(_script_all_correct())
    validator = _report_validator()
    assert result.reports, "no reports emitted"
    for report in result.reports:
        validator.validate(report)
        assert report["verdict"] == "OK", report["subject"]


def test_confident_wrong_answer_grades_spec_failed():
    script = {c["id"]: _wrong_entry(c) for c in _broken_cases()}
    result = _run(script)
    validator = _report_validator()
    # Only the n10 tier is graded (no escalation on an all-fail run).
    assert result.reports
    for report in result.reports:
        validator.validate(report)
        assert report["verdict"] == "SPEC_FAILED", report["subject"]


# --------------------------------------------------------------------------- #
# tiered escalation table (decision 008)
# --------------------------------------------------------------------------- #


def _script_first_k_n10_correct(k: int) -> dict:
    cases = _broken_cases()
    n10 = [c for c in cases if c.get("tier") == "n10"]
    n30 = [c for c in cases if c.get("tier") == "n30"]
    script: dict = {}
    for i, case in enumerate(sorted(n10, key=lambda c: c["id"])):
        script[case["id"]] = _correct_entry(case) if i < k else _wrong_entry(case)
    # n30 all correct — only reached if escalation fires.
    for case in n30:
        script[case["id"]] = _correct_entry(case)
    return script


def test_escalation_8_of_10_passes_without_escalating():
    result = _run(_script_first_k_n10_correct(8))
    assert result.n10.passed_count == 8
    assert result.n10.passed is True
    assert result.escalated is False
    assert result.n30 is None
    ci = result.n10.wilson_ci
    assert ci["n"] == 10 and ci["r"] == 8
    # One ValidationReport per case×repeat: 10 n10 cases × 3 repeats, no escalation.
    assert len(result.reports) == 10 * 3


def test_seven_of_ten_is_a_tier_fail():
    result = _run(_script_first_k_n10_correct(7))
    assert result.n10.passed_count == 7
    assert result.n10.passed is False
    assert result.escalated is False


def test_escalation_perfect_10_of_10_escalates_to_n30():
    result = _run(_script_first_k_n10_correct(10))
    assert result.n10.passed_count == 10
    assert result.escalated is True
    assert result.n30 is not None
    assert result.n30.wilson_ci["n"] == 30
    assert result.n30.passed_count == 30
    # One ValidationReport per case×repeat: all 30 cases (10 n10 + 20 n30) × 3 repeats.
    assert len(result.reports) == 30 * 3


def test_escalation_6_of_10_fails_no_escalation():
    result = _run(_script_first_k_n10_correct(6))
    assert result.n10.passed_count == 6
    assert result.n10.passed is False
    assert result.escalated is False
    assert result.n30 is None


# --------------------------------------------------------------------------- #
# majority-of-R tie boundary (2/3 -> pass, 1/3 -> fail)
# --------------------------------------------------------------------------- #


class _AlternatingBackend:
    """Answers correct on even invocations, wrong on odd, per case — to drive a 2/3 R split."""

    def __init__(self, correct_first: bool) -> None:
        # Keyed over ALL cases so an escalated 10/10 run can grade n30 too.
        self._correct = {c["id"]: _correct_entry(c)["answer"] for c in _broken_cases()}
        self._wrong = "SomeOtherObject is fine; nothing is wrong."
        self._n: dict[str, int] = {}
        self._correct_first = correct_first

    def answer(self, case_id, question, tools, invoke):
        i = self._n.get(case_id, 0)
        self._n[case_id] = i + 1
        # correct_first=True -> correct on repeats 0,2 (2/3 correct); False -> correct only on 1.
        is_correct = (i % 2 == 0) if self._correct_first else (i % 2 == 1)
        ans = self._correct[case_id] if is_correct else self._wrong
        return AnswerResult(final_answer=ans, tool_calls=[])


def test_majority_of_r_two_of_three_passes():
    actor = Actor(_profile_registry())
    backend = _AlternatingBackend(correct_first=True)
    result = actor_run.run_actor_eval(actor, backend, repeats=3)
    assert result.n10.passed_count == 10  # every case is 2/3 correct -> majority pass


def test_majority_of_r_one_of_three_fails():
    actor = Actor(_profile_registry())
    backend = _AlternatingBackend(correct_first=False)
    result = actor_run.run_actor_eval(actor, backend, repeats=3)
    assert result.n10.passed_count == 0  # every case is 1/3 correct -> majority fail


# --------------------------------------------------------------------------- #
# malformed fixture set -> loud failure, not a silent drop
# --------------------------------------------------------------------------- #


def test_untiered_case_raises(monkeypatch, tmp_path):
    bad = tmp_path / "untiered" / "case.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("id: g1-broken-x\ncriterion: G1.2\nexpected: {object: A, cause: b}\n")
    monkeypatch.setattr(actor_run, "BROKEN_DOCS", tmp_path)
    import pytest

    with pytest.raises(ValueError, match="invalid tier"):
        actor_run._load_broken_cases()


def test_empty_broken_docs_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(actor_run, "BROKEN_DOCS", tmp_path)
    import pytest

    with pytest.raises(ValueError, match="no broken-doc cases"):
        actor_run._load_broken_cases()


# --------------------------------------------------------------------------- #
# malformed / no-final-answer -> typed fail, not a crash
# --------------------------------------------------------------------------- #


def test_no_final_answer_grades_typed_fail_not_crash():
    # Empty script -> every case yields a None final answer.
    result = _run({})
    validator = _report_validator()
    assert result.reports
    for report in result.reports:
        validator.validate(report)
        assert report["verdict"] == "SPEC_FAILED", report["subject"]
        code = report["checks"][0]["detail"]["code"]
        assert code == "spec_failed.no_final_answer", code


# --------------------------------------------------------------------------- #
# summarized-tree used (assert on the recorded tool calls)
# --------------------------------------------------------------------------- #


def test_actor_records_summarized_tree_call():
    actor = Actor(_profile_registry())
    backend = ScriptedBackend(_script_all_correct())
    cases = _broken_cases()
    case = next(c for c in cases if c.get("tier") == "n10")
    result = actor.run(backend, case["id"], "q")
    names = [c.name for c in result.tool_calls]
    assert actor_run.SUMMARIZED_TREE_TOOL in names
    assert all(n in READ_ONLY_PROFILE for n in names)


def test_off_profile_tool_call_is_rejected():
    class RawDumpBackend:
        def answer(self, case_id, question, tools, invoke):
            return AnswerResult(
                final_answer="x",
                tool_calls=[ToolCall(name="query_full_tree", args={})],
            )

    actor = Actor(_profile_registry())
    import pytest

    with pytest.raises(ValueError, match="off-profile tool"):
        actor_run.run_actor_eval(actor, RawDumpBackend(), repeats=1)


# --------------------------------------------------------------------------- #
# live backend absent -> skipped (not errored, not silently green)
# --------------------------------------------------------------------------- #


def test_offline_actor_run_reports_live_skip():
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), "--gate", "G1", "--actor-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "live eval skipped" in result.stdout
    assert "escalated to n=30" in result.stdout


def test_live_backend_flag_is_operator_gated_not_ci_green():
    import os

    env = dict(os.environ)
    env["FREECAD_BUDDY_G1_ACTOR_BACKEND"] = "live"
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), "--gate", "G1", "--actor-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    # Live backend is not wired in the harness -> clean usage error (exit 2), never a fake green.
    assert result.returncode == 2, result.stdout
    assert "operator-gated" in result.stderr
