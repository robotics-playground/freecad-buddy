"""Container launch of the scripted UAT runner and the sweep scripts: command building, process
discovery and teardown, with a fake ``/proc`` and fake processes (no FreeCAD, no container)."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "uat" / "runner"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "close-loop"))
import capture  # noqa: E402
import launch  # noqa: E402
import check_harness  # noqa: E402
import run  # noqa: E402
import run_mcp_e2e  # noqa: E402
import run_mcp_edge_cases  # noqa: E402


def _fake_proc(root: Path, processes: dict) -> Path:
    """One ``/proc/<pid>/{cmdline,stat}`` per entry: ``{pid: (parent pid, argv[, group])}``."""
    for pid, (parent, argv, *group) in processes.items():
        entry = root / str(pid)
        entry.mkdir()
        (entry / "cmdline").write_bytes(b"\0".join(part.encode() for part in argv) + b"\0")
        (entry / "stat").write_text(
            f"{pid} (a (b) name) S {parent} {group[0] if group else 1} 1 0 -1", encoding="utf-8"
        )
    (root / "self").mkdir()
    return root


def test_Should_list_only_the_freecad_binary_When_proc_holds_other_processes(tmp_path):
    # Arrange
    proc = _fake_proc(
        tmp_path,
        {
            10: (1, ["/bin/bash", "/opt/freecad/AppRun"]),
            11: (10, [launch.FREECAD_BINARY, "-M", "/repo/tests/uat/probe"]),
            12: (1, ["/usr/bin/vim", launch.FREECAD_BINARY]),
        },
    )

    # Act
    pids = launch.running_freecad_pids(proc)

    # Assert
    assert pids == [11]


def test_Should_skip_an_entry_When_its_stat_file_is_unreadable(tmp_path):
    # Arrange
    proc = _fake_proc(tmp_path, {11: (1, [launch.FREECAD_BINARY])})
    broken = tmp_path / "12"
    broken.mkdir()
    (broken / "cmdline").write_bytes(launch.FREECAD_BINARY.encode() + b"\0")

    # Act
    pids = launch.running_freecad_pids(proc)

    # Assert
    assert pids == [11]


def test_Should_find_the_freecad_below_apprun_When_apprun_starts_it_as_a_child(tmp_path):
    # Arrange
    proc = _fake_proc(
        tmp_path,
        {
            10: (1, ["/bin/bash", "/opt/freecad/AppRun"]),
            11: (10, [launch.FREECAD_BINARY]),
            12: (11, ["/opt/freecad/usr/bin/ccx"]),
            13: (1, [launch.FREECAD_BINARY]),
        },
    )

    # Act
    below = launch.descendant_pids(10, proc)

    # Assert
    assert below == {10, 11, 12}


def test_Should_start_apprun_with_the_probe_and_a_temporary_profile_When_building_the_command(
    tmp_path,
):
    # Arrange
    work = tmp_path / "work"

    # Act
    command = launch.freecad_command(work)

    # Assert
    assert command == [
        launch.FREECAD_APPRUN,
        "-M",
        str(launch.PROBE_DIR),
        "-u",
        str(work / "user.cfg"),
        "-s",
        str(work / "system.cfg"),
    ]
    assert launch.FREECAD_APPRUN == "/opt/freecad/AppRun"


def test_Should_drop_bridge_and_python_variables_When_building_the_launch_environment(
    monkeypatch,
):
    # Arrange
    monkeypatch.setenv("FREECAD_BUDDY_AUTO_APPROVE", "1")
    monkeypatch.setenv("PYTHONPATH", "/opt/fcb-site")
    monkeypatch.setenv("PYTHONHOME", "/opt/freecad/usr")
    monkeypatch.setenv("DISPLAY", ":1")
    launch_map = {"FREECAD_BUDDY_SCRIPT_EXEC": "0"}

    # Act
    environment = launch.launch_environment(launch_map, "/repo/tests/uat/run/x/audit.jsonl")

    # Assert
    assert "FREECAD_BUDDY_AUTO_APPROVE" not in environment
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert environment["DISPLAY"] == ":1"
    assert environment["FREECAD_BUDDY_SCRIPT_EXEC"] == "0"
    assert environment["FREECAD_BUDDY_AUDIT_LOG"] == "/repo/tests/uat/run/x/audit.jsonl"


def test_Should_find_the_discovery_file_by_pid_When_it_is_under_the_data_home(tmp_path):
    # Arrange
    folder = tmp_path / "FreeCAD" / "v1-1" / "fcb-uat-probe"
    folder.mkdir(parents=True)
    wanted = folder / "probe-4242.json"
    wanted.write_text("{}", encoding="utf-8")
    (folder / "probe-4243.json").write_text("{}", encoding="utf-8")

    # Act
    found = launch.discovery_file(4242, data_home=tmp_path)
    missing = launch.discovery_file(1, data_home=tmp_path)

    # Assert
    assert found == wanted
    assert missing is None


def test_Should_refuse_naming_apprun_When_the_apprun_file_is_missing(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(launch, "FREECAD_APPRUN", str(tmp_path / "AppRun"))

    # Act
    act = launch.check_tools

    # Assert
    with pytest.raises(launch.LaunchError, match="FREECAD_APPRUN .* is not a file"):
        act()


def test_Should_end_the_process_group_and_delete_the_discovery_file_When_stopping(
    monkeypatch, tmp_path
):
    # Arrange
    folder = tmp_path / "FreeCAD" / "v1-1" / "fcb-uat-probe"
    folder.mkdir(parents=True)
    discovery = folder / "probe-4242.json"
    discovery.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    (tmp_path / "proc").mkdir()
    monkeypatch.setattr(launch, "_PROC_ROOT", str(tmp_path / "proc"))
    killed = []
    monkeypatch.setattr(
        launch.os, "killpg", lambda pid, sig: killed.append((pid, sig)), raising=False
    )
    monkeypatch.setattr(launch.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: False)
    process = SimpleNamespace(pid=4000, wait=lambda: 0)

    # Act
    launch.stop(process, freecad_pid=4242)

    # Assert
    assert [pid for pid, _ in killed] == [4000]
    assert not discovery.exists()


def test_Should_raise_naming_the_port_When_the_proxy_keeps_8765_after_the_stop(monkeypatch):
    # Arrange
    monkeypatch.setattr(launch.os, "killpg", lambda pid, sig: None, raising=False)
    monkeypatch.setattr(launch.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: True)
    monkeypatch.setattr(launch, "PORT_FREE_TIMEOUT_S", 0.0)
    process = SimpleNamespace(pid=4000, wait=lambda: 0)
    # Act
    act = lambda: launch.stop(process)  # noqa: E731

    # Assert
    with pytest.raises(launch.LaunchError, match=":8765 still held"):
        act()


def test_Should_call_the_pinned_release_binary_When_driving_cua_driver(monkeypatch):
    # Arrange
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(capture.subprocess, "run", fake_run)

    # Act
    capture.cua("list_windows", {"pid": 1})

    # Assert
    assert commands == [["/usr/local/bin/cua-driver", "call", "list_windows"]]


def test_Should_map_a_repository_file_to_the_container_mount_When_building_a_tool_path():
    # Arrange
    golden = run_mcp_e2e.GOLDEN_DIR / "box-10-20-30.FCStd"

    # Act
    path = run_mcp_e2e.container_path(golden)

    # Assert
    assert path == "/repo/benchmarks/g0/golden-models/box-10-20-30.FCStd"


def test_Should_start_the_h1_server_in_the_container_When_building_the_sweep_command():
    # Arrange
    expected_tail = ["fcb-py", "-m", "freecad_buddy.hosts.main", "serve", "--mode", "inline"]

    # Act
    parameters = run_mcp_e2e.server_parameters()

    # Assert
    assert parameters.command == "docker"
    assert parameters.args[:4] == ["exec", "-i", "-u", "cua"]
    assert "fcb-desktop" in parameters.args
    assert parameters.args[parameters.args.index("fcb-py") :][:6] == expected_tail
    assert f"PYTHONPATH={run_mcp_e2e.CONTAINER_ADDON}" in parameters.args
    assert not any("FCB_ENV" in part or "micromamba" in part for part in parameters.args)


def test_Should_silence_the_atspi_warning_and_keep_other_rules_When_building_the_launch_environment(
    monkeypatch,
):
    # Arrange
    monkeypatch.setenv("QT_LOGGING_RULES", "qt.qpa.*=true")

    # Act
    environment = launch.launch_environment({}, "/repo/tests/uat/run/x/audit.jsonl")

    # Assert
    assert environment["QT_LOGGING_RULES"] == "qt.qpa.*=true;qt.accessibility.atspi.warning=false"


def test_Should_silence_the_atspi_warning_When_no_logging_rule_is_set(monkeypatch):
    # Arrange
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)

    # Act
    environment = launch.launch_environment({}, "/repo/tests/uat/run/x/audit.jsonl")

    # Assert
    assert environment["QT_LOGGING_RULES"] == "qt.accessibility.atspi.warning=false"


def _menu_bar():
    """The menu items of the container FreeCAD: top-level items offer only ShowMenu."""
    return [
        {"element_index": 5, "role": "menu item", "label": "View", "element_token": "s1:5"},
        {
            "element_index": 6,
            "role": "menu item",
            "label": "Visibility",
            "parent_index": 5,
            "element_token": "s1:6",
        },
        {
            "element_index": 7,
            "role": "menu item",
            "label": "Show All Objects",
            "parent_index": 6,
            "element_token": "s1:7",
        },
        {"element_index": 8, "role": "page tab", "label": "View", "element_token": "s1:8"},
    ]


def test_Should_press_the_leaf_by_its_token_When_the_menu_path_is_in_the_element_tree(
    monkeypatch,
):
    # Arrange
    calls = []

    def fake_cua(tool, payload):
        calls.append((tool, payload))
        return {"elements": _menu_bar()} if tool == "get_window_state" else {}

    monkeypatch.setattr(capture, "cua", fake_cua)

    # Act
    capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])

    # Assert
    assert calls[-1] == ("click", {"pid": 9, "window_id": 33, "element_token": "s1:7"})


def test_Should_raise_naming_the_segment_When_a_menu_item_is_not_in_the_element_tree(
    monkeypatch,
):
    # Arrange
    elements = [e for e in _menu_bar() if e["label"] != "Visibility"]
    monkeypatch.setattr(capture, "cua", lambda tool, payload: {"elements": elements})
    monkeypatch.setattr(capture, "MENU_ENABLE_S", 0.0)
    # Act
    act = lambda: capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError, match="menu_path_unavailable: 0 menu items 'Visibility'"):
        act()


def test_Should_silence_the_atspi_warning_last_When_the_launch_map_sets_a_logging_rule(monkeypatch):
    # Arrange
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)
    launch_map = {"QT_LOGGING_RULES": "qt.*=true"}

    # Act
    environment = launch.launch_environment(launch_map, "/repo/tests/uat/run/x/audit.jsonl")

    # Assert
    assert environment["QT_LOGGING_RULES"] == "qt.*=true;qt.accessibility.atspi.warning=false"


def test_Should_raise_naming_the_item_When_the_leaf_menu_item_stays_disabled(monkeypatch):
    # Arrange
    elements = _menu_bar()
    elements[2]["enabled"] = False
    monkeypatch.setattr(capture, "cua", lambda tool, payload: {"elements": elements})
    monkeypatch.setattr(capture, "MENU_ENABLE_S", 0.0)
    # Act
    act = lambda: capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError, match="'Show All Objects' is still disabled"):
        act()


def test_Should_press_the_leaf_once_it_is_enabled_When_the_item_starts_disabled(monkeypatch):
    # Arrange
    calls = []
    disabled = _menu_bar()
    disabled[2]["enabled"] = False
    states = iter([disabled, _menu_bar()])

    def fake_cua(tool, payload):
        calls.append(tool)
        return {"elements": next(states)} if tool == "get_window_state" else {}

    monkeypatch.setattr(capture, "cua", fake_cua)
    monkeypatch.setattr(capture, "MENU_POLL_S", 0.0)

    # Act
    capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])

    # Assert
    assert calls == ["get_window_state", "get_window_state", "click"]


def test_Should_return_the_record_of_the_freecad_below_apprun_When_healthz_names_the_child(
    monkeypatch, tmp_path
):
    # Arrange
    folder = tmp_path / "FreeCAD" / "v1-1" / "fcb-uat-probe"
    folder.mkdir(parents=True)
    (folder / "probe-11.json").write_text('{"pid": 11, "port": 1, "token": "t"}', encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(launch, "_healthz", lambda: {"freecad_pid": 11})
    monkeypatch.setattr(launch, "descendant_pids", lambda root: {root, 11})
    process = SimpleNamespace(pid=10, poll=lambda: None)

    # Act
    record = launch.wait_until_ready(process)

    # Assert
    assert record["pid"] == 11
    assert record["user_app_data"] == str(tmp_path / "FreeCAD" / "v1-1")


def test_Should_start_in_a_new_session_and_stop_with_the_freecad_pid_When_the_group_runs(
    monkeypatch, tmp_path
):
    # Arrange
    started = {}
    stopped = {}
    process = SimpleNamespace(pid=10)

    def fake_popen(command, **kwargs):
        started.update(kwargs)
        return process

    monkeypatch.setattr(launch, "check_free", lambda: None)
    monkeypatch.setattr(launch.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(launch, "wait_until_ready", lambda proc: {"pid": 11})
    monkeypatch.setattr(
        launch, "stop", lambda proc, pid=None: stopped.update(process=proc, pid=pid)
    )

    # Act
    with launch.freecad({}, tmp_path / "audit.jsonl") as (yielded, record):
        pass

    # Assert
    assert started["start_new_session"] is True
    assert yielded is process
    assert record == {"pid": 11}
    assert stopped == {"process": process, "pid": 11}


def test_Should_delete_the_discovery_files_of_every_started_pid_When_readiness_failed(
    monkeypatch, tmp_path
):
    # Arrange
    folder = tmp_path / "data" / "FreeCAD" / "v1-1" / "fcb-uat-probe"
    folder.mkdir(parents=True)
    leftover = folder / "probe-11.json"
    leftover.write_text("{}", encoding="utf-8")
    other = folder / "probe-99.json"
    other.write_text("{}", encoding="utf-8")
    # AppRun (10) already exited; its FreeCAD (11) is a child of init but keeps AppRun's group.
    (tmp_path / "proc").mkdir()
    proc = _fake_proc(
        tmp_path / "proc", {11: (1, [launch.FREECAD_BINARY], 10), 99: (1, ["/bin/sleep"], 99)}
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(launch, "_PROC_ROOT", str(proc))
    monkeypatch.setattr(launch.os, "killpg", lambda pid, sig: None, raising=False)
    monkeypatch.setattr(launch.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: False)
    process = SimpleNamespace(pid=10, wait=lambda: 0)

    # Act
    launch.stop(process)

    # Assert
    assert not leftover.exists()
    assert other.exists()


def test_Should_deliver_again_When_the_probe_does_not_confirm_the_first_press(monkeypatch):
    # Arrange
    import test_uat_runner as runner_tests

    session, delivered = runner_tests._menu_session(
        monkeypatch, [None, None], [runner_tests._hidden_box(), runner_tests._box_snapshot()]
    )

    # Act
    attempts = session.menu(runner_tests.SHOW_ALL)

    # Assert
    assert attempts == 2
    assert len(delivered) == 2


def test_Should_raise_naming_the_attempts_When_the_probe_never_confirms_the_press(monkeypatch):
    # Arrange
    import test_uat_runner as runner_tests

    session, delivered = runner_tests._menu_session(
        monkeypatch, [None] * 3, [runner_tests._hidden_box()] * 3
    )
    # Act
    act = lambda: session.menu(runner_tests.SHOW_ALL)  # noqa: E731

    # Assert
    with pytest.raises(run.MenuError, match="had no effect in 0 s on 3 of 3 attempts"):
        act()
    assert len(delivered) == 3


def test_Should_wait_for_the_item_When_it_is_missing_from_the_first_element_tree(monkeypatch):
    # Arrange
    calls = []
    partial = [e for e in _menu_bar() if e["label"] != "Show All Objects"]
    states = iter([partial, _menu_bar()])

    def fake_cua(tool, payload):
        calls.append(tool)
        return {"elements": next(states)} if tool == "get_window_state" else {}

    monkeypatch.setattr(capture, "cua", fake_cua)
    monkeypatch.setattr(capture, "MENU_POLL_S", 0.0)

    # Act
    capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])

    # Assert
    assert calls == ["get_window_state", "get_window_state", "click"]


def test_Should_raise_with_the_refusal_prefix_When_the_driver_refuses_the_click(monkeypatch):
    # Arrange
    def fake_cua(tool, payload):
        if tool == "click":
            raise capture.CuaError("click refused: snapshot_id_required")
        return {"elements": _menu_bar()}

    monkeypatch.setattr(capture, "cua", fake_cua)
    # Act
    act = lambda: capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError, match="menu_path_unavailable: click refused"):
        act()


def test_Should_name_why_each_repeat_happened_When_a_press_is_unconfirmed_then_refused(
    monkeypatch,
):
    # Arrange
    import test_uat_runner as runner_tests

    session, delivered = runner_tests._menu_session(
        monkeypatch,
        [None, runner_tests.REFUSED, None],
        [runner_tests._hidden_box(), runner_tests._hidden_box(), runner_tests._box_snapshot()],
    )

    # Act
    attempts = session.menu(runner_tests.SHOW_ALL)

    # Assert
    assert attempts == 3
    assert len(delivered) == 3
    assert [reason.split(":")[0] for reason in session.last_menu_log] == [
        "delivered, no effect",
        "refused",
    ]


def test_Should_count_each_outcome_When_the_deliveries_are_mixed(monkeypatch):
    # Arrange
    import test_uat_runner as runner_tests

    session, delivered = runner_tests._menu_session(
        monkeypatch,
        [None, runner_tests.REFUSED, runner_tests.REFUSED],
        [runner_tests._hidden_box()] * 3,
    )
    # Act
    act = lambda: session.menu(runner_tests.SHOW_ALL)  # noqa: E731

    # Assert
    with pytest.raises(
        run.MenuError, match=r"not confirmed on 3 of 3 attempts \(2 refused, 1 with no effect\)"
    ):
        act()


def test_Should_not_wrap_a_driver_fault_as_a_refusal_When_the_click_exits_non_zero(monkeypatch):
    # Arrange
    def fake_cua(tool, payload):
        if tool == "click":
            raise capture.CuaError("click exited 1: daemon gone")
        return {"elements": _menu_bar()}

    monkeypatch.setattr(capture, "cua", fake_cua)

    # Act
    act = lambda: capture.invoke_menu(9, 33, ["View", "Visibility", "Show All Objects"])  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError) as raised:
        act()
    assert "menu_path_unavailable" not in str(raised.value)


def test_Should_refuse_naming_display_When_no_desktop_session_is_exported(monkeypatch, tmp_path):
    # Arrange
    apprun = tmp_path / "AppRun"
    apprun.write_bytes(b"")
    monkeypatch.setattr(launch, "FREECAD_APPRUN", str(apprun))
    monkeypatch.delenv("DISPLAY", raising=False)

    # Act
    act = launch.check_tools

    # Assert
    with pytest.raises(launch.LaunchError, match="DISPLAY is not set"):
        act()


def test_Should_keep_the_attempt_reasons_in_the_step_record_When_a_menu_step_repeats(tmp_path):
    # Arrange
    import test_uat_runner as runner_tests

    session = runner_tests._session()

    def repeated_menu(path):
        session.last_menu_log = ["refused: menu_path_unavailable", "delivered, no effect"]
        return 3

    session.menu = repeated_menu

    # Act
    record = run.run_scenario(runner_tests._scenario(tmp_path), session, tmp_path)

    # Assert
    menu_step = next(step for step in record["steps"] if "menu" in step)
    assert menu_step["attempts"] == 3
    assert menu_step["attempt_log"] == ["refused: menu_path_unavailable", "delivered, no effect"]


def test_Should_see_the_process_table_before_the_kill_When_stop_collects_the_started_pids(
    monkeypatch, tmp_path
):
    # Arrange
    folder = tmp_path / "data" / "FreeCAD" / "v1-1" / "fcb-uat-probe"
    folder.mkdir(parents=True)
    leftover = folder / "probe-11.json"
    leftover.write_text("{}", encoding="utf-8")
    proc = tmp_path / "proc"
    proc.mkdir()
    _fake_proc(proc, {11: (1, [launch.FREECAD_BINARY], 10)})

    def kill_everything(pid, sig):
        shutil.rmtree(proc / "11")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(launch, "_PROC_ROOT", str(proc))
    monkeypatch.setattr(launch.os, "killpg", kill_everything, raising=False)
    monkeypatch.setattr(launch.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: False)

    # Act
    launch.stop(SimpleNamespace(pid=10, wait=lambda: 0))

    # Assert
    assert not leftover.exists()


def test_Should_record_a_failed_check_When_the_edge_sweep_finds_no_golden_fixture(
    monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(run_mcp_edge_cases, "GOLDEN_DIR", tmp_path)
    report = run_mcp_e2e.Report()
    session = SimpleNamespace()

    # Act
    handle = asyncio.run(run_mcp_edge_cases._open_golden(session, report, "box-10-20-30"))

    # Assert
    assert handle is None
    assert report.summary()["all_passed"] is False
    assert report.checks[0]["tool"] == "open:box-10-20-30"


def test_Should_find_the_server_by_its_executable_When_the_late_session_script_polls_the_process():
    # Arrange
    script = check_harness.LATE_SESSION_SCRIPT

    # Act
    reads_cmdline = "/cmdline" in script
    reads_executable = "/proc/$mcp_pid/exe" in script

    # Assert
    assert not reads_cmdline
    assert reads_executable


_FRAME_WITH_MENU_BAR = """\
- frame = "FreeCAD 1.1.4"
    - [0] frame "Start" [actions=[SetFocus]]
    - [150] menu item "File" [actions=[ShowMenu]]
        - [151] menu item "New Document" [actions=[Press]]
    - [158] menu item "Edit" [actions=[ShowMenu]]
    - [165] menu item "View" [actions=[ShowMenu]]
        - [166] menu item "Status Bar" [actions=[Press]]
          - [325] page tab "View" [actions=[Press]]
