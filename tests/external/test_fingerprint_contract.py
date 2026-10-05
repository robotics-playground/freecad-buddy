"""FreeCAD-free tests for the fingerprint module surface.

Confirms the ``fingerprint`` module imports without FreeCAD present (ring discipline: FreeCAD
is imported lazily inside functions) and that its pure quantization helper is deterministic.
The behavioral fingerprint tests (stability / sensitivity / cross-tag) run in-FreeCAD.
"""

from __future__ import annotations

import hashlib

from freecad_buddy.usecases import fingerprint


def test_fingerprint_module_imports_without_freecad():
    assert callable(fingerprint.fingerprint)
    assert callable(fingerprint._serialize)
    assert callable(fingerprint._massprops)


class _NullShape:
    def isNull(self):
        return True


class _Object:
    def __init__(self, name, type_id, **attributes):
        self.Name = name
        self.TypeId = type_id
        self.__dict__.update(attributes)


class _Document:
    def __init__(self, *objects):
        self.Objects = list(objects)


def test_an_object_with_a_null_shape_enters_the_digest_as_empty_bytes_and_zero_massprops():
    spreadsheet = _Object("Sheet", "Spreadsheet::Sheet")
    without = fingerprint.fingerprint(_Document(spreadsheet))

    record = fingerprint.fingerprint(
        _Document(spreadsheet, _Object("Pad", "PartDesign::Pad", Shape=_NullShape()))
    )

    assert record["objects"] == [
        {
            "name": "Pad",
            "brep_sha256": hashlib.sha256(b"").hexdigest(),
            "massprops": {
                "volume": 0.0,
                "area": 0.0,
                "bbox": [0.0] * 6,
                "com": [0.0] * 3,
                "principal_moments": [0.0] * 3,
                "quantum": 1e-6,
            },
        }
    ]
    assert record["digest"] != without["digest"]


def test_objects_without_a_shape_and_null_datums_stay_out_of_the_record():
    record = fingerprint.fingerprint(
        _Document(
            _Object("Sheet", "Spreadsheet::Sheet"),
            _Object("XY_Plane", "App::Plane", Shape=_NullShape()),
        )
    )

    assert record["objects"] == []


def test_quantize_snaps_to_fixed_step_deterministically():
    assert fingerprint.Q == 1e-6
    snapped = fingerprint._quantize(1.0 + 4e-7)
    assert snapped == fingerprint._quantize(1.0)  # sub-quantum jitter is erased
    assert fingerprint._quantize(2.000002) != fingerprint._quantize(2.0)
