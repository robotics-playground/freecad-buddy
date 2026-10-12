"""The CI-scope G0 check and the validator source map it reads (external / pytest, no FreeCAD).

``ci-check G0`` passes only when the stored G0.4 report re-derives OK and every validator G0
cites is current. Its run directory and registry are redirected into ``tmp_path`` so no test
writes under ``benchmarks/``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BENCHMARKS / "g0" / "export-fault-injection"))

import score_export_verify  # noqa: E402

from benchmarks import runner  # noqa: E402
from benchmarks.harness.report_build import evidence_report  # noqa: E402

RUN_ID = "ci-test"
G0_CITED = ("verify_shape", "verify_export_step")

# G3.2 and G3.3 cite verify_recompute, but no scorer exists for it and it has no registry entry,
# so leg-b reports it "not in registry" and there is no scorer source list to match. Once a scorer
# registers it, the test below fails until it gets a _VALIDATOR_SOURCES entry.
_UNSCORED_CITED = {"verify_recompute"}


def _report(criterion: str, passed: bool) -> dict:
    return evidence_report(
        criterion,
        [
            {
                "id": criterion,
                "measured": passed,
                "expected": True,
                "passed": passed,
                "detail": {"code": "ok" if passed else "spec_failed.mismatch", "message": "-"},
            }
        ],
    )


def _arrange_run(tmp_path, monkeypatch, *, g0_4_report: str | None = None) -> None:
    """A run dir holding one G0.4 report, plus a registry where every G0 validator is current.

    ``g0_4_report`` is the raw report file text; the default is a passing G0.4 report.
    """
    run_dir = tmp_path / "run"
    (run_dir / "reports").mkdir(parents=True)
    if g0_4_report is None:
        g0_4_report = json.dumps(_report("G0.4", True))
    (run_dir / "reports" / "G0.4.json").write_text(g0_4_report, encoding="utf-8")
    monkeypatch.setattr(runner, "_run_dir", lambda _gate, _run_id: run_dir)

    registry = {
        name: {
            "validator_sha": runner._validator_src_hasher(name),
            "last_run": {"sensitivity": 1.0, "false_alarm": 0.0},
        }
        for name in G0_CITED
    }
    registry_path = tmp_path / "validators.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    monkeypatch.setattr(runner, "_REGISTRY_YAML", registry_path)


def _cited_validators() -> set[str]:
    cited = set()
    for gate_file in BENCHMARKS.glob("*/gate.yaml"):
        data = yaml.safe_load(gate_file.read_text(encoding="utf-8"))
        for criterion in data["criteria"]:
            cited.update(criterion.get("cited_validators") or [])
    return cited


def test_should_have_a_source_set_when_a_validator_is_cited_by_a_gate():
    # Arrange
    registry = yaml.safe_load((BENCHMARKS / "_registry" / "validators.yaml").read_text("utf-8"))
    cited = _cited_validators() - _UNSCORED_CITED

    # Act
    missing = sorted(cited - set(runner._VALIDATOR_SOURCES))

    # Assert
    assert missing == [], f"cited validators with no _VALIDATOR_SOURCES entry: {missing}"
    assert not _UNSCORED_CITED & set(registry), (
        "a registered validator is in _UNSCORED_CITED: remove it from _UNSCORED_CITED and add its "
        "_VALIDATOR_SOURCES entry"
    )


def test_should_hash_the_scorer_sources_in_order_when_the_validator_is_verify_export_step():
    # Arrange
    expected = tuple(path.resolve() for path in score_export_verify.VALIDATOR_SOURCES)

    # Act
    actual = tuple(path.resolve() for path in runner._VALIDATOR_SOURCES["verify_export_step"])

    # Assert
    assert actual == expected


def test_should_exit_0_when_g0_4_passes_and_every_cited_validator_is_current(
    tmp_path, monkeypatch, capsys
):
    # Arrange
    _arrange_run(tmp_path, monkeypatch)

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 0
    assert "gate G0 ci-check: PASS" in capsys.readouterr().out


def test_should_exit_1_naming_the_validator_when_a_cited_validator_source_changed(
    tmp_path, monkeypatch, capsys
):
    # Arrange
    _arrange_run(tmp_path, monkeypatch)
    sources = list(runner._VALIDATOR_SOURCES["verify_export_step"])
    changed = tmp_path / "export_verdict.py"
    shutil.copyfile(sources[2], changed)
    changed.write_bytes(changed.read_bytes() + b"#")
    sources[2] = changed
    monkeypatch.setitem(runner._VALIDATOR_SOURCES, "verify_export_step", tuple(sources))

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 1
    assert "FAILURE verify_export_step (stale: source hash mismatch)" in capsys.readouterr().out


def test_should_exit_1_when_the_g0_4_report_is_not_ok(tmp_path, monkeypatch, capsys):
    # Arrange
    _arrange_run(tmp_path, monkeypatch, g0_4_report=json.dumps(_report("G0.4", False)))

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 1
    assert "FAILURE G0.4" in capsys.readouterr().out


def test_should_exit_2_when_the_g0_4_report_is_missing(tmp_path, monkeypatch):
    # Arrange
    _arrange_run(tmp_path, monkeypatch)
    (tmp_path / "run" / "reports" / "G0.4.json").unlink()

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 2


def test_should_exit_2_when_the_gate_has_no_ci_scope():
    # Arrange
    argv = ["ci-check", "G1", "--run", RUN_ID]

    # Act
    code = runner.main(argv)

    # Assert
    assert code == 2


def test_should_exit_1_when_the_g0_4_report_is_filed_under_another_criterion(
    tmp_path, monkeypatch, capsys
):
    # Arrange
    _arrange_run(tmp_path, monkeypatch, g0_4_report=json.dumps(_report("G0.1", True)))

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 1
    assert "FAILURE G0.4 (report subject mismatch: 'G0.1')" in capsys.readouterr().out


def test_should_exit_2_when_the_run_dir_is_missing(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(runner, "_run_dir", lambda _gate, _run_id: tmp_path / "absent")

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 2


@pytest.mark.parametrize(
    "g0_4_report",
    ["{not json", json.dumps({**_report("G0.4", True), "checks": []})],
    ids=["malformed", "empty-checks"],
)
def test_should_exit_2_when_the_g0_4_report_is_unusable(tmp_path, monkeypatch, g0_4_report):
    # Arrange
    _arrange_run(tmp_path, monkeypatch, g0_4_report=g0_4_report)

    # Act
    code = runner.main(["ci-check", "G0", "--run", RUN_ID])

    # Assert
    assert code == 2
