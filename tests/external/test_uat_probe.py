"""UAT probe (Story 10.7b part P): comparator rows, snapshot shape from fake FreeCAD objects,
the HTTP guard rows, and the static checks that the probe shares no code with the bridge and is
not shipped. The live fault set is ``tests/uat/probe/run_faults.py``."""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import threading
import types
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO_ROOT / "tests" / "uat" / "probe"
sys.path.insert(0, str(PROBE_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_addon  # noqa: E402
import expect  # noqa: E402
import run_faults  # noqa: E402
import snapshot  # noqa: E402

BOX_EXPECTATION = {
    "active_document": "box",
    "documents": {
        "box": {
            "modified": False,
            "objects": {"Box": {"visibility": True, "volume": 6000, "bbox": [0, 0, 0, 10, 20, 30]}},
        }
    },
    "view": {"clipped": False},
}


def _box_snapshot(volume=6000.0, z_max=30.0, visibility=True, modified=False, view=None):
    return {
        "freecad_version": "1.1.4",
        "active_document": "box",
        "documents": [
            {
                "modified": modified,
                "name": "box",
                "label": "box",
                "objects": [
                    {
                        "name": "Box",
                        "type": "Part::Feature",
                        "visibility": visibility,
                        "shape": {
                            "valid": True,
                            "volume": volume,
                            "bbox": [0.0, 0.0, 0.0, 10.0, 20.0, z_max],
                        },
                    }
                ],
            }
        ],
        "view": view
        or {"camera": "", "size": [800, 600], "visible_size": [800, 600], "clipped": False},
    }


def test_Should_return_no_mismatch_When_the_snapshot_equals_the_expectation():
    # Arrange
    observed = _box_snapshot()

    # Act
    mismatches = expect.compare(observed, BOX_EXPECTATION)

    # Assert
    assert mismatches == []


def test_Should_return_no_mismatch_When_volume_and_bbox_are_within_the_tolerance():
    # Arrange
    observed = _box_snapshot(volume=6000.0000005, z_max=30.0000005)

    # Act
    mismatches = expect.compare(observed, BOX_EXPECTATION)

    # Assert
    assert mismatches == []


def test_Should_name_field_expected_and_observed_When_the_volume_is_outside_the_tolerance():
    # Arrange
    observed = _box_snapshot(volume=6000.01)

    # Act
    mismatches = expect.compare(observed, BOX_EXPECTATION)

    # Assert
    assert mismatches == [
        {"field": "documents.box.objects.Box.volume", "expected": 6000, "observed": 6000.01}
    ]


def test_Should_use_the_expectation_tolerance_When_one_is_given():
    # Arrange
    observed = _box_snapshot(volume=6000.01)
    expectation = {**BOX_EXPECTATION, "tolerance": 0.1}

    # Act
    mismatches = expect.compare(observed, expectation)

    # Assert
    assert mismatches == []


def test_Should_report_each_planted_field_When_several_fields_differ():
    # Arrange
    clipped_view = {"camera": "", "size": [500, 375], "visible_size": [232, 135], "clipped": True}
    observed = _box_snapshot(z_max=31.0, visibility=False, modified=True, view=clipped_view)

    # Act
    fields = [mismatch["field"] for mismatch in expect.compare(observed, BOX_EXPECTATION)]

    # Assert
    assert fields == [
        "documents.box.modified",
        "documents.box.objects.Box.visibility",
        "documents.box.objects.Box.bbox",
        "view.clipped",
    ]


def test_Should_report_the_open_documents_When_an_unexpected_document_is_open():
    # Arrange
    observed = _box_snapshot()
    observed["documents"].append(
        {"modified": True, "name": "Other", "label": "Other", "objects": []}
    )
    observed["active_document"] = "Other"

    # Act
    mismatches = expect.compare(observed, BOX_EXPECTATION)

    # Assert
    assert mismatches == [
        {"field": "active_document", "expected": "box", "observed": "Other"},
        {"field": "documents", "expected": ["box"], "observed": ["Other", "box"]},
    ]


def test_Should_report_a_missing_object_When_the_expected_object_is_absent():
    # Arrange
    observed = _box_snapshot()
    observed["documents"][0]["objects"] = []

    # Act
    mismatches = expect.compare(observed, BOX_EXPECTATION)

    # Assert
    assert mismatches == [
        {"field": "documents.box.objects.Box", "expected": "present", "observed": None}
    ]


def test_Should_report_the_view_When_a_view_is_expected_and_none_is_open():
    # Arrange
    observed = {"active_document": None, "documents": [], "view": None}

    # Act
    mismatches = expect.compare(observed, {"view": {"clipped": False}})

    # Assert
    assert mismatches == [{"field": "view", "expected": {"clipped": False}, "observed": None}]


@pytest.mark.parametrize(
    "expectation",
    [
        {"documnets": {}},
        {"documents": {"box": {"modfied": False}}},
        {"documents": {"box": {"objects": {"Box": {"colour": "red"}}}}},
        {"view": {"zoom": 1}},
    ],
)
def test_Should_raise_When_the_expectation_has_an_unknown_key(expectation):
    # Arrange
    observed = _box_snapshot()

    # Act
    act = lambda: expect.compare(observed, expectation)  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match="unknown expectation key"):
        act()


@pytest.mark.parametrize(
    ("expectation", "observed"),
    [
        (
            {"documents": {"absent": {"objects": {"Box": {"colour": "red"}}}}},
            {"documents": []},
        ),
        ({"documents": {"absent": {"modfied": False}}}, {"documents": []}),
        ({"view": {"zoom": 1}}, {"view": None}),
    ],
)
def test_Should_raise_When_an_unknown_key_sits_under_an_absent_document_or_view(
    expectation, observed
):
    # Arrange
    snapshot_input = {"active_document": None, **observed}

    # Act
    act = lambda: expect.compare(snapshot_input, expectation)  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match="unknown expectation key"):
        act()


