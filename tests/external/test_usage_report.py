"""``usage_report`` cases. Each case writes small synthetic Claude Code transcripts to ``tmp_path``;
no fixture holds user content."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))
import usage_report  # noqa: E402

PREFIX = "mcp__freecad-buddy__"
PLUGIN_PREFIX = "mcp__plugin_freecad-buddy_freecad-buddy__"
SINCE = date(2026, 10, 18)
UNTIL = date(2026, 11, 18)


@pytest.fixture(autouse=True)
def _typed_tools(monkeypatch):
    monkeypatch.setattr(usage_report, "_typed_tool_names", lambda: ["tool_a", "tool_b"])


def _envelope(status: str = "OK", message: str = "", text: str = "") -> str:
    detail = {"code": status, "message": message} if message else None
    return json.dumps({"status": status, "detail": detail, "structured_content": {}, "text": text})


def _use(call_id: str, name: str, stamp: str, code: str | None = None) -> dict:
    tool_input = {} if code is None else {"code": code}
    return {
        "type": "assistant",
        "timestamp": stamp,
        "message": {
            "content": [{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}]
        },
    }


def _result(call_id: str, content: object) -> dict:
    return {
        "type": "user",
        "timestamp": "2026-11-01T00:00:00Z",
        "message": {
            "content": [{"type": "tool_result", "tool_use_id": call_id, "content": content}]
        },
    }


def _call(call_id: str, tool: str, content: object, stamp="2026-11-01T10:00:00Z", code=None):
    return [_use(call_id, PREFIX + tool, stamp, code), _result(call_id, content)]


def _write(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    return path


def _report(folder: Path, since=SINCE, until=UNTIL):
    return usage_report.build_report([str(folder)], since, until)


def test_Should_count_a_call_once_When_a_resumed_session_repeats_its_tool_use_id(tmp_path):
    # Arrange
    records = _call("id-1", "document_list", _envelope())
    _write(tmp_path / "aaa.jsonl", records)
    _write(tmp_path / "bbb.jsonl", records)

    # Act
    target = _report(tmp_path)

    # Assert
    assert len(target.calls) == 1


def test_Should_not_count_an_api_request_blob_When_it_repeats_a_tool_use(tmp_path):
    # Arrange
    blob = {
        "type": "api-request-blob",
        "timestamp": "2026-11-01T10:00:00Z",
        "message": _use("id-1", PREFIX + "x", "")["message"],
    }
    _write(tmp_path / "aaa.jsonl", [blob])

    # Act
    target = _report(tmp_path)

    # Assert
    assert target.calls == []


def test_Should_include_both_boundary_days_When_the_range_is_inclusive(tmp_path):
    # Arrange
    records = [
        *_call("before", "tool_before", _envelope(), stamp="2026-10-17T23:59:59Z"),
        *_call("first", "tool_first", _envelope(), stamp="2026-10-18T00:00:00Z"),
        *_call("last", "tool_last", _envelope(), stamp="2026-11-18T23:59:59Z"),
        *_call("after", "tool_after", _envelope(), stamp="2026-11-19T00:00:00Z"),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    target = _report(tmp_path)

    # Assert
    assert {call.tool for call in target.calls} == {"tool_first", "tool_last"}


def test_Should_report_boundary_day_calls_under_both_offsets_When_a_call_crosses_midnight(tmp_path):
    # Arrange
    records = _call("late", "document_list", _envelope(), stamp="2026-11-18T20:00:00Z")
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    target = _report(tmp_path)

    # Assert
    assert target.boundary_counts["2026-11-18"] == (1, 0)


def test_Should_count_a_subagent_call_in_its_parent_session_When_it_lives_in_a_subagents_folder(
    tmp_path,
):
    # Arrange
    _write(tmp_path / "sess1.jsonl", _call("id-1", "document_list", _envelope()))
    _write(
        tmp_path / "sess1" / "subagents" / "agent-x.jsonl",
        _call("id-2", "script_exec", _envelope(), code="x=1"),
    )

    # Act
    target = _report(tmp_path)

    # Assert
    assert len(target.calls) == 2
    assert {call.session for call in target.calls} == {"sess1"}


def test_Should_count_both_tool_name_prefixes_When_a_call_uses_the_plugin_server(tmp_path):
    # Arrange
    records = [
        _use("id-1", PLUGIN_PREFIX + "document_list", "2026-11-01T10:00:00Z"),
        _result("id-1", _envelope()),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    target = _report(tmp_path)

    # Assert
    assert [call.tool for call in target.calls] == ["document_list"]


def test_Should_read_the_status_from_the_spill_file_When_the_result_was_spilled(tmp_path):
    # Arrange
    spill = tmp_path / "spill.txt"
    spill.write_text(_envelope("SPEC_FAILED", "boom", text="abc"), encoding="utf-8")
    stub = f"Error: result (99 characters) exceeds maximum allowed tokens. Output saved to {spill}"
    _write(tmp_path / "aaa.jsonl", _call("id-1", "verify_shape", [{"type": "text", "text": stub}]))

    # Act
    target = _report(tmp_path)

    # Assert
    (call,) = target.calls
    assert (call.status, call.envelope_text_size) == ("SPEC_FAILED", 3)


def test_Should_give_no_status_When_the_spill_file_is_missing(tmp_path):
    # Arrange
    stub = f"Error: result (99 characters) exceeds maximum. Output saved to {tmp_path / 'gone.txt'}"
    _write(tmp_path / "aaa.jsonl", _call("id-1", "verify_shape", stub))

    # Act
    target = _report(tmp_path)

    # Assert
    assert target.calls[0].status is None


def test_Should_read_the_status_from_the_text_prefix_When_the_tool_is_query_tree_summary(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "query_tree_summary", [{"type": "text", "text": "OK: tree"}]),
        *_call("id-2", "query_tree_summary", [{"type": "text", "text": "no prefix here"}]),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    target = _report(tmp_path)

    # Assert
    assert [call.status for call in target.calls] == ["OK", None]


def test_Should_split_read_only_and_mutating_scripts_When_the_code_assigns_an_attribute(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "script_exec", _envelope(), code="print(doc.Objects)"),
        *_call("id-2", "script_exec", _envelope(), code="obj.Label = 'x'"),
        *_call("id-3", "script_exec", _envelope(), code="doc.removeObject('a')"),
    ]
    _write(tmp_path / "aaa.jsonl", records)
    target = _report(tmp_path)

    # Act
    text = usage_report.render(target)

    # Assert
    assert "Read-only 1 (33% of calls), mutating 2." in text


def test_Should_count_a_script_in_every_class_it_matches_When_the_code_matches_several(tmp_path):
    # Arrange
    code = "s = Part.makeBox(1,1,1)\nprint(s.BoundBox, s.isValid())"
    _write(tmp_path / "aaa.jsonl", _call("id-1", "script_exec", _envelope(), code=code))
    target = _report(tmp_path)

    # Act
    text = usage_report.render(target)

    # Assert
    assert "| Bounding box or volume read | 1 |" in text
    assert "| `isValid` check | 1 |" in text
    assert "| Part primitives and booleans | 1 |" in text
    assert "| `removeObject` | 0 |" in text


def test_Should_group_failures_by_class_When_messages_and_statuses_match(tmp_path):
    # Arrange
    records = [
        *_call(
            "id-1",
            "export_step",
            _envelope("INVALID_INPUT", "export supports a single object; got multiple"),
        ),
        *_call(
            "id-2",
            "script_exec",
            _envelope("RECOMPUTE_ERROR", "'NoneType' object has no attribute 'Shape'"),
            code="x",
        ),
        *_call(
            "id-3",
            "document_save",
            _envelope("INVALID_INPUT", "unknown or stale document handle: fcb-doc:x"),
        ),
        *_call("id-4", "verify_shape", _envelope("INVALID_INPUT", "is_valid_solid needs 'expect'")),
        *_call("id-5", "document_list", _envelope()),
    ]
    _write(tmp_path / "aaa.jsonl", records)
    target = _report(tmp_path)

    # Act
    text = usage_report.render(target)

    # Assert
    assert "| Multi-object export refused | 1 |" in text
    assert "| Python error reported as `RECOMPUTE_ERROR` | 1 |" in text
    assert "| Stale document handle | 1 |" in text
    assert "| `verify_shape` input rejected | 1 |" in text


def test_Should_list_typed_tools_with_zero_calls_When_some_typed_tools_were_not_called(tmp_path):
    # Arrange
    _write(tmp_path / "aaa.jsonl", _call("id-1", "tool_a", _envelope()))
    target = _report(tmp_path)

    # Act
    text = usage_report.render(target)

    # Assert
    assert (
        "Typed tools with **0 calls** in scope (catalog of the installed source): `tool_b`." in text
    )


def test_Should_show_not_ok_statuses_per_tool_When_calls_fail(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "script_exec", _envelope(), code="x"),
        *_call("id-2", "script_exec", _envelope("TIMEOUT", "marshaled call timed out"), code="x"),
    ]
    _write(tmp_path / "aaa.jsonl", records)
    target = _report(tmp_path)

    # Act
    text = usage_report.render(target)

    # Assert
    assert "| `script_exec` | 2 | 1 | TIMEOUT 1 |" in text
    assert "| `script_exec` timeout | 1 |" in text


def test_Should_report_first_batch_and_ever_loaded_When_a_transcript_searches_twice(tmp_path):
    # Arrange
    def search(call_id, *names):
        content = [{"type": "tool_reference", "tool_name": PREFIX + name} for name in names]
        return [
            {
                "type": "assistant",
                "timestamp": "2026-11-01T10:00:00Z",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": call_id, "name": "ToolSearch", "input": {}}
                    ]
                },
            },
            _result(call_id, content),
        ]

    _write(tmp_path / "aaa.jsonl", [*search("s1", "document_list"), *search("s2", "script_exec")])

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "1 transcripts load freecad-buddy tools." in text
    assert "| `document_list` | 1 | 1 |" in text
    assert "| `script_exec` | 0 | 1 |" in text


def test_Should_report_the_text_field_share_When_results_carry_a_text_field(tmp_path):
    # Arrange
    body = _envelope(text="x" * 100)
    _write(tmp_path / "aaa.jsonl", _call("id-1", "script_exec", body, code="x"))

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert f"| `script_exec` | 1 | {len(body)} | 100 | {round(100 * 100 / len(body))}% |" in text


def test_Should_read_a_project_folder_by_name_When_the_name_is_under_the_projects_root(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.setattr(usage_report, "_PROJECTS_ROOT", tmp_path)
    _write(tmp_path / "project-name" / "aaa.jsonl", _call("id-1", "document_list", _envelope()))

    # Act
    target = usage_report.build_report(["project-name"], SINCE, UNTIL)

    # Assert
    assert len(target.calls) == 1


def test_Should_read_the_status_from_the_file_When_the_spill_uses_the_persisted_output_format(
    tmp_path,
):
    # Arrange
    spill = tmp_path / "persisted.txt"
    spill.write_text(_envelope("SPEC_FAILED", "boom"), encoding="utf-8")
    stub = f"<persisted-output>\nOutput too large (39.9KB). Full output saved to: {spill}\n"
    _write(tmp_path / "aaa.jsonl", _call("id-1", "verify_shape", [{"type": "text", "text": stub}]))

    # Act
    target = _report(tmp_path)

    # Assert
    assert target.calls[0].status == "SPEC_FAILED"


def test_Should_read_the_status_of_a_spilled_tree_summary_When_the_stub_names_a_file(tmp_path):
    # Arrange
    spill = tmp_path / "tree.txt"
    spill.write_text("OK: long tree", encoding="utf-8")
    stub = f"Error: result (99 characters) exceeds maximum. Output saved to {spill}"
    _write(
        tmp_path / "aaa.jsonl",
        _call("id-1", "query_tree_summary", [{"type": "text", "text": stub}]),
    )

    # Act
    target = _report(tmp_path)

    # Assert
    assert target.calls[0].status == "OK"


def test_Should_pair_a_result_with_its_call_When_the_result_is_in_a_later_file(tmp_path):
    # Arrange
    use, result = _call("id-1", "document_list", _envelope())
    _write(tmp_path / "aaa.jsonl", [use])
    _write(tmp_path / "bbb.jsonl", [use, result])

    # Act
    target = _report(tmp_path)

    # Assert
    assert [call.status for call in target.calls] == ["OK"]


def test_Should_skip_an_unreadable_line_When_the_last_line_is_partly_written(tmp_path):
    # Arrange
    path = _write(tmp_path / "aaa.jsonl", _call("id-1", "document_list", _envelope()))
    path.write_text(path.read_text(encoding="utf-8") + '\n{"type": "assis', encoding="utf-8")

    # Act
    target = _report(tmp_path)

    # Assert
    assert len(target.calls) == 1


def test_Should_fail_with_a_clear_error_When_the_project_folder_does_not_exist(tmp_path):
    # Arrange
    missing = str(tmp_path / "no-such-folder")

    # Act
    act = lambda: usage_report.build_report([missing], SINCE, UNTIL)  # noqa: E731

    # Assert
    with pytest.raises(FileNotFoundError, match="no project folder"):
        act()


def test_Should_reject_the_range_When_since_is_after_until(tmp_path, capsys):
    # Arrange
    arguments = ["--since", "2026-11-18", "--until", "2026-10-18", str(tmp_path)]

    # Act
    act = lambda: usage_report.main(arguments)  # noqa: E731

    # Assert
    with pytest.raises(SystemExit):
        act()
    assert "--since is after --until" in capsys.readouterr().err


def test_Should_group_the_remaining_failure_classes_When_messages_match(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "feature_pad", _envelope("SPEC_FAILED", "TNP audit flagged 4 reference(s)")),
        *_call(
            "id-2",
            "script_exec",
            _envelope("INVALID_INPUT", "document-suspect: prior timeout"),
            code="x",
        ),
        *_call(
            "id-3",
            "feature_set_parameters",
            _envelope(
                "INVALID_INPUT",
                "A is a App::PropertyPlacement, which feature_set_parameters cannot write",
            ),
        ),
        *_call("id-4", "export_stl", _envelope("INVALID_INPUT", "cannot write the file")),
        *_call("id-5", "document_save", _envelope("INVALID_INPUT", "something else")),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "| TNP audit flag on a typed mutation | 1 |" in text
    assert "| Document-suspect refusal after timeout | 1 |" in text
    assert "| `feature_set_parameters` cannot write | 1 |" in text
    assert "| Not OK, no class above (includes calls with no outcome) | 2 |" in text


def test_Should_keep_a_failure_example_on_one_line_When_the_message_has_newlines_and_backticks(
    tmp_path,
):
    # Arrange
    message = "Traceback:\n  File `x`\nValueError"
    _write(
        tmp_path / "aaa.jsonl",
        _call("id-1", "script_exec", _envelope("RECOMPUTE_ERROR", message), code="x"),
    )

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "| `Traceback: File 'x' ValueError` |" in text


def test_Should_ignore_tool_searches_outside_the_range_and_repeated_ones_When_counting_loads(
    tmp_path,
):
    # Arrange
    def search(call_id, stamp, name):
        use = {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "content": [{"type": "tool_use", "id": call_id, "name": "ToolSearch", "input": {}}]
            },
        }
        reference = [{"type": "tool_reference", "tool_name": PLUGIN_PREFIX + name}]
        return [use, _result(call_id, reference)]

    inside = search("s1", "2026-11-01T10:00:00Z", "document_list")
    outside = search("s2", "2026-12-01T10:00:00Z", "script_exec")
    _write(tmp_path / "aaa.jsonl", [*inside, *outside])
    _write(tmp_path / "bbb.jsonl", inside)

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "1 transcripts load freecad-buddy tools." in text
    assert "| `document_list` | 1 | 1 |" in text
    assert "| `script_exec` | 0 | 1 |" not in text


def test_Should_match_the_loft_class_When_the_code_creates_a_partdesign_or_part_loft_shape(
    tmp_path,
):
    # Arrange
    codes = [
        "body.newObject('PartDesign::AdditiveLoft', 'A')",
        "body.newObject('PartDesign::SubtractivePipe', 'B')",
        "body.newObject('PartDesign::AdditiveHelix', 'C')",
        "body.newObject('PartDesign::Thickness', 'D')",
        "doc.addObject('Part::Loft', 'E')",
        "Part.makePipeShell([w], True, False)",
        "name = 'Loft_FloorCavity'",
    ]
    records = [
        record
        for index, code in enumerate(codes)
        for record in _call(f"id-{index}", "script_exec", _envelope(), code=code)
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "| Loft, sweep, helix, thickness | 6 |" in text


def test_Should_count_a_timeout_in_the_row_of_its_own_tool_When_a_typed_tool_times_out(tmp_path):
    # Arrange
    message = "marshaled call timed out after 30 s"
    records = [
        *_call("id-1", "query_tree_summary", [{"type": "text", "text": f"TIMEOUT: {message}"}]),
        *_call("id-2", "script_exec", _envelope("TIMEOUT", message), code="x"),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "| `script_exec` timeout | 1 |" in text
    assert "| `query_tree_summary` | 1 | 0 | TIMEOUT 1 |" in text
    assert "| Not OK, no class above (includes calls with no outcome) | 1 |" in text


def test_Should_count_a_call_of_every_server_whose_name_contains_freecad_buddy(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "document_list", _envelope()),
        _use("id-2", "mcp__freecad-buddy-docker__document_list", "2026-11-01T10:00:00Z"),
        _result("id-2", _envelope()),
        _use("id-3", "mcp__other-server__document_list", "2026-11-01T10:00:00Z"),
        _result("id-3", _envelope()),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    target = _report(tmp_path)
    text = usage_report.render(target)

    # Assert
    assert sorted(call.server for call in target.calls) == ["freecad-buddy", "freecad-buddy-docker"]
    assert "- Servers: `freecad-buddy` 1, `freecad-buddy-docker` 1." in text


def test_Should_count_a_mutation_as_mutating_When_it_follows_a_semicolon_on_one_line(tmp_path):
    # Arrange
    records = [
        *_call("id-1", "script_exec", _envelope(), code="o = doc.getObject('A'); o.Placement = P"),
        *_call(
            "id-2",
            "script_exec",
            _envelope(),
            code="o = doc.getObject('A'); print(o.Shape.Volume == 1)",
        ),
        *_call("id-3", "script_exec", _envelope(), code="d['k'].v = 1"),
        *_call("id-4", "script_exec", _envelope(), code="o.Length += 1"),
        *_call("id-5", "script_exec", _envelope(), code="f(a=1); g.h(b=2)"),
    ]
    _write(tmp_path / "aaa.jsonl", records)

    # Act
    text = usage_report.render(_report(tmp_path))

    # Assert
    assert "Read-only 2 (40% of calls), mutating 3." in text


def test_Should_pair_a_result_with_its_call_When_the_result_file_sorts_before_the_call_file(
    tmp_path,
):
    # Arrange
    use, result = _call("id-1", "document_list", _envelope())
    _write(tmp_path / "aaa.jsonl", [result])
    _write(tmp_path / "bbb.jsonl", [use])

    # Act
    target = _report(tmp_path)

    # Assert
    assert [call.status for call in target.calls] == ["OK"]
