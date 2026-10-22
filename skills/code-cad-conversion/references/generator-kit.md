# Generator kit

Copy this into the generator file, then add the part functions under it. The file runs inside
the live FreeCAD through `script_exec` (`doc` injected) or headless through `freecadcmd` on a
closed document.

## Run it

`script_exec` on the live document. Keep the generator on disk, so each call is short:

```python
p = r"D:/path/to/build_fcstd.py"
doc.openTransaction("build parametric model")
try:
    for o in list(doc.Objects):        # only on a document this generator owns
        doc.removeObject(o.Name)
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"),
         {"doc": doc, "__name__": "fcb_build"})
    doc.recompute()
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise
result = [(o.Name, o.Label, o.State) for o in doc.Objects if "Invalid" in o.State]
```

Then `document_save`. When one build needs more than the 30 s budget, split the generator into
stages (parameters, then one part per call), or let the script append to a log file that ends
with `done` and poll the file.

## Expression values

```python
import math
import FreeCAD as App

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
def ife(c, a, b): a, b = w(a), w(b); return E(f"({c.s} ? {a.s} : {b.s})", a.v if c.v else b.v)
def emin(a, b): a, b = w(a), w(b); return E(f"min({a.s}, {b.s})", min(a.v, b.v))
def emax(a, b): a, b = w(a), w(b); return E(f"max({a.s}, {b.s})", max(a.v, b.v))
def esqrt(a): a = w(a); return E(f"sqrt({a.s})", math.sqrt(a.v))
def ecos(a): a = w(a); return E(f"cos({a.s})", math.cos(math.radians(a.v)))     # degrees
def esin(a): a = w(a); return E(f"sin({a.s})", math.sin(math.radians(a.v)))     # degrees
def eatan2(y, x): y, x = w(y), w(x); return E(f"atan2({y.s}, {x.s})", math.degrees(math.atan2(y.v, x.v)))
```

`x if cond else y` in the source becomes `ife(cond, x, y)`. A Python `if` on a parameter stays a
Python `if` only for a structural choice; it then reads `.v` and is fixed until the next build.

## Parameters

```python
V = doc.addObject("App::VarSet", "Params")
V.Label = "Params"

class _P: pass
P = _P()

def prm(name, val, group, tip=""):
    """Float variable: a number, or an expression (E) on other variables."""
    V.addProperty("App::PropertyFloat", name, group, tip)
    if isinstance(val, E):
        V.setExpression(name, val.s)
    else:
        setattr(V, name, float(val))
    e = E(f"Params.{name}", w(val).v)
    setattr(P, name, e)
    return e

def prm_bool(name, val, group, tip=""):
    V.addProperty("App::PropertyBool", name, group, tip)
    setattr(V, name, bool(val))
    e = E(f"Params.{name}", float(val))
    setattr(P, name, e)
    return e
```

`App::PropertyFloat` is unitless. Assigned to a length it reads as mm, to an angle as degrees.

## Primitives

```python
def _set(o, prop, val):
    if isinstance(val, E):
        o.setExpression(prop, val.s)
    elif prop.startswith("Placement."):
        o.setExpression(prop, _num(val))
    else:
        setattr(o, prop, float(val))

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

def cyl(r, h, at=(0, 0, 0), align="MIN", frame=None, label="cyl"):
    """Z-axis cylinder; `align` is the z alignment (x, y are centered, as build123d)."""
    o = doc.addObject("Part::Cylinder", "Cylinder")
    o.Label = label
    _set(o, "Radius", r); _set(o, "Height", h)
    _place(o, (w(at[0]), w(at[1]), w(at[2]) - _off(w(h), align)), frame)
    return o

def cone(r1, r2, h, at=(0, 0, 0), frame=None, label="cone"):
    """Radius1 at the bottom, Radius2 at the top. r1 == r2 is valid (a cylinder)."""
    o = doc.addObject("Part::Cone", "Cone")
    o.Label = label
    _set(o, "Radius1", r1); _set(o, "Radius2", r2); _set(o, "Height", h)
    _place(o, tuple(w(a) for a in at), frame)
    return o
```

A cylinder on another axis: set a fixed `rot` (`App.Rotation(App.Vector(1, 0, 0), -90)` turns
local +z to world +y) and pass the base point through `_place(o, base, rot=...)`.

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

Hide every primitive and intermediate step; show only the finished parts:

```python
def show_only(*keep):
    for o in doc.Objects:
        if hasattr(o, "Visibility") and o.TypeId != "App::VarSet":
            o.Visibility = o in keep

show_only(bracket)            # last line of the generator
```
