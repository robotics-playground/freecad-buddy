"""FreeCAD-free tests for the fingerprint module surface.

Confirms the ``fingerprint`` module imports without FreeCAD present (ring discipline: FreeCAD
is imported lazily inside functions) and that its pure quantization helper is deterministic.
The behavioral fingerprint tests (stability / sensitivity / cross-tag) run in-FreeCAD.
"""

from __future__ import annotations

from freecad_buddy.contracts import massprops_equal
from freecad_buddy.usecases import fingerprint


def _record(name: str, com: list[float], volume: float = 100.0) -> dict:
    """One FingerprintRecord carrying a single object's mass properties."""
    return {
        "schema": "fcb.fingerprint/1",
        "serializer": "exportBinary",
        "objects": [
            {
                "name": name,
                "brep_sha256": "0" * 64,
                "massprops": {
                    "volume": volume,
                    "area": 50.0,
                    "bbox": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
                    "com": com,
                    "principal_moments": [1.0, 1.0, 1.0],
                    "quantum": 1e-6,
                },
            }
        ],
        "digest": "d",
    }


def test_fingerprint_module_imports_without_freecad():
    assert callable(fingerprint.fingerprint)
    assert callable(fingerprint._serialize)
    assert callable(fingerprint._massprops)


def test_quantize_snaps_to_fixed_step_deterministically():
    assert fingerprint.Q == 1e-6
    snapped = fingerprint._quantize(1.0 + 4e-7)
    assert snapped == fingerprint._quantize(1.0)  # sub-quantum jitter is erased
    assert fingerprint._quantize(2.000002) != fingerprint._quantize(2.0)


def test_Should_stay_equal_When_a_render_jitters_a_curved_solids_centre_of_mass():
    """Rendering re-tessellates a curved solid, and its reported COM moves with the mesh.

    Measured on a plain ``Part::Cut`` hollow sleeve: one render moved com from [0, 0, 8] to
    [0.020376, 0, 8] with volume, area and moments bit-identical. Comparing COM exactly made the
    screenshot read-only guard call that a mutation, so no turned part could be rendered.
    """
    # Arrange
    before = _record("Sleeve", [0.0, 0.0, 8.0])
    after = _record("Sleeve", [0.020376, 0.0, 8.0])

    # Act
    equal = massprops_equal(before, after)

    # Assert
    assert equal


def test_Should_report_changed_When_a_part_is_actually_moved():
    """COM is the only positional signal here, so the band must not swallow a real move.

    Volume, area and the principal moments are all translation-invariant, so dropping COM instead
    of banding it would let a moved part pass the read-only guard unnoticed.
    """
    # Arrange
    before = _record("Block", [0.0, 0.0, 8.0])
    moved = _record("Block", [25.0, 0.0, 8.0])
    nudged = _record("Block", [0.06, 0.0, 8.0])

    # Act
    far = massprops_equal(before, moved)
    just_outside_band = massprops_equal(before, nudged)

    # Assert
    assert not far
    assert not just_outside_band


def test_Should_report_changed_When_an_exact_invariant_differs():
    """Volume, area and moments stay exact; the band applies to COM alone."""
    # Arrange
    before = _record("Block", [0.0, 0.0, 8.0], volume=100.0)
    reshaped = _record("Block", [0.0, 0.0, 8.0], volume=100.5)

    # Act
    equal = massprops_equal(before, reshaped)

    # Assert
    assert not equal
