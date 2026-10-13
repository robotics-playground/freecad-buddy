"""Scenario files: JSON schema, validation, ``$name`` references and JSON paths.

A scenario encodes the scripted Thens of one ``TC-xx-yy`` scenario; the test-case markdown stays
the human source. Keys::

    id      "TC-02-02", required
    tc      "TC-02", required; the id starts with it
    title   optional text
    launch  optional {"ENV_VAR": "value"}; scenarios with the same map share one FreeCAD
    steps   required list; each step is one of
              {"name": "open", "mcp": "<tool>", "args": {...}}   (name and args optional)
              {"menu": ["View", "Visibility", "Show All Objects"]}  (allow-listed paths only)
    expect  optional list of {"step": <name>, "path": <JSON path>, <op>}; <op> is exactly one of
              "equals": <value> | "approx": <number>, "tolerance": <number> |
              "regex": <pattern> (re.search on a string) | "absent": true
    probe   optional expectation for tests/uat/probe/expect.py, compared with the probe snapshot
            taken after the last step
    cross   optional list of {"mcp": "<step>.<path>", "probe": "<snapshot path>",
            "tolerance": <number>}; a difference is a probe/MCP disagreement
    pixel   optional {"samples": ["<document>.<object>", ...],
                      "extent": {"min_fraction": <number>, "inside": <bool>}}
    agent_check  optional text: a Then the script cannot judge, for example a visual Then that
            needs the GUI Fit All toolbar button. A scenario that has one is never PASS: when
            every scripted check passes it is ESCALATE with this text, for the agent.

A string arg or ``equals`` value may hold ``$name`` or ``$name.<path>`` references: ``name`` is
``PROJECT_ROOT``, ``RUN_DIR`` or an earlier step's name, and ``<path>`` reads that step's
result. A string that is one whole reference takes the referenced value as is (any JSON type).

A JSON path is dot-separated. On a list, a segment selects the item whose ``name`` equals it,
or, when it is a number, the item at that index. Probe snapshot paths read the same way, for
example ``documents.box_10_20_30.objects.Box.shape.volume``.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "probe"))
import expect  # noqa: E402

from capture import MENU_ALLOW_LIST  # noqa: E402

PREDEFINED = ("PROJECT_ROOT", "RUN_DIR")
REFERENCE = re.compile(r"\$([A-Za-z_]\w*)((?:\.[\w-]+)*)")
MISSING = object()

_TOP_KEYS = {
    "id", "tc", "title", "launch", "steps", "expect", "probe", "cross", "pixel", "agent_check"
}  # fmt: skip
_STEP_KEYS = {"name", "mcp", "args", "menu"}
_EXPECT_KEYS = {"step", "path", "equals", "approx", "tolerance", "regex", "absent"}
_EXPECT_OPS = ("equals", "approx", "regex", "absent")
_CROSS_KEYS = {"mcp", "probe", "tolerance"}
_PIXEL_KEYS = {"samples", "extent"}
_EXTENT_KEYS = {"min_fraction", "inside"}
_ID = re.compile(r"TC-\d\d-\d\d")


class ScenarioError(ValueError):
    pass


def resolve(value, path):
    """Read a dot-separated ``path`` from ``value``; ``MISSING`` when any segment is absent."""
    for segment in path.split(".") if path else []:
        if isinstance(value, dict):
            value = value.get(segment, MISSING)
        elif isinstance(value, list):
            named = [
                item for item in value if isinstance(item, dict) and item.get("name") == segment
            ]
            if named:
                value = named[0]
            elif segment.isdigit() and int(segment) < len(value):
                value = value[int(segment)]
            else:
                value = MISSING
        else:
            value = MISSING
        if value is MISSING:
            return MISSING
    return value


def substitute(value, bindings):
    """Replace ``$name`` references in every string of ``value`` (see module docstring)."""
    if isinstance(value, dict):
        return {key: substitute(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, bindings) for item in value]
    if not isinstance(value, str):
        return value

    def lookup(match):
        found = resolve(bindings.get(match.group(1), MISSING), match.group(2).lstrip("."))
        if found is MISSING:
            raise KeyError(f"reference {match.group(0)} has no value")
        return found

    whole = REFERENCE.fullmatch(value)
    if whole:
        return lookup(whole)
    return REFERENCE.sub(lambda match: str(lookup(match)), value)


def _references(value):
    if isinstance(value, dict):
        return [name for item in value.values() for name in _references(item)]
    if isinstance(value, list):
        return [name for item in value for name in _references(item)]
    if isinstance(value, str):
        return [match.group(1) for match in REFERENCE.finditer(value)]
    return []


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require(condition, message):
    if not condition:
        raise ScenarioError(message)


def _unknown(mapping, allowed, where):
    if not isinstance(mapping, dict):
        raise ScenarioError(f"{where} must be an object")
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ScenarioError(f"unknown key {unknown[0]!r} in {where}")


def _validate_steps(steps):
    if not isinstance(steps, list) or not steps:
        raise ScenarioError("key 'steps' must be a non-empty list")
    names = set()
    for index, step in enumerate(steps):
        where = f"steps[{index}]"
        _unknown(step, _STEP_KEYS, where)
        if ("mcp" in step) == ("menu" in step):
            raise ScenarioError(f"{where} needs exactly one of key 'mcp' or key 'menu'")
        if "menu" in step:
            _require(isinstance(step["menu"], list), f"{where} key 'menu' must be a list")
            _require("name" not in step, f"{where} key 'name' is not allowed on a menu step")
            _require(
                tuple(step["menu"]) in MENU_ALLOW_LIST,
                f"{where} key 'menu' {step['menu']} is not in the allow-list",
            )
        for name in _references(step.get("args", {})):
            if name not in PREDEFINED and name not in names:
                raise ScenarioError(f"{where} key 'args' references ${name} before it is named")
        if "name" in step:
            if step["name"] in names or step["name"] in PREDEFINED:
                raise ScenarioError(f"{where} key 'name' {step['name']!r} is not unique")
            names.add(step["name"])
    return names


def _validate_expect(checks, names):
    for index, check in enumerate(checks):
        where = f"expect[{index}]"
        _unknown(check, _EXPECT_KEYS, where)
        ops = [op for op in _EXPECT_OPS if op in check]
        if len(ops) != 1:
            raise ScenarioError(f"{where} needs exactly one of keys {list(_EXPECT_OPS)}")
        if check.get("step") not in names or "path" not in check:
            raise ScenarioError(f"{where} key 'step' must name a step, and key 'path' is required")
        if "approx" in check:
            _require(_is_number(check["approx"]), f"{where} key 'approx' must be a number")
            _require(
                _is_number(check.get("tolerance")),
                f"{where} key 'approx' needs a number 'tolerance'",
            )
        if "absent" in check:
            _require(
                isinstance(check["absent"], bool), f"{where} key 'absent' must be true or false"
            )
        if "regex" in check:
            try:
                re.compile(check["regex"])
            except (re.error, TypeError) as exc:
                raise ScenarioError(f"{where} key 'regex' does not compile: {exc}") from exc
        for name in _references(check.get("equals")):
            if name not in PREDEFINED and name not in names:
                raise ScenarioError(f"{where} key 'equals' references unknown ${name}")


def _validate_cross(entries, names):
    for index, entry in enumerate(entries):
        where = f"cross[{index}]"
        _unknown(entry, _CROSS_KEYS, where)
        _require(
            isinstance(entry.get("mcp"), str) and isinstance(entry.get("probe"), str),
            f"{where} keys 'mcp' and 'probe' must be path strings",
        )
        if "tolerance" in entry:
            _require(_is_number(entry["tolerance"]), f"{where} key 'tolerance' must be a number")
        if entry["mcp"].split(".")[0] not in names:
            raise ScenarioError(f"{where} key 'mcp' must start with a step name")


def _validate_pixel(pixel):
    _unknown(pixel, _PIXEL_KEYS, "pixel")
    extent = pixel.get("extent", {})
    _unknown(extent, _EXTENT_KEYS, "pixel.extent")
    if "min_fraction" in extent:
        _require(
            _is_number(extent["min_fraction"]), "key 'pixel.extent.min_fraction' must be a number"
        )
    if "inside" in extent:
        _require(
            isinstance(extent["inside"], bool), "key 'pixel.extent.inside' must be true or false"
        )
    if "extent" in pixel and not pixel.get("samples"):
        raise ScenarioError("key 'pixel.extent' needs key 'pixel.samples' to seed it")
    for sample in pixel.get("samples", []):
        if not isinstance(sample, str) or sample.count(".") != 1:
            raise ScenarioError(f"pixel sample {sample!r} must be '<document>.<object>'")


def validate(data):
    """Return the scenario with defaults filled in; raise ``ScenarioError`` naming the key."""
    _unknown(data, _TOP_KEYS, "scenario")
    for key in ("id", "tc", "steps"):
        if key not in data:
            raise ScenarioError(f"missing key {key!r}")
    if not _ID.fullmatch(str(data["id"])) or not data["id"].startswith(f"{data['tc']}-"):
        raise ScenarioError(f"key 'id' {data['id']!r} must be TC-xx-yy and start with key 'tc'")
    launch = data.get("launch", {})
    if not isinstance(launch, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in launch.items()
    ):
        raise ScenarioError("key 'launch' must map environment names to strings")
    names = _validate_steps(data["steps"])
    _validate_expect(data.get("expect", []), names)
    _validate_cross(data.get("cross", []), names)
    if "probe" in data:
        try:
            expect.compare({}, data["probe"])
        except ValueError as exc:
            raise ScenarioError(f"key 'probe': {exc}") from exc
    if "pixel" in data:
        _validate_pixel(data["pixel"])
    if "agent_check" in data:
        check = data["agent_check"]
        _require(
            isinstance(check, str) and check.strip(), "key 'agent_check' must be non-empty text"
        )
    return {"title": "", "launch": {}, "expect": [], "cross": [], **data}


def load(path):
    """Read and validate one scenario file; errors name the file."""
    path = Path(path)
    try:
        scenario = validate(json.loads(path.read_text(encoding="utf-8")))
    except (ScenarioError, ValueError, OSError) as exc:
        # ValueError covers a JSON syntax error and a file that is not UTF-8.
        raise ScenarioError(f"{path}: {exc}") from exc
    scenario["file"] = str(path)
    return scenario


def load_all(arguments):
    """Load every scenario named by ``arguments`` (files, or folders of ``*.json``), in order."""
    paths = []
    for argument in map(Path, arguments):
        found = sorted(argument.glob("*.json")) if argument.is_dir() else [argument]
        if not found:
            raise ScenarioError(f"{argument}: no scenario files (*.json) in this folder")
        paths.extend(found)
    scenarios = [load(path) for path in paths]
    seen = set()
    for scenario in scenarios:
        if scenario["id"] in seen:
            raise ScenarioError(f"{scenario['file']}: key 'id' {scenario['id']!r} is not unique")
        seen.add(scenario["id"])
    return scenarios
