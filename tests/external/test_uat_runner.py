"""Scripted UAT runner (Story 10.7b part R): every I/O matrix row with a fake session, fake
probe snapshots and synthetic PNGs; the PNG decoder and pixel measures; and the static checks
that the runner calls no menu outside the allow-list and shares no code with the bridge. The
live run is ``tests/uat/runner/run.py``."""

from __future__ import annotations

import concurrent.futures
import contextlib
import json
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_DIR = REPO_ROOT / "tests" / "uat" / "runner"
SCENARIO_DIR = REPO_ROOT / "tests" / "uat" / "scenarios"
TESTCASE_DIR = REPO_ROOT / "tests" / "uat" / "testcases"
sys.path.insert(0, str(RUNNER_DIR))
import capture  # noqa: E402
import compare  # noqa: E402
import launch  # noqa: E402
import mcp_client  # noqa: E402
import pixel  # noqa: E402
import pixel_faults  # noqa: E402
import png  # noqa: E402
import run  # noqa: E402
import scenario  # noqa: E402

BACKGROUND = (240, 240, 240)
MODEL = (100, 100, 110)
WINDOW = {"x": 0, "y": 0, "width": 200, "height": 150}
VIEW_RECT = [20, 10, 160, 120]
BOX_CENTER = [90, 70]


def _paeth(left, up, up_left):
    estimate = left + up - up_left
    distances = [abs(estimate - left), abs(estimate - up), abs(estimate - up_left)]
    return [left, up, up_left][distances.index(min(distances))]


def _encode_png(rows, channels, filters=(0,)):
    """PNG bytes for ``rows`` of pixel tuples; row ``y`` uses ``filters[y % len(filters)]``."""
    raw_rows = [bytes(value for px in row for value in px) for row in rows]
    data, previous = b"", bytes(len(raw_rows[0]))
    for y, row in enumerate(raw_rows):
        kind = filters[y % len(filters)]
        out = bytearray()
        for i, value in enumerate(row):
            left = row[i - channels] if i >= channels else 0
            up_left = previous[i - channels] if i >= channels else 0
            predictor = (
                [0, left, previous[i], (left + previous[i]) // 2][kind]
                if kind < 4
                else (_paeth(left, previous[i], up_left))
            )
            out.append((value - predictor) & 0xFF)
        data += bytes([kind]) + bytes(out)
        previous = row

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    header = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, {3: 2, 4: 6}[channels], 0, 0, 0)
    return (
        png.SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(data))
        + chunk(b"IEND", b"")
    )


def _scene(rectangles=(((60, 40), (120, 100), MODEL),), gradient=False, extra=None):
    """A 200 x 150 capture: background, filled rectangles ``((x0, y0), (x1, y1), colour)``."""
    rows = []
    for y in range(WINDOW["height"]):
        shade = 200 + y // 3 if gradient else BACKGROUND[0]
        row = [(shade, shade, shade)] * WINDOW["width"]
        for (x0, y0), (x1, y1), colour in rectangles:
            if y0 <= y < y1:
                row[x0:x1] = [colour] * (x1 - x0)
        if extra:
            extra(y, row)
        rows.append(row)
    return rows


def _box_snapshot(volume=6000.0, center=BOX_CENTER):
    return {
        "freecad_version": "1.1.4",
        "active_document": "box",
        "documents": [
            {
                "modified": False,
                "name": "box",
                "label": "box",
                "objects": [
                    {
                        "name": "Box",
                        "type": "Part::Feature",
                        "visibility": True,
                        "shape": {"valid": True, "volume": volume, "bbox": [0, 0, 0, 10, 20, 30]},
                        "screen_center": center,
                    }
                ],
            }
        ],
        "view": {
            "camera": "",
            "size": VIEW_RECT[2:],
            "visible_size": VIEW_RECT[2:],
            "clipped": False,
            "rect": VIEW_RECT,
        },
    }


class FakeSession:
    """Answers each tool from ``results``; writes ``capture_png`` as the window capture."""

    def __init__(self, results, snapshot, capture_png=b"", capture_error=None):
        self.results = results
        self.snapshot_value = snapshot
        self.capture_png = capture_png or _encode_png(_scene(), 3)
        self.capture_error = capture_error
        self.calls = []

    def reset(self):
        self.calls.append(("reset", None))

    def call(self, tool, args):
        self.calls.append((tool, args))
        return self.results[tool]

    def menu(self, path):
        self.calls.append(("menu", path))
        return 1

    def snapshot(self):
        return self.snapshot_value

    def capture(self, out_file):
        if self.capture_error:
            raise self.capture_error
        Path(out_file).write_bytes(self.capture_png)
        return dict(WINDOW)


OPEN_OK = {"status": "OK", "structured_content": {"doc": "fcb-doc:abc", "name": "box"}}
MASS_6000 = {"status": "OK", "structured_content": {"volume": {"value": 6000.0, "unit": "mm^3"}}}


def _scenario(tmp_path, **overrides):
    data = {
        "id": "TC-02-02",
        "tc": "TC-02",
        "steps": [
            {"name": "open", "mcp": "document_open", "args": {"path": "$PROJECT_ROOT/box.FCStd"}},
            {"menu": ["View", "Visibility", "Show All Objects"]},
            {
                "name": "mass",
                "mcp": "query_mass_properties",
                "args": {"doc": "$open.structured_content.doc", "object": "Box"},
            },
        ],
        "expect": [{"step": "open", "path": "status", "equals": "OK"}],
        "probe": {"documents": {"box": {"objects": {"Box": {"visibility": True}}}}},
        "cross": [
            {
                "mcp": "mass.structured_content.volume.value",
                "probe": "documents.box.objects.Box.shape.volume",
                "tolerance": 0.01,
            }
        ],
        "pixel": {"samples": ["box.Box"], "extent": {"min_fraction": 0.3, "inside": True}},
    }
    data.update(overrides)
    item = scenario.validate(data)
    item["file"] = str(tmp_path / f"{data['id'].lower()}.json")
    return item


def test_Should_pass_and_record_the_capture_When_every_check_passes(tmp_path):
    # Arrange
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot()
    )
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert (record["verdict"], record["reasons"]) == ("PASS", [])
    assert record["capture"] == str(tmp_path / "captures" / "TC-02-02.png")
    assert Path(record["capture"]).read_bytes() == session.capture_png
    assert ("query_mass_properties", {"doc": "fcb-doc:abc", "object": "Box"}) in session.calls
    assert record["pixel"]["samples"]["box.Box"]["geometry"] is True


def test_Should_escalate_with_no_capture_When_the_capture_fails(tmp_path):
    # Arrange
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000},
        _box_snapshot(),
        capture_error=capture.CuaError("get_window_state exited 1"),
    )
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "ESCALATE"
    assert record["capture"] is None
    assert record["reasons"] == ["no capture: CuaError: get_window_state exited 1"]


def test_Should_fail_naming_field_expected_and_observed_When_an_envelope_field_differs(tmp_path):
    # Arrange
    refused = {"status": "INVALID_INPUT", "structured_content": {"doc": "fcb-doc:abc"}}
    session = FakeSession(
        {"document_open": refused, "query_mass_properties": MASS_6000}, _box_snapshot()
    )
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "FAIL"
    assert [(f["field"], f["expected"], f["observed"]) for f in record["findings"]] == [
        ("open.status", "OK", "INVALID_INPUT")
    ]
    assert record["reasons"] == ['expect open.status: expected "OK", observed "INVALID_INPUT"']


def test_Should_escalate_naming_both_values_once_When_the_probe_and_mcp_disagree(tmp_path):
    # Arrange
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot(volume=6200.0)
    )
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "ESCALATE"
    assert record["reasons"] == [
        "probe/MCP disagreement: MCP mass.structured_content.volume.value = 6000.0, "
        "probe documents.box.objects.Box.shape.volume = 6200.0"
    ]
    assert [tool for tool, _ in session.calls].count("query_mass_properties") == 1


