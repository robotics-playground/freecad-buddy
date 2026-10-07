"""Measure the freecad-buddy load of Claude Code build sessions from their transcripts.

Reads Claude Code session transcripts (``*.jsonl``) and prints one line per session. Every session
is measured with the same rules:

- a FreeCAD call is a ``tool_result`` joined by ``tool_use_id`` to a ``mcp__freecad-buddy__*``
  ``tool_use``; ``previews`` counts the ``preview_dry_run`` calls among them;
- output chars are the text the agent received: only ``text`` items count, so an image content
  block in a ``tool_result`` counts 0 chars;
- a spilled result is one Claude Code saved to a file and replaced by a stub, in either form:
  ``Error: result (N characters) ... saved to <f>.txt`` or ``<persisted-output>`` +
  ``Output too large (39.9KB). Full output saved to: <f>.txt``; it counts its stub in output chars,
  and ``spilled`` counts those stubs;
- ``largest`` is the largest result. An ``Error: result`` stub has the size it states. A
  ``<persisted-output>`` stub has the char length of its spill file, or, when the file is absent,
  its stated size (KB x 1024, MB x 1024 squared);
- ``peak`` is the largest ``input_tokens + cache_read_input_tokens + cache_creation_input_tokens``
  of an assistant ``message.usage``;
- ``compactions`` counts ``system`` records with ``subtype: compact_boundary``; the
  ``isCompactSummary`` user record that follows a boundary is not counted again;
- a feature is an ``OK`` result of a ``feature_*`` tool other than ``feature_set_parameters``; its
  calls are every FreeCAD call after the previous feature, up to and including itself. The first
  feature has no previous feature, so it only starts the count. The status of a spilled result is
  read from its spill file; a missing spill file gives no status.

Sidechain records (``isSidechain: true``) belong to subagents and are skipped. ``:<max results>``
stops reading the transcript at its Nth FreeCAD result, so peak and compactions cover the same
span as the calls.

Run from the uv env::

    uv run python scripts/automation/session_metrics.py <transcript.jsonl>[:<max results>] ...
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from replay_result_sizes import _SPILL, _argument

_TOOL_PREFIX = "mcp__freecad-buddy__"
_PREVIEW = "preview_dry_run"
_FEATURE_PREFIX = "feature_"
_NOT_A_FEATURE = "feature_set_parameters"
_USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_PERSISTED = re.compile(
    r"<persisted-output>\s*Output too large \(([\d.]+)(KB|MB)\)\. Full output saved to: (\S+?\.txt)"
)
_UNIT_BYTES = {"KB": 1024, "MB": 1024**2}


@dataclass(frozen=True)
class SessionMetrics:
    session: str
    calls: int
    previews: int
    output_chars: int
    spilled: int
    largest: int
    peak_context: int
    compactions: int
    calls_per_feature: tuple[int, ...]

    @property
    def chars_per_call(self) -> float:
        return self.output_chars / self.calls if self.calls else 0.0

    @property
    def calls_per_feature_median(self) -> float | None:
        return statistics.median(self.calls_per_feature) if self.calls_per_feature else None


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    return "".join(item.get("text", "") for item in content or [] if isinstance(item, dict))


def _spill(text: str) -> tuple[Path, int] | None:
    """Return the spill file and the result size of a spill stub, or ``None`` for a plain result."""
    stub = _SPILL.match(text)
    if stub:
        return Path(stub.group(2)), int(stub.group(1).replace(",", ""))
    stub = _PERSISTED.match(text)
    if not stub:
        return None
    spill_file = Path(stub.group(3))
    if spill_file.is_file():
        return spill_file, len(spill_file.read_text(encoding="utf-8"))
    return spill_file, round(float(stub.group(1)) * _UNIT_BYTES[stub.group(2)])


def _status(text: str) -> str | None:
    spilled = _spill(text)
    if spilled:
        spill_file = spilled[0]
        if not spill_file.is_file():
            return None
        text = spill_file.read_text(encoding="utf-8")
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError:
        return None
    return envelope.get("status") if isinstance(envelope, dict) else None


def _is_feature(tool: str, text: str) -> bool:
    return tool.startswith(_FEATURE_PREFIX) and tool != _NOT_A_FEATURE and _status(text) == "OK"


def _peak(record: dict) -> int:
    usage = (record.get("message") or {}).get("usage") or {}
    return sum(usage.get(key) or 0 for key in _USAGE_KEYS)


def measure(path: Path, limit: int | None) -> SessionMetrics:
    """Measure the transcript up to its ``limit``-th FreeCAD result (all of it when ``None``)."""
    tool_names: dict[str, str] = {}
    calls = previews = output_chars = spilled = largest = peak = compactions = 0
    calls_per_feature: list[int] = []
    previous_feature: int | None = None
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if limit is not None and calls >= limit:
                break
            record = json.loads(line)
            if record.get("isSidechain"):
                continue
            if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
                compactions += 1
            if record.get("type") == "assistant":
                peak = max(peak, _peak(record))
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if limit is not None and calls >= limit:
                    break
                if item.get("type") == "tool_use":
                    tool_names[item["id"]] = item["name"]
                    continue
                name = tool_names.get(item.get("tool_use_id"), "")
                if item.get("type") != "tool_result" or not name.startswith(_TOOL_PREFIX):
                    continue
                tool = name[len(_TOOL_PREFIX) :]
                text = _text(item.get("content"))
                stub = _spill(text)
                calls += 1
                previews += tool == _PREVIEW
                output_chars += len(text)
                spilled += stub is not None
                largest = max(largest, stub[1] if stub else len(text))
                if _is_feature(tool, text):
                    if previous_feature is not None:
                        calls_per_feature.append(calls - previous_feature)
                    previous_feature = calls
    return SessionMetrics(
        path.stem[:8],
        calls,
        previews,
        output_chars,
        spilled,
        largest,
        peak,
        compactions,
        tuple(calls_per_feature),
    )


def _line(metrics: SessionMetrics) -> str:
    median = metrics.calls_per_feature_median
    return (
        f"{metrics.session}: {metrics.calls} calls, {metrics.previews} previews, "
        f"{metrics.chars_per_call:,.0f} chars per call ({metrics.output_chars:,} total), "
        f"{metrics.spilled} spilled, largest {metrics.largest:,}, peak {metrics.peak_context:,}, "
        f"{metrics.compactions} compactions, "
        f"calls per feature median {median if median is not None else 'n/a'} "
        f"over {len(metrics.calls_per_feature)} features"
    )


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for spec in argv:
        print(_line(measure(*_argument(spec))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