def test_Should_raise_with_the_error_text_When_the_input_is_an_offline_error_report():
    # Arrange
    observed = {"error": "OSError: Invalid project file"}

    # Act
    act = lambda: expect.compare(observed, {"documents": {}})  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match="OSError: Invalid project file"):
        act()


class _FakeRect:
    def __init__(self, width, height):
        self._width, self._height = width, height

    def width(self):
        return self._width

    def height(self):
        return self._height


_TOP_LEFT = object()


def _map_to_global(point, logical_origin):
    assert point is _TOP_LEFT
    return SimpleNamespace(x=lambda: logical_origin[0], y=lambda: logical_origin[1])


def _fake_view(size, logical_visible, ratio, visible=True, logical_origin=(100, 80)):
    """A 3D view whose projection maps a point to ``(100 x, 30 y)`` device pixels, Coin style."""
    region = SimpleNamespace(
        boundingRect=lambda: _FakeRect(*logical_visible),
        isEmpty=lambda: logical_visible[0] * logical_visible[1] == 0,
    )
    graphics_view = SimpleNamespace(
        visibleRegion=lambda: region,
        devicePixelRatioF=lambda: ratio,
        isVisible=lambda: visible,
        rect=lambda: SimpleNamespace(topLeft=lambda: _TOP_LEFT),
        mapToGlobal=lambda point: _map_to_global(point, logical_origin),
    )
    return SimpleNamespace(
        graphicsView=lambda: graphics_view,
        getSize=lambda: tuple(size),
        getCamera=lambda: "#Inventor V2.1 ascii",
        getPointOnViewport=lambda point: (int(point.x * 100), int(point.y * 30)),
    )


def _fake_box_document(name="box"):
    bound_box = SimpleNamespace(
        XMin=0.0,
        YMin=0.0,
        ZMin=0.0,
        XMax=10.0,
        YMax=20.0,
        ZMax=30.0,
        Center=SimpleNamespace(x=5.0, y=10.0, z=15.0),
    )
    shape = SimpleNamespace(
        isNull=lambda: False, isValid=lambda: True, Volume=6000.0, BoundBox=bound_box
    )
    box = SimpleNamespace(Name="Box", TypeId="Part::Feature", Visibility=True, Shape=shape)
    origin = SimpleNamespace(Name="Origin", TypeId="App::Origin", Visibility=False)
    return SimpleNamespace(Name=name, Label="box-10-20-30", Objects=[box, origin])


def _fake_freecad(documents, view):
    app = SimpleNamespace(
        Version=lambda: ["1", "1", "4", "R20260928"],
        ActiveDocument=documents[0] if documents else None,
        listDocuments=lambda: {doc.Name: doc for doc in documents},
    )
    gui = SimpleNamespace(getDocument=lambda name: SimpleNamespace(Modified=False, ActiveView=view))
    return app, gui


