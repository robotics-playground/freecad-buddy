import json, sys
for r in json.load(open(sys.argv[1], encoding="utf-8")):
    if "shell" in r:
        print("SHELL", r["shell"], r["rc"], r["out"][:300]); continue
    sc = r["structuredContent"] or {}
    c = sc.get("structured_content") or {}
    keep = {k: c[k] for k in ("value_repr","changed","new_errors","undo_steps","fingerprint_after","undone","matches_pre_op","undo_count","errors") if k in c}
    if "changed" in keep: keep["changed"] = [x.get("name") for x in keep["changed"]] if isinstance(keep["changed"], list) else keep["changed"]
    if "properties" in c: keep["props"] = {k: c["properties"].get(k) for k in ("Length","Width","Height") if k in c["properties"]}
    print(f"{r['name']}: {sc.get('status')} detail={json.dumps(sc.get('detail'))[:400]} {json.dumps(keep)[:700]}")
    if sys.argv[2:] : print("   TEXT:", sc.get("text","")[-500:].replace("\n"," | "))
