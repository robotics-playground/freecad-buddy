# Generator kit

Copy this into the generator file, then add the part functions under it. The file runs inside
the live FreeCAD through `script_exec` (`doc` and `STAGE` injected) or headless through
`freecadcmd` on a closed document.

## Run it

`script_exec` on the live document. Keep the generator on disk, so each call is short. Run it
once per stage; only the first stage clears the document:

```python
p = r"D:/path/to/build_fcstd.py"
STAGE = "params"                         # then "part_a", "part_b", ... in later calls
doc.openTransaction("build " + STAGE)
try:
    if STAGE == "params":                # first stage only, on a document this generator owns
        for o in list(doc.Objects):
            doc.removeObject(o.Name)
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"),
         {"doc": doc, "STAGE": STAGE, "__name__": "fcb_build"})
    doc.recompute()
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise
result = [(o.Name, o.Label, o.State) for o in doc.Objects if "Invalid" in o.State]
```

The generator always runs its `params()` function (it reuses existing variables) and builds
only the part that `STAGE` names. A small model fits in one call: `STAGE = "all"`. Then
`document_save`.

## Expression values

```python
import math
import FreeCAD as App

STAGE = globals().get("STAGE", "all")
PARK_Z = -1000.0                          # base z of a tool that must cut nothing

def _num(x):
    s = f"{float(x):.10g}"
    return f"({s})" if s.startswith("-") else s

class E:
    """Expression text plus its current value."""
    __slots__ = ("s", "v")
    def __init__(self, s, v): self.s, self.v = s, v
    def __add__(a, b): b = w(b); return E(f"({a.s} + {b.s})", a.v + b.v)
    def __radd__(a, b): return w(b) + a
    def __sub__(a, b): b = w(b); return E(f"({a.s} - {b.s})", a.v - b.v)
    def __rsub__(a, b): return w(b) - a
    def __mul__(a, b): b = w(b); return E(f"({a.s} * {b.s})", a.v * b.v)
    def __rmul__(a, b): return w(b) * a
    def __truediv__(a, b): b = w(b); return E(f"({a.s} / {b.s})", a.v / b.v)
    def __rtruediv__(a, b): return w(b) / a
    def __neg__(a): return E(f"(-{a.s})", -a.v)

def w(x):
    return x if isinstance(x, E) else E(_num(x), float(x))

def gt(a, b): a, b = w(a), w(b); return E(f"({a.s} > {b.s})", float(a.v > b.v))
def lt(a, b): a, b = w(a), w(b); return E(f"({a.s} < {b.s})", float(a.v < b.v))
def eq(a, b): a, b = w(a), w(b); return E(f"({a.s} == {b.s})", float(a.v == b.v))
def ife(c, a, b): a, b = w(a), w(b); return E(f"({c.s} ? {a.s} : {b.s})", a.v if c.v else b.v)
def emin(a, b): a, b = w(a), w(b); return E(f"min({a.s}, {b.s})", min(a.v, b.v))
def emax(a, b): a, b = w(a), w(b); return E(f"max({a.s}, {b.s})", max(a.v, b.v))
def esqrt(a): a = w(a); return E(f"sqrt({a.s})", math.sqrt(a.v))
def ecos(a): a = w(a); return E(f"cos({a.s})", math.cos(math.radians(a.v)))     # degrees
def esin(a): a = w(a); return E(f"sin({a.s})", math.sin(math.radians(a.v)))     # degrees
def eatan2(y, x): y, x = w(y), w(x); return E(f"atan2({y.s}, {x.s})", math.degrees(math.atan2(y.v, x.v)))
```

| Source | Generator |
| --- | --- |
| `x if cond else y` | `ife(cond, x, y)` |
| `if a < b:` that decides whether a tool exists | `at=(x, y, ife(lt(a, b), z, PARK_Z))` |
| `if FASTEN == "insert"` | `eq(P.FASTEN, 0)` (enumeration index) |
| `min(a, b)` | `emin(a, b)` |
| `for i in range(5)` | Python loop; the count is fixed until the next build |

A Python `if` that reads `.v` is fixed until the next build. Use it only for a choice that
changes the object count, and list it in the generator header.

## Parameters

