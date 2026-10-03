"""In-FreeCAD fault scorer for ``verify_shape``.

Run under FreeCADCmd with the scoring opt-in set, so that importing this module for its parsing
helpers never starts a scoring run::

    FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd score_verify_shape.py
    $env:FREECAD_BUDDY_RUN_FAULT_SCORER="1"; FreeCADCmd score_verify_shape.py

For every ``case.yaml`` in this suite: open the paired ``fixture.FCStd``, run ``verify_shape``
with the case's reference ``assertions.checks`` against the fixture's object, and record the
DETECT / PASS_CLEAN outcome. A planted ``DETECT`` case is detected when the verdict is
non-OK; a ``clean_control`` is a false alarm when the verdict is non-OK. Computes
``sensitivity``/``false_alarm`` + a Wilson CI, hashes the validator source
(``usecases/verify.py`` + ``usecases/fingerprint.py`` + ``usecases/assertions.py``) into
``validator_sha``, and rewrites ONLY
the ``verify_shape`` block of ``_registry/validators.yaml`` via the shared
``merge_validators_yaml`` read-merge-write (preserving the ``verify_export_*`` blocks and the file
header). Prints a per-case detection table to stderr and exits non-zero when the bars are not met.

pyyaml is an external-process dependency (AD-12); this scorer runs inside FreeCADCmd and so
parses the small fixed ``case.yaml`` shape itself.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# The export scorer owns the shared read-merge-write for validators.yaml; import it by path so
# both scorers write through one merge-writer and neither full-clobbers the other's blocks.
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import verify  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"
VALIDATOR_SOURCES = (
    SRC / "freecad_buddy" / "usecases" / "verify.py",
    SRC / "freecad_buddy" / "usecases" / "fingerprint.py",
    SRC / "freecad_buddy" / "usecases" / "assertions.py",
)

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05

# Seed header used only when validators.yaml does not yet exist; merge_validators_yaml preserves
# an existing file's header verbatim.
_HEADER = (
    "# Per-validator fault-suite binding (validation-harness-design.md §6).\n"
    "# A score is citable only while validator_sha matches the working tree "
    "(edit the validator to stale it).\n"
)


def _parse_scalar(text: str):
    """Parse a YAML flow scalar (int/float/bool/list/string) as used in the fixed check shape."""
    text = text.strip()
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text.startswith("[") and text.endswith("]"):
        return [_parse_scalar(part) for part in _split_top_level(text[1:-1]) if part.strip()]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text.strip("'\"")


def _split_top_level(body: str) -> list[str]:
    """Split a flow-mapping body on top-level commas (commas outside brackets/braces)."""
    parts = []
    depth = 0
    current = []
    for char in body:
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _iter_flow_mappings(text: str) -> list[str]:
    """Extract each top-level ``{...}`` block's inner body from the ``assertions.checks:`` region.

    Scans ``text`` after the ``assertions.checks:`` line, tracking brace ``{``/``}`` and bracket
    ``[``/``]`` depth while ignoring bracket chars inside single- or double-quoted runs and after a
    depth-zero ``#`` comment. A block starts when depth goes 0->1 on ``{`` and ends when depth
    returns to 0; the accumulated body between (exclusive of) the outer braces is returned. Returns
    the inner bodies in order. Raises ``ValueError`` when no ``checks:`` region exists or a block is
    left unterminated (malformed case shape).
    """
    checks_line = re.search(r"^\s*checks:\s*$", text, re.MULTILINE)
    if checks_line is None:
        raise ValueError("no 'checks:' region found in case.yaml")
    scope = text[checks_line.end() :]

    blocks: list[str] = []
    depth = 0
    quote = ""
    comment = False
    current: list[str] = []
    for char in scope:
        if comment:
            if char == "\n":
                comment = False
            continue
        if quote:
            if char == quote:
                quote = ""
            if depth > 0:
                current.append(char)
            continue
        if depth == 0 and char == "#":
            comment = True
            continue
        if char in "'\"":
            quote = char
            if depth > 0:
                current.append(char)
            continue
        if char in "{[":
            if char == "{" and depth == 0:
                current = []
            else:
                current.append(char)
            depth += 1
            continue
        if char in "}]":
            depth -= 1
            if char == "}" and depth == 0:
                blocks.append("".join(current))
            else:
                current.append(char)
            continue
        if depth > 0:
            current.append(char)
    if depth != 0 or quote:
        raise ValueError("unterminated flow mapping in case.yaml checks")
    return blocks


def _parse_check(flow: str) -> dict:
    """Parse a ``{fn: ..., expect: ..., tol: {...}}`` flow mapping into a check dict."""
    check: dict = {}
    for part in _split_top_level(flow):
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "tol":
            value = value.strip()
            if not (value.startswith("{") and value.endswith("}")):
                raise ValueError(f"malformed tol value: {value!r}")
            inner = value[1:-1]
            check["tol"] = {
                k.strip(): _parse_scalar(v)
                for k, _, v in (p.partition(":") for p in _split_top_level(inner))
                if k.strip()
            }
        else:
            check[key] = _parse_scalar(value)
    return check


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed ``case.yaml`` shape: id, expectation, and the flow ``checks`` list."""
    text = case_yaml.read_text(encoding="utf-8")
    case_id = re.search(r"^id:\s*(\S+)", text, re.MULTILINE).group(1)
    expectation = re.search(r"expectation:\s*(\S+)", text).group(1)
    checks = [_parse_check(flow) for flow in _iter_flow_mappings(text)]
    return {"id": case_id, "expectation": expectation, "checks": checks, "dir": case_yaml.parent}