def test_Should_fail_on_a_probe_mismatch_When_the_snapshot_differs_from_the_expectation(tmp_path):
    # Arrange
    snapshot = _box_snapshot()
    snapshot["documents"][0]["objects"][0]["visibility"] = False
    session = FakeSession({"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, snapshot)
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "FAIL"
    assert [f["field"] for f in record["findings"]] == ["documents.box.objects.Box.visibility"]


def test_Should_escalate_with_the_error_When_a_step_raises(tmp_path):
    # Arrange
    session = FakeSession({"document_open": OPEN_OK}, _box_snapshot())
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "ESCALATE"
    assert record["reasons"] == ["step 2 raised KeyError: 'query_mass_properties'"]


def test_Should_escalate_with_the_agent_check_When_every_scripted_check_passes(tmp_path):
    # Arrange
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot()
    )
    item = _scenario(tmp_path, agent_check="click Fit All and judge the capture")

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "ESCALATE"
    assert record["reasons"] == ["agent check: click Fit All and judge the capture"]


def test_Should_launch_once_per_launch_config_When_scenarios_share_configs(tmp_path):
    # Arrange
    opened = []
    sessions = []

    @contextlib.contextmanager
    def open_session(launch_env, audit_log):
        opened.append(launch_env)
        session = FakeSession(
            {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot()
        )
        sessions.append(session)
        yield session

    off = {"FREECAD_BUDDY_SCRIPT_EXEC": "0"}
    items = [
        _scenario(tmp_path, id="TC-02-01"),
        _scenario(tmp_path, id="TC-02-02", launch=off),
        _scenario(tmp_path, id="TC-02-03"),
    ]

    # Act
    results, groups = run.run(items, tmp_path, open_session=open_session)

    # Assert
    assert opened == [{}, off]
    assert [group["error"] for group in groups] == [None, None]
    assert [r["id"] for r in results] == ["TC-02-01", "TC-02-02", "TC-02-03"]
    assert [call for call in sessions[0].calls if call[0] == "reset"] == [("reset", None)] * 2
    assert [call for call in sessions[1].calls if call[0] == "reset"] == [("reset", None)]


def test_Should_escalate_every_member_When_its_launch_group_fails(tmp_path):
    # Arrange
    @contextlib.contextmanager
    def open_session(launch_env, audit_log):
        raise launch.LaunchError("FreeCAD exited with code 1")
        yield

    items = [_scenario(tmp_path, id="TC-02-01"), _scenario(tmp_path, id="TC-02-02")]

    # Act
    results, groups = run.run(items, tmp_path, open_session=open_session)

    # Assert
    assert [(r["verdict"], r["reasons"], r["not_run"]) for r in results] == [
        ("ESCALATE", ["not run: launch group raised LaunchError: FreeCAD exited with code 1"], True)
    ] * 2
    assert groups[0]["error"] == "launch raised LaunchError: FreeCAD exited with code 1"


@pytest.fixture
def no_launch(monkeypatch):
    """Fail the test if ``main`` reaches preflight or a launch."""

    def refuse(*args, **kwargs):
        raise AssertionError("must not be reached")

    monkeypatch.setattr(run.launch, "preflight", refuse)
    monkeypatch.setattr(run, "run", refuse)


@pytest.mark.parametrize(
    ("change", "named_key"),
    [({"bogus": 1}, "bogus"), ({"id": None}, "id")],
    ids=["unknown key", "missing id"],
)
def test_Should_refuse_before_any_launch_and_exit_2_When_a_scenario_is_invalid(
    tmp_path, capsys, no_launch, change, named_key
):
    # Arrange
    data = {"id": "TC-02-02", "tc": "TC-02", "steps": [{"mcp": "document_list"}], **change}
    data = {key: value for key, value in data.items() if value is not None}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    # Act
    code = run.main([str(path), "--out", str(tmp_path / "out")])

    # Assert
    message = capsys.readouterr().out
    assert code == 2
    assert str(path) in message and f"'{named_key}'" in message


def test_Should_refuse_and_exit_2_naming_the_pid_When_freecad_already_runs(
    tmp_path, capsys, monkeypatch
):
    # Arrange
    def refuse_run(*args, **kwargs):
        raise AssertionError("must not launch")

    monkeypatch.setattr(launch, "check_tools", lambda: None)
    monkeypatch.setattr(launch, "running_freecad_pids", lambda: [4242])
    monkeypatch.setattr(run, "run", refuse_run)
    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"id": "TC-02-02", "tc": "TC-02", "steps": [{"mcp": "x"}]}), "utf-8")

    # Act
    code = run.main([str(path), "--out", str(tmp_path / "out")])

    # Assert
    assert code == 2
    assert "pid 4242" in capsys.readouterr().out


def test_Should_refuse_When_port_8765_is_held(monkeypatch):
    # Arrange
    monkeypatch.setattr(launch, "running_freecad_pids", lambda: [])
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: True)

    # Act
    act = launch.check_free

    # Assert
    with pytest.raises(launch.LaunchError, match="127.0.0.1:8765 is held"):
        act()


def test_Should_measure_the_golden_difference_When_a_golden_png_is_beside_the_scenario(tmp_path):
    # Arrange
    item = _scenario(tmp_path)
    moved = _scene(rectangles=(((70, 40), (130, 100), MODEL),))
    Path(item["file"]).with_suffix(".golden.png").write_bytes(_encode_png(moved, 3))
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot()
    )

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "PASS"
    assert record["golden"]["changed_fraction"] == pytest.approx(2 * 10 * 60 / (160 * 120))


def test_Should_skip_without_failing_When_no_golden_png_exists(tmp_path):
    # Arrange
    item = _scenario(tmp_path)
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000}, _box_snapshot()
    )

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert (record["verdict"], record["golden"]) == ("PASS", None)


@pytest.mark.parametrize("channels", [3, 4], ids=["RGB", "RGBA"])
def test_Should_decode_every_filter_type_When_rows_use_filters_0_to_4(channels):
    # Arrange
    rows = [
        [tuple((x * 37 + y * 11 + c * 53) % 256 for c in range(channels)) for x in range(9)]
        for y in range(10)
    ]
    data = _encode_png(rows, channels, filters=(0, 1, 2, 3, 4))

    # Act
    image = png.decode(data)

    # Assert
    assert (image.width, image.height, image.channels) == (9, 10, channels)
    assert [[image.rgb(x, y) for x in range(9)] for y in range(10)] == [
        [px[:3] for px in row] for row in rows
    ]


def test_Should_refuse_When_the_png_is_not_8_bit_rgb():
    # Arrange
    data = _encode_png([[(1, 2, 3)]], 3).replace(
        struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0), struct.pack(">IIBBBBB", 1, 1, 16, 2, 0, 0, 0)
    )

    # Act
    act = lambda: png.decode(data)  # noqa: E731

    # Assert
    with pytest.raises(png.PngError, match="bit depth 16"):
        act()


def _thin_line_and_cube(y, row):
    if y == 70:
        row[120:180] = [(50, 50, 50)] * 60
    if 12 <= y < 28:
        row[160:176] = [(120, 120, 120)] * 16


@pytest.mark.parametrize("gradient", [False, True], ids=["flat", "vertical gradient"])
def test_Should_measure_only_the_model_When_overlay_lines_and_a_cube_share_the_view(gradient):
    # Arrange
    image = png.decode(_encode_png(_scene(gradient=gradient, extra=_thin_line_and_cube), 3))

    # Act
    measured = pixel.measure(image, WINDOW, VIEW_RECT, {"box.Box": BOX_CENTER})

    # Assert
    assert measured["samples"]["box.Box"] == {
        "point": BOX_CENTER,
        "rgb": list(MODEL),
        "geometry": True,
    }
    assert measured["extent"] == {
        "box": [60, 42, 116, 98],
        "fraction": pytest.approx(56 / 120),
        "touches_edge": False,
    }


def test_Should_report_touching_the_edge_When_the_model_runs_off_the_view():
    # Arrange
    image = png.decode(_encode_png(_scene(rectangles=(((60, 40), (180, 100), MODEL),)), 3))

    # Act
    measured = pixel.measure(image, WINDOW, VIEW_RECT, {"box.Box": BOX_CENTER})

    # Assert
    assert measured["extent"]["touches_edge"] is True


def test_Should_scale_into_the_capture_When_the_capture_is_smaller_than_the_window():
    # Arrange
    image = SimpleNamespace(width=1568, height=979)
    placement = pixel.Placement({"x": 0, "y": 0, "width": 1600, "height": 1000}, image)

    # Act
    box = placement.box([334, 210, 1265, 712])

    # Assert
    assert box == (327, 205, 1567, 902)


