"""``uat_watchdog --since`` cases from the Story 10.7 I/O matrix: a naive, an aware and an
unparsable cutoff, and the creation-time comparison around the cutoff."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))
import uat_watchdog  # noqa: E402


def test_should_return_the_same_naive_time_when_the_cutoff_is_naive():
    # Arrange
    value = "2026-10-03T23:17:00"

    # Act
    since = uat_watchdog.parse_since(value)

    # Assert
    assert since == datetime(2026, 10, 3, 23, 17)
    assert since.tzinfo is None


@pytest.mark.parametrize("value", ["2026-10-03T23:17:00+07:00", "2026-10-03T16:17:00Z"])
def test_should_return_local_naive_time_when_the_cutoff_is_aware(value):
    # Arrange
    expected = datetime.fromisoformat(value).astimezone().replace(tzinfo=None)

    # Act
    since = uat_watchdog.parse_since(value)

    # Assert
    assert since == expected
    assert since.tzinfo is None


def test_should_exit_2_naming_since_when_the_cutoff_is_unparsable(monkeypatch, capsys):
    # Arrange
    argv = ["uat_watchdog.py", "--pid", "1", "--since", "yesterday"]
    monkeypatch.setattr(sys, "argv", argv)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        uat_watchdog.main()

    # Assert
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "argument --since: not an ISO timestamp" in error
    assert "Traceback" not in error


def _folder_created_at(tmp_path: Path) -> tuple[Path, datetime]:
    folder = tmp_path / "FCB_TMP_snap_probe"
    folder.mkdir()
    stat = folder.stat()
    created = getattr(stat, "st_birthtime", None) or stat.st_ctime
    return folder, datetime.fromtimestamp(created)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(timedelta(minutes=-1), True), (timedelta(minutes=1), False)],
)
def test_should_compare_with_the_creation_time_when_the_cutoff_is_aware(tmp_path, offset, expected):
    # Arrange
    folder, created = _folder_created_at(tmp_path)
    aware = (created + offset).astimezone().isoformat()
    since = uat_watchdog.parse_since(aware)

    # Act
    after = uat_watchdog._created_after(folder, since)

    # Assert
    assert after is expected


def test_should_return_false_when_the_path_is_missing(tmp_path):
    # Arrange
    missing = tmp_path / "absent"
    since = datetime.now()

    # Act
    after = uat_watchdog._created_after(missing, since)

    # Assert
    assert after is False
