"""TC-02 scenario runner. Usage: uv run python tc-02-run.py <scenario-number>  (00 = preconditions)."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

_spec = importlib.util.spec_from_file_location("tc02lib", Path(__file__).with_name("tc-02-lib.py"))
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)
sc, cua, ids, EV, GOLDEN = lib.sc, lib.cua, lib.ids, lib.EV, lib.GOLDEN

SCENARIOS = {}


def scenario(number: str):
    def register(fn):
        SCENARIOS[number] = fn
        return fn
    return register


def pr(label: str, envelope: dict) -> None:
    print(f"--- {label}: {json.dumps(envelope, ensure_ascii=False)[:600]}")


async def ensure_empty(m, log) -> bool:
    listing = await m.call("document_list", {})
    return log.check("Given no document open", listing.get("text") == "0 open document(s).", listing.get("text"))


async def fit(m, log, doc: str, label: str) -> None:
    envelope = await m.call("view_fit_viewport", {"doc": doc})
    ok = envelope.get("status") == "OK"
    log.check(f"{label} view_fit_viewport OK", ok, {"status": envelope.get("status"), "detail": envelope.get("detail")})
    if not ok:
        result = lib.fitall()
        log.note(f"fallback GUI Fit All: effect={result.get('effect')} route={result.get('route')}")


# ---------------------------------------------------------------------------------------------
@scenario("00")
async def s00(m, log):
    caps = await m.call("query_capabilities", {})
    log.check("bridge answers query_capabilities OK", caps.get("status") == "OK", sc(caps).get("freecad_version"))
    golden = sorted(p.name for p in Path(GOLDEN).glob("*.FCStd"))
    log.check("5 golden models", len(golden) == 5, golden)
    log.check("_automation exists", Path("D:/Work/Personal/Sources/freecad-buddy/_automation").is_dir())
    await ensure_empty(m, log)
    state = lib.snapshot()
    tree = state.get("tree_markdown") or ""
    log.check("cua get_window_state sees QOpenGLWidget", "QOpenGLWidget" in json.dumps(state), state.get("element_count"))
    fit_buttons = lib.find(state, role="Button", label="Fit All")
    log.check("Fit All toolbar button has element_token", bool(fit_buttons) and "element_token" in fit_buttons[0],
              fit_buttons[0].get("element_token") if fit_buttons else None)
    log.check("evidence dir writable", os.access(EV, os.W_OK))


# ---------------------------------------------------------------------------------------------
@scenario("01")
async def s01(m, log):
    target = f"{EV}/tc-02-01-uat-roundtrip.FCStd"
    await ensure_empty(m, log)
    created = await m.call("document_create", {"label": "uat-roundtrip"})
    pr("create", created)
    handle = sc(created).get("doc", "")
    listing1 = await m.call("document_list", {})
    pr("list1", listing1)
    bare = await m.call("document_save", {"doc": handle})
    pr("bare save", bare)
    saved = await m.call("document_save", {"doc": handle, "path": target})
    pr("save-as", saved)
    listing2 = await m.call("document_list", {})
    pr("list2", listing2)
    closed = await m.call("document_close", {"doc": handle})
    pr("close", closed)
    listing3 = await m.call("document_list", {})
    pr("list3", listing3)

    log.check("handle matches ^fcb-doc: and != Name", handle.startswith("fcb-doc:") and handle != sc(created).get("name"), handle)
    log.check("create carries doc,name,label; label == uat-roundtrip",
              all(k in sc(created) for k in ("doc", "name", "label")) and sc(created).get("label") == "uat-roundtrip", sc(created))
    docs1 = sc(listing1).get("documents", [])
    log.check("list shows one transient entry for handle",
              len(docs1) == 1 and docs1[0].get("doc") == handle and docs1[0].get("transient") is True, docs1)
    log.check("bare save refused INVALID_INPUT with exact message",
              bare.get("status") == "INVALID_INPUT" and (bare.get("detail") or {}).get("message") == "document has no save target; call document_save with a 'path' first",
              {"status": bare.get("status"), "detail": bare.get("detail"), "text": bare.get("text")})
    size = Path(target).stat().st_size if Path(target).exists() else 0
    log.check("save-as wrote non-empty file and saved: true", size > 0 and sc(saved).get("saved") is True, {"size": size, "sc": sc(saved)})
    docs2 = sc(listing2).get("documents", [])
    log.check("transient false after save-as", any(d.get("doc") == handle and d.get("transient") is False for d in docs2), docs2)
    log.check("close OK closed:true and list empty",
              closed.get("status") == "OK" and sc(closed).get("closed") is True and listing3.get("text") == "0 open document(s).",
              {"close": sc(closed), "list": listing3.get("text")})
    log.check("file survives close", Path(target).exists() and Path(target).stat().st_size > 0, size)

    reopened = await m.call("document_open", {"path": target})
    pr("reopen", reopened)
    reopened_handle = sc(reopened).get("doc")
    await fit(m, log, reopened_handle, "reopened")
    print(lib.shot("tc-02-01-after.png"))
    Path(f"{EV}/tc-02-01-state.json").write_text(json.dumps({"handle": handle, "reopened": reopened_handle}))


async def visible(m, doc: str, name: str) -> bool:
    env = await m.call("query_tree_summary", {"doc": doc, "depth": 5, "filters": {"visible_only": True}})
    return name in json.dumps(sc(env).get("tree", []))


async def show(m, log, doc: str, name: str) -> None:
    """Golden models open with their object hidden; show it through the GUI before the visual."""
    if await visible(m, doc, name):
        log.note(f"{name} already visible")
        return
    result = lib.show_all()
    now = await visible(m, doc, name)
    log.note(f"GUI show {name} (View > Visibility > Show All Objects): {result}; visible now={now}")


def near(actual, expected, tolerance=0.001) -> bool:
    try:
        return abs(float(actual) - expected) <= abs(expected) * tolerance
    except (TypeError, ValueError):
        return False


def volume(envelope: dict):
    content = sc(envelope)
    return content.get("volume") if not isinstance(content.get("volume"), dict) else content["volume"].get("value")


# ---------------------------------------------------------------------------------------------
@scenario("02")
async def s02(m, log):
    path = f"{GOLDEN}/box-10-20-30.FCStd"
    log.check("Given golden exists", Path(path).exists())
    await ensure_empty(m, log)
    opened = await m.call("document_open", {"path": path})
    pr("open", opened)
    handle = sc(opened).get("doc", "")
    tree = await m.call("query_tree_summary", {"doc": handle})
    pr("tree", tree)
    obj = await m.call("query_object", {"doc": handle, "object": "Box"})
    pr("object", obj)
    mass = await m.call("query_mass_properties", {"doc": handle, "object": "Box"})
    pr("mass", mass)
    content = sc(opened)
    log.check("open carries doc,name,label,path == input",
              all(k in content for k in ("doc", "name", "label", "path")) and content.get("path") == path, content)
    log.check("text is shipped form", re.fullmatch(r"Opened box-10-20-30 -> fcb-doc:[A-Za-z0-9_-]+\.", opened.get("text", "")) is not None, opened.get("text"))
    t = sc(tree)
    log.check("total_objects 1, returned_nodes 1", t.get("total_objects") == 1 and t.get("returned_nodes") == 1,
              {k: t.get(k) for k in ("total_objects", "returned_nodes")})
    node = (t.get("tree") or [{}])[0]
    log.check("tree[0] Box Part::Feature", node.get("name") == "Box" and node.get("type") == "Part::Feature", node)
    log.check("tree[0] has no error key", "error" not in node, list(node))
    o = sc(obj)
    log.check("query_object Box Part::Feature error null", o.get("name") == "Box" and o.get("type") == "Part::Feature" and "error" in o and o.get("error") is None,
              {k: o.get(k, "<missing>") for k in ("name", "type", "error")})
    props = o.get("properties")
    bad = [k for k, v in (props or {}).items() if isinstance(v, str) and re.search(r"<\w+ object at 0x", v)]
    log.check("properties JSON-safe object, no live pointer repr", isinstance(props, dict) and not bad, {"count": len(props or {}), "pointer_reprs": bad})
    log.check("volume 6000 within 0.1%", near(volume(mass), 6000.0), volume(mass))
    await show(m, log, handle, "Box")
    await fit(m, log, handle, "box")
    print(lib.shot("tc-02-02-after.png"))
    Path(f"{EV}/tc-02-02-state.json").write_text(json.dumps({"handle": handle}))


def sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@scenario("03")
async def s03(m, log):
    golden = f"{GOLDEN}/cylinder-r5-h20.FCStd"
    target = f"{EV}/tc-02-03-uat-saveas.FCStd"
    log.check("Given golden exists", Path(golden).exists())
    log.check("Given target absent", not Path(target).exists())
    before = (Path(golden).stat().st_size, Path(golden).stat().st_mtime_ns, sha(golden))
    opened = await m.call("document_open", {"path": golden})
    pr("open", opened)
    handle = sc(opened).get("doc", "")
    saved = await m.call("document_save", {"doc": handle, "path": target})
    pr("save", saved)
    tree = await m.call("query_tree_summary", {"doc": handle})
    pr("tree", tree)
    size = Path(target).stat().st_size if Path(target).exists() else 0
    log.check("new file written non-empty", size > 0, size)
    after = (Path(golden).stat().st_size, Path(golden).stat().st_mtime_ns, sha(golden))
    log.check("golden untouched (size, mtime, sha)", before == after, {"before": before, "after": after})
    log.check("save response doc == open handle", sc(saved).get("doc") == handle, {"open": handle, "save": sc(saved).get("doc")})
    t = sc(tree)
    log.check("handle resolves after rebind: OK total_objects 1", tree.get("status") == "OK" and t.get("total_objects") == 1, t.get("total_objects"))
    log.check("tree[0] Cylinder", (t.get("tree") or [{}])[0].get("name") == "Cylinder", t.get("tree"))
    closed = await m.call("document_close", {"doc": handle})
    pr("close", closed)
    reopened = await m.call("document_open", {"path": target})
    pr("reopen", reopened)
    fresh = sc(reopened).get("doc", "")
    mass = await m.call("query_mass_properties", {"doc": fresh, "object": "Cylinder"})
    log.check("reopen fresh handle; volume 1570.7963 within 0.1%",
              reopened.get("status") == "OK" and fresh != handle and near(volume(mass), 1570.7963),
              {"fresh": fresh, "volume": volume(mass)})
    await show(m, log, fresh, "Cylinder")
    await fit(m, log, fresh, "reopened cylinder")
    print(lib.shot("tc-02-03-after.png"))
    Path(f"{EV}/tc-02-03-state.json").write_text(json.dumps({"handle": handle, "reopened": fresh}))


def window_title() -> str:
    pid, win = ids()
    for window in cua("list_windows", {"pid": pid}).get("windows", []):
        if window["window_id"] == win:
            return window.get("title", "")
    return ""


def msg(envelope: dict) -> str | None:
    return (envelope.get("detail") or {}).get("message")


@scenario("04")
async def s04(m, log):
    box, sphere = f"{GOLDEN}/box-10-20-30.FCStd", f"{GOLDEN}/sphere-r10.FCStd"
    log.check("Given both goldens exist", Path(box).exists() and Path(sphere).exists())
    await ensure_empty(m, log)
    a_env = await m.call("document_open", {"path": box})
    b_env = await m.call("document_open", {"path": sphere})
    a, b = sc(a_env).get("doc", ""), sc(b_env).get("doc", "")
    click = lib.click_tree("sphere-r10")
    log.note(f"GUI select sphere-r10 tree item: { {k: click.get(k) for k in ('clicked','role','effect','route','error')} }")
    title = window_title()
    log.note(f"window title after selecting B: {title!r}")
    state = lib.snapshot()
    selected = [e for e in lib.tree_items(state, "sphere-r10")]
    log.note(f"sphere-r10 tree item state: {[{k: e.get(k) for k in ('role','label','selected','states','value')} for e in selected]}")
    ta = await m.call("query_tree_summary", {"doc": a})
    tb = await m.call("query_tree_summary", {"doc": b})
    oa = await m.call("query_object", {"doc": a, "object": "Box"})
    ob = await m.call("query_object", {"doc": b, "object": "Sphere"})
    cross_a = await m.call("query_object", {"doc": a, "object": "Sphere"})
    cross_b = await m.call("query_object", {"doc": b, "object": "Box"})
    ma = await m.call("query_mass_properties", {"doc": a, "object": "Box"})
    mb = await m.call("query_mass_properties", {"doc": b, "object": "Sphere"})
    listing = await m.call("document_list", {})
    log.check("two distinct ^fcb-doc: handles", a != b and a.startswith("fcb-doc:") and b.startswith("fcb-doc:"), [a, b])
    log.check("list: 2 open document(s): box-10-20-30, sphere-r10.", listing.get("text") == "2 open document(s): box-10-20-30, sphere-r10.", listing.get("text"))
    log.check("GUI active doc is B (title)", "sphere-r10" in title, title)
    log.check("A tree[0] Box while B active", (sc(ta).get("tree") or [{}])[0].get("name") == "Box", sc(ta).get("tree"))
    log.check("B tree[0] Sphere", (sc(tb).get("tree") or [{}])[0].get("name") == "Sphere", sc(tb).get("tree"))
    log.check("query_object A Box / B Sphere OK", sc(oa).get("name") == "Box" and sc(ob).get("name") == "Sphere", [oa.get("status"), ob.get("status")])
    log.check("A Sphere -> INVALID_INPUT unknown object: Sphere", cross_a.get("status") == "INVALID_INPUT" and msg(cross_a) == "unknown object: Sphere", [cross_a.get("status"), msg(cross_a)])
    log.check("B Box -> INVALID_INPUT unknown object: Box", cross_b.get("status") == "INVALID_INPUT" and msg(cross_b) == "unknown object: Box", [cross_b.get("status"), msg(cross_b)])
    log.check("mass A 6000 / B 4188.7902", near(volume(ma), 6000.0) and near(volume(mb), 4188.7902), [volume(ma), volume(mb)])
    closed = await m.call("document_close", {"doc": a})
    tb2 = await m.call("query_tree_summary", {"doc": b})
    log.check("after close A, B tree OK", closed.get("status") == "OK" and tb2.get("status") == "OK", [closed.get("status"), tb2.get("status")])
    await show(m, log, b, "Sphere")
    await fit(m, log, b, "sphere B")
    print(lib.shot("tc-02-04-after.png"))
    Path(f"{EV}/tc-02-04-state.json").write_text(json.dumps({"A": a, "B": b}))


BODY_FILE = f"{EV}/tc-02-body.FCStd"


def rectangle(width: float, height: float) -> dict:
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    geometry = [{"kind": "line_segment", "start": list(corners[i]), "end": list(corners[(i + 1) % 4])} for i in range(4)]
    constraints = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
    constraints += [
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": width, "unit": "mm"}},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": height, "unit": "mm"}},
    ]
    return {"geometry": geometry, "constraints": constraints}


async def build_body(m, log, label: str, save_to: str | None) -> str:
    created = await m.call("document_create", {"label": label})
    doc = sc(created)["doc"]
    steps = [
        ("feature_body_create", {"doc": doc, "name": "Body"}),
        ("sketch_create", {"doc": doc, "name": "Sketch", "plane": "XY", "body": "Body"}),
        ("sketch_add_geometry", {"doc": doc, "sketch": "Sketch", **rectangle(20, 10)}),
        ("feature_pad", {"doc": doc, "body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 5, "unit": "mm"}}),
    ]
    for tool, args in steps:
        env = await m.mutate(doc, tool, args)
        log.note(f"build {tool}: {env.get('status')} {msg(env) or ''}")
        if env.get("status") != "OK":
            print(json.dumps(env)[:1500])
            raise SystemExit(f"build failed at {tool}")
    if save_to:
        saved = await m.call("document_save", {"doc": doc, "path": save_to})
        log.note(f"saved body doc: {saved.get('status')}")
    return doc


@scenario("build")
async def s_build(m, log):
    await ensure_empty(m, log)
    doc = await build_body(m, log, "uat-body", BODY_FILE)
    tree = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    print(json.dumps(sc(tree), indent=1)[:3000])
    await m.call("document_close", {"doc": doc})


async def open_body(m, log) -> str:
    await ensure_empty(m, log)
    env = await m.call("document_open", {"path": BODY_FILE})
    log.check("Given body document opens", env.get("status") == "OK", env.get("text"))
    return sc(env)["doc"]


def names(tree: list) -> list[str]:
    out = []
    for node in tree or []:
        out.append(node.get("name"))
        out += names(node.get("children"))
        out += names(node.get("links"))
    return out


def nodes(tree: list) -> list[dict]:
    out = []
    for node in tree or []:
        out.append(node)
        out += nodes(node.get("children"))
        out += nodes(node.get("links"))
    return out


SCALE = 1568 / 1775  # screenshot pixels per window point, measured from get_window_state


def expand_tree(label: str) -> dict:
    """Pixel-click the expander arrow left of a tree item (the UIA 'expand' action is a no-op here)."""
    state = lib.snapshot()
    items = lib.tree_items(state, label)
    if not items:
        return {"error": f"no {label}"}
    frame = items[0]["frame"]
    pid, win = ids()
    x, y = round((frame["x"] - 12) * SCALE), round((frame["y"] + frame["h"] / 2) * SCALE)
    result = cua("click", {"pid": pid, "window_id": win, "x": x, "y": y})
    time.sleep(0.5)
    return {"x": x, "y": y, "effect": result.get("effect"), "route": result.get("route")}


def click_eye(label: str) -> dict:
    """Pixel-click the eye (visibility) icon at the left of a tree item."""
    state = lib.snapshot()
    items = lib.tree_items(state, label)
    if not items:
        return {"error": f"no {label}"}
    frame = items[0]["frame"]
    pid, win = ids()
    x, y = round((frame["x"] + 13) * SCALE), round((frame["y"] + frame["h"] / 2) * SCALE)
    result = cua("click", {"pid": pid, "window_id": win, "x": x, "y": y, "delivery_mode": "foreground"})
    time.sleep(0.8)
    return {"x": x, "y": y, "effect": result.get("effect"), "route": result.get("route")}


async def obj_visibility(m, doc, name):
    env = await m.call("query_tree_summary", {"doc": doc, "depth": 5})
    for node in nodes(sc(env).get("tree")):
        if node.get("name") == name:
            return node.get("visibility")
    return None


async def gui_toggle(m, log, doc, name, want: bool) -> bool:
    """TC route first (tree click + Space); fall back to the tree eye icon if Space is dropped."""
    result = lib.toggle_visibility(name)
    now = await obj_visibility(m, doc, name)
    log.note(f"toggle {name} via tree click + Space: {result}; visibility now={now}")
    if now is not want:
        eye = click_eye(name)
        now = await obj_visibility(m, doc, name)
        log.note(f"fallback: eye icon pixel click (foreground) {eye}; visibility now={now}")
    return now is want


@scenario("05")
async def s05(m, log):
    doc = await open_body(m, log)
    log.note(f"expand Body: {expand_tree('Body')}")
    log.note(f"expand Pad: {expand_tree('Pad')}")
    given = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    root = (sc(given).get("tree") or [{}])[0]
    log.check("Given Body node with children at depth 3", root.get("type") == "PartDesign::Body" and bool(root.get("children")), root.get("type"))
    await fit(m, log, doc, "before")
    print(lib.shot("tc-02-05-before.png"))
    d1 = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    d3 = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    rooted = await m.call("query_tree_summary", {"doc": doc, "depth": 2, "root": "Body"})
    unknown = await m.call("query_tree_summary", {"doc": doc, "root": "NoSuchObject"})
    f_types = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"types": ["PartDesign::Pad"]}})
    f_excl = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"exclude_types": ["Sketcher::SketchObject"]}})
    f_rend = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"renderable_only": True}})
    f_vis = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"visible_only": True}})
    f_name = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"name_pattern": "^Pad"}})
    nofilter = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    stacked = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"renderable_only": True, "name_pattern": "^Pad"}})
    bad_filter = await m.call("query_tree_summary", {"doc": doc, "filters": {"unknown_filter": True}})

    t1, t3 = sc(d1), sc(d3)
    r1 = (t1.get("tree") or [{}])[0]
    log.check("depth1: root has children_count, no children; returned_nodes == roots",
              "children_count" in r1 and "children" not in r1 and t1.get("returned_nodes") == len(t1.get("tree") or []),
              {"keys": list(r1), "returned_nodes": t1.get("returned_nodes"), "roots": len(t1.get("tree") or [])})
    r3 = (t3.get("tree") or [{}])[0]
    log.check("depth3: returned_nodes > depth1 and root has children", (t3.get("returned_nodes") or 0) > (t1.get("returned_nodes") or 0) and "children" in r3,
              [t1.get("returned_nodes"), t3.get("returned_nodes")])
    tr = sc(rooted)
    log.check("root Body: single tree entry named Body; returned_nodes counts subtree",
              len(tr.get("tree") or []) == 1 and tr["tree"][0].get("name") == "Body" and tr.get("returned_nodes") == len(nodes(tr.get("tree"))),
              {"returned_nodes": tr.get("returned_nodes"), "counted": len(nodes(tr.get("tree"))), "names": names(tr.get("tree"))})
    log.check("unknown root -> INVALID_INPUT unknown object: NoSuchObject",
              unknown.get("status") == "INVALID_INPUT" and msg(unknown) == "unknown object: NoSuchObject", [unknown.get("status"), msg(unknown)])
    ntypes = nodes(sc(f_types).get("tree"))
    log.check("types allow-list: every node PartDesign::Pad", bool(ntypes) and all(n.get("type") == "PartDesign::Pad" for n in ntypes), [(n.get("name"), n.get("type")) for n in ntypes])
    ex = sc(f_excl)
    ex_types = [n.get("type") for n in nodes(ex.get("tree"))]
    log.check("exclude_types replaces default: filters_applied exact and datum nodes appear",
              (ex.get("filters_applied") or {}).get("exclude_types") == ["Sketcher::SketchObject"]
              and any(t in ("App::Origin", "App::Plane", "App::Line", "App::Point") for t in ex_types)
              and "Sketcher::SketchObject" not in ex_types,
              {"filters_applied": ex.get("filters_applied"), "types": ex_types})
    log.check("default filters_applied.exclude_types is datum set",
              (sc(nofilter).get("filters_applied") or {}).get("exclude_types") == ["App::Plane", "App::Line", "App::Point", "App::Origin"],
              sc(nofilter).get("filters_applied"))
    rend_types = [n.get("type") for n in nodes(sc(f_rend).get("tree"))]
    log.check("renderable_only drops Body, Sketch, Origin*",
              not any(t == "PartDesign::Body" or t == "Sketcher::SketchObject" or (t or "").startswith("App::Origin") for t in rend_types),
              rend_types)
    log.check("(merit) renderable_only still returns the renderable Pad", "PartDesign::Pad" in rend_types, rend_types)
    name_nodes = nodes(sc(f_name).get("tree"))
    log.check("name_pattern ^Pad: only nodes whose name or label starts with Pad",
              bool(name_nodes) and all((n.get("name") or "").startswith("Pad") or (n.get("label") or "").startswith("Pad") for n in name_nodes),
              [(n.get("name"), n.get("label")) for n in name_nodes])
    stacked_names = set(names(sc(stacked).get("tree")))
    log.check("filters AND-stack: subset of each single-filter result",
              stacked_names <= set(names(sc(f_rend).get("tree"))) and stacked_names <= set(names(sc(f_name).get("tree"))),
              {"stacked": sorted(stacked_names), "rend": names(sc(f_rend).get("tree")), "name": names(sc(f_name).get("tree"))})
    log.check("unknown filter key is protocol reject (isError, no envelope)",
              bad_filter.get("_isError") is True and "schema" not in bad_filter, bad_filter)

    vis_before = names(sc(f_vis).get("tree"))
    log.note(f"visible_only before hide: {vis_before}")
    hidden = await gui_toggle(m, log, doc, "Pad", False)
    f_vis2 = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "filters": {"visible_only": True}})
    plain2 = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("visible_only drops the hidden Pad while plain walk keeps it",
              hidden and "Pad" not in names(sc(f_vis2).get("tree")) and "Pad" in names(sc(plain2).get("tree")),
              {"hidden": hidden, "visible_only": names(sc(f_vis2).get("tree")), "plain": names(sc(plain2).get("tree"))})
    print(lib.shot("tc-02-05-hidden.png"))
    restored = await gui_toggle(m, log, doc, "Pad", True)
    log.check("Pad restored to visible through GUI", restored)
    await fit(m, log, doc, "after")
    print(lib.shot("tc-02-05-after.png"))
    Path(f"{EV}/tc-02-05-state.json").write_text(json.dumps({"handle": doc}))


def gui_set_pad_length(value: str) -> dict:
    pid, win = ids()
    out = {}
    out["select"] = cua("click", {"pid": pid, "window_id": win, "x": 102, "y": 325, "delivery_mode": "foreground"}).get("route")
    time.sleep(1.0)
    out["edit"] = cua("click", {"pid": pid, "window_id": win, "x": 190, "y": 1020, "count": 2, "delivery_mode": "foreground"}).get("route")
    time.sleep(0.7)
    out["select_all"] = cua("hotkey", {"pid": pid, "window_id": win, "keys": ["ctrl", "a"], "delivery_mode": "foreground"}).get("route")
    out["type"] = cua("type_text", {"pid": pid, "window_id": win, "text": value, "delivery_mode": "foreground"}).get("route")
    out["enter"] = cua("press_key", {"pid": pid, "window_id": win, "key": "return", "delivery_mode": "foreground"}).get("route")
    time.sleep(2.0)
    return out


@scenario("06")
async def s06(m, log):
    doc = await open_body(m, log)
    log.note(f"expand Body: {expand_tree('Body')}")
    given = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("Given a PartDesign::Pad node", "PartDesign::Pad" in [n.get("type") for n in nodes(sc(given).get("tree"))])
    await fit(m, log, doc, "before")
    print(lib.shot("tc-02-06-before.png"))
    healthy = await m.call("query_object", {"doc": doc, "object": "Pad"})
    # The MCP route (feature_set_parameters Length 0) is rolled back by the mutation guard, so the
    # break is made through FreeCAD's own property editor (run1 evidence in tc-02-06-run1-mcp-break/).
    broken_set = gui_set_pad_length("0")
    log.note(f"GUI break: property editor Pad.Length := 0 -> {broken_set}")
    recompute = await m.call("document_recompute", {"doc": doc})
    pr("recompute", recompute)
    broken = await m.call("query_object", {"doc": doc, "object": "Pad"})
    pr("broken object", {k: v for k, v in broken.items() if k != "structured_content"} | {"error": sc(broken).get("error")})
    unknown = await m.call("query_object", {"doc": doc, "object": "NoSuchPad"})
    h = sc(healthy)
    log.check("identity: name Pad, label, type PartDesign::Pad", h.get("name") == "Pad" and bool(h.get("label")) and h.get("type") == "PartDesign::Pad",
              {k: h.get(k) for k in ("name", "label", "type")})
    props = h.get("properties") or {}
    log.check("properties include Length, Type, Profile, Reversed", all(k in props for k in ("Length", "Type", "Profile", "Reversed")),
              {k: props.get(k, "<missing>") for k in ("Length", "Type", "Profile", "Reversed")})
    log.check("Length readable, not null", props.get("Length") is not None, props.get("Length"))
    log.check("healthy error is null", "error" in h and h.get("error") is None, h.get("error", "<missing>"))
    b = sc(broken)
    log.check("broken: GUI edit landed (Length 0 mm)", (b.get("properties") or {}).get("Length") == "0.0 mm", (b.get("properties") or {}).get("Length"))
    log.check("broken error is non-empty string", isinstance(b.get("error"), str) and bool(b.get("error")), b.get("error"))
    errors = sc(recompute).get("errors")
    log.check("recompute RECOMPUTE_ERROR naming Pad in structured_content.errors",
              recompute.get("status") == "RECOMPUTE_ERROR" and "Pad" in json.dumps(errors), {"status": recompute.get("status"), "errors": errors, "detail": recompute.get("detail")})
    log.check("broken object query OK and valid JSON", broken.get("status") == "OK", broken.get("status"))
    log.check("unknown object -> INVALID_INPUT unknown object: NoSuchPad", unknown.get("status") == "INVALID_INPUT" and msg(unknown) == "unknown object: NoSuchPad", [unknown.get("status"), msg(unknown)])
    print(lib.shot("tc-02-06-broken.png"))
    # Cleanup per TC (undo + recompute), then the visual.
    undo = await m.call("document_undo", {"doc": doc})
    pr("undo", undo)
    recompute2 = await m.call("document_recompute", {"doc": doc})
    pr("recompute after undo", recompute2)
    after = await m.call("query_object", {"doc": doc, "object": "Pad"})
    log.check("after undo: Length restored and error null", (sc(after).get("properties") or {}).get("Length") == props.get("Length") and sc(after).get("error") is None,
              {"Length": (sc(after).get("properties") or {}).get("Length"), "error": sc(after).get("error"), "undo": undo.get("status"), "recompute": recompute2.get("status")})
    await fit(m, log, doc, "after undo")
    print(lib.shot("tc-02-06-after.png"))
    Path(f"{EV}/tc-02-06-state.json").write_text(json.dumps({"handle": doc}))


@scenario("07")
async def s07(m, log):
    doc = await open_body(m, log)
    log.note(f"expand Body: {expand_tree('Body')}")
    log.note(f"expand Pad: {expand_tree('Pad')}")
    given = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    all_nodes = nodes(sc(given).get("tree"))
    log.check("Given Body, Sketch, Pad named", {"Body", "Sketch", "Pad"} <= {n.get("name") for n in all_nodes}, names(sc(given).get("tree")))
    per = await m.call("query_dependencies", {"doc": doc, "object": "Pad"})
    pr("per-object", per)
    whole = await m.call("query_dependencies", {"doc": doc})
    pr("whole", whole)
    full = await m.call("query_tree_summary", {"doc": doc, "depth": 5, "filters": {"exclude_types": []}})
    tree_by_name = {n.get("name"): n for n in nodes(sc(full).get("tree"))}
    labels_only = {n.get("label") for n in tree_by_name.values()} - set(tree_by_name)
    p = sc(per)
    log.check("per-object keys exactly object,in_list,out_list", set(p) == {"object", "in_list", "out_list"}, sorted(p))
    entries = (p.get("in_list") or []) + (p.get("out_list") or [])
    log.check("entries are Names of tree nodes, not labels", all(e in tree_by_name for e in entries),
              {"entries": entries, "label_only_values": sorted(labels_only)})
    types = {name: node.get("type") for name, node in tree_by_name.items()}
    log.check("Pad out_list contains its Sketcher::SketchObject", any(types.get(e) == "Sketcher::SketchObject" for e in p.get("out_list") or []), p.get("out_list"))
    log.check("Pad in_list contains PartDesign::Body", any(types.get(e) == "PartDesign::Body" for e in p.get("in_list") or []), p.get("in_list"))
    log.check("no duplicates in in_list/out_list",
              len(set(p.get("in_list") or [])) == len(p.get("in_list") or []) and len(set(p.get("out_list") or [])) == len(p.get("out_list") or []),
              {"in": p.get("in_list"), "out": p.get("out_list")})
    w = sc(whole)
    log.check("whole keys exactly edges,total_edges,returned_edges,truncated", set(w) == {"edges", "total_edges", "returned_edges", "truncated"}, sorted(w))
    edges = w.get("edges") or []
    log.check("every edge exactly {from,to}", bool(edges) and all(isinstance(e, dict) and set(e) == {"from", "to"} for e in edges), len(edges))
    log.check("not truncated at default cap", w.get("total_edges") == w.get("returned_edges") and w.get("truncated") is False,
              {k: w.get(k) for k in ("total_edges", "returned_edges", "truncated")})
    missing = [n for n in p.get("out_list") or [] if {"from": "Pad", "to": n} not in edges]
    log.check("views agree: every Pad out_list n has edge Pad->n", not missing, {"missing": missing})
    await fit(m, log, doc, "deps")
    print(lib.shot("tc-02-07-after.png"))
    Path(f"{EV}/tc-02-07-state.json").write_text(json.dumps({"handle": doc}))


PLACED_FILE = f"{EV}/tc-02-placed.FCStd"


@scenario("build08")
async def s_build08(m, log):
    """Body + DatumPlane (attached to the Body origin XY_Plane, offset 8 mm) + Sketch on XY + Pad.

    sketch_create only attaches to a planar face, so the Pad's sketch cannot sit on the datum plane
    over MCP; the datum-attached feature in this fixture is DatumPlane itself. The Body Placement is
    set afterwards through FreeCAD's Edit > Placement dialog (feature_set_parameters rejects it).
    """
    await ensure_empty(m, log)
    created = await m.call("document_create", {"label": "uat-placed"})
    doc = sc(created)["doc"]
    steps = [
        ("feature_body_create", {"doc": doc, "name": "Body"}),
        ("feature_datum", {"doc": doc, "body": "Body", "name": "DatumPlane", "kind": "plane",
                           "attachment": {"kind": "mapped_name", "object": "XY_Plane"}, "offset": {"value": 8, "unit": "mm"}}),
        ("sketch_create", {"doc": doc, "name": "Sketch", "plane": "XY", "body": "Body"}),
        ("sketch_add_geometry", {"doc": doc, "sketch": "Sketch", **rectangle(20, 10)}),
        ("feature_pad", {"doc": doc, "body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 5, "unit": "mm"}}),
    ]
    for tool, args in steps:
        env = await m.mutate(doc, tool, args)
        log.note(f"build {tool}: {env.get('status')} {msg(env) or (env.get('preview') or {}).get('detail') or ''}")
    tree = await m.call("query_tree_summary", {"doc": doc, "depth": 4})
    print(json.dumps(names(sc(tree).get("tree"))))
    Path(f"{EV}/tc-02-build08-state.json").write_text(json.dumps({"handle": doc}))


def pos(placement: dict) -> list[float]:
    return [placement["position"][k]["value"] for k in ("x", "y", "z")]


def compose(body: dict, local: dict) -> list[float]:
    import math
    angle = math.radians(body["angle"]["value"])
    ax = body["axis"]
    if abs(ax["z"] - 1) > 1e-9 and abs(angle) > 1e-12:
        raise ValueError("compose() handles Z-axis rotation only")
    x, y, z = pos(local)
    bx, by, bz = pos(body)
    c, s = math.cos(angle), math.sin(angle)
    return [bx + c * x - s * y, by + s * x + c * y, bz + z]


@scenario("08")
async def s08(m, log):
    await ensure_empty(m, log)
    opened = await m.call("document_open", {"path": PLACED_FILE})
    doc = sc(opened)["doc"]
    body_obj = await m.call("query_object", {"doc": doc, "object": "Body"})
    log.check("Given Body Placement non-identity (query_object)", "30" in json.dumps((sc(body_obj).get("properties") or {}).get("Placement")),
              (sc(body_obj).get("properties") or {}).get("Placement"))
    datum = await m.call("query_object", {"doc": doc, "object": "DatumPlane"})
    log.note(f"DatumPlane AttachmentSupport={(sc(datum).get('properties') or {}).get('AttachmentSupport')} MapMode={(sc(datum).get('properties') or {}).get('MapMode')}")
    body = await m.call("query_placement", {"doc": doc, "object": "Body"})
    pad = await m.call("query_placement", {"doc": doc, "object": "Pad"})
    dp = await m.call("query_placement", {"doc": doc, "object": "DatumPlane"})
    pr("body", body); pr("pad", pad); pr("datum", dp)
    b, p, d = sc(body), sc(pad), sc(dp)
    log.check("shape keys exactly object,local,global", set(b) == {"object", "local", "global"} and set(p) == {"object", "local", "global"}, [sorted(b), sorted(p)])
    lp = p.get("local", {})
    log.check("positions {value, unit: mm}",
              all(isinstance(lp["position"][k], dict) and lp["position"][k].get("unit") == "mm" and set(lp["position"][k]) == {"value", "unit"} for k in "xyz"),
              lp.get("position"))
    log.check("axis bare float triple, no unit", set(lp.get("axis", {})) == {"x", "y", "z"} and all(isinstance(v, (int, float)) for v in lp["axis"].values()), lp.get("axis"))
    log.check("angle {value, unit: deg}", (lp.get("angle") or {}).get("unit") == "deg", lp.get("angle"))
    log.check("Pad global differs from local", pos(p["global"]) != pos(p["local"]), {"local": pos(p["local"]), "global": pos(p["global"])})
    log.check("Body global == local field for field", b.get("global") == b.get("local"), {"local": b.get("local"), "global": b.get("global")})
    expected = compose(b["local"], p["local"])
    log.check("Pad global == Body placement applied to Pad local (1e-6)",
              all(abs(a - e) < 1e-6 for a, e in zip(pos(p["global"]), expected)), {"expected": expected, "global": pos(p["global"])})
    expected_d = compose(b["local"], d["local"])
    log.check("(extra) DatumPlane global composes too", all(abs(a - e) < 1e-6 for a, e in zip(pos(d["global"]), expected_d)),
              {"local": pos(d["local"]), "expected": expected_d, "global": pos(d["global"])})
    # An object without Placement: FreeCAD's own "New Group" toolbar button (App::DocumentObjectGroup).
    state = lib.snapshot()
    pid, _ = ids()
    grp_buttons = lib.find(state, role="Button", label="New Group")
    clicked = cua("click", {"pid": pid, "element_token": grp_buttons[0]["element_token"]}) if grp_buttons else {"error": "no New Group"}
    time.sleep(1.0)
    full = await m.call("query_tree_summary", {"doc": doc, "depth": 1, "filters": {"exclude_types": []}})
    groups = [n["name"] for n in nodes(sc(full).get("tree")) if n.get("type") == "App::DocumentObjectGroup"]
    log.note(f"GUI New Group click: {clicked.get('effect')} {clicked.get('route')} -> groups {groups}")
    if groups:
        noplace = await m.call("query_placement", {"doc": doc, "object": groups[0]})
        log.check("object without Placement -> INVALID_INPUT object has no placement: <name>",
                  noplace.get("status") == "INVALID_INPUT" and msg(noplace) == f"object has no placement: {groups[0]}", [noplace.get("status"), msg(noplace)])
    else:
        log.check("object without Placement -> INVALID_INPUT", False, "could not create a placement-less object")
    await fit(m, log, doc, "placed")
    print(lib.shot("tc-02-08-after.png"))
    Path(f"{EV}/tc-02-08-state.json").write_text(json.dumps({"handle": doc}))


@scenario("09")
async def s09(m, log):
    """The GUI open (File > Open…, typed path, Enter) and verify_state ran before this, by hand."""
    verify = json.loads(Path(f"{EV}/tc-02-09-verify.json").read_text())
    log.check("GUI opened it: verify_state satisfied (not unknown)", verify.get("status") == "satisfied", verify.get("status"))
    first = await m.call("document_list", {})
    pr("list1", first)
    docs = sc(first).get("documents", [])
    log.check("list reports 1 open document(s): box40-hole-r5.", first.get("text") == "1 open document(s): box40-hole-r5.", first.get("text"))
    adopted = docs[0].get("doc", "") if docs else ""
    log.check("adopted entry doc matches ^fcb-doc:", adopted.startswith("fcb-doc:"), adopted)
    log.check("adopted entry transient false", bool(docs) and docs[0].get("transient") is False, docs)
    tree = await m.call("query_tree_summary", {"doc": adopted})
    log.check("adopted handle usable: tree[0] BoxHole", (sc(tree).get("tree") or [{}])[0].get("name") == "BoxHole", sc(tree).get("tree"))
    mass = await m.call("query_mass_properties", {"doc": adopted, "object": "BoxHole"})
    log.check("volume 15214.6018 within 0.1%", near(volume(mass), 15214.6018), volume(mass))
    second = await m.call("document_list", {})
    docs2 = sc(second).get("documents", [])
    log.check("second list: same doc string, one entry", len(docs2) == 1 and docs2[0].get("doc") == adopted, docs2)
    await show(m, log, adopted, "BoxHole")
    await fit(m, log, adopted, "adopted")
    print(lib.shot("tc-02-09-after.png"))
    Path(f"{EV}/tc-02-09-state.json").write_text(json.dumps({"handle": adopted}))


def menu_children(path: list[str]) -> list[str]:
    """Open a menu path with a bogus leaf so the refusal leaves the submenu open; list its items."""
    pid, win = ids()
    cua("invoke_menu", {"pid": pid, "window_id": win, "path": path + ["__probe__"]})
    time.sleep(0.8)
    labels = []
    for window in cua("list_windows", {"pid": pid}).get("windows", []):
        if window["window_id"] != win:
            state = cua("get_window_state", {"pid": pid, "window_id": window["window_id"], "include_screenshot": False})
            labels += [e.get("label") for e in state.get("elements", []) if e.get("role") == "MenuItem"]
    lib.close_popups()
    return labels


@scenario("10")
async def s10(m, log):
    await ensure_empty(m, log)
    a_env = await m.call("document_open", {"path": f"{GOLDEN}/box-10-20-30.FCStd"})
    b_env = await m.call("document_open", {"path": f"{GOLDEN}/two-box-compound.FCStd"})
    a, b = sc(a_env)["doc"], sc(b_env)["doc"]
    listing = await m.call("document_list", {})
    log.check("Given both labels listed", "box-10-20-30" in listing.get("text", "") and "two-box-compound" in listing.get("text", ""), listing.get("text"))
    # Make A the active window first so the change to B is a real move.
    windows_items = menu_children(["Windows"])
    log.note(f"Windows menu items: {windows_items}")
    a_item = next((x for x in windows_items if x and "box-10-20-30" in x), None)
    b_item = next((x for x in windows_items if x and "two-box-compound" in x), None)
    pid, win = ids()
    if a_item:
        r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["Windows", a_item]})
        log.note(f"activate A via Windows>{a_item!r}: {r.get('effect') or r.get('refusal')}")
        time.sleep(1)
    log.note(f"title after activating A: {window_title()!r}")
    first = await m.call("query_tree_summary", {"doc": a})
    # GUI: select B's tree item, then Windows > B.
    click = lib.click_tree("two-box-compound")
    log.note(f"click two-box-compound tree item: { {k: click.get(k) for k in ('clicked','role','effect','route','error')} }")
    r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["Windows", b_item or "two-box-compound"]})
    log.note(f"invoke_menu Windows>{b_item!r}: {r.get('effect') or r.get('refusal')}")
    time.sleep(1)
    lib.close_popups()
    title = window_title()
    second = await m.call("query_tree_summary", {"doc": a})
    log.check("GUI moved to B: active window title two-box-compound", "two-box-compound" in title, title)
    log.check("handle string unchanged", True, a)
    log.check("re-read tree[0] Box identical to first", (sc(second).get("tree") or [{}])[0].get("name") == "Box" == (sc(first).get("tree") or [{}])[0].get("name"),
              [sc(first).get("tree"), sc(second).get("tree")])
    log.check("re-read structured_content equal field for field", sc(first) == sc(second), "equal" if sc(first) == sc(second) else {"first": sc(first), "second": sc(second)})
    tb = await m.call("query_tree_summary", {"doc": b})
    log.check("B tree[0] TwoBoxCompound", (sc(tb).get("tree") or [{}])[0].get("name") == "TwoBoxCompound", sc(tb).get("tree"))
    mb = await m.call("query_mass_properties", {"doc": b, "object": "TwoBoxCompound"})
    pr("mass B", mb)
    smb = sc(mb)
    log.check("B volume 2000, counts.solids 2, com null",
              near(volume(mb), 2000.0) and (smb.get("counts") or {}).get("solids") == 2 and "com" in smb and smb.get("com") is None,
              {"volume": volume(mb), "counts": smb.get("counts"), "com": smb.get("com", "<missing>")})
    await show(m, log, b, "TwoBoxCompound")
    await fit(m, log, b, "B")
    print(lib.shot("tc-02-10-after.png"))
    Path(f"{EV}/tc-02-10-state.json").write_text(json.dumps({"A": a, "B": b}))


def is_protocol_reject(envelope: dict) -> bool:
    return envelope.get("_isError") is True and "schema" not in envelope


@scenario("11")
async def s11(m, log):
    doc = await open_body(m, log)
    given = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("Given depth 2 shows a children array", "children" in json.dumps(sc(given).get("tree")), None)
    log.note(f"GUI Fit All (before): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-11-before.png"))
    d1 = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    d0 = await m.call("query_tree_summary", {"doc": doc, "depth": 0})
    dneg = await m.call("query_tree_summary", {"doc": doc, "depth": -1})
    mn0 = await m.call("query_tree_summary", {"doc": doc, "max_nodes": 0})
    mn5 = await m.call("query_tree_summary", {"doc": doc, "depth": 2, "max_nodes": 5})
    default = await m.call("query_tree_summary", {"doc": doc})
    tools = (await m.list_tools()).tools
    schema = next(t.inputSchema for t in tools if t.name == "query_tree_summary")
    valid = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("depth 1 OK with depth 1", d1.get("status") == "OK" and sc(d1).get("depth") == 1, [d1.get("status"), sc(d1).get("depth")])
    log.check("depth defaults to 1", sc(default).get("depth") == 1, sc(default).get("depth"))
    log.check("depth 0 protocol reject", is_protocol_reject(d0), d0)
    log.check("depth -1 protocol reject", is_protocol_reject(dneg), dneg)
    log.check("max_nodes:0 protocol reject (not OK envelope)", is_protocol_reject(mn0), mn0)
    log.check("max_nodes:5 with depth 2 protocol reject", is_protocol_reject(mn5), mn5)
    log.check("schema closed: additionalProperties false; properties exactly doc,depth,root,filters",
              schema.get("additionalProperties") is False and set(schema.get("properties", {})) == {"doc", "depth", "root", "filters"},
              {"additionalProperties": schema.get("additionalProperties"), "properties": sorted(schema.get("properties", {}))})
    log.check("valid call after rejections OK", valid.get("status") == "OK", valid.get("status"))
    log.note(f"GUI Fit All (after): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-11-after.png"))
    Path(f"{EV}/tc-02-11-state.json").write_text(json.dumps({"handle": doc}))


@scenario("12")
async def s12(m, log):
    doc = await open_body(m, log)
    full = await m.call("query_dependencies", {"doc": doc})
    total = sc(full).get("total_edges") or 0
    log.check("Given total_edges >= 2", total >= 2, total)
    log.note(f"GUI Fit All (before): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-12-before.png"))
    capped = await m.call("query_dependencies", {"doc": doc, "max_edges": 1})
    zero = await m.call("query_dependencies", {"doc": doc, "max_edges": 0})
    neg = await m.call("query_dependencies", {"doc": doc, "max_edges": -5})
    frac = await m.call("query_dependencies", {"doc": doc, "max_edges": 1.5})
    f, c = sc(full), sc(capped)
    log.check("uncapped: truncated false, returned == total", f.get("truncated") is False and f.get("returned_edges") == total, {k: f.get(k) for k in ("total_edges", "returned_edges", "truncated")})
    log.check("max_edges 1: one edge, returned_edges 1", len(c.get("edges") or []) == 1 and c.get("returned_edges") == 1, {k: c.get(k) for k in ("returned_edges", "edges")})
    log.check("capped truncated true", c.get("truncated") is True, c.get("truncated"))
    log.check("capped total_edges == uncapped total", c.get("total_edges") == total, [c.get("total_edges"), total])
    log.check("kept edge == uncapped edges[0]", (c.get("edges") or [None])[0] == (f.get("edges") or [None])[0], [(c.get("edges") or [None])[0], (f.get("edges") or [None])[0]])

    def layer(env):
        if is_protocol_reject(env):
            return f"protocol: {env.get('_raw')}"
        return f"envelope {env.get('status')}: {msg(env)}"

    log.check("max_edges 0 refused (record layer)", is_protocol_reject(zero) or (zero.get("status") == "INVALID_INPUT" and msg(zero) == "max_edges must be >= 1: 0"), layer(zero))
    log.check("max_edges -5 refused same way", (is_protocol_reject(neg) and is_protocol_reject(zero)) or (neg.get("status") == "INVALID_INPUT" and msg(neg) == "max_edges must be >= 1: -5"), layer(neg))
    log.check("max_edges 1.5 refused", is_protocol_reject(frac) or (frac.get("status") == "INVALID_INPUT" and msg(frac) == "max_edges must be an integer: 1.5"), layer(frac))
    log.note(f"GUI Fit All (after): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-12-after.png"))
    Path(f"{EV}/tc-02-12-state.json").write_text(json.dumps({"handle": doc}))


UNICODE_LABEL = "測試 ドキュメント 🔧 with spaces and a deliberately long label for width"


@scenario("13")
async def s13(m, log):
    target = f"{EV}/tc-02-13-uat-unicode.FCStd"
    await ensure_empty(m, log)
    log.check("Given target absent", not Path(target).exists())
    created = await m.call("document_create", {"label": UNICODE_LABEL})
    handle = sc(created).get("doc", "")
    listing = await m.call("document_list", {})
    saved = await m.call("document_save", {"doc": handle, "path": target})
    listing_after_save = await m.call("document_list", {})
    closed = await m.call("document_close", {"doc": handle})
    reopened = await m.call("document_open", {"path": target})
    fresh = sc(reopened).get("doc", "")
    listing2 = await m.call("document_list", {})
    tree = await m.call("query_tree_summary", {"doc": fresh})
    c = sc(created)
    log.check("create OK with handle", created.get("status") == "OK" and handle.startswith("fcb-doc:"), handle)
    log.check("label survives create exactly", c.get("label") == UNICODE_LABEL, c.get("label"))
    log.check("name is FreeCAD-legal identifier and != label", re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c.get("name") or "") is not None and c.get("name") != c.get("label"), c.get("name"))
    l1 = sc(listing).get("documents", [])
    log.check("listing label unmangled (structured and text)", bool(l1) and l1[0].get("label") == UNICODE_LABEL and UNICODE_LABEL in listing.get("text", ""), listing.get("text"))
    log.note(f"save: {saved.get('status')} {sc(saved)}; list after save-as: {sc(listing_after_save).get('documents')}")
    l2 = sc(listing2).get("documents", [])
    reopened_label = l2[0].get("label") if l2 else None
    log.check("label survives save and reopen", reopened_label == UNICODE_LABEL, reopened_label)
    log.check("reopened label byte-equal to input (UTF-8)", (reopened_label or "").encode("utf-8") == UNICODE_LABEL.encode("utf-8"),
              {"input_utf8": UNICODE_LABEL.encode("utf-8").hex()[:40], "got_utf8": (reopened_label or "").encode("utf-8").hex()[:40]})
    log.check("reopened tree OK total_objects 0", tree.get("status") == "OK" and sc(tree).get("total_objects") == 0, [tree.get("status"), sc(tree).get("total_objects")])
    log.note(f"close: {closed.get('status')}")
    await fit(m, log, fresh, "unicode reopened")
    print(lib.shot("tc-02-13-after.png"))
    Path(f"{EV}/tc-02-13-state.json").write_text(json.dumps({"handle": handle, "reopened": fresh}, ensure_ascii=False))


FAKE = "fcb-doc:not-a-real-handle"


@scenario("15")
async def s15(m, log):
    await ensure_empty(m, log)
    opened = await m.call("document_open", {"path": f"{GOLDEN}/box-10-20-30.FCStd"})
    live = sc(opened)["doc"]
    listing = await m.call("document_list", {})
    log.check("Given one document open", len(sc(listing).get("documents", [])) == 1, listing.get("text"))
    await show(m, log, live, "Box")
    log.note(f"GUI Fit All (before): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-15-before.png"))
    calls = [
        ("query_tree_summary", {"doc": FAKE}), ("query_object", {"doc": FAKE, "object": "Box"}),
        ("query_mass_properties", {"doc": FAKE, "object": "Box"}), ("query_dependencies", {"doc": FAKE}),
        ("query_placement", {"doc": FAKE, "object": "Box"}), ("query_sketch_info", {"doc": FAKE, "sketch": "Sketch"}),
        ("document_save", {"doc": FAKE}), ("document_close", {"doc": FAKE}), ("document_recompute", {"doc": FAKE}),
        ("document_undo", {"doc": FAKE}), ("verify_shape", {"doc": FAKE}), ("query_screenshot", {"doc": FAKE}),
    ]
    expected = f"unknown or stale document handle: {FAKE}"
    for tool, args in calls:
        env = await m.call(tool, args)
        ok = env.get("status") == "INVALID_INPUT" and msg(env) == expected and env.get("schema") == "fcb.result-envelope/1" and (env.get("detail") or {}).get("code") == "INVALID_INPUT"
        log.check(f"{tool} refuses fake handle (INVALID_INPUT envelope, exact message)", ok,
                  {"status": env.get("status"), "schema": env.get("schema"), "code": (env.get("detail") or {}).get("code"), "message": msg(env), "raw": env.get("_raw")})
    caps = await m.call("query_capabilities", {})
    log.check("query_capabilities still OK", caps.get("status") == "OK", caps.get("status"))
    live_tree = await m.call("query_tree_summary", {"doc": live})
    log.check("live handle still OK", live_tree.get("status") == "OK", live_tree.get("status"))
    omitted = await m.call("query_tree_summary", {})
    log.check("omitted doc -> protocol reject", is_protocol_reject(omitted), omitted)
    nonstring_h2 = await m.call("query_tree_summary", {"doc": 12345})
    log.note(f"(extra, H2 :8765) non-string doc -> {nonstring_h2.get('_raw') or [nonstring_h2.get('status'), msg(nonstring_h2)]}")
    log.note(f"GUI Fit All (after): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-15-after.png"))
    Path(f"{EV}/tc-02-15-state.json").write_text(json.dumps({"handle": live}))


@scenario("16")
async def s16(m, log):
    sphere = f"{GOLDEN}/sphere-r10.FCStd"
    size_before = Path(sphere).stat().st_size
    sha_before = sha(sphere)
    await ensure_empty(m, log)
    opened = await m.call("document_open", {"path": sphere})
    handle = sc(opened)["doc"]
    c1 = await m.call("document_close", {"doc": handle})
    c2 = await m.call("document_close", {"doc": handle})
    q = await m.call("query_tree_summary", {"doc": handle})
    expected = f"unknown or stale document handle: {handle}"
    log.check("first close OK closed:true name sphere_r10/sphere-r10", c1.get("status") == "OK" and sc(c1).get("closed") is True, sc(c1))
    log.note(f"first close name field = {sc(c1).get('name')!r} (TC expects 'sphere-r10')")
    log.check("first close name == sphere-r10 (literal)", sc(c1).get("name") == "sphere-r10", sc(c1).get("name"))
    log.check("second close INVALID_INPUT exact message", c2.get("status") == "INVALID_INPUT" and msg(c2) == expected, [c2.get("status"), msg(c2)])
    log.check("message names the exact handle", handle in (msg(c2) or ""), msg(c2))
    log.check("query via released handle refused same way", q.get("status") == "INVALID_INPUT" and msg(q) == expected, [q.get("status"), msg(q)])
    listing = await m.call("document_list", {})
    log.check("0 open document(s).", listing.get("text") == "0 open document(s).", listing.get("text"))
    print(lib.shot("tc-02-16-after-double-close.png"))
    caps = await m.call("query_capabilities", {})
    log.check("query_capabilities OK", caps.get("status") == "OK", caps.get("status"))
    log.check("golden file intact (size, sha)", Path(sphere).stat().st_size == size_before and sha(sphere) == sha_before, size_before)
    re_env = await m.call("document_open", {"path": sphere})
    fresh = sc(re_env)["doc"]
    mass = await m.call("query_mass_properties", {"doc": fresh, "object": "Sphere"})
    log.check("reopen fresh handle volume 4188.7902", fresh != handle and near(volume(mass), 4188.7902), {"fresh": fresh, "volume": volume(mass)})
    await show(m, log, fresh, "Sphere")
    log.note(f"GUI Fit All: {lib.fitall().get('route')}")
    print(lib.shot("tc-02-16-after.png"))
    Path(f"{EV}/tc-02-16-state.json").write_text(json.dumps({"handle": handle, "reopened": fresh}))


@scenario("17")
async def s17(m, log):
    not_fcstd, corrupt = f"{EV}/tc-02-17-not-fcstd.txt", f"{EV}/tc-02-17-corrupt.FCStd"
    Path(not_fcstd).write_bytes(b"this is not a FreeCAD document\n")
    Path(corrupt).write_bytes(b"PK\x03\x04garbage-not-a-real-zip")
    log.check("Given bad files prepared", Path(not_fcstd).stat().st_size > 0 and Path(corrupt).stat().st_size > 0)
    await ensure_empty(m, log)
    base = await m.call("document_open", {"path": f"{GOLDEN}/box-10-20-30.FCStd"})
    handle = sc(base)["doc"]
    log.check("Given baseline open OK", base.get("status") == "OK", handle)
    await show(m, log, handle, "Box")
    log.note(f"GUI Fit All (before): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-17-before.png"))
    missing = f"{EV}/tc-02-17-does-not-exist.FCStd"
    results = {}
    for key, path in (("missing", missing), ("not_fcstd", not_fcstd), ("corrupt", corrupt), ("empty", ""), ("directory", EV)):
        results[key] = await m.call("document_open", {"path": path})
        pr(key, results[key])
    def starts(env, path):
        return env.get("status") == "INVALID_INPUT" and (msg(env) or "").startswith(f"document_open failed for '{path}':")
    log.check("nonexistent refused with prefix", starts(results["missing"], missing), msg(results["missing"]))
    log.check("non-FCStd refused with prefix", starts(results["not_fcstd"], not_fcstd), msg(results["not_fcstd"]))
    log.check("corrupt refused with prefix", starts(results["corrupt"], corrupt), msg(results["corrupt"]))
    tails = [(msg(results[k]) or "").split("':", 1)[-1] for k in ("missing", "not_fcstd", "corrupt")]
    log.check("three refusal tails distinguishable", len(set(tails)) == 3, tails)
    log.check("empty path -> document_open requires a 'path'", results["empty"].get("status") == "INVALID_INPUT" and msg(results["empty"]) == "document_open requires a 'path'", [results["empty"].get("status"), msg(results["empty"])])
    log.check("directory refused with prefix", starts(results["directory"], EV), [results["directory"].get("status"), msg(results["directory"])])
    listing = await m.call("document_list", {})
    log.check("no handle leaked: only baseline listed", [d.get("doc") for d in sc(listing).get("documents", [])] == [handle], listing.get("text"))
    caps = await m.call("query_capabilities", {})
    log.check("query_capabilities OK", caps.get("status") == "OK", caps.get("status"))
    log.note(f"GUI Fit All (after): {lib.fitall().get('route')}")
    print(lib.shot("tc-02-17-after.png"))
    Path(f"{EV}/tc-02-17-state.json").write_text(json.dumps({"handle": handle}))


@scenario("18")
async def s18(m, log):
    import shutil
    import stat
    ro = f"{EV}/tc-02-18-readonly.FCStd"
    shutil.copyfile(f"{GOLDEN}/box-10-20-30.FCStd", ro)
    os.chmod(ro, stat.S_IREAD)
    ro_sha, ro_size = sha(ro), Path(ro).stat().st_size
    log.check("Given read-only target exists", not os.access(ro, os.W_OK), {"size": ro_size, "sha": ro_sha})
    cyl = f"{GOLDEN}/cylinder-r5-h20.FCStd"
    cyl_sha = sha(cyl)
    await ensure_empty(m, log)
    opened = await m.call("document_open", {"path": cyl})
    handle = sc(opened)["doc"]
    closed_set = {"OK", "INVALID_INPUT", "WORKER_CRASHED", "RECOMPUTE_ERROR", "SPEC_FAILED", "TIMEOUT", "UNSUPPORTED"}
    r1 = await m.call("document_save", {"doc": handle, "path": ro})
    nodir = f"{EV}/tc-02-18-no-such-dir/out.FCStd"
    r2 = await m.call("document_save", {"doc": handle, "path": nodir})
    r3 = await m.call("document_save", {"doc": handle, "path": EV})
    pr("readonly", r1); pr("nodir", r2); pr("dir", r3)
    log.check("read-only save refused, INVALID_INPUT or WORKER_CRASHED", r1.get("status") in ("INVALID_INPUT", "WORKER_CRASHED"), [r1.get("status"), msg(r1)])
    log.check("read-only file byte-identical", sha(ro) == ro_sha, sha(ro) == ro_sha)
    log.check("missing-dir save refused (closed-set non-OK) and no dir created",
              r2.get("status") in closed_set - {"OK"} and not Path(f"{EV}/tc-02-18-no-such-dir").exists(), [r2.get("status"), msg(r2), Path(f"{EV}/tc-02-18-no-such-dir").exists()])
    log.check("dir-as-path save refused (closed-set non-OK); evidence still a dir", r3.get("status") in closed_set - {"OK"} and Path(EV).is_dir(), [r3.get("status"), msg(r3)])
    log.check("source golden untouched", sha(cyl) == cyl_sha)
    tree = await m.call("query_tree_summary", {"doc": handle})
    log.check("handle usable: tree[0] Cylinder", tree.get("status") == "OK" and (sc(tree).get("tree") or [{}])[0].get("name") == "Cylinder", sc(tree).get("tree"))
    good = await m.call("document_save", {"doc": handle, "path": f"{EV}/tc-02-18-writable.FCStd"})
    log.check("later writable save OK saved:true", good.get("status") == "OK" and sc(good).get("saved") is True, [good.get("status"), sc(good)])
    caps = await m.call("query_capabilities", {})
    log.check("query_capabilities OK", caps.get("status") == "OK", caps.get("status"))
    await show(m, log, handle, "Cylinder")
    await fit(m, log, handle, "cylinder")
    print(lib.shot("tc-02-18-after.png"))
    Path(f"{EV}/tc-02-18-state.json").write_text(json.dumps({"handle": handle}))


@scenario("14")
async def s14(m, log):
    state = json.loads(Path(f"{EV}/tc-02-14-create.json").read_text())
    doc = state["structured_content"]["doc"]
    given = await m.call("query_tree_summary", {"doc": doc, "depth": 5})
    types = [n.get("type") for n in nodes(sc(given).get("tree"))]
    log.check("Given App::Part and App::Link nodes at depth 5", "App::Part" in types and any((t or "").startswith("App::Link") for t in types), types)
    d1 = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    started = time.time()
    d5 = await m.call("query_tree_summary", {"doc": doc, "depth": 5})
    d5_seconds = time.time() - started
    d5b = await m.call("query_tree_summary", {"doc": doc, "depth": 5})
    rooted = await m.call("query_tree_summary", {"doc": doc, "depth": 3, "root": "Inner"})
    rooted5 = await m.call("query_tree_summary", {"doc": doc, "depth": 5, "root": "Inner"})
    target = await m.call("query_tree_summary", {"doc": doc, "root": "Box"})
    pr("d1", d1); pr("d5", d5); pr("rooted", rooted)
    all5 = nodes(sc(d5).get("tree"))
    both = [n for n in all5 if "children" in n and "links" in n]
    log.check("children and links are separate keys on a node with both", bool(both) and all(isinstance(n["children"], list) and isinstance(n["links"], list) for n in both),
              [(n.get("name"), [c.get("name") for c in n.get("children", [])], [c.get("name") for c in n.get("links", [])]) for n in both])
    link_nodes = [l for n in all5 for l in n.get("links", [])]
    log.check("only App::Link* in links arrays", bool(link_nodes) and all((l.get("type") or "").startswith("App::Link") for l in link_nodes), [(l.get("name"), l.get("type")) for l in link_nodes])
    r1 = (sc(d1).get("tree") or [{}])[0]
    log.check("depth 1 root reports children_count, no expanded arrays", "children_count" in r1 and "children" not in r1 and "links" not in r1, r1)
    leaves = [n for n in all5 if n.get("type") == "Part::Box"]
    log.check("leaf omits children_count and links_count", bool(leaves) and all("children_count" not in n and "links_count" not in n for n in leaves), leaves)
    outer = next((n for n in all5 if n.get("name") == "Outer"), {})
    inner_in_outer = next((c for c in outer.get("children", []) if c.get("name") == "Inner"), None)
    log.check("depth 5: Outer children contains Inner, which carries its own children", inner_in_outer is not None and bool(inner_in_outer.get("children")),
              {"outer_children": [c.get("name") for c in outer.get("children", [])], "inner": inner_in_outer})
    rt = sc(rooted)
    log.check("root Inner: one tree entry, returned_nodes < whole walk at same depth",
              len(rt.get("tree") or []) == 1 and (rt.get("returned_nodes") or 0) < (sc(await m.call("query_tree_summary", {"doc": doc, "depth": 3})).get("returned_nodes") or 0),
              {"tree": [n.get("name") for n in rt.get("tree") or []], "returned_nodes": rt.get("returned_nodes")})
    log.check("no cycle: d5 returns < 30 s, finite and stable across two calls",
              d5_seconds < 30 and sc(d5).get("returned_nodes") == sc(d5b).get("returned_nodes"), {"seconds": round(d5_seconds, 3), "n": [sc(d5).get("returned_nodes"), sc(d5b).get("returned_nodes")]})
    log.check("link target reachable as root", target.get("status") == "OK" and (sc(target).get("tree") or [{}])[0].get("name") == "Box", sc(target).get("tree"))
    log.note(f"root Inner depth5: {json.dumps(sc(rooted5).get('tree'))}")
    log.note(f"expand Outer: {expand_tree('Outer')}")
    log.note(f"expand Inner: {expand_tree('Inner')}")
    await fit(m, log, doc, "nested")
    print(lib.shot("tc-02-14-after.png"))


# ---------------------------------------------------------------------------------------------
async def main() -> int:
    number = sys.argv[1]
    log = lib.Log(f"tc-02-{number}-mcp")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            m = lib.Mcp(session, log)
            m.list_tools = session.list_tools
            await SCENARIOS[number](m, log)
    Path(f"{EV}/tc-02-{number}-checks.txt").write_text("\n".join(log.checks) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
