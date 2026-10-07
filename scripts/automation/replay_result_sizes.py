"""Replay recorded freecad-buddy tool results through the shipped result projection.

Reads Claude Code session transcripts (``*.jsonl``), collects every ``mcp__freecad-buddy__*`` tool
result, and measures its text before and after the ``fcb.mutation/2`` / ``fcb.geometry-diff/2``
projection. A result Claude Code spilled to a file is read from that file. Each recorded mutation
block goes through ``result_projection.project_mutation``, each preview diff gets the ``{tool}``
op and the projected audit and its text from ``summarize_preview``, and every envelope is written
through ``mcp_server._to_call_result``, so the numbers measure the code that ships.

A recorded result whose text is not valid JSON (Claude Code cut it and kept no spill file, or the
client refused the call before it reached the server) cannot be projected. It is excluded from the
totals and named in the report.

Records written before ``MassProps.inertia`` existed lack it, and the strict comparison then
lists every object as changed. The replay alone fills a missing ``inertia`` with the same
placeholder on both sides, so those objects compare on the other four invariants. Limit: a
recorded object whose only change was a rotation about its centre of mass is not listed.

Run from the uv env::

    uv run python scripts/automation/replay_result_sizes.py <transcript.jsonl>[:<max results>] ...

``:<max results>`` keeps only the first N freecad-buddy results of that transcript.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from freecad_buddy.adapters.mcp_server import _to_call_result
from freecad_buddy.usecases.preview import summarize_preview
from freecad_buddy.usecases.result_projection import project_mutation, wire_audit

_TOOL_PREFIX = "mcp__freecad-buddy__"
_SPILL = re.compile(r"Error: result \(([\d,]+) characters\).*?saved to (\S+?\.txt)", re.S)
_LARGE = 10_000
_INERTIA_PLACEHOLDER = [0.0] * 6


@dataclass
class Result:
    session: str
    index: int
    tool: str
    text: str


def _argument(spec: str) -> tuple[Path, int | None]:
    """Split ``path[:max]``; a drive-letter colon is part of the path."""
    head, sep, tail = spec.rpartition(":")
    if sep and tail.isdigit():
        return Path(head), int(tail)
    return Path(spec), None


def _result_text(content: object) -> str:
    if isinstance(content, str):
        text = content
    else:
        text = "".join(item.get("text", "") for item in content or [] if isinstance(item, dict))
    spilled = _SPILL.match(text)
    if spilled:
        return Path(spilled.group(2)).read_text(encoding="utf-8")
    return text


def load(path: Path, limit: int | None) -> list[Result]:
    """Return the transcript's freecad-buddy results in order, the first ``limit`` of them."""
    tool_names: dict[str, str] = {}
    results: list[Result] = []
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            record = json.loads(line)
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") == "tool_use":
                    tool_names[item["id"]] = item["name"]
                elif item.get("type") == "tool_result":
                    name = tool_names.get(item.get("tool_use_id"), "")
                    if name.startswith(_TOOL_PREFIX):
                        results.append(
                            Result(
                                path.stem[:8],
                                len(results),
                                name[len(_TOOL_PREFIX) :],
                                _result_text(item.get("content")),
                            )
                        )
    return results[:limit]


def fill_inertia(record: object) -> int:
    """Give each recorded entry lacking ``inertia`` the placeholder; return how many."""
    if not isinstance(record, dict):
        return 0
    filled = 0
    for entry in record.get("objects") or []:
        massprops = entry.get("massprops")
        if isinstance(massprops, dict) and "inertia" not in massprops:
            massprops["inertia"] = list(_INERTIA_PLACEHOLDER)
            filled += 1
    return filled


def project(envelope: dict) -> tuple[dict, int]:
    """Return ``envelope`` with its mutation block or preview diff projected, and the fill count."""
    filled = 0
    structured = envelope.get("structured_content")
    if not isinstance(structured, dict):
        return envelope, filled
    mutation = structured.get("mutation")
    already_projected = isinstance(mutation, dict) and mutation.get("schema") == "fcb.mutation/2"
    if isinstance(mutation, dict) and "post_verify" in mutation and not already_projected:
        filled += fill_inertia(mutation.get("fingerprint_before"))
        filled += fill_inertia(mutation.get("fingerprint_after"))
        structured["mutation"] = project_mutation(mutation)
    diff = structured.get("diff")
    if isinstance(diff, dict):
        diff["schema"] = "fcb.geometry-diff/2"
        if isinstance(diff.get("op"), dict):
            diff["op"] = {"tool": diff["op"].get("tool")}
        if isinstance(diff.get("tnp_precheck"), dict):
            diff["tnp_precheck"] = wire_audit(diff["tnp_precheck"])
        envelope["text"] = summarize_preview(structured)
    return envelope, filled


def _drop(before: int, after: int) -> str:
    return f"{100 * (1 - after / before):.1f} %" if before else "n/a"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    rows: list[tuple[Result, int]] = []
    excluded: list[Result] = []
    filled = 0
    for spec in argv:
        for result in load(*_argument(spec)):
            try:
                envelope = json.loads(result.text)
            except json.JSONDecodeError:
                envelope = None
            if not isinstance(envelope, dict):
                excluded.append(result)
                continue
            projected, count = project(envelope)
            filled += count
            text = _to_call_result(projected).content[0].text
            rows.append((result, len(text)))

    sessions: dict[str, list[int]] = {}
    for result, after in rows:
        totals = sessions.setdefault(result.session, [0, 0, 0, 0])
        totals[0] += 1
        totals[1] += len(result.text)
        totals[2] += after
        totals[3] = max(totals[3], after)
    for session, (count, before, after, largest) in sessions.items():
        print(
            f"{session}: {count} results, before {before:,}, after {after:,}, "
            f"drop {_drop(before, after)}, largest {largest:,}"
        )
    before = sum(len(result.text) for result, _ in rows)
    after = sum(size for _, size in rows)
    print(
        f"total: {len(rows)} results, before {before:,}, after {after:,}, "
        f"drop {_drop(before, after)}"
    )

    large = [(result, size) for result, size in rows if size > _LARGE]
    print(f"over {_LARGE:,} chars after projection: {len(large)}")
    for result, size in large:
        print(f"  {result.session} #{result.index} {result.tool}: {size:,}")

    print(
        f"adapted: {filled:,} recorded object entries had no inertia; the replay gave both sides "
        "the same placeholder, so they compare on volume, area, com and principal moments. "
        "A recorded object whose only change was a rotation is not listed in changed."
    )
    print(f"excluded, not a JSON envelope: {len(excluded)}")
    for result in excluded:
        print(f"  {result.session} #{result.index} {result.tool}: {len(result.text):,} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
