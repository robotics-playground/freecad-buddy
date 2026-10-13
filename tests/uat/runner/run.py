"""Scripted UAT runner: run scenario files against a FreeCAD it starts, with no LLM call.

    uv run python tests/uat/runner/run.py <scenario files or folders...> --out <run dir>

Every scenario is validated before anything starts; an invalid one stops the run with exit 2.
Preflight refuses (exit 2) when ``FREECAD_EXE`` or the ``cua-driver`` daemon is missing, another
FreeCAD runs or ``:8765`` is held. Scenarios are grouped by their ``launch`` map, one FreeCAD per
group; each launch repeats the FreeCAD and ``:8765`` check. Per scenario: close every open
document, run the steps over the ``:8765`` MCP proxy, take a probe snapshot and a window capture,
then judge the
``expect``, ``probe``, ``cross`` and ``pixel`` checks.

Verdicts: ``PASS`` only when every check passes and a capture exists. ``FAIL`` when a check
fails. ``ESCALATE`` when the probe and MCP disagree, a step or the probe raised, the capture is
missing, or the scenario names an ``agent_check`` the script cannot judge. A disagreement is
reported, never retried. Every non-``PASS`` scenario is in the escalation queue with its
reasons, for the agent and its ``cua-driver`` ladder.

Writes ``<run dir>/results.json`` (``run`` metadata and ``scenarios``), ``<run dir>/summary.md``
and ``<run dir>/captures/<id>.png``. Exit codes: 0 every scenario ran and none is ``FAIL``; 1 a
scenario is ``FAIL``; 2 the run was refused before any launch; 3 a launch group failed to launch
or to tear down (its scenarios not run, or ``:8765`` left held). 3 wins over 1.
"""

import argparse
import contextlib
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import capture
import launch
import mcp_client
import pixel
import png
import scenario as scenario_file
from scenario import MISSING, resolve, substitute

import expect  # tests/uat/probe; ``scenario`` puts that folder on sys.path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CROSS_TOLERANCE = 1e-6
PASS, FAIL, ESCALATE = "PASS", "FAIL", "ESCALATE"
MENU_EFFECT_TIMEOUT_S = 5.0
POLL_S = 0.25


class MenuError(Exception):
    pass


def _active_shapes_shown(snapshot):
    document = resolve(snapshot, f"documents.{snapshot['active_document']}")
    return document is not MISSING and all(
        obj["visibility"] for obj in document["objects"] if obj["shape"] is not None
    )


# invoke_menu delivers through the foreground and reports its effect as unverifiable, so a
# window that takes the focus at that moment drops the command without an error. The probe
# confirms the effect; a menu path with no entry here is not confirmed.
MENU_EFFECTS = {("View", "Visibility", "Show All Objects"): _active_shapes_shown}


class LiveSession:
    """One launched FreeCAD: MCP calls, allow-listed menu commands, probe and captures."""

    def __init__(self, process, probe_record, client):
        self.pid = process.pid
        self.probe_record = probe_record
        self.client = client
        self.window_id = capture.main_window(self.pid)["window_id"]
        capture.set_frame(self.pid, self.window_id)
        self.info = {
            "freecad_pid": self.pid,
            "freecad_version": self.snapshot()["freecad_version"],
            "addon": launch.addon_info(probe_record["user_app_data"]),
        }

    def call(self, tool, args):
        return self.client.call(tool, args)

    def menu(self, path):
        capture.invoke_menu(self.pid, self.window_id, path)
        effect = MENU_EFFECTS.get(tuple(path))
        deadline = time.monotonic() + MENU_EFFECT_TIMEOUT_S
        while effect is not None and not effect(self.snapshot()):
            if time.monotonic() > deadline:
                raise MenuError(
                    f"menu {list(path)} had no effect in {MENU_EFFECT_TIMEOUT_S:.0f} s; "
                    "FreeCAD may not have had the foreground"
                )
            time.sleep(POLL_S)

    def snapshot(self):
        return launch.get_snapshot(self.probe_record)

    def capture(self, out_file):
        return capture.capture(self.pid, self.window_id, out_file)

    def reset(self):
        """Close every open document, so a scenario starts from an empty session."""
        listed = self.client.call("document_list", {})
        for entry in listed["structured_content"]["documents"]:
            self.client.call("document_close", {"doc": entry["doc"]})


