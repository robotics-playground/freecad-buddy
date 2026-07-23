"""The pure four-leg gate verdict function (FreeCAD-free, network-free, contracts-only).

``compute_verdict`` reads ONLY stored files (``reports/<id>.json`` + ``human/*.json`` +
the passed ``validators`` mapping + the exit run's ``dev_rate.json``) and computes the
global-protocol legs:
  (a) every expected criterion's stored report re-derives to ``OK``;
  (b) every cited validator's fault run is current (source-hash match) at >=95% / <=5%;
  (c) held-out exit leg — for a ``verdict.heldout: sealed`` gate every stored exit report banner
      carries ``wilson_ci.r >= 10`` (R>=10 majority-of-R evidence) AND ``dev_rate.json`` is
      present with a dev/held-out pass-rate gap <=15pp; inert for a ``heldout: inert`` gate;
  (d) every required human token is present and run-bound (``hmac.compare_digest``) + PASS.

No stored ``verdict`` field is ever trusted: leg-a re-derives from ``checks`` via
``derive_verdict`` (AD-13). Re-running on identical files reproduces an identical result.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from freecad_buddy.contracts.report import derive_verdict

_SENSITIVITY_BAR = 0.95
_FALSE_ALARM_BAR = 0.05
_MIN_EXIT_R = 10
_MAX_HELDOUT_GAP = 0.15


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


def _subject_label(report: dict) -> str:
    """Human-readable id for a report: the ``case`` key exit reports use, else the criterion."""
    subject = report.get("subject")
    if isinstance(subject, dict):
        for key in ("case", "criterion"):
            value = subject.get(key)
            if isinstance(value, str):
                return value
    return "?"


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


def _heldout_rate(reports: list[dict]) -> float:
    passed = sum(1 for r in reports if derive_verdict(r) == "OK")
    return passed / len(reports) if reports else 0.0


def check_exit_run(run_dir: Path, gate_def: dict, reports: list[dict]) -> list[str]:
    """Return the leg-c failures for a sealed-gate exit run (empty for an inert gate).

    Inert unless the gate declares ``verdict.heldout == "sealed"``. For a sealed gate:
      - every stored exit report banner must carry ``wilson_ci.r >= 10`` (R>=10 majority-of-R
        evidence); a report missing the banner rate is a failure, never vacuous-OK;
      - ``dev_rate.json`` must exist beside ``reports/`` carrying a numeric ``dev_rate``, and the
        gap between it and the held-out pass rate derived from the same reports must be <=15pp.
    Pure over stored files: the held-out rate is re-derived from the reports, never trusted.
    """
    if gate_def.get("verdict", {}).get("heldout") != "sealed":
        return []

    failures: list[str] = []
    for report in reports:
        criterion = _subject_label(report)
        banner = report.get("banner")
        wilson = banner.get("wilson_ci") if isinstance(banner, dict) else None
        r = wilson.get("r") if isinstance(wilson, dict) else None
        if not isinstance(r, int) or isinstance(r, bool):
            failures.append(f"{criterion} report banner missing wilson_ci.r (R>=10 evidence)")
        elif r < _MIN_EXIT_R:
            failures.append(f"{criterion} report banner wilson_ci.r {r} < {_MIN_EXIT_R}")

    dev_rate_path = run_dir / "dev_rate.json"
    if not dev_rate_path.is_file():
        failures.append("dev_rate.json absent (dev/held-out gap unmeasurable)")
        return failures
    try:
        dev_data = json.loads(dev_rate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"dev_rate.json malformed ({exc.__class__.__name__})")
        return failures
    dev_rate = dev_data.get("dev_rate") if isinstance(dev_data, dict) else None
    if not (type(dev_rate) is int or type(dev_rate) is float):
        failures.append(f"dev_rate.json invalid dev_rate: {dev_rate!r}")
        return failures
    # A non-finite (NaN/Infinity, which stdlib json parses) or out-of-[0,1] dev_rate makes the gap
    # comparison meaningless — `NaN > 0.15` is False, laundering a PASS. Reject it as a leg-c FAIL.
    if not math.isfinite(dev_rate) or not (0.0 <= dev_rate <= 1.0):
        failures.append(f"dev_rate.json out-of-range dev_rate: {dev_rate!r}")
        return failures

    # Round to permille so an exact-boundary gap (e.g. 0.95 - 0.80, which floats to
    # 0.15000000000000002) is not spuriously failed — the bound is "<= 15pp".
    gap = round(abs(dev_rate - _heldout_rate(reports)), 3)
    if gap > _MAX_HELDOUT_GAP:
        failures.append(f"dev/held-out gap {gap:.3f} > {_MAX_HELDOUT_GAP}")
    return failures


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

    for failure in check_exit_run(run_dir, gate_def, reports):
        result.failures.append(f"leg-c: {failure}")

    required_tokens = gate_def.get("required_tokens", []) or []
    token_failures = check_token(run_dir, reports, required_tokens)
    for failure in token_failures:
        result.failures.append(f"leg-d: {failure}")

    result.passed = not result.failures
    return result
