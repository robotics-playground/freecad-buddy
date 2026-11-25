"""FreeCAD-free tests for naming the objects of a written multi-object 3MF.

``Exporter3MF::addMesh`` discards object names, so the bridge adds ``name`` to each ``<object>``
of the written ``3D/3dmodel.model`` (``usecases/exports.py``). Fixtures are zip archives built here
in the layout FreeCAD's ``Writer3MF`` writes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from freecad_buddy.adapters import export_oracle
from freecad_buddy.usecases import exports

MODEL_PART = "3D/3dmodel.model"
CONTENT_TYPES_PART = "[Content_Types].xml"
REPO_ROOT = Path(__file__).resolve().parents[2]
FREECAD_STYLE_3MF = (
    REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection" / "3mf-clean-control" / "export.3mf"
)
GUI_WRITTEN_THREE = Path(__file__).parent / "fixtures" / "gui-written-three-objects.3mf"
THUMBNAIL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8ffff3f0005fe02fea79aa0a00000000049454e44ae426082"
)


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


def _read_with_lib3mf(path: Path):
    import lib3mf

    model = lib3mf.Wrapper().CreateModel()
    model.QueryReader("3mf").ReadFromFile(str(path))
    return model


def _first_mesh_name(path: Path) -> str:
    iterator = _read_with_lib3mf(path).GetMeshObjects()
    iterator.MoveNext()
    return iterator.GetCurrentMeshObject().GetName()


def _gui_style_archive(path: Path, thumbnails: int) -> None:
    """Copy the one-object FreeCAD 3MF fixture and add what the GUI writer adds per mesh.

    The GUI adds a thumbnail part and one ``Default Extension="png"`` entry for each. Headless
    FreeCAD cannot produce this file.
    """
    png = '<Default Extension="png" ContentType="image/png"/>\n'
    with zipfile.ZipFile(FREECAD_STYLE_3MF) as source, zipfile.ZipFile(path, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == CONTENT_TYPES_PART:
                text = data.decode("utf-8").replace("</Types>", png * thumbnails + "</Types>")
                data = text.encode("utf-8")
            target.writestr(info, data)
        for index in range(thumbnails):
            target.writestr(f"Metadata/thumbnail{index}.png", THUMBNAIL_PNG)


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
    target = exports._name_model_objects(model_xml, ['a "b" <c> & d'])

    # Assert
    assert 'name="a &quot;b&quot; &lt;c&gt; &amp; d"' in target


def test_Should_read_the_archive_with_lib3mf_When_the_gui_writer_repeated_the_png_type(tmp_path):
    # Arrange
    import lib3mf

    path = tmp_path / "gui.3mf"
    _gui_style_archive(path, thumbnails=3)
    with pytest.raises(lib3mf.ELib3MFException):
        _read_with_lib3mf(path)

    # Act
    exports._name_3mf_objects(str(path), ["Alpha"])

    # Assert
    after = _read_archive(path)
    assert _first_mesh_name(path) == "Alpha"
    assert after[CONTENT_TYPES_PART].decode("utf-8").count('Extension="png"') == 1
    assert "Metadata/thumbnail2.png" in after


def test_Should_keep_the_content_types_text_When_no_type_is_repeated():
    # Arrange
    xml = (
        '<Types xmlns="urn:x">\n <Default Extension="rels" ContentType="a"/>\n'
        ' <Default Extension="model" ContentType="b"/>\n</Types>'
    )

    # Act
    target = exports._unique_content_types(xml)

    # Assert
    assert target == xml


def test_Should_keep_the_first_entry_of_each_extension_When_content_types_repeat():
    # Arrange
    xml = (
        '<Types>\n <Default Extension="png" ContentType="first"/>\n'
        ' <Default Extension="PNG" ContentType="second"/>\n'
        ' <Default Extension="model" ContentType="b"/>\n</Types>'
    )

    # Act
    target = exports._unique_content_types(xml)

    # Assert
    assert 'ContentType="first"' in target
    assert 'ContentType="second"' not in target
    assert 'Extension="model"' in target


@pytest.mark.parametrize("label", ["one\ntwo", "tab\there", "bell\x07x", "cr\rlf"])
def test_Should_read_the_name_with_lib3mf_as_spaces_When_a_label_holds_a_control_character(
    tmp_path, label
):
    # Arrange
    path = tmp_path / "named.3mf"
    _gui_style_archive(path, thumbnails=1)
    expected = "".join(" " if ord(char) < 32 else char for char in label)

    # Act
    exports._name_3mf_objects(str(path), [label])

    # Assert
    assert exports.three_mf_object_name(label) == expected
    assert _first_mesh_name(path) == expected


def test_Should_expect_the_file_name_When_an_object_label_holds_a_control_character(tmp_path):
    # Arrange
    path = tmp_path / "named.3mf"
    _gui_style_archive(path, thumbnails=1)
    exports._name_3mf_objects(str(path), ["a\tb"])
    objects = [
        {
            "name": "A",
            "label": "a\tb",
            "file_name": exports.three_mf_object_name("a\tb"),
            "volume": 6000.0,
            "band": 1.0,
        }
    ]

    # Act
    target = export_oracle.mesh3mf_oracle(str(path), True, 6000.0, 1.0, None, objects)

    # Assert
    names = next(c for c in target["checks"] if c["id"] == "lib3mf.object_names")
    assert names["passed"] is True


def test_Should_read_every_name_with_lib3mf_When_a_real_gui_written_archive_is_named(tmp_path):
    # Arrange
    import lib3mf

    path = tmp_path / "gui-three.3mf"
    path.write_bytes(GUI_WRITTEN_THREE.read_bytes())
    with pytest.raises(lib3mf.ELib3MFException):
        _read_with_lib3mf(path)

    # Act
    exports._name_3mf_objects(str(path), ["Alpha", "Beta", "Gamma"])

    # Assert
    iterator = _read_with_lib3mf(path).GetMeshObjects()
    names = []
    while iterator.MoveNext():
        names.append(iterator.GetCurrentMeshObject().GetName())
    assert names == ["Alpha", "Beta", "Gamma"]