def test_Should_return_the_matrix_fields_When_one_document_is_open():
    # Arrange
    view = _fake_view(size=[1917, 998], logical_visible=[1534, 799], ratio=1.25)
    app, gui = _fake_freecad([_fake_box_document()], view)

    # Act
    result = snapshot.take_snapshot(app, gui)

    # Assert
    assert json.loads(json.dumps(result)) == {
        "freecad_version": "1.1.4",
        "active_document": "box",
        "documents": [
            {
                "modified": False,
                "name": "box",
                "label": "box-10-20-30",
                "objects": [
                    {
                        "name": "Box",
                        "type": "Part::Feature",
                        "visibility": True,
                        "shape": {"valid": True, "volume": 6000.0, "bbox": [0, 0, 0, 10, 20, 30]},
                        "screen_center": [625, 797],
                    },
                    {
                        "name": "Origin",
                        "type": "App::Origin",
                        "visibility": False,
                        "shape": None,
                        "screen_center": None,
                    },
                ],
            }
        ],
        "view": {
            "camera": "#Inventor V2.1 ascii",
            "size": [1917, 998],
            "visible_size": [1917, 998],
            "clipped": False,
            "rect": [125, 100, 1917, 998],
        },
    }


def test_Should_flip_y_into_global_device_pixels_When_a_point_is_projected():
    # Arrange
    view = _fake_view(
        size=[800, 600], logical_visible=[800, 600], ratio=1.0, logical_origin=(10, 20)
    )
    rect = snapshot.read_view(view)["rect"]
    centre = SimpleNamespace(x=4.0, y=2.0, z=0.0)

    # Act
    point = snapshot.screen_point(view, rect, centre)

    # Assert
    assert rect == [10, 20, 800, 600]
    assert point == [10 + 400, 20 + 600 - 1 - 60]


def test_Should_report_null_screen_centers_When_the_active_view_is_not_a_3d_view():
    # Arrange
    app, gui = _fake_freecad([_fake_box_document()], SimpleNamespace())

    # Act
    result = snapshot.take_snapshot(app, gui)

    # Assert
    assert [o["screen_center"] for o in result["documents"][0]["objects"]] == [None, None]


def test_Should_project_only_the_active_document_When_two_documents_are_open():
    # Arrange
    view = _fake_view(size=[1917, 998], logical_visible=[1534, 799], ratio=1.25)
    app, gui = _fake_freecad([_fake_box_document("active"), _fake_box_document("other")], view)

    # Act
    result = snapshot.take_snapshot(app, gui)

    # Assert
    centers = {d["name"]: d["objects"][0]["screen_center"] for d in result["documents"]}
    assert centers == {"active": [625, 797], "other": None}


def test_Should_mark_the_view_clipped_When_the_visible_region_is_smaller_than_the_view():
    # Arrange
    view = _fake_view(size=[500, 375], logical_visible=[186, 108], ratio=1.25)

    # Act
    result = snapshot.read_view(view)

    # Assert
    assert result["visible_size"] == [232, 135]
    assert result["clipped"] is True


@pytest.mark.parametrize(
    ("logical_visible", "expected_clipped"),
    [([1601, 801], False), ([1599, 799], False), ([1598, 800], True)],
)
def test_Should_allow_one_pixel_of_slack_When_deciding_whether_the_view_is_clipped(
    logical_visible, expected_clipped
):
    # Arrange
    view = _fake_view(size=[1600, 800], logical_visible=logical_visible, ratio=1.0)

    # Act
    result = snapshot.read_view(view)

    # Assert
    assert result["clipped"] is expected_clipped


@pytest.mark.parametrize(
    ("logical_visible", "visible"),
    [([1534, 799], False), ([0, 0], True)],
    ids=["widget hidden", "region empty"],
)
def test_Should_report_null_visible_size_and_clipped_When_the_view_is_not_shown(
    logical_visible, visible
):
    # Arrange
    view = _fake_view([1917, 998], logical_visible, ratio=1.25, visible=visible)

    # Act
    result = snapshot.read_view(view)

    # Assert
    assert (result["size"], result["visible_size"], result["clipped"]) == ([1917, 998], None, None)


def test_Should_report_no_view_When_the_active_view_is_not_a_3d_view():
    # Arrange
    spreadsheet_view = SimpleNamespace()
    app, gui = _fake_freecad([_fake_box_document()], spreadsheet_view)

    # Act
    result = snapshot.take_snapshot(app, gui)

    # Assert
    assert result["view"] is None


def test_Should_return_no_documents_and_no_view_When_no_document_is_open():
    # Arrange
    app, gui = _fake_freecad([], view=None)

    # Act
    result = snapshot.take_snapshot(app, gui)

    # Assert
    assert result == {
        "freecad_version": "1.1.4",
        "active_document": None,
        "documents": [],
        "view": None,
    }