def test_Should_fail_the_sample_When_the_center_is_background(tmp_path):
    # Arrange
    session = FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000},
        _box_snapshot(center=[30, 20]),
    )
    item = _scenario(tmp_path)

    # Act
    record = run.run_scenario(item, session, tmp_path)

    # Assert
    assert record["verdict"] == "FAIL"
    assert [f["field"] for f in record["findings"]] == ["samples.box.Box", "extent"]


def test_Should_keep_the_type_of_a_whole_reference_and_format_an_embedded_one():
    # Arrange
    bindings = {"PROJECT_ROOT": "D:/repo", "open": OPEN_OK, "fit": {"framing": {"ratio": 0.95}}}
    value = {"doc": "$open.structured_content.doc", "path": "$PROJECT_ROOT/a.FCStd", "r": "$fit"}

    # Act
    result = scenario.substitute(value, bindings)

    # Assert
    assert result == {
        "doc": "fcb-doc:abc",
        "path": "D:/repo/a.FCStd",
        "r": {"framing": {"ratio": 0.95}},
    }


@pytest.mark.parametrize(
    ("steps", "message"),
    [
        ([{"mcp": "x", "args": {"doc": "$later.doc"}}, {"name": "later", "mcp": "y"}], "$later"),
        ([{"menu": ["File", "Open"]}], "allow-list"),
        ([{"mcp": "x", "menu": ["Edit", "Recompute"]}], "exactly one"),
    ],
    ids=["forward reference", "menu outside the allow-list", "mcp and menu"],
)
def test_Should_reject_the_scenario_When_a_step_is_invalid(steps, message):
    # Arrange
    data = {"id": "TC-02-02", "tc": "TC-02", "steps": steps}

    # Act
    act = lambda: scenario.validate(data)  # noqa: E731

    # Assert
    with pytest.raises(scenario.ScenarioError, match=re.escape(message)):
        act()


def test_Should_refuse_without_calling_cua_driver_When_the_menu_path_is_not_allow_listed(
    monkeypatch,
):
    # Arrange
    def refuse(*args):
        raise AssertionError("cua-driver must not be called")

    monkeypatch.setattr(capture, "cua", refuse)

    # Act
    act = lambda: capture.invoke_menu(1, 2, ["File", "Open"])  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match="not in the allow-list"):
        act()


def test_Should_raise_When_cua_driver_answers_refused_with_exit_code_0(monkeypatch):
    # Arrange
    answer = '{"refusal": {"code": "menu_path_unavailable"}, "status": "refused"}'
    monkeypatch.setattr(
        capture.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=answer, stderr=""),
    )

    # Act
    act = lambda: capture.cua("invoke_menu", {})  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError, match="menu_path_unavailable"):
        act()


def test_Should_raise_When_show_all_leaves_an_object_hidden(monkeypatch):
    # Arrange
    hidden = _box_snapshot()
    hidden["documents"][0]["objects"][0]["visibility"] = False
    session = object.__new__(run.LiveSession)
    session.pid, session.window_id = 1, 2
    session.snapshot = lambda: hidden
    monkeypatch.setattr(capture, "invoke_menu", lambda *args: None)
    monkeypatch.setattr(run, "MENU_EFFECT_TIMEOUT_S", 0.0)

    # Act
    act = lambda: session.menu(["View", "Visibility", "Show All Objects"])  # noqa: E731

    # Assert
    with pytest.raises(run.MenuError, match="had no effect"):
        act()


SHOW_ALL = ["View", "Visibility", "Show All Objects"]
REFUSED = capture.CuaError(
    'invoke_menu refused: {"refusal": {"code": "menu_path_unavailable"}, "status": "refused"}'
)


def _menu_session(monkeypatch, answers, snapshots):
    """A LiveSession whose ``invoke_menu`` raises or returns ``answers`` in turn."""
    session = object.__new__(run.LiveSession)
    session.pid, session.window_id = 1, 2
    snapshots = iter(snapshots)
    session.snapshot = lambda: next(snapshots)
    delivered = []

    def invoke(*args):
        delivered.append(args)
        answer = answers[len(delivered) - 1]
        if answer is not None:
            raise answer

    monkeypatch.setattr(capture, "invoke_menu", invoke)
    monkeypatch.setattr(run, "MENU_EFFECT_TIMEOUT_S", 0.0)
    monkeypatch.setattr(run, "POLL_S", 0.0)
    return session, delivered


def _hidden_box():
    hidden = _box_snapshot()
    hidden["documents"][0]["objects"][0]["visibility"] = False
    return hidden


def test_Should_pass_with_2_attempts_When_show_all_is_refused_once(monkeypatch):
    # Arrange
    session, delivered = _menu_session(
        monkeypatch, [REFUSED, None], [_hidden_box(), _box_snapshot()]
    )

    # Act
    attempts = session.menu(SHOW_ALL)

    # Assert
    assert attempts == 2
    assert len(delivered) == 2


def test_Should_raise_naming_the_refusal_When_show_all_is_refused_3_times(monkeypatch):
    # Arrange
    session, delivered = _menu_session(monkeypatch, [REFUSED] * 3, [_hidden_box()] * 3)

    # Act
    act = lambda: session.menu(SHOW_ALL)  # noqa: E731

    # Assert
    with pytest.raises(run.MenuError, match="refused on 3 of 3 attempts.*menu_path_unavailable"):
        act()
    assert len(delivered) == 3


def test_Should_not_deliver_again_When_the_probe_shows_a_refused_attempt_took_effect(monkeypatch):
    # Arrange
    session, delivered = _menu_session(monkeypatch, [REFUSED, None], [_box_snapshot()])

    # Act
    attempts = session.menu(SHOW_ALL)

    # Assert
    assert attempts == 1
    assert len(delivered) == 1


def test_Should_deliver_once_When_the_effect_shows_on_the_second_poll_after_a_refusal(
    monkeypatch,
):
    # Arrange
    session, delivered = _menu_session(
        monkeypatch, [REFUSED, None], [_hidden_box(), _box_snapshot()]
    )
    monkeypatch.setattr(run, "POLL_S", 0.01)

    # Act
    attempts = session.menu(SHOW_ALL)

    # Assert
    assert attempts == 1
    assert len(delivered) == 1


@pytest.mark.parametrize(
    ("path", "error"),
    [
        (SHOW_ALL, capture.CuaError("invoke_menu exited 1: daemon gone")),
        (["Edit", "Recompute"], REFUSED),
    ],
    ids=["other cua error", "path with no probe effect"],
)
def test_Should_raise_after_one_delivery_When_the_refusal_is_not_a_retried_one(
    monkeypatch, path, error
):
    # Arrange
    session, delivered = _menu_session(monkeypatch, [error, None], [_hidden_box()])

    # Act
    act = lambda: session.menu(path)  # noqa: E731

    # Assert
    with pytest.raises(capture.CuaError):
        act()
    assert len(delivered) == 1


def test_Should_record_the_attempt_count_When_a_menu_step_runs(tmp_path):
    # Arrange
    session = _session()
    session.menu = lambda path: 2

    # Act
    record = run.run_scenario(_scenario(tmp_path), session, tmp_path)

    # Assert
    assert record["steps"][1] == {"menu": SHOW_ALL, "attempts": 2, "attempt_log": []}
    assert record["verdict"] == "PASS"


def test_Should_escalate_naming_the_refusal_When_show_all_is_refused_3_times(tmp_path):
    # Arrange
    session = _session()

    def refuse(path):
        raise run.MenuError(f"menu {path} refused on 3 of 3 attempts: {REFUSED}")

    session.menu = refuse

    # Act
    record = run.run_scenario(_scenario(tmp_path), session, tmp_path)

    # Assert
    assert record["verdict"] == "ESCALATE"
    assert "menu_path_unavailable" in record["reasons"][0]
    assert [call[0] for call in session.calls].count("document_open") == 1


def test_Should_list_the_queue_with_reasons_When_the_summary_is_written():
    # Arrange
    results = [
        {
            "id": "TC-02-02",
            "title": "t",
            "launch": {},
            "verdict": "PASS",
            "capture": "a.png",
            "reasons": [],
            "review": None,
        },
        {
            "id": "TC-11-17",
            "title": "u",
            "launch": {"FREECAD_BUDDY_SCRIPT_EXEC": "0"},
            "verdict": "FAIL",
            "capture": None,
            "reasons": ['expect exec.status: expected "INVALID_INPUT", observed "OK"'],
            "review": "fail",
        },
    ]

    # Act
    text = run.summary(results, _metadata(seed=7, source="given"))

    # Assert
    assert "2 scenarios: 1 PASS, 1 FAIL, 0 ESCALATE." in text
    assert "| TC-11-17 | u | FREECAD_BUDDY_SCRIPT_EXEC=0 | FAIL | - |" in text
    assert text.endswith(
        "## Escalation queue\n\n### TC-11-17: FAIL\n\n"
        '- expect exec.status: expected "INVALID_INPUT", observed "OK"\n\n'
        "## Agent review\n\n"
        "Sample seed 7 (given). The agent reads these captures (tests/uat/test-plan.md §9); "
        "the scripted pixel check grades the rest.\n\n"
        "- TC-11-17 (fail): no capture\n"
    )