@contextlib.contextmanager
def live_session(launch_env, audit_log):
    with launch.freecad(launch_env, audit_log) as (process, probe_record):
        with mcp_client.McpClient() as client:
            session = LiveSession(process, probe_record, client)
            try:
                yield session
            finally:
                # Closing the documents before the kill lets FreeCAD remove their transient
                # folders, so the next FreeCAD start offers no document recovery. A FreeCAD that
                # already died cannot answer; the kill that follows still runs.
                with contextlib.suppress(Exception):
                    session.reset()


def _json(value):
    return "<absent>" if value is MISSING else json.dumps(value, ensure_ascii=False)


def _finding(kind, field, expected, observed):
    return {
        "kind": kind,
        "field": field,
        "expected": None if expected is MISSING else expected,
        "observed": None if observed is MISSING else observed,
        "reason": f"{kind} {field}: expected {_json(expected)}, observed {_json(observed)}",
    }


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def agree(first, second, tolerance):
    if _is_number(first) and _is_number(second):
        return abs(first - second) <= tolerance
    if isinstance(first, list) and isinstance(second, list):
        return len(first) == len(second) and all(
            agree(a, b, tolerance) for a, b in zip(first, second)
        )
    return first == second


def check_expect(check, bindings):
    """Return a finding, or ``None`` when the check passes."""
    observed = resolve(bindings[check["step"]], check["path"])
    field = f"{check['step']}.{check['path']}"
    if "absent" in check:
        expected = "<absent>" if check["absent"] else "<present>"
        passed = (observed is MISSING) == check["absent"]
    elif "equals" in check:
        try:
            expected = substitute(check["equals"], bindings)
        except KeyError as exc:
            return _finding("expect", field, f"unresolved: {exc}", observed)
        passed = observed == expected
    elif "approx" in check:
        expected = f"{check['approx']} +/- {check['tolerance']}"
        passed = _is_number(observed) and abs(observed - check["approx"]) <= check["tolerance"]
    else:
        expected = f"regex {check['regex']}"
        passed = isinstance(observed, str) and re.search(check["regex"], observed) is not None
    return None if passed else _finding("expect", field, expected, observed)


def check_cross(entry, bindings, snapshot):
    """Return ``(finding, disagreement)``; at most one is not ``None``."""
    mcp_value = resolve(bindings, entry["mcp"])
    probe_value = resolve(snapshot, entry["probe"])
    field = f"{entry['mcp']} vs probe {entry['probe']}"
    if mcp_value is MISSING or probe_value is MISSING:
        return _finding(
            "cross", field, "both values present", [_json(mcp_value), _json(probe_value)]
        ), None
    if agree(mcp_value, probe_value, entry.get("tolerance", DEFAULT_CROSS_TOLERANCE)):
        return None, None
    return None, {
        "mcp": entry["mcp"],
        "mcp_value": mcp_value,
        "probe": entry["probe"],
        "probe_value": probe_value,
        "reason": f"probe/MCP disagreement: MCP {entry['mcp']} = {_json(mcp_value)}, "
        f"probe {entry['probe']} = {_json(probe_value)}",
    }


def check_pixel(config, snapshot, image, window):
    """Return ``(measurement, findings)`` for the scenario's ``pixel`` block."""
    view = snapshot.get("view")
    if view is None:
        return None, [_finding("pixel", "view", "a 3D view", None)]
    # A clipped, hidden or minimized view puts non-render pixels inside the rectangle.
    if view.get("clipped") is not False:
        return None, [_finding("pixel", "view.clipped", False, view.get("clipped"))]
    box = pixel.Placement(window, image).box(view["rect"])
    if not pixel.inside_capture(box, image):
        observed = f"view rect outside capture: {list(box)} in {image.width}x{image.height}"
        return None, [_finding("pixel", "view.rect", "inside the capture", observed)]
    centers = {}
    for sample in config.get("samples", []):
        document, obj = sample.split(".")
        center = resolve(snapshot, f"documents.{document}.objects.{obj}.screen_center")
        centers[sample] = None if center is MISSING else center
    measured = pixel.measure(image, window, view["rect"], centers)
    findings = [
        _finding("pixel", f"samples.{name}", "geometry at screen_center", sample)
        for name, sample in measured["samples"].items()
        if not sample["geometry"]
    ]
    wanted = config.get("extent")
    extent = measured["extent"]
    if wanted is not None and extent is None:
        findings.append(_finding("pixel", "extent", "model under a sample", None))
    elif wanted is not None:
        if extent["fraction"] < wanted.get("min_fraction", 0):
            findings.append(
                _finding(
                    "pixel", "extent.fraction", f">= {wanted['min_fraction']}", extent["fraction"]
                )
            )
        if "inside" in wanted and extent["touches_edge"] == wanted["inside"]:
            findings.append(
                _finding(
                    "pixel", "extent.touches_edge", not wanted["inside"], extent["touches_edge"]
                )
            )
    return measured, findings


