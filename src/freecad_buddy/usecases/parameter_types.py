"""The VarSet parameter vocabulary shared by ``feature_parameters_define`` and ``query_parameters``.

A parameter ``type`` on the wire names one FreeCAD property type, so the writer and the reader
must agree on the pairs.
"""

PARAMETER_PROPERTY_TYPES = {
    "length": "App::PropertyLength",
    "angle": "App::PropertyAngle",
    "float": "App::PropertyFloat",
    "integer": "App::PropertyInteger",
    "bool": "App::PropertyBool",
    "string": "App::PropertyString",
}
