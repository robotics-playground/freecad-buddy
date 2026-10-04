"""TC-04 helpers on top of tc03lib: generic fully constrained profiles, feature_state readers."""

from tc03lib import *  # noqa: F401,F403
from tc03lib import EVIDENCE, Log, Mcp, cua, fitall, ids, json, mut, pv, sc, shot, short, snap_temp  # noqa: F401

MM = "mm"


def q(value, unit="mm"):
    return {"value": value, "unit": unit}


def sel(obj, name=None):
    out = {"kind": "mapped_name", "object": obj}
    if name is not None:
        out["mapped_name"] = name
    return out


def rect_profile(x0, y0, w, h):
    """Rectangle with lower-left corner (x0, y0), fully constrained against the sketch root."""
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    geometry = [{"kind": "line_segment", "start": list(pts[i]), "end": list(pts[(i + 1) % 4])} for i in range(4)]
    constraints = [
        {"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)
    ] + [
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(w)},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(h)},
    ]
    if x0 == 0 and y0 == 0:
        constraints.append({"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1})
    else:
        constraints.append({"type": "DistanceX", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": q(x0)})
        constraints.append({"type": "DistanceY", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": q(y0)})
    return geometry, constraints


def point_profile(x, y):
    geometry = [{"kind": "point", "center": [x, y]}]
    constraints = [
        {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": q(x)},
        {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": q(y)},
    ]
    return geometry, constraints


def circle_profile(x, y, r):
    geometry = [{"kind": "circle", "center": [x, y], "radius": q(r)}]
    if x == 0 and y == 0:
        constraints = [{"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1}]
    else:
        constraints = [
            {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 0, "second_pos": 3, "value": q(x)},
            {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 0, "second_pos": 3, "value": q(y)},
        ]
    constraints.append({"type": "Radius", "first": 0, "value": q(r)})
    return geometry, constraints


async def sketch(m, doc, name, body, profile, plane="XY", face=None):
    args = {"doc": doc, "name": name, "body": body}
    if face is not None:
        args["face"] = face
    else:
        args["plane"] = plane
    created = await m.call("sketch_create", args)
    geometry, constraints = profile
    added = await m.call("sketch_add_geometry", {"doc": doc, "sketch": name, "geometry": geometry,
                                                 "constraints": constraints})
    return created, added


async def body_pad(m, doc, body, profile_name, pad_name, profile, length, plane="XY", **extra):
    await m.call("feature_body_create", {"doc": doc, "name": body})
    await sketch(m, doc, profile_name, body, profile, plane=plane)
    args = {"doc": doc, "body": body, "profile": profile_name, "name": pad_name, "length": q(length)}
    args.update(extra)
    return await m.call("feature_pad", args)


def fs(envelope):
    return sc(envelope).get("feature_state") or {}


def ss(envelope):
    return fs(envelope).get("shape_summary") or {}


def ok_commit(envelope):
    return envelope.get("status") == "OK" and mut(envelope).get("rolled_back") is False


def near(actual, expected, rel=0.001):
    try:
        return abs(float(actual) - expected) <= abs(expected) * rel
    except (TypeError, ValueError):
        return False


def vol(envelope):
    s = sc(envelope)
    v = s.get("volume")
    if isinstance(v, dict):
        return v.get("value")
    return v


def detail_msg(envelope):
    d = envelope.get("detail")
    if isinstance(d, dict):
        return d.get("message") or ""
    return str(d or envelope.get("_raw") or "")


def tree_names(envelope):
    return json.dumps(sc(envelope))


async def capture(m, doc, png):
    fit = await m.fit(doc)
    import time as _t
    _t.sleep(1.0)
    rec = shot(png)
    m.log.write({"capture": png, "fit": fit, "shot": rec})
    return fit, rec


WORKDIR_TMP = "C:/Users/thuan/freecad-buddy-workdir/tmp"


def snaps():
    """Snapshot dirs in both places: $TEMP (what the TC names) and the bridge workdir (where snapshot_path points)."""
    import glob as _g
    import os as _o
    temp = _o.environ.get("TEMP") or ""
    return sorted(_g.glob(_o.path.join(temp, "FCB_TMP_snap_*")) + _g.glob(WORKDIR_TMP + "/FCB_TMP_snap_*"))