def golden_path(item):
    return Path(item["file"]).with_suffix(".golden.png")


def verdict_of(record):
    if record["disagreements"] or record["errors"]:
        return ESCALATE
    if record["findings"]:
        return FAIL
    if record["capture"] is None or record["agent_check"]:
        return ESCALATE
    return PASS


def _run_steps(item, session, bindings, record):
    for step in item["steps"]:
        if "menu" in step:
            session.menu(step["menu"])
            record["steps"].append({"menu": step["menu"]})
            continue
        args = substitute(step.get("args", {}), bindings)
        result = session.call(step["mcp"], args)
        if "name" in step:
            bindings[step["name"]] = result
        record["steps"].append(
            {"name": step.get("name"), "mcp": step["mcp"], "args": args, "result": result}
        )


def _identity(item):
    return {key: item[key] for key in ("id", "tc", "title", "file", "launch")}


def _judge(item, bindings, snapshot, image, window, record):
    """Add the findings and disagreements of every check to ``record``."""
    for check in item["expect"]:
        finding = check_expect(check, bindings)
        if finding:
            record["findings"].append(finding)
    if "probe" in item:
        for mismatch in expect.compare(snapshot, item["probe"]):
            record["findings"].append(
                _finding("probe", mismatch["field"], mismatch["expected"], mismatch["observed"])
            )
    for entry in item["cross"]:
        finding, disagreement = check_cross(entry, bindings, snapshot)
        if finding:
            record["findings"].append(finding)
        if disagreement:
            record["disagreements"].append(disagreement)
    if "pixel" in item and image is not None:
        record["pixel"], findings = check_pixel(item["pixel"], snapshot, image, window)
        record["findings"].extend(findings)


def _golden(item, snapshot, image, window):
    golden = golden_path(item)
    if image is None or not golden.exists() or not (snapshot and snapshot.get("view")):
        return None
    box = pixel.Placement(window, image).box(snapshot["view"]["rect"])
    if not pixel.inside_capture(box, image):
        return {"file": str(golden), "error": "view rect outside capture"}
    return {"file": str(golden)} | pixel.golden_difference(image, png.read(golden), box)


def run_scenario(item, session, run_dir):
    """Run one scenario in an open session; return its result record."""
    record = _identity(item) | {
        "steps": [],
        "findings": [],
        "disagreements": [],
        "errors": [],
        "capture": None,
        "agent_check": item.get("agent_check"),
    }
    bindings = {"PROJECT_ROOT": REPO_ROOT.as_posix(), "RUN_DIR": run_dir.as_posix()}
    try:
        session.reset()
        _run_steps(item, session, bindings, record)
    except Exception as exc:
        record["errors"].append(f"step {len(record['steps'])} raised {type(exc).__name__}: {exc}")

    snapshot = None
    try:
        snapshot = session.snapshot()
    except Exception as exc:
        record["errors"].append(f"probe snapshot raised {type(exc).__name__}: {exc}")
    record["probe_snapshot"] = snapshot

    capture_file = run_dir / "captures" / f"{item['id']}.png"
    capture_file.parent.mkdir(parents=True, exist_ok=True)
    # A capture left by an earlier run into the same folder must never be judged.
    capture_file.unlink(missing_ok=True)
    image = window = None
    try:
        window = session.capture(capture_file)
        image = png.read(capture_file)
        record["capture"] = str(capture_file)
    except Exception as exc:
        record["capture_error"] = f"{type(exc).__name__}: {exc}"

    record["golden"] = None
    try:
        if not record["errors"]:
            _judge(item, bindings, snapshot, image, window, record)
        record["golden"] = _golden(item, snapshot, image, window)
    except Exception as exc:
        record["errors"].append(f"checks raised {type(exc).__name__}: {exc}")
    record["verdict"] = verdict_of(record)
    record["reasons"] = (
        record["errors"]
        + [d["reason"] for d in record["disagreements"]]
        + [f["reason"] for f in record["findings"]]
        + ([f"no capture: {record.get('capture_error')}"] if record["capture"] is None else [])
        + ([f"agent check: {record['agent_check']}"] if record["agent_check"] else [])
    )
    return record


