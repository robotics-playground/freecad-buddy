"""Pure tests for the plain-text document tree (no FreeCAD required)."""

import re
from pathlib import Path

from freecad_buddy.usecases.tree_text import (
    LINE_CAP,
    TYPE_CODE_OVERRIDES,
    TreeNode,
    cap_lines,
    node_line,
    path_line,
    tree_lines,
    type_code,
)

CATALOG = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "freecad-fundamentals"
    / "references"
    / "tree-codes.md"
)


def _node(name, type_id="PartDesign::Pad", visible=True, **kw):
    return TreeNode(name=name, label=kw.pop("label", name), type_id=type_id, visible=visible, **kw)


def test_should_use_the_override_when_the_type_id_is_in_the_table():
    # Arrange
    type_id = "PartDesign::Plane"

    # Act
    code = type_code(type_id)

    # Assert
    assert code == "DPLANE"


def test_should_capitalize_the_suffix_when_the_type_id_is_unknown():
    # Arrange
    type_id = "Foo::BarBaz"

    # Act
    code = type_code(type_id)

    # Assert
    assert code == "BARBAZ"


def test_should_capitalize_the_whole_id_when_the_type_id_has_no_namespace():
    # Arrange
    type_id = "Spreadsheet"

    # Act
    code = type_code(type_id)

    # Assert
    assert code == "SPREADSHEET"


def test_should_render_name_only_when_label_equals_name_and_node_is_a_leaf():
    # Arrange
    node = _node("sma_boss", visible=True)

    # Act
    line = node_line(node)

    # Assert
    assert line == "v [PAD] sma_boss"


def test_should_render_every_suffix_in_order_when_all_apply():
    # Arrange
    node = _node(
        "Pad",
        label="boss",
        visible=False,
        tip=True,
        status="Invalid\n  shape",
        not_shown=2,
    )

    # Act
    line = node_line(node)

    # Assert
    assert line == '- [PAD] Pad "boss" (+2) *tip !Invalid shape'


def test_should_keep_one_line_and_escape_quotes_when_the_label_has_newlines_and_quotes():
    # Arrange
    node = _node("Pad", label='the "boss"\n  pad')

    # Act
    line = node_line(node)

    # Assert
    assert line == 'v [PAD] Pad "the \\"boss\\" pad"'


def test_should_say_more_when_a_node_shows_some_children_and_hides_others():
    # Arrange
    node = _node("body", "PartDesign::Body", visible=True, children=[_node("x")], not_shown=5)

    # Act
    line = node_line(node)

    # Assert
    assert line == "v [BODY] body (+5 more)"


def test_should_end_with_the_target_when_the_node_is_a_link():
    # Arrange
    node = _node("L", "App::Link", visible=True, link_target="Box")

    # Act
    line = node_line(node)

    # Assert
    assert line == "v [LINK] L -> Box"


def test_should_draw_middle_and_last_connectors_with_matching_prefixes():
    # Arrange
    pocket = _node(
        "cut",
        "PartDesign::Pocket",
        visible=False,
        children=[_node("cut_sketch", "Sketcher::SketchObject", visible=False)],
    )
    pad = _node(
        "boss",
        visible=True,
        children=[_node("boss_sketch", "Sketcher::SketchObject", visible=False)],
    )
    body = _node("body", "PartDesign::Body", visible=True, children=[pocket, pad])
    other = _node("other", "PartDesign::Body", visible=True, not_shown=3)

    # Act
    lines = tree_lines([body, other])

    # Assert
    assert lines == [
        "v [BODY] body",
        "|-- - [POCKET] cut",
        "|   `-- - [SKETCH] cut_sketch",
        "`-- v [PAD] boss",
        "    `-- - [SKETCH] boss_sketch",
        "v [BODY] other (+3)",
    ]


def test_should_join_names_with_arrows_when_building_the_path_line():
    # Arrange
    names = ["drawer", "Origin", "XY_Plane"]

    # Act
    line = path_line(names)

    # Assert
    assert line == "path: drawer > Origin > XY_Plane"


def test_should_keep_every_line_when_the_tree_fits_the_cap():
    # Arrange
    lines = [f"line {index}" for index in range(LINE_CAP)]

    # Act
    capped, truncated = cap_lines(lines)

    # Assert
    assert capped == lines
    assert truncated is False


def test_should_cut_and_steer_when_the_tree_exceeds_the_cap():
    # Arrange
    lines = [f"line {index}" for index in range(LINE_CAP + 7)]

    # Act
    capped, truncated = cap_lines(lines)

    # Assert
    assert truncated is True
    assert capped[:LINE_CAP] == lines[:LINE_CAP]
    assert capped[-1] == "... 7 more lines; narrow with focus or a smaller depth"
    assert len(capped) == LINE_CAP + 1


def test_should_match_the_code_table_when_the_skill_catalog_is_parsed():
    # Arrange
    row = re.compile(r"^\| `([^`]+)` \| `([A-Z]+)` \|$")
    text = CATALOG.read_text(encoding="utf-8")

    # Act
    catalog = dict(
        match.groups() for match in map(row.match, text.splitlines()) if match is not None
    )

    # Assert
    assert catalog == TYPE_CODE_OVERRIDES
