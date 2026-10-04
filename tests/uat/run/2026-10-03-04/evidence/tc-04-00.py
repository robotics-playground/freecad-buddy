from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    tools = (await m.session.list_tools()).tools
    names = sorted(t.name for t in tools)
    schemas = {t.name: t.inputSchema for t in tools if t.name.startswith("feature_") or t.name in ("query_object", "query_mass_properties", "verify_shape", "query_placement")}
    (EVIDENCE / "tc-04-00-schemas.json").write_text(json.dumps(schemas, indent=1), encoding="utf-8")
    log.check("tools/list count (TC says 44; run context says 45)", len(names) == 45, len(names))
    caps = await m.call("query_capabilities", {})
    log.note(f"capabilities: {json.dumps(sc(caps))[:600]}")
    d = await new_doc(m, "Probe")
    probe = await m.call("feature_body_create", {"doc": d, "name": "ProbeBody"})
    log.check("PartDesign available + auto-approve: feature_body_create without confirm OK",
              probe.get("status") == "OK", short(probe))
    await m.call("document_close", {"doc": d})
    st = snapshot()
    gl = [e for e in st.get("elements", []) if "OpenGL" in (e.get("label") or "") + (e.get("role") or "") + json.dumps(e)]
    log.check("cua-driver get_window_state sees the window", st.get("element_count", 0) > 0, f"elements={st.get('element_count')} gl_hits={len(gl)}")
    log.note(f"temp snaps: {snap_temp()}")


go("tc-04-00", body)
