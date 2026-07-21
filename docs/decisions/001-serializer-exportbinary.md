# 001 — Fingerprint Serializer: exportBinary with exportBrep Fallback

## Decision

The geometry fingerprint (AD-6) serializes a `TopoShape` for hashing by probing
`TopoShape.exportBinary` first; if it is not Python-exposed on the running build, it falls
back to an `exportBrep` stream. Every hash is tagged with a serializer id (`exportBinary`
vs `exportBrep`). Cross-tag comparison is banned — a fingerprint produced with one
serializer is never compared against one produced with another. When neither serializer is
available for a shape, the fingerprint degrades to a mass-property tuple (volume, area,
center-of-mass, bbox) and is tagged accordingly.

Serializer availability is exposed through `usecases/shim.export_binary_available()` so no
downstream code branches on FreeCAD version strings.

## Drives

- AD-6 geometry fingerprint (story 1.6).
- The serializer-id tag carried by every `FingerprintRecord`.

## Runtime-confirm

- Is `TopoShape.exportBinary` Python-exposed on the conda-forge **1.0.0** build?
- Is `TopoShape.exportBinary` Python-exposed on the conda-forge **1.1.0** build?
- To be confirmed on the CI headless legs via `shim.export_binary_available()`; record per leg.
- If absent on both, verify the `exportBrep` stream fallback produces stable, order-independent hashes.
