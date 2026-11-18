"""``scripts/automation/fcb_cua.sh``: tool dispatch and host-path rewriting of the JSON on standard
input, with a fake ``docker`` that prints what it receives (no container, no cua-driver)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "automation" / "fcb_cua.sh"
BASH = shutil.which("bash")
ROOT = "/work/freecad-buddy"

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def _run(tmp_path: Path, args: list[str], stdin: str, environment: dict[str, str]):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@"\nprintf -- "---STDIN---\\n"\ncat\n',
        encoding="utf-8",
        newline="\n",
    )
    fake_docker.chmod(0o755)
    env = dict(os.environ)
    env.pop("PROJECT_ROOT", None)
    env["MSYS_NO_PATHCONV"] = "1"
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env.update(environment)
    return subprocess.run(
        [BASH, WRAPPER.as_posix(), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _stdin_of(done: subprocess.CompletedProcess) -> str:
    return done.stdout.split("---STDIN---\n", 1)[1]


def test_Should_run_the_tool_as_cua_in_the_session_When_a_tool_name_is_given(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}

    # Act
    done = _run(tmp_path, ["get_window_state"], '{"pid":1}', environment)

    # Assert
    lines = done.stdout.splitlines()
    assert done.returncode == 0
    assert lines[:5] == ["exec", "-i", "-u", "cua", "fcb-desktop"]
    assert lines[5:7] == ["bash", "-c"]
    assert 'eval "$(fcb-session-env)"' in lines[7]
    assert lines[-4:-2] == ["_", "get_window_state"]
    assert 'cua-driver call "$@"' in lines[7]
    assert _stdin_of(done) == '{"pid":1}'


@pytest.mark.parametrize("word", ["status", "doctor", "list-tools", "describe"])
def test_Should_pass_the_word_on_without_call_When_a_management_word_is_given(tmp_path, word):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}

    # Act
    done = _run(tmp_path, [word], "", environment)

    # Assert
    lines = done.stdout.splitlines()
    assert lines[-3:-1] == ["_", word]
    assert "-i" not in lines
    assert "call" not in lines[7]


def test_Should_rewrite_the_root_When_a_json_string_holds_it(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = f'{{"a":"{ROOT}/tests/x.png","b":"{ROOT}"}}'

    # Act
    done = _run(tmp_path, ["screenshot"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"a":"/repo/tests/x.png","b":"/repo"}'


def test_Should_leave_a_sibling_folder_alone_When_its_name_starts_with_the_root(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = f'{{"a":"{ROOT}-other/x","b":"{ROOT}2","c":"{ROOT}2/y"}}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == payload


def test_Should_rewrite_the_backslash_root_When_json_escapes_the_backslashes(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = '{"a":"\\\\work\\\\freecad-buddy\\\\tests\\\\x.png"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"a":"/repo/tests/x.png"}'


def test_Should_leave_a_backslash_sibling_alone_When_its_name_starts_with_the_root(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = '{"a":"\\\\work\\\\freecad-buddy-other\\\\x","b":"\\\\work\\\\freecad-buddy2"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == payload


def test_Should_keep_other_double_backslashes_When_the_string_is_not_below_the_root(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = '{"a":"C:\\\\logs\\\\audit.jsonl"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == payload


def test_Should_rewrite_the_root_When_it_follows_a_flag_prefix_inside_json(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = f'{{"args":["--out={ROOT}/x","--out={ROOT}-other/x"]}}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"args":["--out=/repo/x","--out=/work/freecad-buddy-other/x"]}'


def test_Should_keep_line_breaks_When_the_json_spans_lines(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}
    payload = f'{{\n  "a": "{ROOT}/x"\n}}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{\n  "a": "/repo/x"\n}'


def test_Should_exit_2_naming_the_variable_When_project_root_is_not_set(tmp_path):
    # Arrange
    environment: dict[str, str] = {}

    # Act
    done = _run(tmp_path, ["t"], "{}", environment)

    # Assert
    assert done.returncode == 2
    assert "PROJECT_ROOT is not set" in done.stderr


def test_Should_expand_the_literal_tokens_When_a_single_quoted_line_keeps_them(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT, "RUN_DIR": f"{ROOT}/tests/uat/run/x"}
    payload = '{"a":"$RUN_DIR/evidence/s.png","b":"$PROJECT_ROOT/benchmarks"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"a":"/repo/tests/uat/run/x/evidence/s.png","b":"/repo/benchmarks"}'


def test_Should_exit_2_naming_the_variable_When_the_json_holds_run_dir_and_it_is_not_set(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}

    # Act
    done = _run(tmp_path, ["t"], '{"a":"$RUN_DIR/x"}', environment)

    # Assert
    assert done.returncode == 2
    assert "RUN_DIR is not set" in done.stderr


def test_Should_leave_standard_input_unread_When_a_management_word_is_given(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}

    # Act
    done = _run(tmp_path, ["status"], "untouched", environment)

    # Assert
    assert _stdin_of(done) == "untouched"


def test_Should_map_run_dir_c_to_its_container_path_When_the_token_is_a_longer_name(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT, "RUN_DIR": f"{ROOT}/tests/uat/run/x"}
    payload = '{"a":"$RUN_DIR_C/evidence/s.png"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"a":"/repo/tests/uat/run/x/evidence/s.png"}'


def test_Should_keep_the_closing_quote_When_the_text_ends_with_one(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": ROOT}

    # Act
    done = _run(tmp_path, ["t"], '"abc"', environment)

    # Assert
    assert _stdin_of(done) == '"abc"'


def test_Should_not_expand_an_ampersand_When_the_root_holds_one(tmp_path):
    # Arrange
    root = "/work/a&b"
    environment = {"PROJECT_ROOT": root}
    payload = '{"a":"$PROJECT_ROOT/x"}'

    # Act
    done = _run(tmp_path, ["t"], payload, environment)

    # Assert
    assert _stdin_of(done) == '{"a":"/repo/x"}'