```python
V = doc.getObject("Params")
if V is None:
    V = doc.addObject("App::VarSet", "Params")
    V.Label = "Params"

class _P: pass
P = _P()

def prm(name, val, group, tip=""):
    """Float variable: a number, or an expression (E) on other variables. A later stage
    reuses the existing variable and reads its current value."""
    if name not in V.PropertiesList:
        V.addProperty("App::PropertyFloat", name, group, tip)
        if isinstance(val, E):
            V.setExpression(name, val.s)
        else:
            setattr(V, name, float(val))
        value = w(val).v          # an expression is not evaluated before the next recompute
    else:
        value = float(getattr(V, name))
    setattr(P, name, E(f"Params.{name}", value))

def prm_bool(name, val, group, tip=""):
    if name not in V.PropertiesList:
        V.addProperty("App::PropertyBool", name, group, tip)
        setattr(V, name, bool(val))
    setattr(P, name, E(f"Params.{name}", float(getattr(V, name))))

def prm_enum(name, options, val, group, tip=""):
    """Text choice. Expressions compare the index (`eq(P.NAME, 0)`); a string compare such as
    `Params.NAME == <<insert>>` is always false and raises no error."""
    if name not in V.PropertiesList:
        V.addProperty("App::PropertyEnumeration", name, group, tip)
        setattr(V, name, list(options))
        setattr(V, name, val)
    setattr(P, name, E(f"Params.{name}", float(list(options).index(getattr(V, name)))))
```

`App::PropertyFloat` is unitless. Assigned to a length it reads as mm, to an angle as degrees.
A tuple constant becomes one variable per item: `RAIL_Z[1]` -> `prm("RAIL_Z_1", ...)`.

## Primitives

```python
def _set(o, prop, val):
    """Every size and position goes on the expression engine, a literal as a constant."""
    o.setExpression(prop, val.s if isinstance(val, E) else _num(val))

def _off(size, align):                         # build123d Align.CENTER / MIN / MAX
    return size / 2 if align == "C" else (0.0 if align == "MIN" else size)

def to_world(frame, x, y):
    """frame = (tx, ty, deg) about world z; each item a number or an E."""
    if frame is None:
        return w(x), w(y)
    tx, ty, d = frame
    c, s = ecos(d), esin(d)
    return w(tx) + w(x) * c - w(y) * s, w(ty) + w(x) * s + w(y) * c

def _place(o, base, frame=None, rot=None):
    if rot is not None:
        o.Placement = App.Placement(App.Vector(), rot)
    elif frame is not None:
        # Seed a non-zero angle so the axis is z before the expression drives it (checked:
        # the axis stays z through 0 and negative angles).
        o.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), w(frame[2]).v or 90.0))
        _set(o, "Placement.Rotation.Angle", w(frame[2]))
    x, y = to_world(frame, base[0], base[1])
    _set(o, "Placement.Base.x", x)
    _set(o, "Placement.Base.y", y)
    _set(o, "Placement.Base.z", base[2])

def box(sx, sy, sz, at=(0, 0, 0), align=("C", "C", "C"), frame=None, label="box"):
    o = doc.addObject("Part::Box", "Box")
    o.Label = label
    _set(o, "Length", sx); _set(o, "Width", sy); _set(o, "Height", sz)
    size = (w(sx), w(sy), w(sz))
    base = tuple(w(at[i]) - _off(size[i], align[i]) for i in range(3))
    _place(o, base, frame)
    return o

# Fixed rotation turning the cylinder's local +z to the named world axis.
_AXIS = {"z": (None, (0, 0, 1)),
         "y": (App.Rotation(App.Vector(1, 0, 0), -90), (0, 1, 0)),
         "-y": (App.Rotation(App.Vector(1, 0, 0), 90), (0, -1, 0)),
         "x": (App.Rotation(App.Vector(0, 1, 0), 90), (1, 0, 0))}

def cyl(r, h, at=(0, 0, 0), align="MIN", axis="z", frame=None, label="cyl"):
    """Cylinder centered on its axis; `align` places `at` on the axis (MIN: the start face).
    build123d `Cylinder(r, h, rotation=..., align=...)` aligns before it rotates, so
    `_cyl_y` (rotation (-90, 0, 0), align MIN) is `cyl(r, h, at, "MIN", axis="y")` and
    `_cyl_x` (rotation (0, 90, 0), align CENTER) is `cyl(r, h, at, "C", axis="x")`."""
    rot, d = _AXIS[axis]
    assert frame is None or axis == "z"
    o = doc.addObject("Part::Cylinder", "Cylinder")
    o.Label = label
    _set(o, "Radius", r); _set(o, "Height", h)
    k = _off(w(h), align)
    _place(o, tuple(w(at[i]) - k * d[i] for i in range(3)), frame, rot)
    return o

def cone(r1, r2, h, at=(0, 0, 0), frame=None, label="cone"):
    """Radius1 at the bottom, Radius2 at the top. r1 == r2 is valid (a cylinder)."""
    o = doc.addObject("Part::Cone", "Cone")
    o.Label = label
    _set(o, "Radius1", r1); _set(o, "Radius2", r2); _set(o, "Height", h)
    _place(o, tuple(w(a) for a in at), frame)
    return o

def taper_z(z0, h, bottom, top, label="taper"):
    """`loft` between two rectangles normal to z: `bottom` at z0, `top` at z0 + h, each
    ((x_min, x_max), (y_min, y_max)) in world coordinates. A Part::Wedge rotated so its
    local Y is world z and its local Z is world -y."""
    o = doc.addObject("Part::Wedge", "Wedge")
    o.Label = label
    (bx, by), (tx, ty) = bottom, top
    _set(o, "Ymin", 0.0); _set(o, "Ymax", h)
    _set(o, "Xmin", bx[0]); _set(o, "Xmax", bx[1])
    _set(o, "X2min", tx[0]); _set(o, "X2max", tx[1])
    _set(o, "Zmin", -w(by[1])); _set(o, "Zmax", -w(by[0]))
    _set(o, "Z2min", -w(ty[1])); _set(o, "Z2max", -w(ty[0]))
    _place(o, (0.0, 0.0, z0), rot=App.Rotation(App.Vector(1, 0, 0), 90))
    return o
```

