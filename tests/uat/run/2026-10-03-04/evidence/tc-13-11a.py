import asyncio, json
from tclib import *
log = Log("tc-13-11-literal.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        args = {"doc": H, "feature": "Box", "parameters": {"Length": {"value": 25, "unit": "mm"}}}
        await mutate(s, H, "feature_set_parameters", args, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
asyncio.run(main())
