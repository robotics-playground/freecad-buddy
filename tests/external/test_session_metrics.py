"""``session_metrics`` cases from the Story 11.6 I/O matrix and the calls-per-feature rule. Each
case writes a synthetic Claude Code transcript to ``tmp_path``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))
import session_metrics  # noqa: E402

FREECAD = "mcp__freecad-buddy__"


def _call(call_id: str, name: str, text: object) -> list[dict]:
    return [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": call_id, "name": name}]},
        },
        {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": call_id, "content": text}]
            },
        },
    ]


def _envelope(status: str) -> str:
    return json.dumps({"schema": "fcb.result-envelope/1", "status": status, "detail": None})


def _usage(input_tokens: int, cache_read: int, cache_creation: int, sidechain=False) -> dict:
    usage = {
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "output_tokens": 999,
    }
    return {"type": "assistant", "isSidechain": sidechain, "message": {"usage": usage}}


def _compaction() -> list[dict]:
    return [
        {"type": "system", "subtype": "compact_boundary"},
        {"type": "user", "isCompactSummary": True, "message": {"content": "summary"}},
    ]


def _transcript(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "abcdef12-0000.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def _spill_stub(size: str, spill_file: Path) -> str:
    return (
        f"Error: result ({size} characters) exceeds maximum allowed tokens. "
        f"Output has been saved to {spill_file}.\nFormat: JSON with schema: {{schema: string}}"
    )


def test_should_count_one_call_with_its_text_size_when_the_result_is_plain(tmp_path):
    # Arrange
    text = "x" * 500
    path = _transcript(tmp_path, _call("a", FREECAD + "query_object", [{"text": text}]))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert (metrics.calls, metrics.output_chars, metrics.largest) == (1, 500, 500)
    assert metrics.spilled == 0
    assert metrics.session == "abcdef12"


def _persisted_stub(size: str, spill_file: Path) -> str:
    return (
        f"<persisted-output>\nOutput too large ({size}). Full output saved to: {spill_file}\n\n"
        'Preview (first 2KB):\n{"schema"'
    )


def _sequence(calls: list[tuple[str, object]]) -> list[dict]:
    return [
        record
        for index, (tool, text) in enumerate(calls)
        for record in _call(str(index), FREECAD + tool, text)
    ]


def test_should_count_the_stub_and_the_stated_size_when_the_result_spilled(tmp_path):
    # Arrange
    stub = _spill_stub("52,000", tmp_path / "absent.txt")
    records = _sequence(
        [("feature_pad", _envelope("OK")), ("feature_pad", stub), ("feature_pad", _envelope("OK"))]
    )
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.spilled == 1
    assert metrics.output_chars == len(stub) + 2 * len(_envelope("OK"))
    assert metrics.largest == 52_000
    assert metrics.calls_per_feature == (2,)


def test_should_take_largest_from_the_spill_file_when_a_persisted_output_stub_has_its_file(
    tmp_path,
):
    # Arrange
    spill_file = tmp_path / "persisted.txt"
    spill_file.write_text(_envelope("OK") + " " * 40_000, encoding="utf-8")
    stub = _persisted_stub("39.9KB", spill_file)
    path = _transcript(tmp_path, _call("a", FREECAD + "query_object", stub))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.spilled == 1
    assert metrics.output_chars == len(stub)
    assert metrics.largest == len(_envelope("OK")) + 40_000


def test_should_take_largest_from_the_stated_size_when_a_persisted_output_file_is_absent(
    tmp_path,
):
    # Arrange
    stub = _persisted_stub("39.9KB", tmp_path / "absent.txt")
    path = _transcript(tmp_path, _call("a", FREECAD + "query_object", stub))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.spilled == 1
    assert metrics.output_chars == len(stub)
    assert metrics.largest == round(39.9 * 1024)


def test_should_read_the_status_from_the_spill_file_when_a_persisted_output_feature_spilled(
    tmp_path,
):
    # Arrange
    spill_file = tmp_path / "persisted-pocket.txt"
    spill_file.write_text(_envelope("OK"), encoding="utf-8")
    records = _sequence(
        [
            ("feature_pad", _envelope("OK")),
            ("feature_pocket", _persisted_stub("50.0KB", spill_file)),
        ]
    )
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.calls_per_feature == (1,)


def test_should_not_count_the_result_when_another_tool_made_it(tmp_path):
    # Arrange
    path = _transcript(tmp_path, _call("a", "Bash", "y" * 300))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert (metrics.calls, metrics.output_chars, metrics.largest) == (0, 0, 0)


def test_should_stop_reading_at_the_nth_result_when_a_limit_is_given(tmp_path):
    # Arrange
    records = [
        _usage(100, 0, 0),
        *_call("a", FREECAD + "query_object", "1"),
        *_call("b", FREECAD + "query_object", "22"),
        _usage(5_000, 0, 0),
        *_compaction(),
        *_call("c", FREECAD + "query_object", "333"),
    ]
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, 2)

    # Assert
    assert (metrics.calls, metrics.output_chars) == (2, 3)
    assert metrics.peak_context == 100
    assert metrics.compactions == 0


def test_should_count_one_compaction_when_a_boundary_has_its_summary_record(tmp_path):
    # Arrange
    path = _transcript(tmp_path, _compaction())

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.compactions == 1


def test_should_sum_the_three_input_counts_and_skip_sidechains_when_reading_peak(tmp_path):
    # Arrange
    records = [_usage(10, 200, 30), _usage(1, 2, 3), _usage(90_000, 0, 0, sidechain=True)]
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.peak_context == 240


def test_should_skip_freecad_calls_and_compactions_when_their_records_are_sidechain(tmp_path):
    # Arrange
    records = [
        *_call("a", FREECAD + "query_object", "x" * 200),
        {"type": "system", "subtype": "compact_boundary"},
    ]
    for record in records:
        record["isSidechain"] = True
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert (metrics.calls, metrics.output_chars, metrics.compactions) == (0, 0, 0)


def test_should_report_peak_zero_when_the_transcript_has_no_usage(tmp_path):
    # Arrange
    path = _transcript(tmp_path, _call("a", FREECAD + "query_object", "z"))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.peak_context == 0


def test_should_count_calls_after_the_previous_ok_feature_when_measuring_features(tmp_path):
    # Arrange
    spill_file = tmp_path / "spilled-pocket.txt"
    spill_file.write_text(_envelope("OK"), encoding="utf-8")
    sequence = [
        ("query_tree_summary", _envelope("OK")),
        ("preview_dry_run", _envelope("OK")),
        ("feature_pad", _envelope("OK")),
        ("sketch_create", _envelope("OK")),
        ("feature_set_parameters", _envelope("OK")),
        ("feature_pocket", _spill_stub("40,000", spill_file)),
        ("feature_pad", _envelope("SPEC_FAILED")),
        ("verify_shape", _envelope("OK")),
        ("preview_dry_run", _envelope("OK")),
        ("feature_pad", _envelope("OK")),
        ("view_screenshot", _envelope("OK")),
    ]
    path = _transcript(tmp_path, _sequence(sequence))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.calls_per_feature == (3, 4)
    assert metrics.calls_per_feature_median == 3.5
    assert metrics.previews == 2


def test_should_report_no_median_when_the_session_has_fewer_than_two_features(tmp_path):
    # Arrange
    path = _transcript(tmp_path, _call("a", FREECAD + "feature_pad", _envelope("OK")))

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.calls_per_feature_median is None


def test_should_average_output_chars_over_calls_when_the_session_has_calls(tmp_path):
    # Arrange
    records = _sequence([("query_object", "a" * 100), ("query_object", "b" * 300)])
    path = _transcript(tmp_path, records)

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.chars_per_call == 200.0


def test_should_report_zero_chars_per_call_when_the_session_has_no_calls(tmp_path):
    # Arrange
    path = _transcript(tmp_path, [_usage(1, 1, 1)])

    # Act
    metrics = session_metrics.measure(path, None)

    # Assert
    assert metrics.chars_per_call == 0.0


def test_should_print_every_measure_on_one_line_when_formatting_a_session():
    # Arrange
    target = session_metrics.SessionMetrics(
        session="abcdef12",
        calls=4,
        previews=1,
        output_chars=12_345,
        spilled=1,
        largest=10_500,
        peak_context=819_990,
        compactions=2,
        calls_per_feature=(2, 3),
    )

    # Act
    line = session_metrics._line(target)

    # Assert
    assert line == (
        "abcdef12: 4 calls, 1 previews, 3,086 chars per call (12,345 total), 1 spilled, "
        "largest 10,500, peak 819,990, 2 compactions, calls per feature median 2.5 over 2 features"
    )