def run(scenarios, run_dir, open_session=live_session):
    """Run every scenario, one session per launch group.

    Returns ``(records, groups)``: the result records in scenario order, and per group its
    ``launch`` map, scenario ids, the session ``info`` and ``error``. ``error`` names the stage
    that raised: ``launch`` (its scenarios not run) or ``teardown`` (all ran; FreeCAD or
    ``:8765`` may be left behind).
    """
    results, groups = {}, []
    for index, (launch_env, members) in enumerate(launch.group_by_launch(scenarios)):
        group = {"launch": launch_env, "scenarios": [m["id"] for m in members], "error": None}
        groups.append(group)
        try:
            with open_session(launch_env, run_dir / f"audit-group-{index}.jsonl") as session:
                group.update(getattr(session, "info", {}))
                for item in members:
                    results[item["id"]] = run_scenario(item, session, run_dir)
        except Exception as exc:
            stage = "teardown" if all(m["id"] in results for m in members) else "launch"
            group["error"] = f"{stage} raised {type(exc).__name__}: {exc}"
            for item in members:
                results.setdefault(item["id"], _not_run(item, exc))
    return [results[item["id"]] for item in scenarios], groups


def _not_run(item, exc):
    reason = f"not run: launch group raised {type(exc).__name__}: {exc}"
    return _identity(item) | {
        "verdict": ESCALATE,
        "not_run": True,
        "reasons": [reason],
        "errors": [reason],
        "capture": None,
    }


def _launch_text(launch_env):
    return " ".join(f"{k}={v}" for k, v in launch_env.items()) or "default"


def _cell(text):
    """``text`` safe inside a Markdown table cell or list item."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def group_errors(groups):
    return [
        f"group {index} ({_launch_text(group['launch'])}): {group['error']}"
        for index, group in enumerate(groups)
        if group["error"]
    ]


def summary(results, errors=()):
    counts = {v: sum(r["verdict"] == v for r in results) for v in (PASS, FAIL, ESCALATE)}
    lines = [
        "# Scripted UAT run",
        "",
        f"{len(results)} scenarios: {counts[PASS]} PASS, {counts[FAIL]} FAIL, "
        f"{counts[ESCALATE]} ESCALATE.",
        "",
        "| Scenario | Title | Launch | Verdict | Capture |",
        "|----------|-------|--------|---------|---------|",
    ]
    for r in results:
        cells = [r["id"], r["title"], _launch_text(r["launch"]), r["verdict"], r["capture"] or "-"]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    if errors:
        lines += ["", "## Run errors", ""] + [f"- {_cell(error)}" for error in errors]
    lines += ["", "## Escalation queue", ""]
    queue = [r for r in results if r["verdict"] != PASS]
    if not queue:
        lines.append("Empty: every scenario passed.")
    for r in queue:
        lines += [f"### {r['id']}: {r['verdict']}", ""]
        lines += [f"- {_cell(reason)}" for reason in r["reasons"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenarios", nargs="+", help="scenario files or folders of *.json")
    parser.add_argument("--out", required=True, type=Path, help="run folder for the results")
    args = parser.parse_args(argv)
    try:
        scenarios = scenario_file.load_all(args.scenarios)
    except scenario_file.ScenarioError as exc:
        print(f"invalid scenario: {exc}")
        return 2
    try:
        launch.preflight()
    except launch.LaunchError as exc:
        print(f"preflight refused: {exc}")
        return 2
    run_dir = args.out.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    started = _now()
    results, groups = run(scenarios, run_dir)
    errors = group_errors(groups)
    metadata = run_metadata(groups, errors, started, _now())
    (run_dir / "results.json").write_text(
        json.dumps({"run": metadata, "scenarios": results}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    text = summary(results, errors)
    (run_dir / "summary.md").write_text(text, encoding="utf-8")
    # Only ASCII lines: MCP messages in the reasons may not encode on a cp1252 console.
    print(text.splitlines()[2])
    print(f"run errors: {len(errors)}")
    print(f"summary: {run_dir / 'summary.md'}")
    if errors:
        return 3
    return 1 if any(r["verdict"] == FAIL for r in results) else 0


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _git(*args):
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_metadata(groups, errors, started, ended):
    """What was tested: the commit, the addon FreeCAD loaded, the FreeCAD build, the times.

    The runner tests the installed addon (``Mod/FreeCADBuddy``), not the working tree; ``addon``
    says whether its package links back to a source folder.
    """
    launched = next((group for group in groups if "freecad_version" in group), {})
    status = _git("status", "--porcelain")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
        "freecad_exe": launch.FREECAD_EXE,
        "freecad_version": launched.get("freecad_version"),
        "addon": launched.get("addon"),
        "started": started,
        "ended": ended,
        "groups": groups,
        "errors": errors,
    }


if __name__ == "__main__":
    sys.exit(main())
