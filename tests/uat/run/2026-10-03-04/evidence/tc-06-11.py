"""TC-06-11: H1 headless host render ladder. Conditional skip when H1 reports render != none."""
import asyncio, glob, json, os, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tc06lib import shot

FCB = os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb")
env = dict(os.environ)
env["PYTHONPATH"] = ";".join([rf"{FCB}\Library\bin", rf"{FCB}\Library\lib", r"D:\Work\Personal\Sources\freecad-buddy\src"])
env["PATH"] = rf"{FCB}\Library\bin;" + env["PATH"]
env["PYTHONUTF8"] = "1"
GOLD = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"
out = []


def t(res):
    return json.loads("".join(b.text for b in res.content if hasattr(b, "text")))


async def main():
    out.append({"gui_before": shot("tc-06-11-before.png")})
    before = set(glob.glob(os.environ["TEMP"] + "/FCB_TMP_shot_*.png"))
    params = StdioServerParameters(command=rf"{FCB}\python.exe", args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            caps = t(await s.call_tool("query_capabilities", {}))
            out.append({"h1_query_capabilities": caps.get("structured_content")})
            render = (caps.get("structured_content") or {}).get("render")
            print("H1 render ladder:", render, "freecad", (caps.get("structured_content") or {}).get("freecad_version"))
            if render == "none":
                op = t(await s.call_tool("document_open", {"path": GOLD}))
                doc = (op.get("structured_content") or {}).get("doc")
                rr = t(await s.call_tool("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}))
                out.append({"h1_render": rr})
    after = set(glob.glob(os.environ["TEMP"] + "/FCB_TMP_shot_*.png"))
    out.append({"new_temp_pngs": sorted(after - before)})
    time.sleep(0.5)
    out.append({"gui_after": shot("tc-06-11-after.png")})

asyncio.run(main())
open("tc-06-11-h1.json", "w", encoding="utf-8").write(json.dumps(out, indent=1))
print(json.dumps(out)[:1500])
