"""The pure four-leg gate verdict function (FreeCAD-free, network-free, contracts-only).

``compute_verdict`` reads ONLY stored files (``reports/<id>.json`` + ``human/*.json`` +
the passed ``validators`` mapping) and computes the global-protocol legs:
  (a) every expected criterion's stored report re-derives to ``OK``;
  (b) every cited validator's fault run is current (source-hash match) at >=95% / <=5%;
  (c) exit/held-out legs — inert for G0's non-actor gate;
  (d) every required human token is present and run-bound (``hmac.compare_digest``) + PASS.

No stored ``verdict`` field is ever trusted: leg-a re-derives from ``checks`` via
``derive_verdict`` (AD-13). Re-running on identical files reproduces an identical result.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path

from freecad_buddy.contracts.report import derive_verdict

_SENSITIVITY_BAR = 0.95
_FALSE_ALARM_BAR = 0.05


class ArtifactError(Exception):
    """A stored artifact is missing/malformed — surfaced by the runner as an exit-2 error."""


@dataclass
class VerdictResult:
    passed: bool
    per_criterion: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def bind_hash(reports: list[dict]) -> str:
    """Canonical SHA-256 over the run's report set: sorted by criterion id, then concatenated.

    Each report is serialized with ``json.dumps(..., sort_keys=True)``; ``attest`` and
    ``verdict`` produce identical bytes for an unmodified run so the token binding is stable.
    """
    ordered = sorted(reports, key=lambda r: _criterion_of(r))
    joined = "".join(json.dumps(report, sort_keys=True) for report in ordered)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _criterion_of(report: dict) -> str:
    subject = report.get("subject")
    if isinstance(subject, dict):
        criterion = subject.get("criterion")
        if isinstance(criterion, str):
            return criterion
    return ""


def load_reports(run_dir: Path, expected_ids: list[str]) -> list[dict]:
    """Read only ``reports/<id>.json`` for each expected criterion id, in ``expected_ids`` order.

    Orphan/stray files under ``reports/`` are ignored (neither ride the bind set nor force an
    error). A missing, unparseable, non-mapping, or empty/non-list-``checks`` report raises
    ``ArtifactError`` (exit-2) — an empty-checks stored report is malformed, never vacuous-OK.
    """
    reports_dir = run_dir / "reports"
    loaded: list[dict] = []
    for criterion_id in expected_ids:
        path = reports_dir / f"{criterion_id}.json"
        if not path.is_file():
            raise ArtifactError(f"missing report: reports/{criterion_id}.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactError(
                f"malformed report reports/{criterion_id}.json ({exc.__class__.__name__})"
            ) from exc
        if not isinstance(data, dict):
            raise ArtifactError(f"malformed report reports/{criterion_id}.json: not a mapping")
        checks = data.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ArtifactError(
                f"malformed report reports/{criterion_id}.json: empty/non-list checks"
            )
        loaded.append(data)
    return loaded


def check_validator_currency(gate_def: dict, validators: dict, hasher) -> list[str]:
    """Return the names of every stale or below-bar cited validator (leg-b failures).

    A validator is current iff its ``validator_sha`` matches a freshly computed hash of its
    source AND ``last_run.sensitivity >= 0.95`` AND ``last_run.false_alarm <= 0.05``. A boolean
    sensitivity/false_alarm is REJECTED (``type(x) is int or type(x) is float`` — ``isinstance``
    would accept ``True``).
    """
    cited: list[str] = []
    for criterion in gate_def.get("criteria", []):
        for name in criterion.get("cited_validators", []) or []:
            if name not in cited:
                cited.append(name)

    failures: list[str] = []
    for name in cited:
        entry = validators.get(name)
        if not isinstance(entry, dict):
            failures.append(f"{name} (not in registry)")
            continue
        if entry.get("validator_sha") != hasher(name):
            failures.append(f"{name} (stale: source hash mismatch)")
            continue
        last_run = entry.get("last_run")
        if not isinstance(last_run, dict):
            failures.append(f"{name} (no current fault run)")
            continue
        sensitivity = last_run.get("sensitivity")
        false_alarm = last_run.get("false_alarm")
        if not (type(sensitivity) is int or type(sensitivity) is float):
            failures.append(f"{name} (invalid sensitivity: {sensitivity!r})")
            continue
        if not (type(false_alarm) is int or type(false_alarm) is float):
            failures.append(f"{name} (invalid false_alarm: {false_alarm!r})")
            continue
        if sensitivity < _SENSITIVITY_BAR:
            failures.append(f"{name} (sensitivity {sensitivity} < {_SENSITIVITY_BAR})")
        elif false_alarm > _FALSE_ALARM_BAR:
            failures.append(f"{name} (false_alarm {false_alarm} > {_FALSE_ALARM_BAR})")
    return failures


def check_token(run_dir: Path, reports: list[dict], required_tokens: list[str]) -> list[str]:
    """Return a failure string for each required token type not satisfied (leg-d).

    A token type is accepted iff ANY ``human/*.json`` of that type is bound to this run
    (``binds_reports_sha256`` matches ``bind_hash(reports)`` via ``hmac.compare_digest``) AND
    ``outcome == "PASS"``. It never lets an earlier-by-filename stale/FAIL token shadow a valid
    bound-PASS one — every matching token is examined, not just ``matching[0]``.
    """
    expected_hash = bind_hash(reports)
    human_dir = run_dir / "human"
    tokens: list[dict] = []
    if human_dir.is_dir():
        for path in sorted(human_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                tokens.append(data)

    failures: list[str] = []
    for token_type in required_tokens:
        matching = [t for t in tokens if t.get("token_type") == token_type]
        if not matching:
            failures.append(f"{token_type} token absent")
            continue
        bound_pass = any(
            _token_bound(t, expected_hash) and t.get("outcome") == "PASS" for t in matching
        )
        if bound_pass:
            continue
        if any(t.get("outcome") == "FAIL" for t in matching):
            failures.append(f"{token_type} outcome FAIL — run invalidated")
        else:
            failures.append(f"{token_type} token not bound to this run")
    return failures


def _token_bound(token: dict, expected_hash: str) -> bool:
    stored = token.get("binds_reports_sha256")
    if not isinstance(stored, str):
        return False
    return hmac.compare_digest(stored, expected_hash)


def compute_verdict(run_dir: Path, gate_def: dict, validators: dict, hasher) -> VerdictResult:
    """Compose legs a/b/d (c inert for G0) into a ``VerdictResult`` — pure over stored files.

    Leg-a resolves each expected criterion to its ``reports/<id>.json`` (matched by filename
    id, carried in ``expected_ids`` order), verifies the body's ``subject.criterion == id``
    (a mismatch is a leg-a FAIL, never a ``{}``->OK fallback), and RE-DERIVES the verdict from
    ``checks`` via ``derive_verdict`` — the stored ``verdict`` field is never read.
    """
    expected_ids = [
        c["id"] for c in gate_def.get("criteria", []) if isinstance(c, dict) and "id" in c
    ]
    reports = load_reports(run_dir, expected_ids)

    result = VerdictResult(passed=True)
    for criterion_id, report in zip(expected_ids, reports):
        subject_id = _criterion_of(report)
        if subject_id != criterion_id:
            result.per_criterion[criterion_id] = "FAIL"
            result.failures.append(
                f"leg-a: {criterion_id} report subject mismatch (subject.criterion={subject_id!r})"
            )
            continue
        verdict = derive_verdict(report)
        if verdict == "OK":
            result.per_criterion[criterion_id] = "PASS"
        else:
            result.per_criterion[criterion_id] = "FAIL"
            result.failures.append(f"leg-a: {criterion_id} verdict {verdict} (not OK)")

    stale = check_validator_currency(gate_def, validators, hasher)
    for name in stale:
        result.failures.append(f"leg-b: validator {name}")

    required_tokens = gate_def.get("required_tokens", []) or []
    token_failures = check_token(run_dir, reports, required_tokens)
    for failure in token_failures:
        result.failures.append(f"leg-d: {failure}")

    result.passed = not result.failures
    return result