A `taper_z` whose `bottom` is larger than its `top` tapers upward; swap them for a downward
taper with `z0` at the lower rectangle. One end may be a line (zero width) for a triangular
prism.

## Booleans in source order

```python
def fuse(objs, label):
    if len(objs) == 1:
        return objs[0]
    o = doc.addObject("Part::MultiFuse", "Fusion")
    o.Label = label; o.Shapes = objs; o.Refine = True
    return o

def cut(base, tools, label):
    o = doc.addObject("Part::Cut", "Cut")
    o.Label = label; o.Base = base; o.Tool = fuse(tools, label + "_tools"); o.Refine = True
    return o

class Solid:
    """`body += a` -> add(a); `body -= b` -> sub(b). Consecutive same ops share one step."""
    def __init__(self, base, label):
        self.cur, self.label, self.mode, self.pending, self.n = base, label, None, [], 0
    def _flush(self):
        if not self.pending:
            return
        self.n += 1
        name = f"{self.label}_step{self.n}"
        self.cur = (fuse([self.cur] + self.pending, name) if self.mode == "add"
                    else cut(self.cur, self.pending, name))
        self.pending = []
    def _op(self, mode, objs):
        if self.mode != mode:
            self._flush()
            self.mode = mode
        self.pending.extend(objs)
    def add(self, *objs): self._op("add", objs)
    def sub(self, *objs): self._op("sub", objs)
    def done(self):
        self._flush()
        self.cur.Label = self.label
        return self.cur
```

A nested source expression that contains a subtraction is its own `Solid`. A union-only
helper (`return block + loft`) needs none: add its pieces to the body directly
(`body.add(block, taper)`), because a union does not depend on grouping.
`body += (post + lips) - slot` becomes:

```python
guide = Solid(post, "guide_L")
guide.add(lips)
guide.sub(slot)
body.add(guide.done())          # slot cuts the guide only, never the body
```

Hide every primitive and intermediate step; show only the finished parts:

```python
def show_only(*keep):
    for o in doc.Objects:
        if hasattr(o, "Visibility") and o.TypeId != "App::VarSet":
            o.Visibility = o in keep
```

The generator ends with `params()`, then the part functions that `STAGE` selects, then
`show_only(...)` on the finished parts that exist.
