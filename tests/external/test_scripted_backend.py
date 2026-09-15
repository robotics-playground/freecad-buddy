"""Scripted-backend tests (external / pytest). The offline actor-run driver replays a recorded
plan over the read-only tool surface; these assert it dispatches what the plan says, answers what
the plan says, refuses a tool outside the allow-list, and holds no state across cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.harness.scripted_backend import (  # noqa: E402
    ScriptedBackend,
    readonly_tool_names,
)


class _RecordingInvoker:
    """Captures every dispatch so a test can assert the exact call sequence."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, tool: str, args: dict) -> dict:
        self.calls.append((tool, args))
        return {"status": "OK", "structured_content": {}}


def test_Should_dispatch_recorded_steps_in_order_When_case_has_a_plan():
    # Arrange
    plans = {
        "case-1": (
            [("query_tree_summary", {"doc": "d"}), ("verify_recompute", {"doc": "d"})],
            "Pad is in error: broken reference.",
        )
    }
    target = ScriptedBackend(plans)
    invoke = _RecordingInvoker()

    # Act
    result = target.answer("case-1", "why is it broken?", readonly_tool_names(), invoke)

    # Assert
    assert invoke.calls == [
        ("query_tree_summary", {"doc": "d"}),
        ("verify_recompute", {"doc": "d"}),
    ]
    assert result.final_answer == "Pad is in error: broken reference."


def test_Should_answer_empty_and_dispatch_nothing_When_case_has_no_plan():
    # Arrange
    target = ScriptedBackend({})
    invoke = _RecordingInvoker()

    # Act
    result = target.answer("unknown-case", "q", readonly_tool_names(), invoke)

    # Assert — an ungraded case fails honestly rather than raising as a harness defect
    assert invoke.calls == []
    assert result.final_answer == ""


def test_Should_refuse_When_plan_names_a_tool_outside_the_read_only_allow_list():
    # Arrange
    plans = {"case-1": ([("feature_pad", {"doc": "d"})], "answer")}
    target = ScriptedBackend(plans)
    invoke = _RecordingInvoker()

    # Act
    act = lambda: target.answer("case-1", "q", readonly_tool_names(), invoke)  # noqa: E731

    # Assert — the double may only drive the surface the live path is limited to
    with pytest.raises(ValueError, match="outside the read-only allow-list"):
        act()
    assert invoke.calls == []


def test_Should_replay_the_full_plan_every_time_When_one_case_is_graded_repeatedly():
    # Arrange — grading a case R times must not exhaust a shared cursor
    plans = {"case-1": ([("query_tree_summary", {"doc": "d"})], "answer")}
    target = ScriptedBackend(plans)

    # Act
    results = []
    for _ in range(3):
        invoke = _RecordingInvoker()
        results.append((target.answer("case-1", "q", [], invoke).final_answer, invoke.calls))

    # Assert
    assert results == [("answer", [("query_tree_summary", {"doc": "d"})])] * 3


def test_Should_exclude_geometry_mutating_tools_When_resolving_the_allow_list():
    # Arrange — document lifecycle is read-only-safe; geometry mutation is not
    mutating_prefixes = ("sketch_", "feature_")

    # Act
    names = readonly_tool_names()

    # Assert
    assert names, "the read-only allow-list resolved empty"
    assert not [n for n in names if n.startswith(mutating_prefixes)]
