"""Print the element_token of the first element with this exact role and label."""
import json, sys

d = json.load(open(sys.argv[1]))
for e in d.get("elements", []):
    if e.get("role") == sys.argv[2] and str(e.get("label")) == sys.argv[3]:
        print(e["element_token"])
        break
