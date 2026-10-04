"""TC-14-01: build the read-only assistant registry and list its method names."""
import dataclasses, json
from freecad_buddy.hosts import tool_catalog as tc
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry
from freecad_buddy.usecases.capabilities import Capabilities

fields = {f.name: None for f in dataclasses.fields(Capabilities)}
caps = Capabilities(**fields)
reg = tc.build_readonly_profile(DocumentRegistry(), ExportRegistry(), caps, None)
names = sorted(m.name for m in reg.methods())
print(json.dumps({"count": len(names), "view_fit_viewport_listed": "view_fit_viewport" in names, "names": names}))
