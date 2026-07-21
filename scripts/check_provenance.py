"""Provenance gate: every ``benchmarks/**`` artifact has a valid manifest.

Recursively walks ``benchmarks/**`` for artifact files (``*.FCStd``), excluding ``heldout/``
(sealed), ``_registry/provenance/`` itself, and ``__pycache__``. For each artifact:

  - a provenance manifest under ``_registry/provenance/`` must declare its ``artifact`` id
    (path relative to ``benchmarks/`` without the ``.FCStd`` suffix);
  - the manifest ``source.kind`` must be in the closed set.

Additionally flags:
  - a fault case dir with a ``case.yaml`` but no ``fixture.FCStd``;
  - duplicate ``artifact`` ids across manifests (a duplicate must not silently overwrite).

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


def _load_manifests(benchmarks_root: Path) -> tuple[dict[str, dict], list[str]]:
    """Return ({artifact_id: manifest}, [violations]) — duplicate ids are flagged."""
    provenance_dir = benchmarks_root.joinpath(*_PROVENANCE_REL)
    manifests: dict[str, dict] = {}
    violations: list[str] = []
    if not provenance_dir.is_dir():
        return manifests, violations

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

    return manifests, violations


def _iter_artifacts(benchmarks_root: Path):
    provenance_dir = benchmarks_root.joinpath(*_PROVENANCE_REL)
    for fcstd in sorted(benchmarks_root.rglob("*.FCStd")):
        parts = fcstd.relative_to(benchmarks_root).parts
        if any(part in _EXCLUDED_DIRS for part in parts):
            continue
        if provenance_dir in fcstd.parents:
            continue
        yield fcstd


def _check_missing_fixtures(benchmarks_root: Path) -> list[str]:
    """A case dir with a case.yaml must carry its declared fixture.FCStd."""
    violations: list[str] = []
    for case_yaml in sorted(benchmarks_root.rglob("case.yaml")):
        parts = case_yaml.relative_to(benchmarks_root).parts
        if any(part in _EXCLUDED_DIRS for part in parts):
            continue
        if not (case_yaml.parent / "fixture.FCStd").is_file():
            rel = case_yaml.parent.relative_to(benchmarks_root).as_posix()
            violations.append(f"{rel} -- case.yaml present but fixture.FCStd missing")
    return violations


def check_tree(benchmarks_root: Path) -> list[str]:
    manifests, violations = _load_manifests(benchmarks_root)
    violations.extend(_check_missing_fixtures(benchmarks_root))

    for fcstd in _iter_artifacts(benchmarks_root):
        rel = fcstd.relative_to(benchmarks_root).as_posix()
        artifact_id = _artifact_id(fcstd, benchmarks_root)
        manifest = manifests.get(artifact_id)
        if manifest is None:
            violations.append(f"{rel} -- no provenance manifest (artifact id '{artifact_id}')")
            continue
        source = manifest.get("source")
        kind = source.get("kind") if isinstance(source, dict) else None
        if kind not in CLOSED_SOURCE_KINDS:
            violations.append(
                f"{rel} -- source.kind '{kind}' not in closed set "
                f"({', '.join(sorted(CLOSED_SOURCE_KINDS))})"
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
