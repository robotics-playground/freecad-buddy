"""``ci.yml`` never hides a failing exit code (external / pytest, no FreeCAD).

Every CI job blocks: no ``continue-on-error``, no ``|| true``, and a ``set +e`` step must check
the exit code it captured.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

CI_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

_OR_TRUE = re.compile(r"\|\|\s*true\b")
_EXIT_CODE_CHECK = re.compile(r"\$\?|\$code\b|\$\{code\}")


def _jobs() -> dict:
    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _run_steps():
    for job_name, job in _jobs().items():
        for step in job.get("steps", []):
            if "run" in step:
                yield f"{job_name}/{step.get('name', step['run'][:40])}", step["run"]


def test_should_have_no_continue_on_error_when_ci_yml_is_read():
    # Arrange
    jobs = _jobs()

    # Act
    offenders = [
        name
        for name, job in jobs.items()
        if "continue-on-error" in job
        or any("continue-on-error" in step for step in job.get("steps", []))
    ]

    # Assert
    assert offenders == [], f"jobs with continue-on-error: {offenders}"


def test_should_have_no_or_true_when_a_step_runs_a_command():
    # Arrange
    steps = list(_run_steps())

    # Act
    offenders = [name for name, script in steps if _OR_TRUE.search(script)]

    # Assert
    assert offenders == [], f"steps hiding an exit code with || true: {offenders}"


def test_should_check_the_exit_code_when_a_step_uses_set_plus_e():
    # Arrange
    steps = list(_run_steps())

    # Act
    offenders = [
        name
        for name, script in steps
        if "set +e" in script and not _EXIT_CODE_CHECK.search(script.split("set +e", 1)[1])
    ]

    # Assert
    assert offenders == [], f"set +e steps that never check the exit code: {offenders}"