def test_Should_separate_the_empty_queue_from_the_agent_review_When_every_scenario_passed():
    # Arrange
    results = [_record("PASS", review="first of TC-02")]

    # Act
    text = run.summary(results, _metadata(seed=3, source="drawn"))

    # Assert
    assert "Empty: every scenario passed.\n\n## Agent review\n\n" in text
    assert text.endswith("- TC-02-02 (first of TC-02): a.png\n")


def _metadata(seed=1, source="given", errors=()):
    return {"errors": list(errors), "sample_seed": seed, "sample_seed_source": source}


def _verdicts(*pairs):
    """Result records from ``(id, verdict)`` pairs, in run order."""
    return [
        {"id": scenario_id, "tc": scenario_id[:5], "verdict": verdict, "capture": None}
        for scenario_id, verdict in pairs
    ]


def _items(records, no_pixel=()):
    """The scenarios behind ``records``; those named in ``no_pixel`` have no ``pixel`` block."""
    return [
        {"id": r["id"]} if r["id"] in no_pixel else {"id": r["id"], "pixel": {"samples": ["d.o"]}}
        for r in records
    ]


def _reviews(records):
    return {record["id"]: record["review"] for record in records}


def test_Should_review_fails_escalations_firsts_and_a_sample_When_a_run_is_mixed():
    # Arrange
    records = _verdicts(
        *[(f"TC-02-0{i}", "FAIL" if i == 3 else "PASS") for i in range(1, 8)],
        *[(f"TC-14-0{i}", "ESCALATE" if i == 2 else "PASS") for i in range(1, 4)],
    )
    items = _items(records)

    # Act
    run.mark_review(records, items, 12345)

    # Assert
    reviews = _reviews(records)
    fixed = {
        "TC-02-01": "first of TC-02",
        "TC-02-03": "fail",
        "TC-14-01": "first of TC-14",
        "TC-14-02": "escalate",
    }
    assert {key: reviews[key] for key in fixed} == fixed
    rest = [value for key, value in reviews.items() if key not in fixed]
    # 6 remaining PASS scenarios: 20 % is 1.2, rounded up to 2.
    assert sorted(rest, key=str) == [None, None, None, None, "sample", "sample"]


def test_Should_review_with_no_pixel_check_When_a_pass_scenario_has_no_pixel_block():
    # Arrange
    records = _verdicts(("TC-02-01", "PASS"), ("TC-02-02", "PASS"))
    items = _items(records, no_pixel={"TC-02-02"})

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records)["TC-02-02"] == "no pixel check"


def test_Should_review_with_no_pixel_check_When_the_pixel_block_has_no_samples():
    # Arrange
    records = _verdicts(("TC-02-01", "PASS"), ("TC-02-02", "PASS"))
    items = _items(records)
    items[1]["pixel"] = {}

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records)["TC-02-02"] == "no pixel check"


def test_Should_name_the_first_pass_When_the_first_scenario_of_a_test_case_fails():
    # Arrange
    records = _verdicts(("TC-02-01", "FAIL"), ("TC-02-02", "PASS"), ("TC-02-03", "PASS"))
    items = _items(records)

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records)["TC-02-01"] == "fail"
    assert _reviews(records)["TC-02-02"] == "first of TC-02"


def test_Should_name_the_next_pass_When_the_first_pass_is_already_in_for_no_pixel_check():
    # Arrange
    records = _verdicts(("TC-02-01", "PASS"), ("TC-02-02", "PASS"))
    items = _items(records, no_pixel={"TC-02-01"})

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records) == {"TC-02-01": "no pixel check", "TC-02-02": "first of TC-02"}


def test_Should_pick_the_first_pass_by_id_When_the_scenarios_arrive_out_of_order():
    # Arrange
    records = _verdicts(("TC-02-05", "PASS"), ("TC-02-02", "PASS"))
    items = _items(records)

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records)["TC-02-02"] == "first of TC-02"


def test_Should_name_no_first_When_a_test_case_has_no_pass():
    # Arrange
    records = _verdicts(("TC-02-01", "PASS"), ("TC-14-01", "FAIL"), ("TC-14-02", "ESCALATE"))
    items = _items(records)

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert "first of TC-14" not in _reviews(records).values()
    assert _reviews(records) == {
        "TC-02-01": "first of TC-02",
        "TC-14-01": "fail",
        "TC-14-02": "escalate",
    }


def test_Should_leave_the_sample_empty_When_every_scenario_is_already_in():
    # Arrange
    records = _verdicts(
        ("TC-02-01", "PASS"), ("TC-02-02", "FAIL"), ("TC-11-01", "ESCALATE"), ("TC-14-01", "PASS")
    )
    items = _items(records)

    # Act
    run.mark_review(records, items, 1)

    # Assert
    assert _reviews(records) == {
        "TC-02-01": "first of TC-02",
        "TC-02-02": "fail",
        "TC-11-01": "escalate",
        "TC-14-01": "first of TC-14",
    }


@pytest.mark.parametrize(
    ("rest_size", "sample_size"),
    [(1, 1), (5, 1), (6, 2), (10, 2), (15, 3), (16, 4)],
)
def test_Should_sample_20_percent_rounded_up_When_scenarios_remain(rest_size, sample_size):
    # Arrange
    records = _verdicts(*[(f"TC-02-{i:02d}", "PASS") for i in range(1, rest_size + 2)])
    items = _items(records)

    # Act
    run.mark_review(records, items, 7)

    # Assert
    assert list(_reviews(records).values()).count("sample") == sample_size


def test_Should_draw_the_same_sample_When_the_argument_order_changes():
    # Arrange
    pairs = [(f"TC-02-{i:02d}", "PASS") for i in range(1, 21)]
    forward, backward = _verdicts(*pairs), _verdicts(*reversed(pairs))
    run.mark_review(forward, _items(forward), 99)

    # Act
    run.mark_review(backward, _items(backward), 99)

    # Assert
    assert _reviews(backward) == _reviews(forward)


def _sampled(records):
    return {record["id"] for record in records if record["review"] == "sample"}


def test_Should_draw_a_different_sample_When_the_seed_changes():
    # Arrange
    pairs = [(f"TC-02-{i:02d}", "PASS") for i in range(1, 21)]
    first, second = _verdicts(*pairs), _verdicts(*pairs)

    # Act
    run.mark_review(first, _items(first), 1)
    run.mark_review(second, _items(second), 2)

    # Assert
    assert _sampled(first) != _sampled(second)


def _scenario_folder(folder, count):
    """``count`` TC-02 scenario files with a ``pixel`` block in ``folder``."""
    folder.mkdir()
    for index in range(1, count + 1):
        data = {
            "id": f"TC-02-{index:02d}",
            "tc": "TC-02",
            "steps": [{"mcp": "document_list"}],
            "pixel": {"samples": ["d.o"]},
        }
        (folder / f"tc-02-{index:02d}.json").write_text(json.dumps(data), "utf-8")
    return folder


def _all_pass(scenarios, run_dir):
    """A fake ``run.run``: every scenario ``PASS`` with a capture, no group error."""
    return [_record("PASS", id=item["id"], tc=item["tc"]) for item in scenarios], []


def test_Should_draw_and_record_a_seed_that_redraws_the_set_When_no_seed_is_given(
    tmp_path, monkeypatch
):
    # Arrange
    folder = _scenario_folder(tmp_path / "scenarios", 20)
    monkeypatch.setattr(launch, "preflight", lambda: None)
    monkeypatch.setattr(run, "run", _all_pass)
    out = tmp_path / "out"

    # Act
    run.main([str(folder), "--out", str(out)])

    # Assert
    written = json.loads((out / "results.json").read_text("utf-8"))
    seed = written["run"]["sample_seed"]
    items = scenario.load_all([folder])
    redrawn, _ = _all_pass(items, out)
    run.mark_review(redrawn, items, seed)
    assert written["run"]["sample_seed_source"] == "drawn"
    assert 0 <= seed < 2**32
    assert _reviews(written["scenarios"]) == _reviews(redrawn)
    assert list(_reviews(redrawn).values()).count("sample") == 4
    assert f"Sample seed {seed} (drawn)." in (out / "summary.md").read_text("utf-8")


def test_Should_record_different_seeds_When_two_runs_draw_them(tmp_path, monkeypatch):
    # Arrange
    folder = _scenario_folder(tmp_path / "scenarios", 5)
    monkeypatch.setattr(launch, "preflight", lambda: None)
    monkeypatch.setattr(run, "run", _all_pass)
    outs = [tmp_path / "first", tmp_path / "second"]

    # Act
    for out in outs:
        run.main([str(folder), "--out", str(out)])

    # Assert
    first, second = (
        json.loads((out / "results.json").read_text("utf-8"))["run"]["sample_seed"] for out in outs
    )
    assert first != second


def test_Should_draw_the_same_set_and_record_the_seed_as_given_When_a_past_seed_is_replayed(
    tmp_path, monkeypatch
):
    # Arrange
    folder = _scenario_folder(tmp_path / "scenarios", 20)
    monkeypatch.setattr(launch, "preflight", lambda: None)
    monkeypatch.setattr(run, "run", _all_pass)
    run.main([str(folder), "--out", str(tmp_path / "past")])
    past = json.loads((tmp_path / "past" / "results.json").read_text("utf-8"))
    replay_out = tmp_path / "replay"

    # Act
    run.main([str(folder), "--out", str(replay_out), "--seed", str(past["run"]["sample_seed"])])

    # Assert
    replay = json.loads((replay_out / "results.json").read_text("utf-8"))
    summary_text = (replay_out / "summary.md").read_text("utf-8")
    assert replay["run"]["sample_seed"] == past["run"]["sample_seed"]
    assert replay["run"]["sample_seed_source"] == "given"
    assert _reviews(replay["scenarios"]) == _reviews(past["scenarios"])
    sampled = [key for key, value in _reviews(replay["scenarios"]).items() if value == "sample"]
    assert all(f"- {key} (sample): a.png" in summary_text for key in sampled)


def test_Should_refuse_with_exit_2_naming_the_value_When_the_seed_is_not_an_integer(
    tmp_path, capsys, no_launch
):
    # Arrange
    argv = [str(SCENARIO_DIR / "tc-02-02.json"), "--out", str(tmp_path / "out"), "--seed", "abc"]

    # Act
    with pytest.raises(SystemExit) as exited:
        run.main(argv)

    # Assert
    assert exited.value.code == 2
    assert "'abc'" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_Should_detect_every_fault_with_no_false_alarm_When_the_pixel_fault_set_runs(capsys):
    # Arrange
    expected_lines = ("detected 4/4", "false alarms 0/2")

    # Act
    code = pixel_faults.main()

    # Assert
    output = capsys.readouterr().out
    assert code == 0
    assert all(line in output for line in expected_lines)


def test_Should_exit_1_naming_the_miss_When_the_pixel_check_misses_a_fault(capsys, monkeypatch):
    # Arrange
    monkeypatch.setattr(run, "check_pixel", lambda *args: (None, []))

    # Act
    code = pixel_faults.main()

    # Assert
    output = capsys.readouterr().out
    assert code == 1
    assert "MISSED      empty-view" in output
    assert "detected 0/4" in output


def _runner_sources():
    return {p: p.read_text("utf-8") for p in RUNNER_DIR.glob("*.py")}


def test_Should_not_import_freecad_buddy_When_any_runner_file_is_read():
    # Arrange
    sources = _runner_sources()
    pattern = re.compile(r"^\s*(import|from)\s+freecad_buddy\b", re.MULTILINE)

    # Act
    importers = [p.name for p, text in sources.items() if pattern.search(text)]

    # Assert
    assert sources
    assert importers == []


def test_Should_reach_invoke_menu_only_through_the_allow_list_When_runner_files_are_read():
    # Arrange
    sources = _runner_sources()

    # Act
    callers = sorted(
        (p.name, line.strip())
        for p, text in sources.items()
        for line in text.splitlines()
        if "invoke_menu" in line and not line.lstrip().startswith(("#", '"', "def "))
    )

    # Assert
    assert callers == [
        ("run.py", "capture.invoke_menu(self.pid, self.window_id, path)"),
    ]
    assert capture.MENU_ALLOW_LIST == (
        ("View", "Visibility", "Show All Objects"),
        ("Edit", "Recompute"),
    )


def test_Should_validate_every_file_When_the_committed_scenarios_are_read():
    # Arrange
    paths = sorted(SCENARIO_DIR.glob("*.json"))

    # Act
    items = scenario.load_all([SCENARIO_DIR])

    # Assert
    assert len(items) == len(paths)
    assert [Path(item["file"]).name for item in items] == [
        f"{item['id'].lower()}.json" for item in items
    ]
    assert {"FREECAD_BUDDY_SCRIPT_EXEC": "0"} in [item["launch"] for item in items]
    assert any(item["cross"] for item in items)
    assert any("pixel" in item for item in items)
    assert any("probe" in item for item in items)
    assert any(check for item in items for check in item["expect"])


