"""FreeCAD-free tests for the fingerprint module surface.

Confirms the ``fingerprint`` module imports without FreeCAD present (ring discipline: FreeCAD
is imported lazily inside functions) and that its pure quantization helper is deterministic.
The behavioral fingerprint tests (stability / sensitivity / cross-tag) run in-FreeCAD.
"""

from __future__ import annotations

from freecad_buddy.usecases import fingerprint


def test_fingerprint_module_imports_without_freecad():
    assert callable(fingerprint.fingerprint)
    assert callable(fingerprint._serialize)
    assert callable(fingerprint._massprops)


def test_quantize_snaps_to_fixed_step_deterministically():
    assert fingerprint.Q == 1e-6
    snapped = fingerprint._quantize(1.0 + 4e-7)
    assert snapped == fingerprint._quantize(1.0)  # sub-quantum jitter is erased
    assert fingerprint._quantize(2.000002) != fingerprint._quantize(2.0)
