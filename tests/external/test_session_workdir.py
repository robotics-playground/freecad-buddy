"""Session-workdir and session-start-sweep cases from the story 9.4 I/O matrix.

Covers where the two temp-file creation sites land, what the sweep reaches, what it must never
reach, and that a failing snapshot cleanup is logged rather than discarded.
"""

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from freecad_buddy.usecases import documents, fingerprint, screenshot, transaction


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Point the session workdir at a fresh directory for the duration of one test."""
    root = tmp_path / "session"
    monkeypatch.setenv("FREECAD_BUDDY_WORKDIR", str(root))
    return root


@pytest.fixture
def live_pid():
    """The pid of a live process other than this one, terminated when the test ends."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield process.pid
    process.terminate()
    process.wait()


class _StubRenderPort:
    """A ``RenderPort`` that writes one byte to the path it is handed."""

    class _Result:
        empty_scene = False

    def render(self, document, scene, out_path):
        # Arrange-time stand-in for the real renderer: the lifecycle only requires a non-empty file.
        Path(out_path).write_bytes(b"\x89PNG")
        return self._Result()


class _StubShape:
    """A shape whose ``exportBinary`` writes deterministic bytes to the path it is given."""

    def exportBinary(self, path):  # noqa: N802 - mirrors the FreeCAD API name
        Path(path).write_bytes(b"brep-bytes")


def test_Should_create_render_temp_inside_workdir_When_a_render_runs(workdir):
    # Arrange
    target = _StubRenderPort()

    # Act
    _, out_path = screenshot._render_with_lifecycle(target, object(), object(), None, True)

    # Assert
    assert Path(out_path).parent == Path(documents.temp_dir())
    assert Path(out_path).name.startswith("FCB_TMP_shot_")


def test_Should_place_the_temp_dir_in_this_hosts_own_session_folder_When_it_is_created(workdir):
    # Arrange
    expected_prefix = f"FCB_TMP_session_{os.getpid()}_"

    # Act
    target = Path(documents.temp_dir())

    # Assert
    assert target.parent == workdir / "tmp"
    assert target.name.startswith(expected_prefix)
    assert target.is_dir()


def test_Should_create_fingerprint_temp_inside_workdir_When_the_binary_serializer_is_used(
    workdir, monkeypatch
):
    # Arrange
    monkeypatch.setattr(fingerprint.shim, "export_binary_available", lambda: True)
    seen = []
    real_mkstemp = tempfile.mkstemp
    monkeypatch.setattr(
        tempfile,
        "mkstemp",
        lambda **kwargs: seen.append(kwargs["dir"]) or real_mkstemp(**kwargs),
    )

    # Act
    payload = fingerprint._serialize(_StubShape())

    # Assert
    assert payload == b"brep-bytes"
    assert seen == [documents.temp_dir()]


def test_Should_remove_a_dead_sessions_folder_When_the_sweep_runs(workdir):
    # Arrange
    dead_session = workdir / "tmp" / f"FCB_TMP_session_{_dead_pid()}_deadbeef"
    leftover_dir = dead_session / "FCB_TMP_snap_xyz"
    leftover_dir.mkdir(parents=True)
    (leftover_dir / "Doc.FCStd").write_bytes(b"stale")
    (dead_session / "FCB_TMP_shot_abc.png").write_bytes(b"stale")

    # Act
    removed = documents.sweep_temp_dir()

    # Assert
    assert removed == 1
    assert not dead_session.exists()


