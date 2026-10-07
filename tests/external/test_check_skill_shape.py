"""``check_skill_shape`` cases: section names, order and content, the body word cap, and the CLI
exit codes. Each case builds a skill tree in ``tmp_path``; one case checks the real ``skills/``
tree."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_skill_shape  # noqa: E402

FRONT_MATTER = "---\nname: demo\ntrack: A\n---\n"
VALID_BODY = (
    "\n## Scope\n\nOne scope line.\n"
    "\n## Decision Rules\n\n- One rule.\n"
    "\n## Worked Examples\n\nOne example.\n"
    "\n## Anti-Patterns\n\n- One trap.\n"
)


def _make_skill(tmp_path: Path, text: str) -> Path:
    skills_dir = tmp_path / "skills"
    skill = skills_dir / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    return skills_dir


def test_should_report_nothing_when_every_skill_has_the_four_sections(tmp_path):
    # Arrange
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + VALID_BODY)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert violations == []


def test_should_name_the_file_rule_and_found_headings_when_a_heading_is_wrong(tmp_path):
    # Arrange
    body = VALID_BODY.replace("## Worked Examples", "## Examples")
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert len(violations) == 1
    assert violations[0].startswith("demo/SKILL.md -- H2 sections must be")
    assert "'Examples'" in violations[0]


def test_should_flag_the_order_when_two_sections_are_swapped(tmp_path):
    # Arrange
    body = (
        "\n## Decision Rules\n\n- One rule.\n"
        "\n## Scope\n\nOne scope line.\n"
        "\n## Worked Examples\n\nOne example.\n"
        "\n## Anti-Patterns\n\n- One trap.\n"
    )
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert len(violations) == 1
    assert "['Decision Rules', 'Scope', 'Worked Examples', 'Anti-Patterns']" in violations[0]


def test_should_flag_the_extra_heading_when_a_fifth_section_is_added(tmp_path):
    # Arrange
    body = VALID_BODY + "\n## Notes\n\nOne note.\n"
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert len(violations) == 1
    assert "'Notes'" in violations[0]


def test_should_name_the_file_and_section_when_a_section_is_empty(tmp_path):
    # Arrange
    body = VALID_BODY.replace("\n- One rule.\n", "")
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert violations == ["demo/SKILL.md -- section '## Decision Rules' is empty"]


def test_should_flag_the_missing_heading_when_a_section_is_deleted(tmp_path):
    # Arrange
    body = VALID_BODY.replace("\n## Anti-Patterns\n\n- One trap.\n", "")
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert len(violations) == 1
    assert "found ['Scope', 'Decision Rules', 'Worked Examples']" in violations[0]


def test_should_report_the_measured_count_when_the_body_has_1501_words(tmp_path):
    # Arrange
    body_words = len(VALID_BODY.split())
    padding = " ".join(["word"] * (1501 - body_words))
    body = VALID_BODY.replace("One example.", f"One example. {padding}")
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert violations == ["demo/SKILL.md -- body has 1501 words; limit is 1500"]


def test_should_pass_when_the_body_has_exactly_1500_words(tmp_path):
    # Arrange
    body_words = len(VALID_BODY.split())
    padding = " ".join(["word"] * (1500 - body_words))
    body = VALID_BODY.replace("One example.", f"One example. {padding}")
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert violations == []


def test_should_not_count_front_matter_words_when_the_front_matter_is_long(tmp_path):
    # Arrange
    long_description = " ".join(["routing"] * 400)
    front_matter = f"---\nname: demo\ndescription: >-\n  {long_description}\n---\n"
    body_words = len(VALID_BODY.split())
    padding = " ".join(["word"] * (1500 - body_words))
    body = VALID_BODY.replace("One example.", f"One example. {padding}")
    skills_dir = _make_skill(tmp_path, front_matter + body)

    # Act
    violations = check_skill_shape.check_tree(skills_dir)

    # Assert
    assert violations == []


def test_should_exit_1_and_print_the_violation_when_the_tree_is_bad(tmp_path, capsys):
    # Arrange
    skills_dir = _make_skill(tmp_path, FRONT_MATTER + VALID_BODY.replace("## Scope", "## Intro"))

    # Act
    code = check_skill_shape.main([str(skills_dir)])

    # Assert
    assert code == 1
    assert "demo/SKILL.md -- H2 sections must be" in capsys.readouterr().out


def test_should_exit_1_and_print_root_not_found_when_the_root_is_missing(tmp_path, capsys):
    # Arrange
    missing_root = tmp_path / "no-skills"

    # Act
    code = check_skill_shape.main([str(missing_root)])

    # Assert
    assert code == 1
    assert "root not found" in capsys.readouterr().out


def test_should_exit_0_with_no_output_when_the_real_skills_tree_is_checked(capsys):
    # Arrange
    skills_dir = REPO_ROOT / "skills"

    # Act
    code = check_skill_shape.main([str(skills_dir)])

    # Assert
    assert code == 0
    assert capsys.readouterr().out == ""