def _validator_sha() -> str:
    """SHA-256 over the concatenated validator source files."""
    hasher = hashlib.sha256()
    for path in VALIDATOR_SOURCES:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _score_case(registry: DocumentRegistry, case: dict) -> tuple[bool, str]:
    """Run ``verify_shape`` on the case fixture; return ``(non_ok, verdict)``."""
    fixture = case["dir"] / "fixture.FCStd"
    handle = registry.document_open(str(fixture))["structured_content"]["doc"]
    try:
        object_name = registry.with_document(handle, lambda _h, d: d.Objects[0].Name)
        envelope = verify.verify_shape(
            registry, doc=handle, object=object_name, checks=case["checks"]
        )
        verdict = envelope["structured_content"]["verdict"]
        return verdict != "OK", verdict
    finally:
        registry.document_close(handle)


def _render_block(sha: str, run: dict) -> str:
    """Render the ``verify_shape`` validators.yaml block (merged via ``merge_validators_yaml``)."""
    wilson = run["wilson_ci"]
    return (
        "verify_shape:\n"
        "  suite: g0/fault-injection/\n"
        f'  validator_sha: "{sha}"\n'
        "  last_run:\n"
        f"    run_id: {run['run_id']}\n"
        f"    sensitivity: {run['sensitivity']}\n"
        f"    false_alarm: {run['false_alarm']}\n"
        f"    date: {run['date']}\n"
        "    wilson_ci:\n"
        f"      rate: {wilson['rate']}\n"
        f"      low: {wilson['low']}\n"
        f"      high: {wilson['high']}\n"
        f"      n: {wilson['n']}\n"
        f"      r: {wilson['r']}\n"
    )


def score() -> dict:
    """Run ``verify_shape`` over the committed suite; return the aggregate scoring result.

    The returned dict carries ``rows`` (per-case ``(id, expectation, verdict, outcome)``),
    ``sensitivity``, ``false_alarm``, ``wilson_ci``, and the planted/control counts. No file is
    written — ``main`` persists the result to ``validators.yaml``.
    """
    from freecad_buddy.usecases import stats

    registry = DocumentRegistry()
    cases = [_load_case(p) for p in sorted(HERE.rglob("case.yaml"))]

    planted = [c for c in cases if c["expectation"] == "DETECT"]
    controls = [c for c in cases if c["expectation"] == "PASS_CLEAN"]

    detected = 0
    flagged = 0
    rows = []
    for case in cases:
        non_ok, verdict = _score_case(registry, case)
        is_defect = case["expectation"] == "DETECT"
        if is_defect and non_ok:
            detected += 1
            outcome = "DETECTED"
        elif is_defect and not non_ok:
            outcome = "MISSED"
        elif not is_defect and non_ok:
            flagged += 1
            outcome = "FALSE_ALARM"
        else:
            outcome = "PASS_CLEAN"
        rows.append((case["id"], case["expectation"], verdict, outcome))

    return {
        "rows": rows,
        "planted": len(planted),
        "controls": len(controls),
        "detected": detected,
        "flagged": flagged,
        "sensitivity": stats.sensitivity(detected, len(planted)),
        "false_alarm": stats.false_alarm(flagged, len(controls)),
        "wilson_ci": stats.wilson_ci(detected, len(planted)),
    }


def main() -> int:
    result = score()
    rows = result["rows"]
    sensitivity = result["sensitivity"]
    false_alarm = result["false_alarm"]
    wilson = result["wilson_ci"]
    planted = result["planted"]
    controls = result["controls"]
    detected = result["detected"]
    flagged = result["flagged"]

    for case_id, expectation, verdict, outcome in rows:
        sys.stderr.write(f"  {case_id:42s} {expectation:11s} {verdict:16s} {outcome}\n")
    sys.stderr.write(
        f"\n  planted={planted} detected={detected} sensitivity={sensitivity:.3f}\n"
        f"  controls={controls} flagged={flagged} false_alarm={false_alarm:.3f}\n"
        f"  wilson_ci=[{wilson['low']:.3f}, {wilson['high']:.3f}]\n"
    )

    run = {
        "run_id": f"fr-{datetime.date.today().isoformat()}-1",
        "sensitivity": round(sensitivity, 4),
        "false_alarm": round(false_alarm, 4),
        "date": datetime.date.today().isoformat(),
        "wilson_ci": {
            "rate": round(wilson["rate"], 4),
            "low": round(wilson["low"], 4),
            "high": round(wilson["high"], 4),
            "n": wilson["n"],
            "r": wilson["r"],
        },
    }
    existing = VALIDATORS_YAML.read_text(encoding="utf-8") if VALIDATORS_YAML.exists() else _HEADER
    merged = merge_validators_yaml(existing, {"verify_shape": _render_block(_validator_sha(), run)})
    VALIDATORS_YAML.write_text(merged, encoding="utf-8")
    sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")

    if sensitivity < SENSITIVITY_BAR or false_alarm > FALSE_ALARM_BAR:
        sys.stderr.write("  BARS NOT MET: sensitivity<0.95 or false_alarm>0.05\n")
        return 1
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_FAULT_SCORER"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit scoring-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether direct execution or an explicit opt-in asked for a scoring run.

    An import never scores: ``__name__`` is the module name and the flag is absent.
    """
    return __name__ == "__main__" or _run_requested_in(os.environ)


if _run_requested():
    sys.exit(main())