def test_Should_omit_gui_fields_When_a_document_is_read_offline():
    # Arrange
    doc = _fake_box_document()

    # Act
    result = snapshot.read_document(doc)

    # Assert
    assert set(result) == {"name", "label", "objects"}


class _FakeSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self):
        for slot in self.slots:
            slot()


class _FakeTimer:
    def __init__(self):
        self.timeout = _FakeSignal()
        self.active = False

    def start(self, interval_ms):
        self.active = True

    def stop(self):
        self.active = False


@pytest.fixture
def probe_server(monkeypatch, tmp_path):
    """``probe_server`` imported against stand-in FreeCAD and PySide modules; FreeCAD's user
    app data folder is ``tmp_path``."""
    freecad = types.ModuleType("FreeCAD")
    freecad.getUserAppDataDir = lambda: str(tmp_path) + os.sep
    freecad.Console = SimpleNamespace(PrintMessage=lambda text: None)
    qt_application = SimpleNamespace(aboutToQuit=_FakeSignal())
    pyside = types.ModuleType("PySide")
    pyside.QtCore = types.ModuleType("PySide.QtCore")
    pyside.QtCore.QTimer = _FakeTimer
    pyside.QtCore.QCoreApplication = SimpleNamespace(instance=lambda: qt_application)
    for name, module in {
        "FreeCAD": freecad,
        "FreeCADGui": types.ModuleType("FreeCADGui"),
        "PySide": pyside,
        "PySide.QtCore": pyside.QtCore,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "probe_server", raising=False)
    module = importlib.import_module("probe_server")
    monkeypatch.setattr(module, "MAIN_THREAD_TIMEOUT_S", 0.2)
    yield module
    sys.modules.pop("probe_server", None)


@pytest.fixture
def probe_url(probe_server):
    """A probe listener whose main thread never runs a queued read."""
    server = probe_server.ThreadingHTTPServer(("127.0.0.1", 0), probe_server._Handler)
    server.token = "good-token"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def main_thread(probe_server):
    """A helper thread that stands in for the Qt timer and runs queued reads."""
    stop = threading.Event()

    def run():
        while not stop.is_set():
            probe_server._run_queued_jobs()
            stop.wait(0.01)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    yield
    stop.set()
    thread.join()


def _get(url, token):
    request = urllib.request.Request(url, headers={"X-Probe-Token": token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


@pytest.mark.parametrize("token", ["wrong-token", None])
def test_Should_answer_403_without_a_read_When_the_token_is_wrong_or_missing(
    probe_server, probe_url, token
):
    # Arrange
    url = f"{probe_url}/snapshot"

    # Act
    status, body = _get(url, token)

    # Assert
    assert (status, body) == (403, {"error": "bad token"})
    assert probe_server._jobs.empty()


def test_Should_answer_504_When_the_main_thread_does_not_run_the_read(probe_server, probe_url):
    # Arrange
    url = f"{probe_url}/snapshot"

    # Act
    status, body = _get(url, "good-token")

    # Assert
    assert (status, body) == (504, {"error": "main thread did not answer"})


def test_Should_skip_an_abandoned_read_When_the_main_thread_runs_it_late(
    probe_server, probe_url, monkeypatch
):
    # Arrange
    reads = []
    monkeypatch.setattr(probe_server.snapshot, "take_snapshot", lambda app, gui: reads.append(1))
    _get(f"{probe_url}/snapshot", "good-token")

    # Act
    probe_server._run_queued_jobs()

    # Assert
    assert reads == []


def test_Should_answer_200_with_the_snapshot_When_the_main_thread_runs_the_read(
    probe_server, probe_url, main_thread, monkeypatch
):
    # Arrange
    body = {"active_document": None, "documents": [], "view": None}
    monkeypatch.setattr(probe_server.snapshot, "take_snapshot", lambda app, gui: body)

    # Act
    result = _get(f"{probe_url}/snapshot", "good-token")

    # Assert
    assert result == (200, body)


def test_Should_answer_500_with_the_error_When_the_read_raises(
    probe_server, probe_url, main_thread, monkeypatch
):
    # Arrange
    def failing_read(app, gui):
        raise ValueError("boom")

    monkeypatch.setattr(probe_server.snapshot, "take_snapshot", failing_read)

    # Act
    result = _get(f"{probe_url}/snapshot", "good-token")

    # Assert
    assert result == (500, {"error": "ValueError: boom"})


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/health", (200, {"status": "ok", "pid": os.getpid()})),
        ("/nope", (404, {"error": "unknown path /nope"})),
    ],
)
def test_Should_answer_health_and_reject_unknown_paths_When_the_token_is_good(
    probe_server, probe_url, path, expected
):
    # Arrange
    url = f"{probe_url}{path}"

    # Act
    result = _get(url, "good-token")

    # Assert
    assert result == expected


