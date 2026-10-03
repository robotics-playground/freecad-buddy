"""Provenance gate: every ``benchmarks/**`` artifact has a valid manifest.

Recursively walks ``benchmarks/**`` for artifact files (``*.FCStd``), excluding ``heldout/``
(sealed), ``_registry/provenance/`` itself, and ``__pycache__``. For each artifact:

  - a provenance manifest under ``_registry/provenance/`` must declare its ``artifact`` id
    (path relative to ``benchmarks/`` without the ``.FCStd`` suffix);
  - the manifest ``source.kind`` must be in the closed set.

Additionally flags:
  - a fault case dir with a ``case.yaml`` but no fixture — ``fixture.FCStd``, or the artifact
    file the case declares itself (``export_file``, ``render_file``);
  - duplicate ``artifact`` ids across manifests (a duplicate must not silently overwrite);
  - an orphan manifest whose ``artifact`` id has no matching ``.FCStd`` on disk;
  - a manifest whose ``source.kind`` is a non-``hand-authored`` closed-set kind but is missing
    a non-empty ``source.url``, ``source.license``, or ``source.attribution``.

A manifest declaring ``kind: part-spec`` or ``kind: fault-case`` binds to a written case rather
than a geometry file, so its artifact id resolves against ``<artifact>.yaml`` (the case file)
instead of ``<artifact>.FCStd``. A Phase 3 spec case declares ``fixture: none-spec-to-part``: the
part is built from the spec text, so there is no input document, and the case is exempt from the
fixture-presence rule.

On any violation: print ``path -- rule`` and exit 1. Clean tree: exit 0.

Importable: ``check_tree(benchmarks_root)`` returns a list[str] of violations (unit-testable).
Runnable: ``python scripts/check_provenance.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

CLOSED_SOURCE_KINDS = frozenset(
    {
        "freecad-parts-library",
        "freecad-wiki-tutorial",
        "hand-authored",
        "hf-verified-permissive",
    }
)

_EXCLUDED_DIRS = frozenset({"heldout", "__pycache__"})
_PROVENANCE_REL = ("_registry", "provenance")


def _artifact_id(fcstd: Path, benchmarks_root: Path) -> str:
    rel = fcstd.relative_to(benchmarks_root).as_posix()
    return rel[: -len(".FCStd")]


def _load_manifests(
    benchmarks_root: Path,
) -> tuple[dict[str, dict], dict[str, Path], list[str]]:
    """Return ({artifact_id: manifest}, {artifact_id: manifest_path}, [violations])."""
    provenance_dir = benchmarks_root.joinpath(*_PROVENANCE_REL)
    manifests: dict[str, dict] = {}
    manifest_paths: dict[str, Path] = {}
    violations: list[str] = []
    if not provenance_dir.is_dir():
        return manifests, manifest_paths, violations

    for manifest_path in sorted(provenance_dir.rglob("*.yaml")):
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            # OSError = unreadable manifest; still a reported violation, never a crash.
            violations.append(f"{manifest_path} -- unreadable manifest ({exc.__class__.__name__})")
            continue
        if not isinstance(data, dict) or "artifact" not in data:
            violations.append(f"{manifest_path} -- manifest missing 'artifact' id")
            continue
        artifact_id = str(data["artifact"])
        if artifact_id in manifests:
            violations.append(f"{manifest_path} -- duplicate artifact id '{artifact_id}'")
            continue
        manifests[artifact_id] = data
        manifest_paths[artifact_id] = manifest_path

    return manifests, manifest_paths, violations


def _iter_artifacts(benchmarks_root: Path):
    provenance_dir = benchmarks_root.joinpath(*_PROVENANCE_REL)
    for fcstd in sorted(benchmarks_root.rglob("*.FCStd")):
        parts = fcstd.relative_to(benchmarks_root).parts
        if any(part in _EXCLUDED_DIRS for part in parts):
            continue
        if provenance_dir in fcstd.parents:
            continue
        yield fcstd


_ARTIFACT_FILE_KEYS = ("export_file", "render_file")


def _declared_artifact_file(case_yaml: Path) -> str | None:
    """Return the artifact file a case declares, or ``None`` for a geometry-fixture case.

    An export-fault case declares ``export_file`` (the written ``.stl``/``.3mf``/``.step``) and a
    render-fault case declares ``render_file`` (the rendered ``.png``). In both the declared file
    IS the fixture — there is no ``.FCStd`` to carry.
    """
    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    for key in _ARTIFACT_FILE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _reuses_an_existing_document(case_yaml: Path) -> bool:
    """Whether a case carries no local fixture because it runs against a committed document.

    A G2 command case names an existing golden model in ``inputs.document`` and mutates it, so
    duplicating that model into the case directory would fork the reference geometry. The
    referenced file must exist: a case pointing at a missing document is still flagged.
    """
    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    if not isinstance(data, dict):
        return False
    document = (data.get("inputs") or {}).get("document")
    if not isinstance(document, str):
        return False
    return (case_yaml.parent / document).is_file()


def _declares_pending_fixture(case_yaml: Path) -> bool:
    """Whether a case explicitly declares ``fixture: pending`` — an entry-gate case.

    An entry gate lands its benchmark BEFORE the runtime that can plant the fixtures (AD-19),
    so a G2 fault case specifies a fault that only becomes buildable once the mutation runtime
    exists. The exemption requires the pending state to be *declared*: a case that simply omits
    its fixture is still flagged, so a forgotten fixture cannot hide behind this.
    """
    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(data, dict) and data.get("fixture") == "pending"


# The fixture state a spec-to-part case declares. Distinct from `pending` (a fixture that does not
# exist yet): a written spec has no input document and never will.
_SPEC_TO_PART_FIXTURE = "none-spec-to-part"

# The manifest kinds that bind to a case file rather than a geometry file.
_CASE_FILE_MANIFEST_KINDS = frozenset({"part-spec", "fault-case"})


def _declares_spec_to_part(case_yaml: Path) -> bool:
    """Whether a case declares that it ships a written spec and no input document.

    The exemption requires the state to be *declared*, matching the ``fixture: pending`` rule: a
    case that simply omits its fixture is still flagged.
    """
    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(data, dict) and data.get("fixture") == _SPEC_TO_PART_FIXTURE


def _is_text_case(case_yaml: Path) -> bool:
    """Whether a case is a text case (a planted answer the grader judges), carrying no fixture.

    A G1 grader fault case declares a ``candidate_answer`` and no geometry — there is no
    ``.FCStd``/exported file to carry, so it is exempt from the fixture-presence rule. The
    exemption is scoped to a case that declares NEITHER a geometry ``fixture`` NOR an
    ``export_file`` NOR an ``expected`` geometry block: a case that declares a fixture is never
    exempted even if a stray ``candidate_answer`` key is also present (a mis-authored geometry
    case must still be flagged for its missing fixture).
    """
    try:
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    if not isinstance(data, dict) or "candidate_answer" not in data:
        return False
    declares_geometry = ("fixture" in data) or ("export_file" in data) or ("expected" in data)
    return not declares_geometry


def _check_missing_fixtures(benchmarks_root: Path) -> list[str]:
    """A case dir with a case.yaml must carry its declared fixture.

    A geometry-fixture case must carry ``fixture.FCStd``; a case that declares its own artifact
    file (an export-fault case's ``export_file``, a render-fault case's ``render_file``) must
    carry that file instead — the written ``.stl``/``.3mf``/``.step``/``.png`` is the fixture and
    there is no ``.FCStd``. A text case (one carrying a ``candidate_answer`` the grader judges)
    has no geometry and is exempt.
    """
    violations: list[str] = []
    for case_yaml in sorted(benchmarks_root.rglob("case.yaml")):
        parts = case_yaml.relative_to(benchmarks_root).parts
        if any(part in _EXCLUDED_DIRS for part in parts):
            continue
        if (
            _is_text_case(case_yaml)
            or _declares_pending_fixture(case_yaml)
            or _declares_spec_to_part(case_yaml)
            or _reuses_an_existing_document(case_yaml)
        ):
            continue
        rel = case_yaml.parent.relative_to(benchmarks_root).as_posix()
        artifact_file = _declared_artifact_file(case_yaml)
        if artifact_file is not None:
            if not (case_yaml.parent / artifact_file).is_file():
                violations.append(f"{rel} -- case.yaml present but {artifact_file} missing")
        elif not (case_yaml.parent / "fixture.FCStd").is_file():
            violations.append(f"{rel} -- case.yaml present but fixture.FCStd missing")
    return violations


def check_tree(benchmarks_root: Path) -> list[str]:
    manifests, manifest_paths, violations = _load_manifests(benchmarks_root)
    violations.extend(_check_missing_fixtures(benchmarks_root))

    for fcstd in _iter_artifacts(benchmarks_root):
        rel = fcstd.relative_to(benchmarks_root).as_posix()
        artifact_id = _artifact_id(fcstd, benchmarks_root)
        manifest = manifests.get(artifact_id)
        if manifest is None:
            violations.append(f"{rel} -- no provenance manifest (artifact id '{artifact_id}')")
            continue
        violations.extend(_check_source(manifest, rel))

    for artifact_id, manifest_path in sorted(manifest_paths.items()):
        if any(part in _EXCLUDED_DIRS for part in Path(artifact_id).parts):
            continue
        manifest_rel = manifest_path.relative_to(benchmarks_root).as_posix()
        # A case-file manifest is never reached by the .FCStd walk above, so its source block is
        # checked here.
        if manifests[artifact_id].get("kind") in _CASE_FILE_MANIFEST_KINDS:
            suffix = ".yaml"
            violations.extend(_check_source(manifests[artifact_id], manifest_rel))
        else:
            suffix = ".FCStd"
        if not (benchmarks_root / (artifact_id + suffix)).is_file():
            violations.append(
                f"{manifest_rel} -- orphan manifest "
                f"(artifact '{artifact_id}' has no matching {suffix})"
            )

    return violations


def _check_source(manifest: dict, rel: str) -> list[str]:
    """The source-block violations of one manifest, reported against ``rel``.

    ``source.kind`` must be in the closed set; a non-``hand-authored`` kind must also carry a
    non-empty ``url``, ``license`` and ``attribution``.
    """
    violations: list[str] = []
    source = manifest.get("source")
    kind = source.get("kind") if isinstance(source, dict) else None
    if kind not in CLOSED_SOURCE_KINDS:
        violations.append(
            f"{rel} -- source.kind '{kind}' not in closed set "
            f"({', '.join(sorted(CLOSED_SOURCE_KINDS))})"
        )
    elif kind != "hand-authored":
        for field in ("url", "license", "attribution"):
            value = source.get(field)
            if not (isinstance(value, str) and value.strip()):
                violations.append(
                    f"{rel} -- source.{field} required for non-hand-authored kind '{kind}'"
                )
    return violations


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent / "benchmarks"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]) if argv else _default_root()

    if not root.exists():
        print(f"check_provenance: benchmarks root not found: {root}")
        return 1

    violations = check_tree(root)
    if violations:
        for violation in violations:
            print(violation)
        return 1

    print("check_provenance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