def test_Should_remove_only_dead_sessions_and_stray_prefixed_entries_When_tmp_is_shared(
    workdir, live_pid
):
    # Arrange — a live GUI host and this host share one workdir (F-30).
    tmp = workdir / "tmp"
    own_file = Path(documents.temp_dir()) / "FCB_TMP_shot_own.png"
    own_file.write_bytes(b"in use")
    live_session = tmp / f"FCB_TMP_session_{live_pid}_cafebabe"
    live_session.mkdir()
    (live_session / "FCB_TMP_shot_live.png").write_bytes(b"in use")
    dead_session = tmp / f"FCB_TMP_session_{_dead_pid()}_deadbeef"
    dead_session.mkdir()
    (dead_session / "FCB_TMP_fp_old.bin").write_bytes(b"stale")
    stray = tmp / "FCB_TMP_shot_stray.png"
    stray.write_bytes(b"stale")
    user_notes = tmp / "user_notes.txt"
    user_notes.write_text("keep me")
    not_prefixed = tmp / "not_prefixed"
    not_prefixed.mkdir()
    (not_prefixed / "data.bin").write_bytes(b"keep me")

    # Act
    removed = documents.sweep_temp_dir()

    # Assert
    assert removed == 2
    assert not dead_session.exists()
    assert not stray.exists()
    assert own_file.exists(), "the sweep removed this host's own session files"
    assert (live_session / "FCB_TMP_shot_live.png").exists(), "the sweep removed a live session"
    assert user_notes.exists() and (not_prefixed / "data.bin").exists()


def test_Should_leave_an_OS_temp_stray_untouched_When_the_sweep_runs(workdir):
    # Arrange
    documents.temp_dir()
    fd, stray = tempfile.mkstemp(prefix="FCB_TMP_shot_", suffix=".png")
    os.close(fd)

    # Act
    documents.sweep_temp_dir()

    # Assert
    try:
        assert Path(stray).exists(), "the sweep must never reach outside the session workdir"
    finally:
        os.remove(stray)


def test_Should_never_unlink_an_in_memory_document_name_When_the_sweep_runs(workdir, monkeypatch):
    # Arrange — the reserved prefixes that name FreeCAD documents, not files. The sweep walks a
    # real directory, so none of these can ever be a directory entry; the assertion states that
    # rather than leaving it to the directory's contents staying lucky.
    document_names = [
        "FCB_TMP_prev_Doc",
        "FCB_TMP_varset_probe",
        "FCB_TMP_partdesign_probe",
        "FCB_TMP_type_probe",
    ]
    temp = workdir / "tmp"
    temp.mkdir(parents=True)
    (temp / "FCB_TMP_shot_real.png").write_bytes(b"stale")
    unlinked = []
    real_unlink = Path.unlink

    def recording_unlink(self, *args, **kwargs):
        unlinked.append(self.name)
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", recording_unlink)

    # Act
    documents.sweep_temp_dir()

    # Assert
    assert unlinked == ["FCB_TMP_shot_real.png"]
    assert not [name for name in unlinked if name in document_names]


def test_Should_log_and_not_raise_When_a_snapshot_directory_removal_fails(workdir, caplog):
    # Arrange
    snapshot_dir = Path(documents.temp_dir()) / "FCB_TMP_snap_locked"
    snapshot_dir.mkdir()
    path = snapshot_dir / "Doc.FCStd"
    path.write_bytes(b"snapshot")

    # Act — the patch is scoped to this call alone, so the sweep below runs against a working
    # rmdir and measures whether the failed cleanup really left a sweepable directory.
    with caplog.at_level(logging.WARNING, logger="freecad_buddy.usecases.transaction"):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(transaction.os, "rmdir", _raise_oserror)
            transaction._delete_snapshot(str(path))

    # Assert
    assert "could not remove snapshot directory" in caplog.text
    assert snapshot_dir.is_dir(), "the directory must survive so the next sweep can reach it"
    with pytest.MonkeyPatch.context() as patch:
        # The next host's sweep sees this session's pid as dead.
        patch.setattr(documents, "pid_alive", lambda pid: pid != os.getpid())
        assert documents.sweep_temp_dir() == 1
    assert not snapshot_dir.exists()


def _raise_oserror(*_args, **_kwargs):
    raise OSError("directory in use")


def _dead_pid() -> int:
    """The pid of a process that has already exited."""
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid
