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
import launch  # noqa: E402
import mcp_client  # noqa: E402
import pixel  # noqa: E402
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
        },
        {
            "id": "TC-11-17",
            "title": "u",
            "launch": {"FREECAD_BUDDY_SCRIPT_EXEC": "0"},
            "verdict": "FAIL",
            "capture": None,
            "reasons": ['expect exec.status: expected "INVALID_INPUT", observed "OK"'],
        },
    ]

    # Act
    text = run.summary(results)

    # Assert
    assert "2 scenarios: 1 PASS, 1 FAIL, 0 ESCALATE." in text
    assert "| TC-11-17 | u | FREECAD_BUDDY_SCRIPT_EXEC=0 | FAIL | - |" in text
    assert text.endswith(
        "## Escalation queue\n\n### TC-11-17: FAIL\n\n"
        '- expect exec.status: expected "INVALID_INPUT", observed "OK"\n'
    )


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
        (
            "capture.py",
            'cua("invoke_menu", {"pid": pid, "window_id": window_id, "path": list(path)})',
        ),
        ("run.py", "capture.invoke_menu(self.pid, self.window_id, path)"),
    ]
    assert capture.MENU_ALLOW_LIST == (
        ("View", "Visibility", "Show All Objects"),
        ("Edit", "Recompute"),
    )


def test_Should_load_the_pilot_set_When_the_committed_scenarios_are_read():
    # Arrange
    paths = sorted(SCENARIO_DIR.glob("*.json"))

    # Act
    items = scenario.load_all([SCENARIO_DIR])

    # Assert
    assert len(items) == len(paths)
    assert 10 <= len(items) <= 15
    assert len({item["tc"] for item in items}) in (2, 3)
    assert {"FREECAD_BUDDY_SCRIPT_EXEC": "0"} in [item["launch"] for item in items]
    assert any(item["cross"] for item in items)
    assert any("pixel" in item for item in items)
    assert any("probe" in item for item in items)
    assert any(check for item in items for check in item["expect"])


def test_Should_name_a_heading_of_its_test_case_When_a_pilot_scenario_is_read():
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
        "title": "t",
        "launch": {},
        "verdict": verdict,
        "capture": "a.png",
        "reasons": [],
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
    code = run.main([str(SCENARIO_DIR / "tc-02-02.json"), "--out", str(out)])

    # Assert
    written = json.loads((out / "results.json").read_text("utf-8"))
    summary_text = (out / "summary.md").read_text("utf-8")
    assert code == expected_code
    assert written["scenarios"] == records
    assert set(written["run"]) >= {"git_commit", "git_dirty", "freecad_exe", "started", "errors"}
    assert written["run"]["errors"] == (
        [f"group 0 (default): {group_error}"] if group_error else []
    )
    assert ("## Run errors" in summary_text) is bool(group_error)


def test_Should_escape_pipes_and_newlines_When_titles_and_reasons_hold_them():
    # Arrange
    results = [_record("FAIL", title="a | b\nc", reasons=["x | y\nz"])]

    # Act
    text = run.summary(results)

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
        ({"FREECAD_EXE": "Z:/no/freecad.exe"}, "is not a file"),
        ({"which": None}, "is not on PATH"),
        ({"status": "Cua Driver daemon is not running"}, "daemon is not running"),
    ],
    ids=["no freecad.exe", "no cua-driver", "daemon down"],
)
def test_Should_refuse_When_a_tool_the_run_needs_is_missing(monkeypatch, tmp_path, change, message):
    # Arrange
    exe = tmp_path / "freecad.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(launch, "FREECAD_EXE", change.get("FREECAD_EXE", str(exe)))
    monkeypatch.setattr(launch.shutil, "which", lambda name: change.get("which", "cua-driver.exe"))
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


def test_Should_exit_2_without_a_traceback_When_tasklist_fails(tmp_path, capsys, monkeypatch):
    # Arrange
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "tasklist")

    monkeypatch.setattr(launch, "check_tools", lambda: None)
    monkeypatch.setattr(launch.subprocess, "run", fail)

    # Act
    code = run.main([str(SCENARIO_DIR / "tc-02-02.json"), "--out", str(tmp_path / "out")])

    # Assert
    assert code == 2
    assert "cannot list processes with tasklist" in capsys.readouterr().out


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
    monkeypatch.setattr(launch, "START_TIMEOUT_S", 0.2)
    monkeypatch.setattr(launch, "POLL_S", 0.05)

    # Act
    act = lambda: launch.wait_until_ready(_FakeProcess())  # noqa: E731

    # Assert
    with pytest.raises(launch.LaunchError, match="no /healthz naming it"):
        act()


def test_Should_end_only_its_own_process_When_it_stops_freecad(monkeypatch, tmp_path):
    # Arrange
    def no_other_process(*args, **kwargs):
        raise AssertionError("stop must not start or end another process")

    monkeypatch.setattr(launch.subprocess, "run", no_other_process)
    monkeypatch.setattr(launch.subprocess, "Popen", no_other_process)
    monkeypatch.setattr(launch, "discovery_file", lambda pid: tmp_path / "gone.json")
    monkeypatch.setattr(launch, "port_held", lambda port=launch.PROXY_PORT: False)
    process = _FakeProcess()

    # Act
    launch.stop(process)

    # Assert
    assert process.killed == 1


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
