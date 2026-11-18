"""``uat_watchdog --since`` cases from the Story 10.7 I/O matrix: a naive, an aware and an
unparsable cutoff, and the creation-time comparison around the cutoff."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))
import uat_watchdog  # noqa: E402


def test_should_refuse_the_cutoff_naming_the_offset_when_the_cutoff_has_no_utc_offset(
    monkeypatch, capsys
):
    # Arrange
    argv = ["uat_watchdog.py", "--pid", "1", "--since", "2026-10-03T23:17:00"]
    monkeypatch.setattr(sys, "argv", argv)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        uat_watchdog.main()

    # Assert
    assert exit_info.value.code == 2
    assert "has no UTC offset" in capsys.readouterr().err


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


def test_should_name_the_pinned_binary_when_cua_driver_is_not_executable(monkeypatch):
    # Arrange
    monkeypatch.setattr(uat_watchdog.shutil, "which", lambda name: None)

    # Act
    act = lambda: uat_watchdog._cua("get_session", {"session": "uat"})  # noqa: E731

    # Assert
    with pytest.raises(uat_watchdog.CheckFailed, match="/usr/local/bin/cua-driver is not"):
        act()


def test_should_report_active_When_get_session_answers_with_the_state_active(monkeypatch):
    # Arrange
    reply = {"client_kind": "cli", "session": "uat", "state": "active", "transport": "cli"}
    monkeypatch.setattr(uat_watchdog, "_cua", lambda command, payload: reply)

    # Act
    report = uat_watchdog.check_cua_session("uat", revive=False)

    # Assert
    assert report == "cua session 'uat' active"


def test_should_name_the_session_When_get_session_is_refused_in_plain_text(monkeypatch):
    # Arrange
    text = "session 'uat' has ended; tool call 'get_session' was rejected."
    monkeypatch.setattr(uat_watchdog, "_cua", lambda command, payload: {"_text": text})

    # Act
    act = lambda: uat_watchdog.check_cua_session("uat", revive=False)  # noqa: E731

    # Assert
    with pytest.raises(uat_watchdog.CheckFailed, match="session 'uat' is not active"):
        act()


def _session_folder(workdir: Path) -> Path:
    session = workdir / "tmp" / "FCB_TMP_session_4242_ab12cd34"
    session.mkdir(parents=True)
    return session


def test_should_fail_naming_the_folder_when_a_snapshot_folder_appears_after_the_cutoff(tmp_path):
    # Arrange
    cutoff = datetime.now() - timedelta(minutes=1)
    (_session_folder(tmp_path) / "FCB_TMP_snap_x").mkdir()
    # Act
    act = lambda: uat_watchdog.check_temp(cutoff, tmp_path)  # noqa: E731

    # Assert
    with pytest.raises(uat_watchdog.CheckFailed, match="FCB_TMP_snap_x"):
        act()


def test_should_report_the_counts_when_no_snapshot_folder_is_newer_than_the_cutoff(tmp_path):
    # Arrange
    (_session_folder(tmp_path) / "FCB_TMP_snap_old").mkdir()
    cutoff = datetime.now() + timedelta(minutes=1)

    # Act
    report = uat_watchdog.check_temp(cutoff, tmp_path)

    # Assert
    assert report.endswith("1 snapshot dir(s) total, 0 render file(s)")


def test_should_not_count_a_snapshot_folder_in_the_os_temp_folder_when_the_workdir_is_given(
    monkeypatch, tmp_path
):
    # Arrange
    workdir = tmp_path / "workdir"
    _session_folder(workdir)
    os_temp = tmp_path / "os-temp"
    (os_temp / "FCB_TMP_snap_old_place").mkdir(parents=True)
    monkeypatch.setattr(tempfile, "tempdir", str(os_temp))
    cutoff = datetime.now() - timedelta(minutes=1)

    # Act
    report = uat_watchdog.check_temp(cutoff, workdir)

    # Assert
    assert report.endswith("0 snapshot dir(s) total, 0 render file(s)")


def test_should_fail_naming_the_folder_when_the_given_workdir_does_not_exist(tmp_path):
    # Arrange
    # Act
    act = lambda: uat_watchdog.check_temp(None, tmp_path / "typo")  # noqa: E731

    # Assert
    with pytest.raises(uat_watchdog.CheckFailed, match="typo.*does not exist"):
        act()


def test_should_report_zero_when_the_workdir_has_no_tmp_folder_yet(tmp_path):
    # Arrange
    cutoff = datetime.now() - timedelta(minutes=1)

    # Act
    report = uat_watchdog.check_temp(cutoff, tmp_path)

    # Assert
    assert report.endswith("0 snapshot dir(s) total, 0 render file(s)")


def test_should_count_the_render_files_when_a_session_folder_holds_them(tmp_path):
    # Arrange
    (_session_folder(tmp_path) / "FCB_TMP_shot_a.png").write_bytes(b"x")

    # Act
    report = uat_watchdog.check_temp(None, tmp_path)

    # Assert
    assert report.endswith("0 snapshot dir(s) total, 1 render file(s)")


def test_should_check_the_workdir_it_was_given_when_main_runs_with_workdir(monkeypatch, tmp_path):
    # Arrange
    (_session_folder(tmp_path) / "FCB_TMP_snap_leak").mkdir()
    cutoff = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat()
    for name in ("check_cua_session", "check_window", "check_proxy"):
        monkeypatch.setattr(uat_watchdog, name, lambda *args: "ok")
    argv = ["uat_watchdog.py", "--pid", "1", "--since", cutoff, "--workdir", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", argv)

    # Act
    code = uat_watchdog.main()

    # Assert
    assert code == 1


def test_should_find_the_newest_version_folder_when_the_workdir_variable_is_unset(
    monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.delenv("FREECAD_BUDDY_WORKDIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for version in ("v1-0", "v1-1"):
        (tmp_path / ".local/share/FreeCAD" / version / "freecad-buddy/workdir").mkdir(parents=True)

    # Act
    workdir = uat_watchdog.default_workdir()

    # Assert
    assert workdir == tmp_path / ".local/share/FreeCAD/v1-1/freecad-buddy/workdir"


def test_should_fall_back_to_the_gui_default_when_no_version_folder_exists(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.delenv("FREECAD_BUDDY_WORKDIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Act
    workdir = uat_watchdog.default_workdir()

    # Assert
    assert workdir == tmp_path / ".local/share/FreeCAD/v1-1/freecad-buddy/workdir"


def test_should_use_the_workdir_variable_When_it_is_set(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("FREECAD_BUDDY_WORKDIR", str(tmp_path))

    # Act
    workdir = uat_watchdog.default_workdir()

    # Assert
    assert workdir == tmp_path
