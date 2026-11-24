import json, sys, jsonschema
out = json.load(open(sys.argv[1])); schema = json.load(open(sys.argv[2]))
for name, env in out["_envelopes"].items():
    try:
        jsonschema.validate(env, schema); r = "valid"
    except jsonschema.ValidationError as exc:
        r = "INVALID: " + exc.message[:150]
    print(name, out[name]["status"], repr(out[name]["detail_code"]), "json_ok", out[name]["json_ok"], r)
