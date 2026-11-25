"""Pin the reason TC-18-04b grades REPOINTED: run the installed guard around the same Boss edit,
once as shipped and once with the positional-name detector and lineage walk switched off."""
import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

CODE = """
from freecad_buddy.usecases import tnp_guard as g
boss = doc.getObject('Boss')
def graded(off):
    saved = (g._has_positional_counter, g._lineage_has_counter)
    if off:
        g._has_positional_counter = lambda n: False
        g._lineage_has_counter = lambda *a: False
    try:
        snap = g.snapshot_references(doc)
        boss.Length = 20
        doc.recompute()
        audit = g.audit_references(doc, snap)
        return [(f['owner'], f['verdict'], f['layer']) for f in audit['findings'] if f['owner'] == 'BossPoint']
    finally:
        g._has_positional_counter, g._lineage_has_counter = saved
        boss.Length = 15
        doc.recompute()
rec = next(r for r in g.snapshot_references(doc) if r['owner'] == 'BossPoint')
e = rec['entries'][0]
f = boss.Shape.getElement(e['indexed'] or 'Face6')
result = dict(mapped=e['mapped'], history=e['history'], counter=g._has_positional_counter(e['mapped']),
              lineage=g._lineage_has_counter(boss, e['mapped']), counts=rec.get('target_counts'),
              shipped=graded(False), detector_off=graded(True))
"""


async def main():
    async with streamablehttp_client("http://127.0.0.1:18765/mcp", timeout=60) as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            docs = (await s.call_tool("document_list", {})).structuredContent["structured_content"]["documents"]
            doc = docs[0].get("doc") or docs[0].get("handle")
            res = await s.call_tool("script_exec", {"doc": doc, "code": CODE})
            sc = res.structuredContent
            print(json.dumps(sc.get("structured_content", {}).get("value_repr") or sc, indent=1)[:2500])


asyncio.run(main())
