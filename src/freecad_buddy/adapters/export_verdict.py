"""Verdict assembly for the mesh export verifiers.

``assemble_export_verdict`` merges the independent oracle legs (trimesh, second STL oracle,
lib3mf) with the FreeCAD self-read facts into one ``ResultEnvelope``. Any leg failing, OR any
cross-oracle disagreement on a shared property, forces the verdict to FAIL — disagreement is
signal, never averaged. The verdict is DERIVED from the merged checks via ``derive_verdict``.
The banner is passed in from the marshaled self-read leg so this module needs no FreeCAD import.
"""

from __future__ import annotations

from freecad_buddy.contracts import ResultEnvelope, derive_verdict, mirror_text


def _self_read_checks(self_read_facts: dict) -> list[dict]:
    """Return the checks comparing the FreeCAD self-read facts against the recorded mesh facts.

    The self-read facet/vertex counts must equal the written mesh's recorded counts (same
    tessellation source). This is necessary but not sufficient — FreeCAD's reader is lenient —
    so it is one leg among the independent oracles, never the sole verdict.
    """
    self_read = self_read_facts["self_read"]
    recorded = self_read_facts["recorded"]
    if not self_read.get("readable", True):
        return [
            {
                "id": "self_read.readable",
                "measured": self_read.get("error", "unreadable"),
                "passed": False,
                "detail": {"message": "FreeCAD could not re-read the exported file"},
            }
        ]
    facets_ok = self_read["facets"] == recorded["facets"]
    vertices_ok = self_read["vertices"] == recorded["vertices"]
    return [
        {
            "id": "self_read.facet_count",
            "measured": self_read["facets"],
            "expected": recorded["facets"],
            "passed": facets_ok,
            "detail": {"message": f"facets {self_read['facets']} vs {recorded['facets']}"},
        },
        {
            "id": "self_read.vertex_count",
            "measured": self_read["vertices"],
            "expected": recorded["vertices"],
            "passed": vertices_ok,
            "detail": {"message": f"vertices {self_read['vertices']} vs {recorded['vertices']}"},
        },
    ]


def _disagreement_check(oracle_legs: list[dict]) -> dict:
    """Return a check that fails when the oracles disagree on overall pass/fail.

    Each oracle reports a single ``ok`` verdict; if any two oracles disagree the meshes are not
    unambiguously sound, so the merged verdict must FAIL even if one oracle passed.
    """
    verdicts = {leg["oracle"]: bool(leg["ok"]) for leg in oracle_legs}
    values = set(verdicts.values())
    agree = len(values) <= 1
    return {
        "id": "oracle.agreement",
        "measured": verdicts,
        "passed": agree,
        "detail": {"message": "oracles disagree" if not agree else "oracles agree"},
    }


def assemble_export_verdict(
    oracle_legs: list[dict], self_read_facts: dict, banner: dict
) -> ResultEnvelope:
    """Merge oracle legs and the self-read facts into one verdict envelope.

    Flattens every oracle's per-check results, appends the self-read count comparison and a
    cross-oracle agreement check, derives the verdict, and wraps it with ``banner``. Any failed
    leg check or an oracle disagreement drives the verdict to a non-OK status.
    """
    checks: list[dict] = []
    for leg in oracle_legs:
        checks.extend(leg["checks"])
    checks.extend(_self_read_checks(self_read_facts))
    checks.append(_disagreement_check(oracle_legs))

    report = {
        "schema": "fcb.validation-report/1",
        "subject": {"path": self_read_facts.get("path")},
        "checks": checks,
        "banner": banner,
        "volume_band": self_read_facts.get("volume_band"),
        "tess": self_read_facts.get("tess"),
    }
    report["verdict"] = derive_verdict(report)
    verdict = report["verdict"]
    return {
        "schema": "fcb.result-envelope/1",
        "status": verdict,
        "detail": None if verdict == "OK" else _failure_detail(report),
        "structured_content": report,
        "text": mirror_text(report),
    }


def _failure_detail(report: dict) -> dict:
    """Build the envelope ``ErrorDetail`` from the report's failed checks."""
    failed = [c for c in report.get("checks", []) if not c.get("passed")]
    ids = [c.get("id") for c in failed]
    return {
        "code": report["verdict"],
        "message": "; ".join(str(i) for i in ids) or report["verdict"],
        "objects": [],
    }