def test_Should_write_and_then_delete_the_discovery_file_When_the_probe_starts_and_quits(
    probe_server, tmp_path
):
    # Arrange
    discovery = tmp_path / "fcb-uat-probe" / f"probe-{os.getpid()}.json"
    about_to_quit = probe_server.QtCore.QCoreApplication.instance().aboutToQuit
    probe_server.start()
    server = probe_server._running["server"]
    record = json.loads(discovery.read_text(encoding="utf-8"))

    # Act
    about_to_quit.emit()

    # Assert
    assert record == {"pid": os.getpid(), "port": server.server_address[1], "token": server.token}
    assert not discovery.exists()
    assert probe_server._running["timer"].active is False


def test_Should_not_raise_When_the_discovery_file_is_already_gone_at_quit(probe_server):
    # Arrange
    probe_server.start()
    os.remove(probe_server._running["discovery"])
    about_to_quit = probe_server.QtCore.QCoreApplication.instance().aboutToQuit

    # Act
    about_to_quit.emit()

    # Assert
    assert not os.path.exists(probe_server._running["discovery"])


@pytest.fixture
def run_read_fcstd(monkeypatch):
    """Import ``read_fcstd`` as FreeCADCmd would, with a stand-in FreeCAD; return the exit code."""
    freecad = types.ModuleType("FreeCAD")
    freecad.Version = lambda: ["1", "1", "4", "R20260928"]
    freecad.openDocument = lambda path: _fake_box_document()
    freecad.closeDocument = lambda name: None
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)

    def run(*passed):
        monkeypatch.setattr(sys, "argv", ["freecadcmd.exe", "read_fcstd.py", "--pass", *passed])
        monkeypatch.delitem(sys.modules, "read_fcstd", raising=False)
        with pytest.raises(SystemExit) as exit_info:
            importlib.import_module("read_fcstd")
        return exit_info.value.code

    yield run
    sys.modules.pop("read_fcstd", None)


def test_Should_write_the_kernel_read_and_exit_0_When_the_file_opens(run_read_fcstd, tmp_path):
    # Arrange
    source = tmp_path / "box.FCStd"
    source.write_bytes(b"stand-in")
    out = tmp_path / "out.json"

    # Act
    code = run_read_fcstd(str(source), str(out))

    # Assert
    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["documents"][0]["objects"][0]["shape"]["volume"] == 6000.0


def test_Should_write_the_error_and_exit_1_When_the_file_is_missing(run_read_fcstd, tmp_path):
    # Arrange
    source = tmp_path / "missing.FCStd"
    out = tmp_path / "out.json"

    # Act
    code = run_read_fcstd(str(source), str(out))

    # Assert
    assert code == 1
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "error": f"FileNotFoundError: no such file: {source}"
    }


def test_Should_exit_2_and_write_the_error_When_too_many_arguments_name_the_out_file(
    run_read_fcstd, tmp_path
):
    # Arrange
    out = tmp_path / "out.json"

    # Act
    code = run_read_fcstd("a.FCStd", "b.FCStd", str(out))

    # Assert
    assert code == 2
    assert json.loads(out.read_text(encoding="utf-8"))["error"].startswith("usage:")


def test_Should_exit_2_without_a_file_When_the_out_path_is_unknown(run_read_fcstd, tmp_path):
    # Arrange
    only_argument = str(tmp_path / "a.FCStd")

    # Act
    code = run_read_fcstd(only_argument)

    # Assert
    assert code == 2
    assert list(tmp_path.iterdir()) == []


def test_Should_exit_non_zero_When_out_json_cannot_be_written(run_read_fcstd, tmp_path):
    # Arrange
    source = tmp_path / "box.FCStd"
    source.write_bytes(b"stand-in")
    out = tmp_path / "no-such-folder" / "out.json"

    # Act
    code = run_read_fcstd(str(source), str(out))

    # Assert
    assert code == 1


_VISIBILITY_FAULT = {
    "id": "wrong-visibility",
    "kind": "fault",
    "field": "documents.box.objects.Box.visibility",
}


