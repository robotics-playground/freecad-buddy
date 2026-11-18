"""``canary.yml`` keeps its contract (external / pytest, no FreeCAD).

The weekly canary tracks the next FreeCAD development line and may fail without blocking a pull
request (AD-11). The tests are an allowlist of the workflow's structure: the triggers, the solve
inputs, the two suite commands and the step conditions must be exactly the expected ones, so a
change that runs nothing, narrows a suite or hides an exit code fails here.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CANARY_WORKFLOW = WORKFLOWS / "canary.yml"
CI_WORKFLOW = WORKFLOWS / "ci.yml"

_INSTALL_MARKER = "--no-deps -e ."
_SETUP_INPUTS = {"environment-name", "create-args", "condarc", "cache-environment"}
_STEP_CONDITIONS = {
    "In-FreeCAD suite": "${{ !cancelled() && steps.install.outcome == 'success' }}",
    "External suite": "${{ !cancelled() && steps.install.outcome == 'success' }}",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key_node, deep=deep) for key_node, _ in node.value]
        duplicates = sorted({str(key) for key in keys if keys.count(key) > 1})
        if duplicates:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate keys {duplicates}")
        return super().construct_mapping(node, deep=deep)


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506


def _canary_job() -> dict:
    jobs = _load(CANARY_WORKFLOW)["jobs"]
    assert len(jobs) == 1, f"the canary is one job, found {list(jobs)}"
    return next(iter(jobs.values()))


def _step_starting(steps: list[dict], name_prefix: str) -> dict:
    matches = [s for s in steps if s.get("name", "").startswith(name_prefix)]
    assert len(matches) == 1, f"expected one step named '{name_prefix}...', found {len(matches)}"
    return matches[0]


def _install_line(steps: list[dict]) -> str:
    lines = [s["run"] for s in steps if _INSTALL_MARKER in s.get("run", "")]
    assert len(lines) == 1, f"expected one install step, found {len(lines)}"
    return lines[0]


def _setup_inputs() -> dict:
    steps = _canary_job()["steps"]
    return next(s for s in steps if "setup-micromamba" in s.get("uses", ""))["with"]


def test_should_have_unique_keys_when_canary_yml_is_parsed():
    # Arrange
    path = CANARY_WORKFLOW

    # Act
    workflow = _load(path)

    # Assert
    assert "jobs" in workflow


def test_should_run_only_on_schedule_and_dispatch_when_canary_yml_is_read():
    # Arrange
    workflow = _load(CANARY_WORKFLOW)

    # Act
    triggers = workflow[True] if True in workflow else workflow["on"]

    # Assert
    assert sorted(triggers) == ["schedule", "workflow_dispatch"]


def test_should_ask_a_dev_freecad_from_conda_forge_only_when_the_environment_is_solved():
    # Arrange
    setup = _setup_inputs()

    # Act
    specs = setup["create-args"].split()
    channels = yaml.safe_load(setup["condarc"])["channels"]

    # Assert
    assert specs == ["freecad>=2026"]
    assert channels == ["conda-forge"]
    assert set(setup) <= _SETUP_INPUTS, f"unexpected setup inputs: {set(setup) - _SETUP_INPUTS}"


def test_should_install_the_ci_headless_dependency_line_when_the_package_is_installed():
    # Arrange
    ci_steps = _load(CI_WORKFLOW)["jobs"]["headless"]["steps"]

    # Act
    canary_line = _install_line(_canary_job()["steps"])

    # Assert
    assert canary_line == _install_line(ci_steps)


def test_should_run_the_ci_suite_commands_when_the_canary_steps_are_read():
    # Arrange
    ci_steps = _load(CI_WORKFLOW)["jobs"]["headless"]["steps"]
    canary_steps = _canary_job()["steps"]

    # Act
    canary_commands = {
        name: _step_starting(canary_steps, name)["run"].strip() for name in _STEP_CONDITIONS
    }
    ci_commands = {name: _step_starting(ci_steps, name)["run"].strip() for name in _STEP_CONDITIONS}

    # Assert
    assert canary_commands == ci_commands


def test_should_not_hide_a_failure_when_canary_yml_is_read():
    # Arrange
    workflow = _load(CANARY_WORKFLOW)
    job = _canary_job()
    steps = job["steps"]

    # Act
    masking_keys = [
        scope
        for scope, node in {
            "workflow": workflow,
            "job": job,
            **{f"step {i}": s for i, s in enumerate(steps)},
        }.items()
        if {"continue-on-error", "shell", "defaults"} & set(node)
    ]
    masking_commands = [
        step["run"]
        for step in steps
        if "||" in step.get("run", "") or "set +e" in step.get("run", "")
    ]

    # Assert
    assert masking_keys == [], f"scopes with continue-on-error, shell or defaults: {masking_keys}"
    assert masking_commands == [], f"commands hiding an exit code: {masking_commands}"


def test_should_run_the_suites_after_a_failed_suite_only_when_the_install_succeeded():
    # Arrange
    job = _canary_job()
    steps = job["steps"]

    # Act
    conditions = {
        name: _step_starting(steps, name).get("if", "").strip() for name in _STEP_CONDITIONS
    }

    # Assert
    assert conditions == _STEP_CONDITIONS
    assert "if" not in job
