"""RT4: script_exec errors with a non-str `code` through the real catalog dispatch."""
import json, os, sys
ROOT = os.environ["FCB_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "src"))
import FreeCAD as App
from freecad_buddy.hosts import tool_catalog
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.capabilities import Capabilities
reg = DocumentRegistry()
methods = tool_catalog.build_inline_handlers(reg, tool_catalog.ExportRegistry(), Capabilities(script_exec=True, auto_approve=True), None, render_port=object())
h = reg.document_create("rt4")["structured_content"]["doc"]
cases = {
    "oserror_int_code": "raise OSError(5, 'access denied')",
    "code_method": "class E(Exception):\n    def code(self):\n        return 1\nraise E('boom')",
    "int_code_attr": "class E(Exception):\n    code = 404\nraise E('nf')",
}
out = {}
for name, code in cases.items():
    env = methods.dispatch("script_exec", {"doc": h, "code": code})
    try:
        text = json.dumps(env); ok_json = True
    except Exception as exc:
        text = repr(exc); ok_json = False
    d = env.get("detail") or {}
    out.setdefault("_envelopes", {})[name] = json.loads(json.dumps(env, default=repr))
    out[name] = {"status": env["status"], "detail_code": d.get("code") if isinstance(d.get("code"), (str, int)) else repr(d.get("code")), "code_type": type(d.get("code")).__name__, "json_ok": ok_json, "message": (d.get("message") or "")[:120]}
try:
    import jsonschema
    schema = json.load(open(os.path.join(ROOT, "src/freecad_buddy/contracts/jsonschema/result-envelope.schema.json")))
    for name, code in cases.items():
        env = methods.dispatch("script_exec", {"doc": h, "code": code})
        try:
            jsonschema.validate(json.loads(json.dumps(env)), schema); out[name]["schema_ok"] = True
        except Exception as exc:
            out[name]["schema_ok"] = f"{type(exc).__name__}: {str(exc)[:150]}"
except ImportError:
    out["_schema"] = "jsonschema not importable under freecadcmd"
open(os.environ["FCB_OUT"], "w").write(json.dumps(out, indent=1))
sys.stderr.write("RT4 DONE %s\n" % json.dumps(out))
