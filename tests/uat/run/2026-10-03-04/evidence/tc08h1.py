"""H1 headless host (FCB_PYTHON, stdio, inline) for TC-08-05 / TC-08-18. Never touches the GUI."""
import contextlib
import json
import os
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FCB = os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb")


def h1_env(extra=None, drop=()):
    env = dict(os.environ)
    env["PYTHONPATH"] = ";".join([rf"{FCB}\Library\bin", rf"{FCB}\Library\lib", r"D:\Work\Personal\Sources\freecad-buddy\src"])
    env["PATH"] = rf"{FCB}\Library\bin;" + env["PATH"]
    env["PYTHONUTF8"] = "1"
    for k in drop:
        env.pop(k, None)
    env.update(extra or {})
    return env


class H1:
    """Same call()/log interface as tc03lib.Mcp so tc05lib.apply/body_sketch work against H1."""

    def __init__(self, session, log, tag):
        self.session, self.log, self.tag = session, log, tag

    async def call(self, tool, args):
        t0 = time.time()
        r = await self.session.call_tool(tool, args)
        text = "".join(b.text for b in r.content if hasattr(b, "text"))
        try:
            env = json.loads(text)
        except json.JSONDecodeError:
            env = {"_raw": text}
        if not isinstance(env, dict):
            env = {"_value": env}
        self.log.write({"host": "H1", "tag": self.tag, "tool": tool, "args": args, "isError": bool(r.isError),
                        "seconds": round(time.time() - t0, 3), "envelope": env})
        env["_isError"] = bool(r.isError)
        return env


@contextlib.asynccontextmanager
async def h1(log, tag, errlog_path, extra=None, drop=()):
    params = StdioServerParameters(command=rf"{FCB}\python.exe",
                                   args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
                                   env=h1_env(extra, drop))
    with open(errlog_path, "w", encoding="utf-8") as err:
        async with stdio_client(params, errlog=err) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                yield H1(s, log, tag)
