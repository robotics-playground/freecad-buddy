"""Compare a probe snapshot (or offline read) with an expectation. Stdlib only.

An expectation names only the fields it checks::

    {
      "tolerance": 1e-6,
      "active_document": "box_10_20_30",
      "documents": {
        "box_10_20_30": {
          "label": "box-10-20-30",
          "modified": false,
          "objects": {
            "Box": {"type": "Part::Feature", "visibility": true, "valid": true,
                    "volume": 6000, "bbox": [0, 0, 0, 10, 20, 30]}
          }
        }
      },
      "view": {"clipped": false}
    }

``documents`` lists every document that must be open, and no other. ``view`` may be ``null``
to require no view. ``volume`` and ``bbox`` match within the absolute ``tolerance`` (default
1e-6); every other field matches exactly. ``clipped`` and ``visible_size`` are ``null`` in a
snapshot of a hidden or minimized view, so they then mismatch any expected value. An unknown key
raises ``ValueError``, whether or not its document or view is open. An offline-reader result
that carries ``error`` raises ``ValueError`` with that error, since it read nothing.
"""

DEFAULT_TOLERANCE = 1e-6

_TOP_KEYS = {"tolerance", "freecad_version", "active_document", "documents", "view"}
_DOCUMENT_KEYS = {"label", "modified", "objects"}
_OBJECT_KEYS = {"type", "visibility", "valid", "volume", "bbox"}
_SHAPE_KEYS = {"valid", "volume", "bbox"}
_VIEW_KEYS = {"size", "visible_size", "clipped"}
_TOLERANT_KEYS = {"volume", "bbox"}


def _check_keys(expected, allowed, where):
    unknown = sorted(set(expected) - allowed)
    if unknown:
        raise ValueError(f"unknown expectation key(s) {unknown} in {where}")


def _validate(expectation):
    _check_keys(expectation, _TOP_KEYS, "expectation")
    for name, document in expectation.get("documents", {}).items():
        _check_keys(document, _DOCUMENT_KEYS, f"documents.{name}")
        for object_name, expected_object in document.get("objects", {}).items():
            _check_keys(expected_object, _OBJECT_KEYS, f"documents.{name}.objects.{object_name}")
    if expectation.get("view") is not None:
        _check_keys(expectation["view"], _VIEW_KEYS, "view")


def _within(expected, observed, tolerance):
    if isinstance(expected, list):
        return (
            isinstance(observed, list)
            and len(expected) == len(observed)
            and all(_within(e, o, tolerance) for e, o in zip(expected, observed))
        )
    return isinstance(observed, (int, float)) and abs(observed - expected) <= tolerance


class _Comparison:
    def __init__(self, tolerance):
        self.tolerance = tolerance
        self.mismatches = []

    def check(self, field, expected, observed, tolerant=False):
        if tolerant:
            equal = _within(expected, observed, self.tolerance)
        else:
            equal = expected == observed
        if not equal:
            self.mismatches.append({"field": field, "expected": expected, "observed": observed})

    def fields(self, prefix, expected, observed):
        for key, value in expected.items():
            self.check(f"{prefix}.{key}", value, observed.get(key), key in _TOLERANT_KEYS)


def _object_fields(snapshot_object):
    shape = snapshot_object["shape"] or {}
    fields = {key: shape.get(key) for key in _SHAPE_KEYS}
    fields.update(type=snapshot_object["type"], visibility=snapshot_object["visibility"])
    return fields


def _compare_document(comparison, prefix, expected, observed):
    for key in ("label", "modified"):
        if key in expected:
            comparison.check(f"{prefix}.{key}", expected[key], observed.get(key))
    objects = {obj["name"]: obj for obj in observed.get("objects", [])}
    for name, expected_object in expected.get("objects", {}).items():
        where = f"{prefix}.objects.{name}"
        if name in objects:
            comparison.fields(where, expected_object, _object_fields(objects[name]))
        else:
            comparison.check(where, "present", None)


def compare(snapshot, expectation):
    """Return the mismatches as ``{"field", "expected", "observed"}`` dicts; empty when equal."""
    _validate(expectation)
    if "error" in snapshot:
        raise ValueError(f"input is an error report, not a read: {snapshot['error']}")
    comparison = _Comparison(expectation.get("tolerance", DEFAULT_TOLERANCE))
    for key in ("freecad_version", "active_document"):
        if key in expectation:
            comparison.check(key, expectation[key], snapshot.get(key))

    if "documents" in expectation:
        observed = {doc["name"]: doc for doc in snapshot.get("documents", [])}
        comparison.check("documents", sorted(expectation["documents"]), sorted(observed))
        for name, expected_document in expectation["documents"].items():
            if name in observed:
                _compare_document(
                    comparison, f"documents.{name}", expected_document, observed[name]
                )

    if "view" in expectation:
        expected_view, observed_view = expectation["view"], snapshot.get("view")
        if expected_view is None or observed_view is None:
            comparison.check("view", expected_view, observed_view)
        else:
            comparison.fields("view", expected_view, observed_view)
    return comparison.mismatches