def _strings_of(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _strings_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings_of(inner)


def test_Should_hold_no_control_character_in_a_string_When_the_committed_scenarios_are_decoded():
    # Arrange
    paths = sorted(SCENARIO_DIR.glob("*.json"))

    # Act
    offenders = [
        (path.name, text)
        for path in paths
        for text in _strings_of(json.loads(path.read_text(encoding="utf-8")))
        if any(ord(character) < 32 and character not in "\n\r\t" for character in text)
    ]

    # Assert
    assert paths
    assert offenders == []


def test_Should_name_a_heading_of_its_test_case_When_a_committed_scenario_is_read():
    # Arrange
    items = scenario.load_all([SCENARIO_DIR])

    # Act
    missing = [
        item["id"]
        for item in items
        if not any(
            f"### {item['id']}:" in path.read_text("utf-8")
            for path in TESTCASE_DIR.glob(f"{item['tc']}-*.md")
        )
    ]

    # Assert
    assert missing == []


BINDINGS = {"open": OPEN_OK, "mass": MASS_6000, "label": {"text": "Box", "count": 3}}


@pytest.mark.parametrize(
    ("check", "passes"),
    [
        ({"path": "structured_content.volume.value", "approx": 6000.5, "tolerance": 1}, True),
        ({"path": "structured_content.volume.value", "approx": 6002, "tolerance": 1}, False),
        ({"path": "structured_content.volume.unit", "approx": 6000, "tolerance": 1}, False),
        ({"path": "structured_content.volume.unit", "regex": "^mm"}, True),
        ({"path": "structured_content.volume.unit", "regex": "^cm"}, False),
        ({"path": "structured_content.volume.value", "regex": "6000"}, False),
        ({"path": "structured_content.volume", "absent": False}, True),
        ({"path": "structured_content.volume", "absent": True}, False),
        ({"path": "structured_content.mass", "absent": True}, True),
        ({"path": "structured_content.mass", "absent": False}, False),
    ],
    ids=[
        "approx inside",
        "approx outside",
        "approx non-number",
        "regex match",
        "regex no match",
        "regex non-string",
        "absent false, present",
        "absent true, present",
        "absent true, missing",
        "absent false, missing",
    ],
)
def test_Should_judge_each_operator_When_an_expect_check_runs(check, passes):
    # Arrange
    full_check = {"step": "mass", **check}

    # Act
    finding = run.check_expect(full_check, BINDINGS)

    # Assert
    assert (finding is None) is passes


def test_Should_compare_with_the_referenced_value_When_equals_names_a_step_path():
    # Arrange
    same = {
        "step": "open",
        "path": "structured_content.doc",
        "equals": "$open.structured_content.doc",
    }
    other = {
        "step": "open",
        "path": "structured_content.name",
        "equals": "$open.structured_content.doc",
    }

    # Act
    findings = [run.check_expect(same, BINDINGS), run.check_expect(other, BINDINGS)]

    # Assert
    assert findings[0] is None
    assert (findings[1]["expected"], findings[1]["observed"]) == ("fcb-doc:abc", "box")


@pytest.mark.parametrize(
    ("mcp_path", "probe_path"),
    [
        ("mass.structured_content.missing", "documents.box.objects.Box.shape.volume"),
        ("mass.structured_content.volume.value", "documents.box.objects.Gone.shape.volume"),
        ("mass.structured_content.missing", "documents.box.objects.Gone.shape.volume"),
    ],
    ids=["mcp value missing", "probe value missing", "both missing"],
)
def test_Should_fail_and_not_escalate_When_a_cross_value_is_missing(mcp_path, probe_path):
    # Arrange
    entry = {"mcp": mcp_path, "probe": probe_path}

    # Act
    finding, disagreement = run.check_cross(entry, BINDINGS, _box_snapshot())

    # Assert
    assert disagreement is None
    assert finding["kind"] == "cross"


def _session(snapshot=None, **kwargs):
    return FakeSession(
        {"document_open": OPEN_OK, "query_mass_properties": MASS_6000},
        snapshot or _box_snapshot(),
        **kwargs,
    )


def _view_snapshot(**view):
    snapshot = _box_snapshot()
    snapshot["view"] = None if view.get("none") else snapshot["view"] | view
    return snapshot


@pytest.mark.parametrize(
    ("snapshot", "field", "observed"),
    [
        (_view_snapshot(none=True), "view", None),
        (_view_snapshot(clipped=True), "view.clipped", True),
        (_view_snapshot(clipped=None), "view.clipped", None),
        (
            _view_snapshot(rect=[-10, 10, 160, 120]),
            "view.rect",
            "view rect outside capture: [-10, 10, 150, 130] in 200x150",
        ),
        (
            _view_snapshot(rect=[100, 10, 160, 120]),
            "view.rect",
            "view rect outside capture: [100, 10, 260, 130] in 200x150",
        ),
    ],
    ids=["no view", "clipped", "hidden", "left of the capture", "past the capture width"],
)
def test_Should_fail_without_measuring_When_the_view_cannot_be_measured(
    tmp_path, snapshot, field, observed
):
    # Arrange
    item = _scenario(tmp_path, probe={"documents": {"box": {}}})

    # Act
    record = run.run_scenario(item, _session(snapshot), tmp_path)

    # Assert
    assert record["verdict"] == "FAIL"
    assert [(f["field"], f["observed"]) for f in record["findings"]] == [(field, observed)]
    assert record["pixel"] is None


def test_Should_escalate_only_that_scenario_When_a_check_raises(tmp_path):
    # Arrange
    broken = _scenario(tmp_path, id="TC-02-01")
    Path(broken["file"]).with_suffix(".golden.png").write_bytes(b"not a png")
    healthy = _scenario(tmp_path, id="TC-02-02")

    @contextlib.contextmanager
    def open_session(launch_env, audit_log):
        yield _session()

    # Act
    results, groups = run.run([broken, healthy], tmp_path, open_session=open_session)

    # Assert
    assert [r["verdict"] for r in results] == ["ESCALATE", "PASS"]
    assert results[0]["reasons"] == ["checks raised PngError: not a PNG file"]
    assert groups[0]["error"] is None


def test_Should_record_a_teardown_error_When_the_group_fails_after_its_scenarios_ran(tmp_path):
    # Arrange
    @contextlib.contextmanager
    def open_session(launch_env, audit_log):
        yield _session()
        raise launch.LaunchError(":8765 still held 15 s after exit")

    items = [_scenario(tmp_path)]

    # Act
    results, groups = run.run(items, tmp_path, open_session=open_session)

    # Assert
    assert results[0]["verdict"] == "PASS"
    assert run.group_errors(groups) == [
        "group 0 (default): teardown raised LaunchError: :8765 still held 15 s after exit"
    ]


def test_Should_delete_a_stale_capture_When_the_new_capture_fails(tmp_path):
    # Arrange
    stale = tmp_path / "captures" / "TC-02-02.png"
    stale.parent.mkdir()
    stale.write_bytes(_encode_png(_scene(), 3))
    session = _session(capture_error=capture.CuaError("get_window_state wrote nothing"))

    # Act
    record = run.run_scenario(_scenario(tmp_path), session, tmp_path)

    # Assert
    assert record["capture"] is None
    assert not stale.exists()


def _record(verdict, **extra):
    return {
        "id": "TC-02-02",
        "tc": "TC-02",
        "title": "t",
        "launch": {},
        "verdict": verdict,
        "capture": "a.png",
        "reasons": [],
        "review": None,
    } | extra


@pytest.mark.parametrize(
    ("verdicts", "group_error", "expected_code"),
    [
        (["PASS", "ESCALATE"], None, 0),
        (["PASS", "FAIL"], None, 1),
        (["ESCALATE", "ESCALATE"], "launch raised LaunchError: FreeCAD exited with code 1", 3),
        (["FAIL", "PASS"], "teardown raised LaunchError: :8765 still held", 3),
    ],
    ids=["pass and escalate", "one fail", "not run", "teardown error"],
)
def test_Should_exit_with_the_documented_code_and_write_both_files_When_the_run_ends(
    tmp_path, monkeypatch, verdicts, group_error, expected_code
):
    # Arrange
    records = [_record(v, id=f"TC-02-0{i}") for i, v in enumerate(verdicts, 1)]
    groups = [{"launch": {}, "scenarios": [r["id"] for r in records], "error": group_error}]
    monkeypatch.setattr(launch, "preflight", lambda: None)
    monkeypatch.setattr(run, "run", lambda scenarios, run_dir: (records, groups))
    out = tmp_path / "out"

    # Act
    code = run.main(
        [str(SCENARIO_DIR / f"{r['id'].lower()}.json") for r in records] + ["--out", str(out)]
    )

    # Assert
    written = json.loads((out / "results.json").read_text("utf-8"))
    summary_text = (out / "summary.md").read_text("utf-8")
    assert code == expected_code
    assert written["scenarios"] == records
    assert set(written["run"]) >= {"git_commit", "git_dirty", "freecad_apprun", "started", "errors"}
    assert written["run"]["errors"] == (
        [f"group 0 (default): {group_error}"] if group_error else []
    )
    assert ("## Run errors" in summary_text) is bool(group_error)


def test_Should_escape_pipes_and_newlines_When_titles_and_reasons_hold_them():
    # Arrange
    results = [_record("FAIL", title="a | b\nc", reasons=["x | y\nz"])]

    # Act
    text = run.summary(results, _metadata())

    # Assert
    assert "| TC-02-02 | a \\| b c | default | FAIL | a.png |" in text
    assert "- x \\| y z" in text


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"expect": [{"step": "s", "path": "a", "regex": "("}]}, "does not compile"),
        ({"expect": [{"step": "s", "path": "a", "approx": "1", "tolerance": 1}]}, "'approx'"),
        ({"expect": [{"step": "s", "path": "a", "approx": 1, "tolerance": "1"}]}, "'tolerance'"),
        ({"expect": [{"step": "s", "path": "a", "absent": "yes"}]}, "'absent'"),
        ({"pixel": {"samples": ["d.o"], "extent": {"min_fraction": "0.5"}}}, "min_fraction"),
        ({"pixel": {"samples": ["d.o"], "extent": {"inside": 1}}}, "inside"),
        ({"cross": [{"mcp": ["s"], "probe": "documents"}]}, "path strings"),
        ({"cross": [{"mcp": "s.a", "probe": "documents", "tolerance": "0.1"}]}, "'tolerance'"),
        ({"steps": [{"menu": "View"}]}, "must be a list"),
        ({"steps": [{"name": "m", "menu": ["Edit", "Recompute"]}]}, "not allowed on a menu step"),
        ({"agent_check": " "}, "non-empty"),
    ],
    ids=[
        "bad regex",
        "approx not a number",
        "tolerance not a number",
        "absent not a bool",
        "min_fraction not a number",
        "inside not a bool",
        "cross path not a string",
        "cross tolerance not a number",
        "menu not a list",
        "name on a menu step",
        "empty agent_check",
    ],
)
def test_Should_refuse_the_scenario_When_a_value_has_the_wrong_type(change, message):
    # Arrange
    data = {"id": "TC-02-02", "tc": "TC-02", "steps": [{"name": "s", "mcp": "x"}], **change}

    # Act
    act = lambda: scenario.validate(data)  # noqa: E731

    # Assert
    with pytest.raises(scenario.ScenarioError, match=re.escape(message)):
        act()


