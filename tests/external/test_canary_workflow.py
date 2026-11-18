"""``canary.yml`` keeps its contract (external / pytest, no FreeCAD).

The weekly canary tracks the next FreeCAD development line and may fail without blocking a pull
request (AD-11). It must still run on a schedule or by hand only, resolve a real FreeCAD build,
install what both suites import, and never hide a failing exit code.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CANARY_WORKFLOW = WORKFLOWS / "canary.yml"
CI_WORKFLOW = WORKFLOWS / "ci.yml"

_OR_TRUE = re.compile(r"\|\|\s*true\b")
_INSTALL_MARKER = "--no-deps -e ."


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _canary_steps() -> list[dict]:
    jobs = _load(CANARY_WORKFLOW)["jobs"]
    assert len(jobs) == 1, f"the canary is one job, found {list(jobs)}"
    return next(iter(jobs.values()))["steps"]


def _step_named(name: str) -> dict:
    return next(step for step in _canary_steps() if step.get("name") == name)


def _install_line(steps: list[dict]) -> str:
    lines = [s["run"] for s in steps if _INSTALL_MARKER in s.get("run", "")]
    assert len(lines) == 1, f"expected one install step, found {len(lines)}"
    return lines[0]


def test_should_run_only_on_schedule_and_dispatch_when_canary_yml_is_read():
    # Arrange
    workflow = _load(CANARY_WORKFLOW)

    # Act
    triggers = workflow[True] if True in workflow else workflow["on"]

    # Assert
    assert sorted(triggers) == ["schedule", "workflow_dispatch"]


def test_should_ask_a_dev_freecad_from_conda_forge_only_when_the_environment_is_solved():
    # Arrange
    setup = next(s for s in _canary_steps() if "setup-micromamba" in s.get("uses", ""))["with"]

    # Act
    specs = setup["create-args"].split()
    channels = yaml.safe_load(setup["condarc"])["channels"]

    # Assert
    assert specs == ["freecad>=2026"]
    assert channels == ["conda-forge"]


def test_should_install_the_ci_headless_dependency_line_when_the_package_is_installed():
    # Arrange
    ci_steps = _load(CI_WORKFLOW)["jobs"]["headless"]["steps"]

    # Act
    canary_line = _install_line(_canary_steps())

    # Assert
    assert canary_line == _install_line(ci_steps)


def test_should_not_hide_a_failure_when_canary_yml_is_read():
    # Arrange
    jobs = _load(CANARY_WORKFLOW)["jobs"]
    steps = [step for job in jobs.values() for step in job["steps"]]

    # Act
    masked = [
        step.get("name", step.get("run", step.get("uses", "?"))[:40])
        for step in steps
        if "continue-on-error" in step or _OR_TRUE.search(step.get("run", ""))
    ]
    job_masked = [name for name, job in jobs.items() if "continue-on-error" in job]

    # Assert
    assert masked == [], f"steps hiding a failure: {masked}"
    assert job_masked == [], f"jobs hiding a failure: {job_masked}"


def test_should_run_the_external_suite_after_a_failed_in_freecad_suite_when_canary_yml_is_read():
    # Arrange
    step = _step_named("External suite")

    # Act
    condition = step.get("if", "")

    # Assert
    assert "!cancelled()" in condition
