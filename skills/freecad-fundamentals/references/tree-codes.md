# Reading `query_tree_summary` lines

Load this when you read the tree text that `query_tree_summary` returns. The
result is plain text. The first line is the status and the counts, for example
`OK: 184 objects, 59 shown, 51 matches.` (`matches` only when you gave
`filters`, `truncated` when the line cap cut the tree, then any errors). A
`framing:` line follows when a 3D view is open. The tree lines come next.

## Line format

```
<prefix><v|-> [<CODE>] <Name>[ "<Label>"][ (+N)][ *tip][ !<status>]
```

| Part | Meaning |
| --- | --- |
| `v` / `-` | `v` = the object is visible. `-` = the object is hidden. |
| `[<CODE>]` | Type code. See the table below. |
| `<Name>` | Immutable object Name. Use it in every other tool call. |
| `"<Label>"` | Display Label. Shown only when it differs from the Name. |
| `(+N)` | The node is closed. It has N children that are not shown. |
| `(+N more)` | The node is open only along a path. It shows the path child; N other children are not shown. |
| `*tip` | The object is the Tip of its Body: the Body's solid. |
| `!<status>` | The object is in an error state. The text is FreeCAD's status string. |
| `-> <target>` | Ends an `App::Link` line. The tool does not open the link target. |

Connectors: `|-- ` is a middle child and `` `-- `` is the last child. Below a
middle child the prefix is `|   `; below the last child it is four spaces.

With `focus`, the first line is `path: <A> > <B> > <Name>`, the place of the
focused object in the tree. When the tree has more than 200 lines, the last line
is `... <K> more lines; narrow with focus or a smaller depth`.

Children are what FreeCAD's Model panel shows, not dependencies:

- A Body or Part: its `Origin` first, then its `Group`. It leaves out each member
  that another member shows as a child (a Pad's sketch, for example).
- An Origin: its axes, planes and point.
- A sketch-based feature (Pad, Pocket, Hole...): its `Profile` sketch.
- A Loft: its profile and section sketches. A Pipe: its profile, section, spine
  and auxiliary spine sketches. A MultiTransform: its transformations.
- A Part boolean (Cut, Fuse, Common): its `Base` and `Tool`. A MultiFuse or
  MultiCommon: its `Shapes`.
- A group: its `Group`. A link group: its elements.

Use `query_dependencies` for what an object depends on.

## Type codes

A code is the part of the `TypeId` after `::`, in capitals: `PartDesign::Pad`
is `PAD`, `PartDesign::Pocket` is `POCKET`, `Part::Box` is `BOX`. A `TypeId`
without `::` is used in capitals as it is. These `TypeId`s use a fixed code:

| TypeId | Code |
| --- | --- |
| `PartDesign::Plane` | `DPLANE` |
| `App::Plane` | `PLANE` |
| `App::Line` | `AXIS` |
| `PartDesign::Line` | `DLINE` |
| `App::Point` | `POINT` |
| `PartDesign::Point` | `DPOINT` |
| `Sketcher::SketchObject` | `SKETCH` |
| `PartDesign::FeatureBase` | `BASE` |
| `PartDesign::Body` | `BODY` |
| `App::Origin` | `ORIGIN` |
| `App::Link` | `LINK` |

A code is not unique. `Part::Plane` and `App::Plane` are both `PLANE`;
`Part::Fillet` and `PartDesign::Fillet` are both `FILLET`. `filters.types`
takes a code in any case (`PAD`, `pad`), which matches every `TypeId` with that
code, or a full `TypeId` (`PartDesign::Fillet`), which matches only that type.

The one-line `text` of the result names every object in error in the start
subtree, also when its line is not shown.