@pytest.mark.parametrize(
    ("content", "name"),
    [(None, "missing.json"), (b"\xff\xfe{", "latin.json")],
    ids=["missing file", "not UTF-8"],
)
def test_Should_raise_a_scenario_error_naming_the_file_When_it_cannot_be_read(
    tmp_path, content, name
):
    # Arrange
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)

    # Act
    act = lambda: scenario.load(path)  # noqa: E731

    # Assert
    with pytest.raises(scenario.ScenarioError, match=re.escape(str(path))):
        act()


def test_Should_refuse_When_a_folder_argument_holds_no_scenario_file(tmp_path):
    # Arrange
    empty = tmp_path / "empty"
    empty.mkdir()

    # Act
    act = lambda: scenario.load_all([empty])  # noqa: E731

    # Assert
    with pytest.raises(scenario.ScenarioError, match="no scenario files"):
        act()


def test_Should_drop_inherited_bridge_variables_When_the_launch_environment_is_built(
    monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setenv("FREECAD_BUDDY_AUTO_APPROVE", "0")
    monkeypatch.setenv("FREECAD_BUDDY_SCRIPT_EXEC", "0")
    audit_log = tmp_path / "audit.jsonl"

    # Act
    environment = launch.launch_environment({"FREECAD_BUDDY_UNATTENDED": "1"}, audit_log)

    # Assert
    bridge = {k: v for k, v in environment.items() if k.startswith("FREECAD_BUDDY_")}
    assert bridge == {"FREECAD_BUDDY_AUDIT_LOG": str(audit_log), "FREECAD_BUDDY_UNATTENDED": "1"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"FREECAD_APPRUN": "Z:/no/AppRun"}, "is not a file"),
        ({"which": None}, "is not an executable file"),
        ({"status": "Cua Driver daemon is not running"}, "daemon is not running"),
    ],
    ids=["no AppRun", "no cua-driver", "daemon down"],
)
def test_Should_refuse_When_a_tool_the_run_needs_is_missing(monkeypatch, tmp_path, change, message):
    # Arrange
    apprun = tmp_path / "AppRun"
    apprun.write_bytes(b"")
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(launch, "FREECAD_APPRUN", change.get("FREECAD_APPRUN", str(apprun)))
    monkeypatch.setattr(launch.shutil, "which", lambda name: change.get("which", "cua-driver"))
    status = change.get("status", "Cua Driver daemon is running")
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=status, stderr=""),
    )

    # Act
    act = launch.check_tools

    # Assert
    with pytest.raises(launch.LaunchError, match=message):
        act()


def test_Should_exit_2_without_a_traceback_When_the_process_list_is_unreadable(
    tmp_path, capsys, monkeypatch
):
    # Arrange
    monkeypatch.setattr(launch, "check_tools", lambda: None)
    monkeypatch.setattr(launch, "_PROC_ROOT", str(tmp_path / "no-proc"))

    # Act
    code = run.main([str(SCENARIO_DIR / "tc-02-02.json"), "--out", str(tmp_path / "out")])

    # Assert
    assert code == 2
    assert "cannot list processes under" in capsys.readouterr().out


def test_Should_refuse_before_starting_FreeCAD_When_a_group_finds_8765_held(monkeypatch, tmp_path):
    # Arrange
    def no_start(*args, **kwargs):
        raise AssertionError("FreeCAD must not start")

    monkeypatch.setattr(launch, "running_freecad_pids", lambda: [])
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: True)
    monkeypatch.setattr(launch.subprocess, "Popen", no_start)

    # Act
    act = lambda: launch.freecad({}, tmp_path / "audit.jsonl").__enter__()  # noqa: E731

    # Assert
    with pytest.raises(launch.LaunchError, match="8765 is held"):
        act()


class _FakeProcess:
    def __init__(self, pid=4242, running=True):
        self.pid = pid
        self.running = running
        self.killed = 0

    def poll(self):
        return None if self.running else 1

    def kill(self):
        self.killed += 1
        self.running = False

    def wait(self):
        return 1


def test_Should_wait_When_healthz_names_another_freecad(monkeypatch, tmp_path):
    # Arrange
    discovery = tmp_path / "fcb-uat-probe" / "probe-4242.json"
    discovery.parent.mkdir()
    discovery.write_text('{"pid": 4242, "port": 1, "token": "t"}', "utf-8")
    monkeypatch.setattr(launch, "_healthz", lambda: {"freecad_pid": 999})
    monkeypatch.setattr(launch, "discovery_file", lambda pid: discovery)
    monkeypatch.setattr(launch, "descendant_pids", lambda root: {root})
    monkeypatch.setattr(launch, "START_TIMEOUT_S", 0.2)
    monkeypatch.setattr(launch, "POLL_S", 0.05)

    # Act
    act = lambda: launch.wait_until_ready(_FakeProcess())  # noqa: E731

    # Assert
    with pytest.raises(launch.LaunchError, match="no /healthz naming a FreeCAD below it"):
        act()


def test_Should_end_only_its_own_process_group_When_it_stops_freecad(monkeypatch, tmp_path):
    # Arrange
    def no_other_process(*args, **kwargs):
        raise AssertionError("stop must not start or end another process")

    ended = []
    monkeypatch.setattr(launch.subprocess, "run", no_other_process)
    monkeypatch.setattr(launch.subprocess, "Popen", no_other_process)
    monkeypatch.setattr(launch.os, "killpg", lambda pid, sig: ended.append(pid), raising=False)
    monkeypatch.setattr(launch.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(launch, "discovery_file", lambda pid: tmp_path / "gone.json")
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: False)
    process = _FakeProcess()

    # Act
    launch.stop(process)

    # Assert
    assert ended == [process.pid]


def test_Should_return_structured_content_or_the_text_When_a_tool_result_arrives():
    # Arrange
    text_block = SimpleNamespace(type="text", text="OK: 1 objects")
    structured = SimpleNamespace(structuredContent={"status": "OK"}, content=[], isError=False)
    plain = SimpleNamespace(structuredContent=None, content=[text_block], isError=True)

    # Act
    results = [mcp_client.to_result(structured), mcp_client.to_result(plain)]

    # Assert
    assert results == [{"status": "OK"}, {"text": "OK: 1 objects", "is_error": True}]


def test_Should_raise_at_once_When_the_session_task_has_ended():
    # Arrange
    client = mcp_client.McpClient()
    ended = concurrent.futures.Future()
    ended.set_exception(OSError("connection refused"))
    client._served = ended

    # Act
    act = lambda: client.call("document_list", {})  # noqa: E731

    # Assert
    with pytest.raises(ConnectionError, match="connection refused"):
        act()
    client._loop.close()


def _replay_record(scenario_id, verdict, **extra):
    record = {
        "id": scenario_id,
        "verdict": verdict,
        "capture": "c.png",
        "errors": [],
        "disagreements": [],
        "findings": [],
        "agent_check": None,
    }
    return record | extra


@pytest.mark.parametrize(
    ("old", "record", "notes", "row", "kind"),
    [
        ("PASS", _replay_record("TC-02-02", "PASS"), {}, "same", "-"),
        (
            "FAIL",
            _replay_record("TC-02-02", "PASS"),
            {"TC-02-02": {"class": "product fixed (F-01, 10.1)"}},
            "differs",
            "product fixed (F-01, 10.1)",
        ),
        (
            "PARTIAL",
            _replay_record("TC-02-02", "ESCALATE", agent_check="Fit All framing"),
            {},
            "same",
            "-",
        ),
        ("FAIL", _replay_record("TC-02-02", "FAIL"), {}, "same", "-"),
        ("PASS", _replay_record("TC-02-02", "FAIL"), {}, "differs", "unexplained"),
        (
            "PASS",
            _replay_record(
                "TC-02-02", "ESCALATE", agent_check="Fit All", errors=["step 1 raised MenuError"]
            ),
            {},
            "differs",
            "unexplained",
        ),
        ("BLOCKED", _replay_record("TC-02-02", "PASS"), {}, "new", "-"),
        (
            "PASS",
            _replay_record(
                "TC-02-02", "ESCALATE", agent_check="Fit All", disagreements=[{"reason": "r"}]
            ),
            {},
            "differs",
            "unexplained",
        ),
        (
            "PASS",
            _replay_record("TC-02-02", "ESCALATE", agent_check="Fit All", findings=[{"r": 1}]),
            {},
            "differs",
            "unexplained",
        ),
        (
            "PASS",
            _replay_record("TC-02-02", "ESCALATE", agent_check="Fit All", capture=None),
            {},
            "differs",
            "unexplained",
        ),
    ],
    ids=[
        "same verdict",
        "product fixed",
        "visual only",
        "fail stays fail",
        "unexplained difference",
        "escalate with an error is not visual only",
        "blocked is not compared",
        "escalate with a disagreement is not visual only",
        "escalate with a finding is not visual only",
        "escalate with no capture is not visual only",
    ],
)
def test_Should_classify_the_row_When_a_replayed_scenario_is_compared(
    old, record, notes, row, kind
):
    # Arrange
    current = ["TC-02-02"]

    # Act
    table = compare.rows({"TC-02-02": old}, [record], current, notes)

    # Assert
    assert [(r["row"], r["class"]) for r in table] == [(row, kind)]


