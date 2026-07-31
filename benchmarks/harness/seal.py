"""Held-out sealing helpers (FreeCAD-free, stdlib-only, deterministic under test).

Seals the ``g1/heldout/`` split into a SHA-verified, key-bound archive plus a ``SEAL.json``
manifest, and unseals it only when handed the key. The cipher is a stdlib ``hashlib``-derived
keystream XOR'd over the ``tarfile`` bytes — enough to make the archive non-plaintext and
key-bound for the auditable ceremony; the runner only ever checks ``archive_sha256`` + the
manifest, never the cipher internals (decision 012). No ``age``/``pyrage``/third-party dep.

Timestamps and ``git_sha`` are injected by the caller so this module is deterministic under
test; it never reads the clock or spawns ``git``.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

ARCHIVE_NAME = "heldout.tar.enc"
MANIFEST_NAME = "SEAL.json"

_CASE_GLOB = "case.yaml"
_KEYSTREAM_ROUNDS_TAG = b"fcb.heldout.seal/1"


class SealError(Exception):
    """A seal artifact is missing, tampered, or burned — surfaced by the runner as exit-2."""


def _keystream(key: str, length: int) -> bytes:
    """Deterministic ``length``-byte keystream derived from ``key`` via chained SHA-256 blocks."""
    out = bytearray()
    counter = 0
    seed = _KEYSTREAM_ROUNDS_TAG + key.encode("utf-8")
    while len(out) < length:
        block = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, key: str) -> bytes:
    stream = _keystream(key, len(data))
    return bytes(b ^ k for b, k in zip(data, stream))


def _staged_case_dirs(heldout_dir: Path) -> list[Path]:
    """The case directories staged under ``heldout_dir`` (each holding a ``case.yaml``), sorted."""
    return sorted({case_yaml.parent for case_yaml in heldout_dir.rglob(_CASE_GLOB)})


def _build_tar_bytes(heldout_dir: Path, case_dirs: list[Path]) -> bytes:
    """Tar the staged case dirs into a deterministic in-memory archive (sorted, mtime-zeroed)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for case_dir in case_dirs:
            for path in sorted(p for p in case_dir.rglob("*") if p.is_file()):
                info = tarfile.TarInfo(name=path.relative_to(heldout_dir).as_posix())
                payload = path.read_bytes()
                info.size = len(payload)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _case_id_list_sha256(case_dirs: list[Path], heldout_dir: Path) -> str:
    joined = "\n".join(d.relative_to(heldout_dir).as_posix() for d in case_dirs)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _write_manifest(heldout_dir: Path, manifest: dict) -> None:
    path = heldout_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(heldout_dir: Path) -> dict | None:
    """Return the parsed ``SEAL.json`` manifest, or ``None`` when no seal is present."""
    path = heldout_dir / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SealError(f"malformed {MANIFEST_NAME} ({exc.__class__.__name__})") from exc
    if not isinstance(data, dict):
        raise SealError(f"malformed {MANIFEST_NAME}: not a mapping")
    return data


def seal_heldout(
    heldout_dir: Path, *, sealed_by: str, sealed_at: str, key: str, gate: str = "G1"
) -> dict:
    """Seal the staged held-out cases into ``heldout.tar.enc`` + ``SEAL.json``; return the manifest.

    Tars every staged case dir (an empty archive when none are staged — ``case_count: 0`` is a
    valid placeholder seal, not an error), encrypts it with the ``key``-derived keystream, writes
    the pair, and records ``archive_sha256`` over the encrypted bytes. ``sealed_at``/``sealed_by``
    are injected by the caller.

    :param gate: the gate the sealed set belongs to, recorded in the manifest.
    """
    heldout_dir.mkdir(parents=True, exist_ok=True)
    case_dirs = _staged_case_dirs(heldout_dir)
    plain = _build_tar_bytes(heldout_dir, case_dirs)
    encrypted = _xor(plain, key)
    (heldout_dir / ARCHIVE_NAME).write_bytes(encrypted)

    manifest = {
        "gate": gate,
        "sealed_at": sealed_at,
        "sealed_by": sealed_by,
        "case_count": len(case_dirs),
        "archive_sha256": hashlib.sha256(encrypted).hexdigest(),
        "case_id_list_sha256": _case_id_list_sha256(case_dirs, heldout_dir),
        "unseal_events": [],
    }
    _write_manifest(heldout_dir, manifest)
    return manifest


