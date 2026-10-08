"""Plain-text document tree in the shape of FreeCAD's Model panel.

One object per line: ``<prefix><v|-> [<CODE>] <Name>[ "<Label>"][ (+N)][ *tip][ !<status>]``,
with `` -> <target>`` closing an ``App::Link`` line. Pure: no FreeCAD import, so the line format
and the type-code table are unit-tested FreeCAD-free. ``skills/freecad-fundamentals/references/
tree-codes.md`` publishes the same table to agents; a test fails when the two differ.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A PartDesign datum and an App origin feature share a ``TypeId`` suffix (``Plane``), and
# ``SketchObject``/``FeatureBase`` read badly. The common PartDesign codes are pinned here too, even
# where the suffix rule agrees, so the skill catalog lists every code a PartDesign tree shows.
TYPE_CODE_OVERRIDES: dict[str, str] = {
    "PartDesign::Plane": "DPLANE",
    "App::Plane": "PLANE",
    "App::Line": "AXIS",
    "PartDesign::Line": "DLINE",
    "App::Point": "POINT",
    "PartDesign::Point": "DPOINT",
    "Sketcher::SketchObject": "SKETCH",
    "PartDesign::FeatureBase": "BASE",
    "PartDesign::Body": "BODY",
    "App::Origin": "ORIGIN",
    "App::Link": "LINK",
}

LINE_CAP = 200


@dataclass
class TreeNode:
    """One rendered object and the children shown under it.

    ``not_shown`` counts the children not shown. With no shown children the line ends ``(+N)``;
    beside shown children (a node opened only along a path) it ends ``(+N more)``.
    """

    name: str
    label: str
    type_id: str
    visible: bool
    tip: bool = False
    status: str | None = None
    link_target: str | None = None
    children: list[TreeNode] = field(default_factory=list)
    not_shown: int = 0


def type_code(type_id: str) -> str:
    """The short code for ``type_id``: an override, else the part after ``::`` in capitals."""
    override = TYPE_CODE_OVERRIDES.get(type_id)
    if override is not None:
        return override
    return type_id.rpartition("::")[2].upper()


def node_line(node: TreeNode) -> str:
    """The line for ``node`` without its connector prefix."""
    parts = ["v" if node.visible else "-", f"[{type_code(node.type_id)}]", node.name]
    # A multi-line Label or OCC message would break the one-object-per-line contract, and a bare
    # quote would end the quoted Label early.
    if node.label != node.name:
        label = " ".join(node.label.split()).replace('"', '\\"')
        parts.append(f'"{label}"')
    if node.not_shown:
        parts.append(f"(+{node.not_shown} more)" if node.children else f"(+{node.not_shown})")
    if node.tip:
        parts.append("*tip")
    if node.status:
        parts.append("!" + " ".join(node.status.split()))
    if node.link_target is not None:
        parts.append(f"-> {node.link_target}")
    return " ".join(parts)


def tree_lines(roots: list[TreeNode]) -> list[str]:
    """Every line of the forest under ``roots``; roots carry no connector."""
    lines: list[str] = []
    for root in roots:
        lines.append(node_line(root))
        _append_children(root, "", lines)
    return lines


def _append_children(node: TreeNode, prefix: str, lines: list[str]) -> None:
    last = len(node.children) - 1
    for index, child in enumerate(node.children):
        is_last = index == last
        lines.append(prefix + ("`-- " if is_last else "|-- ") + node_line(child))
        _append_children(child, prefix + ("    " if is_last else "|   "), lines)


def path_line(names: list[str]) -> str:
    """The breadcrumb from the top level down to the focused object."""
    return "path: " + " > ".join(names)


def cap_lines(lines: list[str]) -> tuple[list[str], bool]:
    """``lines`` cut to ``LINE_CAP`` plus a steering line, and whether the cut happened."""
    if len(lines) <= LINE_CAP:
        return lines, False
    more = len(lines) - LINE_CAP
    steering = f"... {more} more lines; narrow with focus or a smaller depth"
    return [*lines[:LINE_CAP], steering], True
