"""FreeCAD-free fixture tests for the STEP header reader behind ``export_step.schema``.

The header texts are fixed copies of what the OCC writers emit: the FreeCAD 1.1.4 build writes
``…_MIM_LF.`` with the version braces split over a line, and a ``FILE_SCHEMA`` entry may also
break between its parentheses and the quoted name.
"""

from __future__ import annotations

import pytest

from freecad_buddy.usecases import exports

_HEADER = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('FreeCAD Model'),'2;1');
FILE_NAME('Open CASCADE Shape Model','2026-10-05T10:00:00',('FreeCAD'),(
    'FreeCAD'),'Open CASCADE STEP processor 7.8','FreeCAD','Unknown');
{file_schema}
ENDSEC;
DATA;
#1 = APPLICATION_PROTOCOL_DEFINITION('international standard',
  'automotive_design',2000,#2);
ENDSEC;
END-ISO-10303-21;
"""


@pytest.mark.parametrize(
    ("file_schema", "expected"),
    [
        (
            "FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF. "
            "{1 0 10303 442 1 1 4 \n}'));",
            "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF",
        ),
        (
            "FILE_SCHEMA((\n'AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
            "AUTOMOTIVE_DESIGN",
        ),
    ],
    ids=["ap242_freecad_1_1_4_form", "ap214_split_after_parentheses"],
)
def test_should_return_schema_identifier_when_header_names_it(tmp_path, file_schema, expected):
    # Arrange
    path = tmp_path / "export.step"
    path.write_text(_HEADER.format(file_schema=file_schema), encoding="ascii")

    # Act
    measured = exports._read_file_schema(str(path))

    # Assert
    assert measured == expected
