from freecad_buddy.usecases.queries import (
    _is_renderable,
    _node_passes,
    _sparse_node,
    _DATUM_EXCLUDE_DEFAULT,
)


class FakeObj:
    def __init__(self, name, label, type_id, visibility=True, status="Valid", shape=True):
        self.Name = name
        self.Label = label
        self.TypeId = type_id
        self.Visibility = visibility
        self._status = status
        self.Shape = object() if shape else None

    def getStatusString(self):
        return self._status


def test_datum_exclude_default_covers_the_clutter_types():
    assert _DATUM_EXCLUDE_DEFAULT == ("App::Plane", "App::Line", "App::Point", "App::Origin")


def test_is_renderable_false_for_datum_and_container():
    assert _is_renderable(FakeObj("P", "P", "App::Plane")) is False
    assert _is_renderable(FakeObj("B", "B", "PartDesign::Body")) is False
    assert _is_renderable(FakeObj("S", "S", "Sketcher::SketchObject")) is False


def test_is_renderable_true_for_shape_leaf():
    assert _is_renderable(FakeObj("F", "F", "Part::Feature")) is True


def test_node_passes_types_and_visible_only_and_stack():
    obj = FakeObj("USB", "USB 3.0", "App::Link", visibility=True)
    assert _node_passes(obj, {"types": ["App::Link"]}) is True
    assert _node_passes(obj, {"types": ["App::Part"]}) is False
    hidden = FakeObj("H", "H", "App::Link", visibility=False)
    assert _node_passes(hidden, {"visible_only": True}) is False
    # AND-stack: passes types but fails visible_only
    assert _node_passes(hidden, {"types": ["App::Link"], "visible_only": True}) is False


def test_node_passes_exclude_types_and_name_pattern():
    plane = FakeObj("XY", "XY-plane", "App::Plane")
    assert _node_passes(plane, {"exclude_types": ["App::Plane"]}) is False
    usb = FakeObj("USB_3_0", "USB 3.001", "App::Link")
    assert _node_passes(usb, {"name_pattern": "USB"}) is True
    assert _node_passes(usb, {"name_pattern": "HDMI"}) is False


def test_sparse_node_omits_empty_fields():
    obj = FakeObj("pcb", "pcb001", "App::Link", visibility=True, status="Valid")
    node = _sparse_node(obj, children=[], links=[], children_count=0, links_count=0)
    assert node == {"name": "pcb", "label": "pcb001", "type": "App::Link", "visibility": True}


def test_sparse_node_includes_error_and_counts_when_present():
    obj = FakeObj("Joint002", "Master Sketch004", "App::FeaturePython",
                  visibility=True, status="Broken link in: Reference1")
    node = _sparse_node(obj, children=[], links=[], children_count=3, links_count=2)
    assert node["error"] == "Broken link in: Reference1"
    assert node["children_count"] == 3
    assert node["links_count"] == 2
    assert "children" not in node  # empty list omitted even when count>0 (unexpanded)
    assert "links" not in node


def test_sparse_node_includes_arrays_when_expanded():
    obj = FakeObj("Assembly", "h96max-mainboard", "Assembly::AssemblyObject")
    child = {"name": "Joint002", "label": "x", "type": "App::FeaturePython", "visibility": True}
    link = {"name": "pcb", "label": "pcb001", "type": "App::Link", "visibility": True}
    node = _sparse_node(obj, children=[child], links=[link], children_count=1, links_count=1)
    assert node["children"] == [child]
    assert node["links"] == [link]
