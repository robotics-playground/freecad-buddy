"""ReAct backend + actor-run tests (external / pytest).

Drive the 2.2 actor-run through the ReAct ``Backend`` offline (a ``ScriptedChat`` double replaying
recorded assistant turns) over the real broken-doc fixtures and the independent Story 2.1 grader.
Assert the identical read-only surface (recorded tool_calls ⊆ allow-list, summarized-tree used),
that per-case ``ValidationReport``s are emitted, that the tiered n10→n30 escalation fires via the
shared ``run_actor_eval``, and — via the runner subprocess — that the live-local backend is skipped
(explicit, not errored) and that an ``actor_local.model == grader.model`` gate hard-fails exit 2.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
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
from benchmarks.harness.actor import Actor  # noqa: E402
from benchmarks.harness.react_backend import ReactBackend, ScriptedChat  # noqa: E402
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
    return [
        yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        for case_yaml in sorted(BROKEN_DIR.rglob("case.yaml"))
    ]


def _correct_turns(case: dict) -> list[str]:
    expected = case["expected"]
    keyword = expected["cause_keywords"][0]
    return [
        '```json\n{"tool": "query_tree_summary", "args": {"doc": "d"}}\n```',
        '```json\n{"tool": "verify_recompute", "args": {"doc": "d"}}\n```',
        f"{expected['object']} is in error: {keyword}.",
    ]


def _all_correct_scripts() -> dict[str, list[str]]:
    return {c["id"]: _correct_turns(c) for c in _broken_cases()}


def _run(scripts: dict[str, list[str]]):
    actor = Actor(_profile_registry())
    backend = ReactBackend(ScriptedChat(scripts).for_case)
    return actor_run.run_actor_eval(actor, backend, repeats=3)


def test_react_backend_identical_surface_and_summarized_tree():
    actor = Actor(_profile_registry())
    backend = ReactBackend(ScriptedChat(_all_correct_scripts()).for_case)
    case = next(c for c in _broken_cases() if c.get("tier") == "n10")
    result = actor.run(backend, case["id"], "q")
    names = [c.name for c in result.tool_calls]
    assert actor_run.SUMMARIZED_TREE_TOOL in names
    assert all(n in READ_ONLY_PROFILE for n in names)


def test_react_backend_correct_answers_grade_ok_and_escalate():
    result = _run(_all_correct_scripts())
    validator = _report_validator()
    assert result.reports
    for report in result.reports:
        validator.validate(report)
        assert report["verdict"] == "OK", report["subject"]
    # 10/10 → escalation fires via the shared run_actor_eval, all 30 cases × 3 repeats.
    assert result.escalated is True
    assert result.n30 is not None
    assert len(result.reports) == 30 * 3


def test_react_backend_no_final_answer_grades_typed_fail():
    # Scripts that only ever emit tool calls (never a final-answer prose turn) → the adapter hits
    # the iteration cap → final_answer=None → the harness grades a typed SPEC_FAILED, not a crash.
    tool_only = ['```json\n{"tool": "verify_recompute", "args": {"doc": "d"}}\n```'] * 20
    scripts = {c["id"]: tool_only for c in _broken_cases()}
    result = _run(scripts)
    validator = _report_validator()
    assert result.reports
    for report in result.reports:
        validator.validate(report)
        assert report["verdict"] == "SPEC_FAILED", report["subject"]
        assert report["checks"][0]["detail"]["code"] == "spec_failed.no_final_answer"


def test_offline_actor_run_reports_live_skip():
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), "--gate", "G1", "--actor-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "live eval skipped" in result.stdout
    assert "escalated to n=30" in result.stdout


def test_actor_local_grader_collision_hard_fails_exit_2(tmp_path):
    gate = yaml.safe_load((G1 / "gate.yaml").read_text(encoding="utf-8"))
    gate["actor_local"]["model"] = gate["grader"]["model"]
    gate_dir = tmp_path / "benchmarks" / "g1"
    gate_dir.mkdir(parents=True)
    (gate_dir / "gate.yaml").write_text(yaml.safe_dump(gate), encoding="utf-8")

    probe = tmp_path / "probe.py"
    probe.write_text(
        "import pathlib, sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "import benchmarks.runner as r\n"
        f"r.BENCHMARKS_ROOT = pathlib.Path({str(tmp_path / 'benchmarks')!r})\n"
        "try:\n"
        "    r._preflight_actor_grader('G1')\n"
        "except r.UsageError as exc:\n"
        "    print(exc); sys.exit(2)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "actor_local==grader" in result.stdout


def test_actor_descriptors_rejects_scalar_actor_value():
    import benchmarks.runner as runner

    with pytest.raises(runner.UsageError):
        runner._actor_descriptors({"actor_local": "llama-x", "grader": {"model": "g"}})


def test_actor_descriptors_rejects_scalar_actors_list_entry():
    import benchmarks.runner as runner

    with pytest.raises(runner.UsageError):
        runner._actor_descriptors({"actors": ["llama-x"], "grader": {"model": "g"}})


def test_preflight_inert_when_grader_has_no_model(tmp_path):
    import benchmarks.runner as runner

    gate = yaml.safe_load((G1 / "gate.yaml").read_text(encoding="utf-8"))
    gate["grader"].pop("model", None)
    gate["actor"].pop("model", None)
    gate_dir = tmp_path / "benchmarks" / "g1"
    gate_dir.mkdir(parents=True)
    (gate_dir / "gate.yaml").write_text(yaml.safe_dump(gate), encoding="utf-8")

    original_root = runner.BENCHMARKS_ROOT
    runner.BENCHMARKS_ROOT = tmp_path / "benchmarks"
    try:
        runner._preflight_actor_grader("G1")
    finally:
        runner.BENCHMARKS_ROOT = original_root