"""


def test_Should_report_no_missing_item_When_the_menu_bar_holds_file_edit_and_view():
    # Arrange
    tree = _FRAME_WITH_MENU_BAR

    # Act
    missing = check_harness.missing_menu_items(tree)

    # Assert
    assert missing == []


def test_Should_report_view_missing_When_only_a_page_tab_and_a_submenu_carry_that_label():
    # Arrange
    tree = _FRAME_WITH_MENU_BAR.replace(
        '    - [165] menu item "View" [actions=[ShowMenu]]\n',
        '    - [165] menu item "Tools" [actions=[ShowMenu]]\n',
    ).replace('menu item "Status Bar"', 'menu item "View"')

    # Act
    missing = check_harness.missing_menu_items(tree)

    # Assert
    assert missing == ["View"]


def test_Should_record_a_failed_check_When_the_edge_sweep_golden_file_does_not_open(
    monkeypatch, tmp_path
):
    # Arrange
    (tmp_path / "box-10-20-30.FCStd").write_bytes(b"not a document")
    monkeypatch.setattr(run_mcp_edge_cases, "GOLDEN_DIR", tmp_path)
    monkeypatch.setattr(run_mcp_edge_cases, "container_path", lambda path: str(path))
    refusal = SimpleNamespace(
        structuredContent={"status": "INVALID_INPUT", "structured_content": {}}, content=[]
    )

    async def call_tool(name, arguments):
        return refusal

    report = run_mcp_e2e.Report()

    # Act
    handle = asyncio.run(
        run_mcp_edge_cases._open_golden(
            SimpleNamespace(call_tool=call_tool), report, "box-10-20-30"
        )
    )

    # Assert
    assert handle is None
    assert report.checks[0]["tool"] == "open:box-10-20-30"
    assert report.checks[0]["ok"] is False
    assert report.checks[0]["status"] == "INVALID_INPUT"
