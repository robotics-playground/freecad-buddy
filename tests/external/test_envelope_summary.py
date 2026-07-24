from freecad_buddy.contracts.envelope import summary_text


def test_summary_text_flattens_scalars_inline():
    out = summary_text({"status": "OK", "volume": 8642.85, "solid": True})
    assert "status: OK" in out
    assert "volume: 8642.85" in out
    assert "solid: True" in out


def test_summary_text_summarizes_containers_not_dumps_them():
    out = summary_text({"tree": [1, 2, 3], "banner": {"a": 1, "b": 2}})
    assert "tree: [3 items]" in out
    assert "banner: {2 fields}" in out
    assert "[1, 2, 3]" not in out  # NOT a raw dump