def unseal_heldout(
    heldout_dir: Path, *, key: str, run_id: str, timestamp: str, git_sha: str
) -> Path:
    """Verify + decrypt the sealed archive into a temp dir; append an unseal event; return the dir.

    Verifies ``archive_sha256`` over the on-disk encrypted bytes BEFORE decrypting (a mismatch is
    tamper), refuses a burned set, decrypts + extracts to a fresh temp dir, and appends the
    ``{run_id, timestamp, git_sha}`` unseal event to ``SEAL.json``. The caller owns and deletes the
    returned temp dir.
    """
    manifest = read_manifest(heldout_dir)
    if manifest is None:
        raise SealError(f"no seal to unseal: {heldout_dir / MANIFEST_NAME} absent")
    if manifest.get("burned"):
        burned = manifest["burned"]
        burned_run = burned.get("run_id") if isinstance(burned, dict) else None
        raise SealError(f"seal is burned (run_id={burned_run!r}); re-seal to re-run")

    archive_path = heldout_dir / ARCHIVE_NAME
    if not archive_path.is_file():
        raise SealError(f"sealed archive absent: {archive_path}")
    encrypted = archive_path.read_bytes()
    if hashlib.sha256(encrypted).hexdigest() != manifest.get("archive_sha256"):
        raise SealError(f"archive_sha256 mismatch (tamper): {archive_path}")

    import tempfile

    extract_dir = Path(tempfile.mkdtemp(prefix="fcb-heldout-"))
    try:
        plain = _xor(encrypted, key)
        try:
            with tarfile.open(fileobj=io.BytesIO(plain), mode="r") as tar:
                _extract_sealed(tar, extract_dir)
        except tarfile.TarError as exc:
            raise SealError(f"unseal failed (wrong key?): {exc}") from exc

        events = manifest.get("unseal_events")
        if not isinstance(events, list):
            events = []
        events.append({"run_id": run_id, "timestamp": timestamp, "git_sha": git_sha})
        manifest["unseal_events"] = events
        _write_manifest(heldout_dir, manifest)
    except BaseException:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    return extract_dir


def _extract_sealed(tar: tarfile.TarFile, extract_dir: Path) -> None:
    """Extract the archive into ``extract_dir``, refusing any member that escapes the directory.

    Uses the stdlib ``data`` filter when available (Py 3.12+); on older interpreters it screens
    each member for symlink/device members and for absolute-path or ``..`` traversal before
    extracting, matching the properties the ``data`` filter enforces.
    """
    if hasattr(tarfile, "data_filter"):
        tar.extractall(extract_dir, filter="data")
        return
    root = extract_dir.resolve()
    for member in tar.getmembers():
        if member.issym() or member.islnk() or member.isdev():
            raise SealError(f"unsafe archive member (symlink/device): {member.name!r}")
        target = (extract_dir / member.name).resolve()
        if target != root and not target.is_relative_to(root):
            raise SealError(f"unsafe archive member (path traversal): {member.name!r}")
    tar.extractall(extract_dir)


def burn_seal(heldout_dir: Path, *, run_id: str, reason: str) -> None:
    """Stamp ``burned`` into ``SEAL.json`` so a subsequent unseal refuses until a fresh seal."""
    manifest = read_manifest(heldout_dir)
    if manifest is None:
        raise SealError(f"no seal to burn: {heldout_dir / MANIFEST_NAME} absent")
    manifest["burned"] = {"run_id": run_id, "reason": reason}
    _write_manifest(heldout_dir, manifest)


__all__ = [
    "ARCHIVE_NAME",
    "MANIFEST_NAME",
    "SealError",
    "seal_heldout",
    "unseal_heldout",
    "burn_seal",
    "read_manifest",
]