def test_Should_not_detect_a_fault_When_only_another_field_mismatches():
    # Arrange
    snapshots = [_box_snapshot(volume=6200.0)]

    # Act
    flagged, _ = run_faults.judge(_VISIBILITY_FAULT, snapshots, BOX_EXPECTATION)

    # Assert
    assert flagged is False


def test_Should_detect_a_fault_When_its_named_field_mismatches():
    # Arrange
    snapshots = [_box_snapshot(visibility=False)]

    # Act
    flagged, detail = run_faults.judge(_VISIBILITY_FAULT, snapshots, BOX_EXPECTATION)

    # Assert
    assert flagged is True
    assert "documents.box.objects.Box.visibility" in detail


def test_Should_flag_a_control_When_any_field_mismatches():
    # Arrange
    control = {"id": "clean", "kind": "control"}

    # Act
    flagged, _ = run_faults.judge(control, [_box_snapshot(modified=True)], BOX_EXPECTATION)

    # Assert
    assert flagged is True


def test_Should_flag_a_control_When_its_two_snapshots_differ():
    # Arrange
    control = {"id": "clean-queried-twice", "kind": "control", "queries": 2}
    moved = {"camera": "moved", "size": [800, 600], "visible_size": [800, 600], "clipped": False}
    snapshots = [_box_snapshot(), _box_snapshot(view=moved)]

    # Act
    flagged, detail = run_faults.judge(control, snapshots, BOX_EXPECTATION)

    # Assert
    assert (flagged, detail) == (True, "snapshot changed between queries")


def _cases(faults, controls, extra_kind=None):
    cases = [{"kind": "fault"}] * faults + [{"kind": "control"}] * controls
    return cases + ([{"kind": extra_kind}] if extra_kind else [])


@pytest.mark.parametrize(
    ("cases", "message"),
    [
        (_cases(4, 2), "need at least 5 faults and 2 controls, got 4 and 2"),
        (_cases(5, 1), "need at least 5 faults and 2 controls, got 5 and 1"),
        (_cases(5, 2, extra_kind="faul"), "unknown case kind"),
    ],
)
def test_Should_reject_the_case_set_When_it_cannot_prove_the_rate(cases, message):
    # Arrange
    case_set = cases

    # Act
    act = lambda: run_faults.check_case_set(case_set)  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match=message):
        act()


def test_Should_accept_the_committed_case_set_When_it_is_checked():
    # Arrange
    cases = json.loads((PROBE_DIR / "faults" / "cases.json").read_text(encoding="utf-8"))["cases"]

    # Act
    run_faults.check_case_set(cases)

    # Assert
    assert len(cases) == 7


def test_Should_report_the_plant_error_When_the_done_marker_carries_one(monkeypatch, tmp_path):
    # Arrange
    discovery = tmp_path / "probe-1.json"
    discovery.write_text('{"pid": 1, "port": 2, "token": "t"}', encoding="utf-8")
    marker = tmp_path / "planted"
    marker.write_text("the 3D view has no QMdiSubWindow parent", encoding="utf-8")
    monkeypatch.setattr(run_faults, "discovery_file", lambda pid: discovery)
    process = SimpleNamespace(pid=1, poll=lambda: None)

    # Act
    act = lambda: run_faults.wait_until_planted(process, marker)  # noqa: E731

    # Assert
    with pytest.raises(run_faults.LaunchError, match="no QMdiSubWindow parent"):
        act()


_FREECAD_BUDDY_IMPORT = re.compile(r"^\s*(import|from)\s+freecad_buddy\b", re.MULTILINE)


def test_Should_not_import_freecad_buddy_When_any_probe_file_is_read():
    # Arrange
    sources = [p for p in PROBE_DIR.rglob("*") if p.suffix in {".py", ".FCMacro"}]

    # Act
    importers = [p for p in sources if _FREECAD_BUDDY_IMPORT.search(p.read_text("utf-8"))]

    # Assert
    assert sources
    assert importers == []


def test_Should_ship_no_probe_file_When_the_addon_is_built(tmp_path):
    # Arrange
    probe_files = {
        p.read_bytes() for p in PROBE_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    }

    # Act
    out = build_addon.build(tmp_path / "addon")

    # Assert
    built = [p for p in out.rglob("*") if p.is_file()]
    assert [p for p in built if {"uat", "probe"} & set(p.relative_to(out).parts)] == []
    assert [p for p in built if p.read_bytes() in probe_files] == []