@pytest.mark.parametrize(
    ("old", "current", "notes", "row", "kind"),
    [
        (
            {"TC-10-07": "PASS"},
            ["TC-10-07"],
            {"TC-10-07": {"coverage": "H1 host"}},
            "not covered",
            "H1 host",
        ),
        (
            {"TC-04-08": "PASS"},
            ["TC-04-08"],
            {"TC-04-08": {"coverage": "not encoded"}},
            "not encoded",
            "not encoded",
        ),
        ({}, ["TC-11-19"], {"TC-11-19": {"coverage": "H1 host"}}, "new", "H1 host"),
        ({"TC-05-19": "PASS"}, [], {}, "removed", "-"),
        ({"TC-04-08": "PASS"}, ["TC-04-08"], {}, "not covered", "unexplained"),
    ],
    ids=["not covered", "not encoded", "new id", "old id missing", "no note"],
)
def test_Should_classify_the_row_When_a_scenario_was_not_replayed(old, current, notes, row, kind):
    # Arrange
    records = []

    # Act
    table = compare.rows(old, records, current, notes)

    # Assert
    assert [(r["row"], r["class"]) for r in table] == [(row, kind)]


def test_Should_cite_the_edit_inventory_When_an_old_id_is_removed():
    # Arrange
    old = {"TC-05-19": "PASS"}

    # Act
    table = compare.rows(old, [], [], {})

    # Assert
    assert "spec-10-7-edit-inventory.md" in table[0]["explanation"]


def test_Should_list_the_new_id_with_its_runner_verdict_When_it_was_replayed():
    # Arrange
    record = _replay_record("TC-11-17", "FAIL")

    # Act
    table = compare.rows({}, [record], ["TC-11-17"], {})

    # Assert
    assert [(r["row"], r["old"], r["runner"], r["class"]) for r in table] == [
        ("new", None, "FAIL", "-")
    ]


@pytest.mark.parametrize(
    "note",
    [
        {"coverage": "too hard"},
        {"class": "product fixed"},
        {"class": "unexplained"},
        {"left_out": [{"then": "file saved", "reason": "too hard"}]},
    ],
    ids=[
        "reason outside the set",
        "class without finding",
        "class unexplained",
        "left-out reason outside the set",
    ],
)
def test_Should_refuse_When_a_note_is_outside_the_closed_sets(note):
    # Arrange
    notes = {"TC-02-02": note}

    # Act
    act = lambda: compare.rows({"TC-02-02": "PASS"}, [], ["TC-02-02"], notes)  # noqa: E731

    # Assert
    with pytest.raises(compare.CompareError, match="TC-02-02"):
        act()


def test_Should_name_the_thens_left_out_When_a_scenario_encodes_part_of_its_test_case():
    # Arrange
    notes = {
        "TC-02-01": {
            "explanation": "pilot",
            "left_out": [
                {"then": "ls -l shows the saved file", "reason": "file check"},
                {"then": "addon.log has no traceback", "reason": "log or audit read"},
            ],
        }
    }

    # Act
    table = compare.rows(
        {"TC-02-01": "PASS"}, [_replay_record("TC-02-01", "PASS")], ["TC-02-01"], notes
    )

    # Assert
    assert table[0]["row"] == "same"
    assert table[0]["explanation"] == (
        "pilot Not checked: ls -l shows the saved file (file check); "
        "addon.log has no traceback (log or audit read)."
    )


REPORT_HEAD = (
    "| Scenario | Priority | Verdict | Evidence | Note |\n| --- | --- | --- | --- | --- |\n"
)


def _replay_dirs(tmp_path, report_rows, records, notes):
    old = tmp_path / "old"
    old.mkdir()
    (old / "report.md").write_text("## TC-02\n\n" + REPORT_HEAD + report_rows, encoding="utf-8")
    replay = tmp_path / "replay"
    replay.mkdir()
    (replay / "results.json").write_text(
        json.dumps({"run": {"git_commit": "abc"}, "scenarios": records}), encoding="utf-8"
    )
    (replay / "replay-notes.json").write_text(json.dumps(notes), encoding="utf-8")
    testcases = tmp_path / "testcases"
    testcases.mkdir()
    (testcases / "TC-02-x.md").write_text("### TC-02-01: a\n\n### TC-02-02: b\n", encoding="utf-8")
    return [str(old), str(replay), "--testcases", str(testcases)]


def test_Should_exit_2_naming_the_line_When_a_report_row_cannot_be_parsed(tmp_path, capsys):
    # Arrange
    rows = "| TC-02-01 | Critical | **PASS** | e | n |\n| TC-02-02 | Critical | PASS | e | n |\n"
    argv = _replay_dirs(tmp_path, rows, [], {})

    # Act
    code = compare.main(argv)

    # Assert
    assert code == 2
    assert "report.md:6" in capsys.readouterr().out
    assert not (tmp_path / "replay" / "replay.md").exists()


def test_Should_exit_2_naming_the_folder_When_the_testcases_folder_has_no_heading(tmp_path, capsys):
    # Arrange
    rows = "| TC-02-01 | Critical | **PASS** | e | n |\n"
    argv = _replay_dirs(tmp_path, rows, [], {})
    empty = tmp_path / "empty"
    empty.mkdir()
    argv[-1] = str(empty)

    # Act
    code = compare.main(argv)

    # Assert
    assert code == 2
    assert f"{empty}: no '### TC-xx-yy:' heading" in capsys.readouterr().out
    assert not (tmp_path / "replay" / "replay.md").exists()


@pytest.mark.parametrize(
    ("notes", "expected_code", "unexplained"),
    [
        ({"TC-02-02": {"coverage": "GUI action", "explanation": "tree click"}}, 0, 0),
        ({}, 1, 1),
    ],
    ids=["every row explained", "a row unexplained"],
)
def test_Should_write_one_row_per_id_When_the_report_and_results_are_read(
    tmp_path, notes, expected_code, unexplained
):
    # Arrange
    rows = "| TC-02-01 | Critical | **PARTIAL** | e | n |\n| TC-02-02 | High | **FAIL** | e | n |\n"
    argv = _replay_dirs(tmp_path, rows, [_replay_record("TC-02-01", "PASS")], notes)

    # Act
    code = compare.main(argv)

    # Assert
    text = (tmp_path / "replay" / "replay.md").read_text("utf-8")
    assert code == expected_code
    assert (
        "2 rows: 1 same, 0 differs, 1 not covered, 0 not encoded, 0 new, 0 removed. "
        f"Unexplained: {unexplained}.\n"
    ) in text
    assert "| TC-02-01 | PARTIAL | PASS | same | - | - |" in text
    assert re.search(r"^\| TC-02-02 \| FAIL \| - \| not covered \|", text, re.MULTILINE)


def test_Should_prefer_the_results_json_When_a_test_case_has_one(tmp_path):
    # Arrange
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    rows = [
        {"id": "TC-04-00-preconditions", "verdict": "PASS"},
        {"id": "TC-04-01", "verdict": "FAIL"},
    ]
    (evidence / "tc-04-results.json").write_text(json.dumps(rows), encoding="utf-8")
    report_rows = (
        "| TC-04-01 | Critical | **PASS** | e | n |\n| TC-02-01 | High | **PASS** | e | n |\n"
    )
    (tmp_path / "report.md").write_text(REPORT_HEAD + report_rows, encoding="utf-8")

    # Act
    verdicts = compare.old_verdicts(tmp_path)

    # Assert
    assert verdicts == {"TC-02-01": "PASS", "TC-04-01": "FAIL"}
