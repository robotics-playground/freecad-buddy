"""Measure how Claude Code sessions use the freecad-buddy MCP tools, for a date range.

Reads Claude Code transcripts and prints the tables of
``_bmad-output/specs/spec-mcp-usage-improvement/usage-evidence.md`` (totals, per-tool outcome,
script classes, failure classes, tool loading, ``text`` share). A later run measures the success
signal of ``SPEC.md``. This is a dev tool: the addon does not ship it and ``src/`` never imports it.

Rules:

- a project folder is a directory of ``<session>.jsonl`` transcripts. Each session may hold
  ``<session>/subagents/*.jsonl``; those count as part of the session;
- a call is a ``tool_use`` whose name contains ``freecad-buddy`` (both
  ``mcp__freecad-buddy__*`` and ``mcp__plugin_freecad-buddy_freecad-buddy__*``). It is counted once
  by ``tool_use.id``, because a resumed session repeats lines, and it belongs to the first
  transcript file (in sorted path order) that holds it;
- a call is in range when the UTC date of its ``tool_use`` record is between ``--since`` and
  ``--until``, both inclusive. The report also prints the calls of both boundary days under UTC and
  under a local offset (``--utc-offset-hours``), so a boundary difference is visible;
- the outcome of a call is the ``status`` of the paired ``tool_result`` envelope; for
  ``query_tree_summary`` it is the ``<STATUS>:`` text prefix. A result that Claude Code spilled to a
  file is read from that file; a missing file gives no outcome;
- the ``text`` share is the length of the envelope ``text`` field over the length of the whole
  result (the spill file when the result was spilled);
- a tool is loaded when a ``ToolSearch`` result names it in a ``tool_reference``.

Run from the uv env::

    uv run python scripts/automation/usage_report.py --since 2026-10-18 --until 2026-11-18 \\
        <project folder> [<project folder> ...]

A project folder is a path, or a name under ``~/.claude/projects``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from replay_result_sizes import _SPILL
from session_metrics import _PERSISTED, _text

_TOOL_NAME = re.compile(r"mcp__((?:(?!__).)*freecad-buddy(?:(?!__).)*)__(.+)")
_SCRIPT_TOOL = "script_exec"
_TREE_TOOL = "query_tree_summary"
_TREE_STATUS = re.compile(r"([A-Z][A-Z_]+):")
_PROJECTS_ROOT = Path.home() / ".claude" / "projects"

_MUTATING_CALL = re.compile(
    r"addObject|removeObject|setExpression|addProperty|newObject|addGeometry|addConstraint"
    r"|delGeometry|\.recompute\(|\.save\("
)
_ATTRIBUTE_ASSIGNMENT = re.compile(r"[^#=]*[\w\])]\.\w+\s*(?:[-+*/%|&^]|//|\*\*|<<|>>)?=(?!=)")
_STATEMENT_SEPARATOR = re.compile(r"[;\n]")


def _is_mutating(code: str) -> bool:
    return bool(_MUTATING_CALL.search(code)) or any(
        _ATTRIBUTE_ASSIGNMENT.match(statement) for statement in _STATEMENT_SEPARATOR.split(code)
    )


# Classes of ``script_exec`` code. One script can match several classes.
SCRIPT_CLASSES: dict[str, re.Pattern[str]] = {
    "Bounding box or volume read": re.compile(r"BoundBox|\.Volume\b"),
    "`isValid` check": re.compile(r"isValid\("),
    "Face/edge scan": re.compile(r"\.Faces\b|\.Edges\b"),
    "VarSet, `addProperty`, `setExpression`": re.compile(r"VarSet|addProperty|setExpression"),
    "Property or expression read": re.compile(r"ExpressionEngine|getPropertyByName|PropertiesList"),
    "PartDesign `newObject`/`addObject`": re.compile(
        r"(?:newObject|addObject)\(\s*[\"']PartDesign::"
    ),
    "`exec` of a local helper or generator file": re.compile(
        r"\bexec\(|\bexecfile\(|runpy|sys\.path|importlib"
    ),
    "Interference: `common` volume, `distToShape`": re.compile(r"\.common\(|distToShape"),
    "Part primitives and booleans": re.compile(
        r"Part\.make\w+|Part\.(?:Box|Cylinder|Sphere|Cone)\b|\.(?:fuse|cut)\("
    ),
    "Slice or section": re.compile(r"\.slice\(|\.section\(|\.slices\("),
    "Sketch geometry/constraints in script": re.compile(r"addGeometry|addConstraint"),
    "Placement or `AttachmentOffset` write": re.compile(
        r"\.(?:Placement|AttachmentOffset)\s*=[^=]"
    ),
    "`removeObject`": re.compile(r"removeObject"),
    "`json.dump` of measured data to disk": re.compile(r"json\.dump"),
    "`Label` rename": re.compile(r"\.Label\s*=[^=]"),
    "Loft, sweep, helix, thickness": re.compile(
        r"makeLoft|makeSweep|makeHelix|makeThickness|makePipe"
        r"|(?:Part|PartDesign)::(?:(?:Additive|Subtractive)?(?:Loft|Pipe|Helix)|Sweep|Thickness)"
    ),
    "`App::Link` or clone": re.compile(r"App::Link|makeLink|Clone"),
}


@dataclass(frozen=True)
class FailureClass:
    """A class of failed results. A call joins it when every given condition holds."""

    name: str
    tool: str | None = None
    status: str | None = None
    message: re.Pattern[str] | None = None

    def matches(self, call: Call) -> bool:
        return (
            (self.tool is None or call.tool == self.tool)
            and (self.status is None or call.status == self.status)
            and (self.message is None or bool(self.message.search(call.message)))
        )


FAILURE_CLASSES = (
    FailureClass(
        "`script_exec` timeout", "script_exec", message=re.compile(r"marshaled call timed out")
    ),
    FailureClass("Python error reported as `RECOMPUTE_ERROR`", "script_exec", "RECOMPUTE_ERROR"),
    FailureClass(
        "Multi-object export refused", message=re.compile(r"export supports a single object")
    ),
    FailureClass("`verify_shape` input rejected", "verify_shape", "INVALID_INPUT"),
    FailureClass("TNP audit flag on a typed mutation", message=re.compile(r"TNP audit flagged")),
    FailureClass("Stale document handle", message=re.compile(r"unknown or stale document handle")),
    FailureClass("Document-suspect refusal after timeout", message=re.compile(r"document-suspect")),
    FailureClass(
        "`feature_set_parameters` cannot write",
        "feature_set_parameters",
        message=re.compile(r"cannot write"),
    ),
)
_UNCLASSIFIED = "Not OK, no class above (includes calls with no outcome)"


@dataclass
class Call:
    server: str
    tool: str
    timestamp: datetime
    session: str
    source: Path
    code: str | None
    result_size: int = 0
    status: str | None = None
    message: str = ""
    envelope_text_size: int = 0


@dataclass
class Transcript:
    path: Path
    session: str
    loaded_tools: list[tuple[date, list[str]]] = field(default_factory=list)


@dataclass
class Report:
    since: date
    until: date
    calls: list[Call]
    transcripts: list[Transcript]
    typed_tool_names: list[str]
    boundary_counts: dict[str, tuple[int, int]]


@dataclass
class _Scan:
    """State shared by every transcript file of one run.

    A resumed session repeats the lines of an earlier file, so a call is owned by the first file
    that holds it, and its result can sit in any later file.
    """

    seen: set[str] = field(default_factory=set)
    pending: dict[str, Call] = field(default_factory=dict)
    searches: dict[str, tuple[Transcript, date]] = field(default_factory=dict)
    # Results read before their tool_use, because that sits in a file that sorts later.
    orphan_results: dict[str, object] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)


def _resolve(folder: str) -> Path:
    path = Path(folder)
    if path.is_dir():
        return path
    if (_PROJECTS_ROOT / folder).is_dir():
        return _PROJECTS_ROOT / folder
    raise FileNotFoundError(f"no project folder: {folder}")


def _transcript_files(folder: Path) -> list[tuple[Path, str]]:
    files = [(path, path.stem) for path in folder.glob("*.jsonl")]
    for path in folder.glob("*/subagents/*.jsonl"):
        files.append((path, path.parent.parent.name))
    return sorted(files)


def _timestamp(record: dict) -> datetime | None:
    raw = record.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_spill(text: str) -> str | None:
    """Return the full text of a spilled result, or ``None`` when the file is gone."""
    stub = _SPILL.match(text) or _PERSISTED.match(text)
    if not stub:
        return text
    spill_file = Path(stub.group(2) if _SPILL.match(text) else stub.group(3))
    if not spill_file.is_file():
        return None
    return spill_file.read_text(encoding="utf-8")


def _first_text(content: object) -> str:
    if isinstance(content, str):
        return content
    for item in content or []:
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text", "")
    return ""


def _apply_result(call: Call, content: object) -> None:
    joined = _text(content)
    full = _read_spill(joined)
    call.result_size = len(full) if full is not None else len(joined)
    first = _first_text(content)
    body = _read_spill(first) if full is not None else None
    if call.tool == _TREE_TOOL:
        text = body if body is not None else first
        match = _TREE_STATUS.match(text)
        call.status = match.group(1) if match else None
        call.message = text
        return
    try:
        envelope = json.loads(body) if body is not None else None
    except json.JSONDecodeError:
        envelope = None
    if not isinstance(envelope, dict):
        return
    call.status = envelope.get("status")
    detail = envelope.get("detail") or {}
    call.message = str(detail.get("message", "")) if isinstance(detail, dict) else ""
    call.envelope_text_size = len(envelope.get("text") or "")


def _read_transcript(path: Path, session: str, scan: _Scan) -> Transcript:
    transcript = Transcript(path, session)
    known_ids: set[str] = set()
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # Claude Code may still be writing the last line of a live session.
                continue
            # A blob repeats the whole request, including earlier tool calls, and has no timestamp.
            if record.get("type") == "api-request-blob":
                continue
            content = (record.get("message") or {}).get("content")
            moment = _timestamp(record)
            if not isinstance(content, list) or moment is None:
                continue
            for item in content:
                if item.get("type") == "tool_use":
                    known_ids.add(item["id"])
                    _read_tool_use(item, moment, transcript, scan)
                elif item.get("type") == "tool_result":
                    _read_tool_result(item, known_ids, scan)
    return transcript


def _read_tool_use(item: dict, moment: datetime, transcript: Transcript, scan: _Scan) -> None:
    if item["id"] in scan.seen:
        return
    if item["name"] == "ToolSearch":
        scan.seen.add(item["id"])
        scan.searches[item["id"]] = (transcript, moment.astimezone(timezone.utc).date())
        if item["id"] in scan.orphan_results:
            _read_tool_result(
                {"tool_use_id": item["id"], "content": scan.orphan_results.pop(item["id"])},
                {item["id"]},
                scan,
            )
        return
    match = _TOOL_NAME.fullmatch(item["name"])
    if not match:
        return
    scan.seen.add(item["id"])
    code = (item.get("input") or {}).get("code")
    call = Call(
        match.group(1),
        match.group(2),
        moment,
        transcript.session,
        transcript.path,
        code if isinstance(code, str) else None,
    )
    scan.calls.append(call)
    if item["id"] in scan.orphan_results:
        _apply_result(call, scan.orphan_results.pop(item["id"]))
    else:
        scan.pending[item["id"]] = call


def _read_tool_result(item: dict, known_ids: set[str], scan: _Scan) -> None:
    call_id = item["tool_use_id"]
    if call_id in scan.pending:
        _apply_result(scan.pending.pop(call_id), item.get("content"))
    elif call_id in scan.searches:
        transcript, day = scan.searches.pop(call_id)
        names = _loaded_tools(item.get("content"))
        if names:
            transcript.loaded_tools.append((day, names))
    elif call_id not in known_ids:
        scan.orphan_results[call_id] = item.get("content")


def _loaded_tools(content: object) -> list[str]:
    names = []
    for item in content if isinstance(content, list) else []:
        if isinstance(item, dict) and item.get("type") == "tool_reference":
            match = _TOOL_NAME.fullmatch(item.get("tool_name", ""))
            if match:
                names.append(match.group(2))
    return names


def _typed_tool_names() -> list[str]:
    from freecad_buddy.hosts.tool_catalog import tool_specs

    return sorted(spec.name for spec in tool_specs() if spec.name != _SCRIPT_TOOL)


def build_report(
    folders: list[str], since: date, until: date, utc_offset_hours: float = 7.0
) -> Report:
    scan = _Scan()
    transcripts: list[Transcript] = []
    for folder in folders:
        for path, session in _transcript_files(_resolve(folder)):
            transcripts.append(_read_transcript(path, session, scan))
    every_call = scan.calls
    local = timedelta(hours=utc_offset_hours)
    boundary_counts = {
        str(day): (
            sum(call.timestamp.astimezone(timezone.utc).date() == day for call in every_call),
            sum(
                (call.timestamp.astimezone(timezone.utc) + local).date() == day
                for call in every_call
            ),
        )
        for day in (since, until)
    }
    in_range = [
        call
        for call in every_call
        if since <= call.timestamp.astimezone(timezone.utc).date() <= until
    ]
    return Report(since, until, in_range, transcripts, _typed_tool_names(), boundary_counts)


def _family(tool: str) -> str:
    return "script" if tool == _SCRIPT_TOOL else tool.split("_", 1)[0]


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def _share(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def _scripts(report: Report) -> list[Call]:
    return [call for call in report.calls if call.tool == _SCRIPT_TOOL and call.code is not None]


def _totals(report: Report) -> list[str]:
    calls = report.calls
    scripts = [call for call in report.calls if call.tool == _SCRIPT_TOOL]
    read_only = sum(not _is_mutating(call.code or "") for call in scripts)
    sizes = [len((call.code or "").splitlines()) for call in scripts]
    sessions = {call.session for call in calls}
    families = Counter(_family(call.tool) for call in calls)
    servers = Counter(call.server for call in calls)
    lines = [
        "## Totals",
        "",
        "- Servers: "
        + (", ".join(f"`{name}` {count}" for name, count in servers.most_common()) or "none")
        + ".",
        f"- {len(calls):,} calls in {len(sessions)} sessions "
        f"({len({call.source for call in calls})} transcript files with subagents) "
        f"between {report.since} and {report.until}.",
        f"- `script_exec`: {len(scripts)} calls = {_share(len(scripts), len(calls))}. "
        f"Read-only {read_only} ({_share(read_only, len(calls))} of calls), "
        f"mutating {len(scripts) - read_only}.",
    ]
    if sizes:
        lines.append(
            f"- Script size: median {statistics.median(sizes):g} lines, "
            f"p90 {_percentile(sizes, 0.9)}, max {max(sizes)}."
        )
    lines.append(
        "- Calls by family: "
        + ", ".join(f"`{name}` {count}" for name, count in families.most_common())
        + "."
    )
    boundary = "; ".join(
        f"{day}: {utc} by UTC, {local} by local offset"
        for day, (utc, local) in report.boundary_counts.items()
    )
    lines.append(f"- Calls on the boundary days (all transcripts): {boundary}.")
    return lines


def _outcome_table(report: Report) -> list[str]:
    by_tool: dict[str, list[Call]] = defaultdict(list)
    for call in report.calls:
        by_tool[call.tool].append(call)
    rows = [
        "## Per-tool outcome",
        "",
        "| Tool | Calls | OK | Not OK |",
        "|------|------:|---:|--------|",
    ]
    for tool, calls in sorted(by_tool.items(), key=lambda pair: -len(pair[1])):
        statuses = Counter(call.status or "no status" for call in calls)
        ok = statuses.pop("OK", 0)
        not_ok = ", ".join(f"{status} {count}" for status, count in statuses.most_common()) or "—"
        rows.append(f"| `{tool}` | {len(calls)} | {ok} | {not_ok} |")
    unused = [name for name in report.typed_tool_names if name not in by_tool]
    rows += [
        "",
        f"Typed tools with **0 calls** in scope (catalog of the installed source): "
        f"{', '.join(f'`{n}`' for n in unused) or 'none'}.",
    ]
    return rows


def _script_class_table(report: Report) -> list[str]:
    scripts = _scripts(report)
    rows = ["## What `script_exec` does", "", "| Class | Scripts |", "|-------|--------:|"]
    counts = {
        name: sum(bool(pattern.search(call.code or "")) for call in scripts)
        for name, pattern in SCRIPT_CLASSES.items()
    }
    for name, count in sorted(counts.items(), key=lambda pair: -pair[1]):
        rows.append(f"| {name} | {count} |")
    return rows


def _failure_class(call: Call) -> list[str]:
    return [failure_class.name for failure_class in FAILURE_CLASSES if failure_class.matches(call)]


def _failure_table(report: Report) -> list[str]:
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for call in report.calls:
        if call.status == "OK":
            continue
        for name in _failure_class(call) or [_UNCLASSIFIED]:
            counts[name] += 1
            readable = " ".join(call.message.split()).replace("|", "\\|").replace("`", "'")
            examples.setdefault(name, readable[:80])
    rows = [
        "## Failure classes",
        "",
        "| Class | Count | Example message |",
        "|-------|------:|-----------------|",
    ]
    for name, count in counts.most_common():
        rows.append(f"| {name} | {count} | `{examples[name]}` |")
    return rows


def _loading_table(report: Report) -> list[str]:
    first: Counter[str] = Counter()
    ever: Counter[str] = Counter()
    loading = 0
    for transcript in report.transcripts:
        batches = [
            names for day, names in transcript.loaded_tools if report.since <= day <= report.until
        ]
        if not batches:
            continue
        loading += 1
        first.update(set(batches[0]))
        ever.update({name for batch in batches for name in batch})
    rows = [
        "## Tool loading",
        "",
        f"{loading} transcripts load freecad-buddy tools.",
        "",
        "| Tool | In first `ToolSearch` batch | Ever loaded |",
        "|------|----------------------------:|------------:|",
    ]
    for name, count in sorted(ever.items(), key=lambda pair: (-pair[1], pair[0])):
        rows.append(f"| `{name}` | {first[name]} | {count} |")
    return rows


def _text_share_table(report: Report) -> list[str]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for call in report.calls:
        if call.status is None:
            continue
        for key in (call.tool, "All freecad-buddy tools"):
            totals[key][0] += 1
            totals[key][1] += call.result_size
            totals[key][2] += call.envelope_text_size
    rows = [
        "## Duplicated tokens in results",
        "",
        "| Tool | Results | Result chars | `text` field chars | Share |",
        "|------|--------:|-------------:|-------------------:|------:|",
    ]
    overall = totals.pop("All freecad-buddy tools", [0, 0, 0])
    ranked = sorted(totals.items(), key=lambda pair: -pair[1][2])[:3]
    for name, (count, size, text) in [*ranked, ("All freecad-buddy tools", overall)]:
        rows.append(f"| `{name}` | {count:,} | {size:,} | {text:,} | {_share(text, size)} |")
    return rows


def render(report: Report) -> str:
    sections = [
        _totals(report),
        _outcome_table(report),
        _script_class_table(report),
        _failure_table(report),
        _loading_table(report),
        _text_share_table(report),
    ]
    return "\n\n".join("\n".join(section) for section in sections) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since", type=date.fromisoformat, required=True)
    parser.add_argument("--until", type=date.fromisoformat, required=True)
    parser.add_argument("--utc-offset-hours", type=float, default=7.0)
    parser.add_argument(
        "folders", nargs="+", help="project folder: a path or a name under ~/.claude/projects"
    )
    arguments = parser.parse_args(argv)
    if arguments.since > arguments.until:
        parser.error("--since is after --until")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        report = build_report(
            arguments.folders, arguments.since, arguments.until, arguments.utc_offset_hours
        )
    except FileNotFoundError as error:
        parser.error(str(error))
    sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
