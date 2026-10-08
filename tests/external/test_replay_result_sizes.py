"""Pure tests for the transcript result-size replay (no FreeCAD required)."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))

import replay_result_sizes  # noqa: E402

_ENVELOPE = {
    "schema": "fcb.result-envelope/1",
    "status": "OK",
    "detail": None,
    "structured_content": {"doc": "fcb-doc:D", "total_objects": 3, "shown": 2, "truncated": False},
    "text": "3 objects, 2 shown.",
}
_TREE = "v [BODY] Body\n`-- v [PAD] Pad *tip"


def _transcript(tmp_path: Path) -> Path:
    envelope_text = json.dumps(_ENVELOPE, separators=(",", ":"))
    records = [
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "mcp__freecad-buddy__query_tree_summary",
                    }
                ]
            }
        },
        {
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [
                            {"type": "text", "text": envelope_text},
                            {"type": "text", "text": _TREE},
                        ],
                    }
                ]
            }
        },
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    return path


def test_should_parse_the_first_item_and_count_every_item_when_a_result_has_two_blocks(
    tmp_path, capsys
):
    # Arrange
    transcript = _transcript(tmp_path)
    envelope_size = len(json.dumps(_ENVELOPE, separators=(",", ":"), ensure_ascii=False))
    expected = envelope_size + len(_TREE)

    # Act
    exit_code = replay_result_sizes.main([str(transcript)])

    # Assert
    report = capsys.readouterr().out
    assert exit_code == 0
    assert "excluded, not a JSON envelope: 0" in report
    assert f"total: 1 results, before {expected:,}, after {expected:,}" in report
