"""FreeCAD-free tests for naming the objects of a written multi-object 3MF.

``Exporter3MF::addMesh`` discards object names, so the bridge adds ``name`` to each ``<object>``
of the written ``3D/3dmodel.model`` (``usecases/exports.py``). Fixtures are zip archives built here
in the layout FreeCAD's ``Writer3MF`` writes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from freecad_buddy.usecases import exports

MODEL_PART = "3D/3dmodel.model"


def _write_archive(path: Path, model: bytes | None) -> dict[str, bytes]:
    parts = {"_rels/.rels": b"<Relationships/>", "[Content_Types].xml": b"<Types/>"}
    if model is not None:
        parts = {MODEL_PART: model, **parts}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return parts


def _read_archive(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_Should_keep_every_other_part_byte_identical_When_3mf_objects_are_named(tmp_path):
    # Arrange
    path = tmp_path / "freecad-style.3mf"
    model = (
        b'<model unit="millimeter"><resources><object id="1" type="model"><mesh/></object>'
        b'<object id="2" type="model"><mesh/></object></resources></model>'
    )
    parts = _write_archive(path, model)

    # Act
    exports._name_3mf_objects(str(path), ["Alpha", "Beta"])

    # Assert
    after = _read_archive(path)
    assert list(after) == list(parts)
    assert after["_rels/.rels"] == parts["_rels/.rels"]
    assert after["[Content_Types].xml"] == parts["[Content_Types].xml"]
    assert b'<object id="2" type="model" name="Beta"><mesh/>' in after[MODEL_PART]


def test_Should_keep_the_object_type_When_a_surface_object_is_named():
    # Arrange
    model_xml = '<object id="1" type="surface"></object>'

    # Act
    target = exports._name_model_objects(model_xml, ["A"])

    # Assert
    assert target == '<object id="1" type="surface" name="A"></object>'


def test_Should_raise_When_the_3mf_object_count_differs_from_the_labels():
    # Arrange
    model_xml = '<object id="1" type="model"></object>'

    # Act
    act = lambda: exports._name_model_objects(model_xml, ["A", "B"])  # noqa: E731

    # Assert
    with pytest.raises(RuntimeError):
        act()


def test_Should_raise_and_leave_the_file_untouched_When_the_model_part_is_missing(tmp_path):
    # Arrange
    path = tmp_path / "no-model.3mf"
    parts = _write_archive(path, None)

    # Act
    act = lambda: exports._name_3mf_objects(str(path), ["A"])  # noqa: E731

    # Assert
    with pytest.raises(RuntimeError):
        act()
    assert _read_archive(path) == parts
    assert not Path(f"{path}.named").exists()


def test_Should_escape_the_label_When_a_3mf_object_is_named():
    # Arrange
    model_xml = '<object id="1" type="model"></object>'

    # Act
    target = exports._name_model_objects(model_xml, ['a "b" <c>'])

    # Assert
    assert 'name="a &quot;b&quot; &lt;c&gt;"' in target


def test_Should_write_character_references_When_a_label_holds_a_newline_or_tab():
    # Arrange
    model_xml = '<object id="1" type="model"></object>'

    # Act
    target = exports._name_model_objects(model_xml, ["one\ntwo\tthree"])

    # Assert
    assert 'name="one&#10;two&#9;three"' in target
