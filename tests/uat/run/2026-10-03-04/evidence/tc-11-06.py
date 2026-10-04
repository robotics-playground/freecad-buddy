"""TC-11-06: the MCP HTTP endpoint binds loopback only (H2 proxy). Framing via GUI Fit All, as the TC prefers."""
import asyncio
import subprocess
import time

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, REPO, Log, Mcp, close_all, sc, short, show_all
from tc03lib import fitall, shot
from tc11rpc import LAN_IP, netstat_port

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-06"


def sh(cmd, **kw):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    return r.returncode, r.stdout, r.stderr


async def main():
    log = Log(TAG)
    lines = netstat_port(8765)
    log.check("Given proxy serving: :8765 LISTENING", bool(lines), lines)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            await close_all(m, log)
            opened = await m.call("document_open", {"path": BOX})
            doc = sc(opened).get("doc")
            log.check("Given document_open box OK", opened.get("status") == "OK", short(opened))
    log.note(f"GUI Show All Objects: {show_all()}")
    fa = fitall()
    time.sleep(1)
    log.check("Given GUI Fit All toolbar click (route accessibility)", fa.get("route") == "accessibility", fa)
    log.check("Given baseline captured", shot(f"{TAG}-before.png").get("exists"), f"{TAG}-before.png")

    # When / Then
    lines = netstat_port(8765)
    log.check("Then endpoint bound to 127.0.0.1:8765 (only)", bool(lines) and all(ln.split()[1] == "127.0.0.1:8765" for ln in lines), lines)
    rc, out, err = sh(["curl", "-sS", "-m", "5", "-X", "POST", f"http://{LAN_IP}:8765/mcp", "-H", "Content-Type: application/json",
                       "-d", '{"jsonrpc":"2.0","id":1,"method":"ping"}'])
    log.write({"curl_lan": {"rc": rc, "out": out[:300], "err": err[:300]}})
    log.check("Then LAN-IP POST fails at transport (connection refused)", rc != 0 and ("refused" in err.lower() or "couldn't connect" in err.lower() or rc == 7),
              f"rc={rc} {err.strip()[:200]}")
    rc, out, err = sh(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:8765/mcp"])
    log.check("Then loopback request served with a real HTTP status", out.strip().isdigit() and out.strip() != "000", f"http_code={out.strip()} rc={rc}")
    rc, out, err = sh(["uv", "run", "python", "-m", "freecad_buddy.hosts.main", "serve", "--transport", "http", "--mode", "rpc",
                       "--host", "0.0.0.0"], timeout=120)
    log.write({"rebind": {"rc": rc, "out": out[-500:], "err": err[-500:]}})
    log.check("Then --host 0.0.0.0 exits non-zero with unrecognized-argument error", rc != 0 and "unrecognized arguments" in err,
              f"rc={rc} {err.strip().splitlines()[-1] if err.strip() else ''}")
    rc, out, err = sh(["grep", "-n", r"_HOST\|_PORT", "src/freecad_buddy/hosts/gui_external/entry.py"])
    log.note("grep _HOST/_PORT:\n" + out)
    rc2, out2, _ = sh(["grep", "-n", "os.environ", "src/freecad_buddy/hosts/gui_external/entry.py"])
    env_on_bind = [ln for ln in out2.splitlines() if "_HOST" in ln or "_PORT" in ln or "host" in ln.lower() or "port" in ln.lower()]
    log.check("Then bind hard-coded: literal _HOST/_PORT, no os.environ lookup for them",
              '_HOST = "127.0.0.1"' in out and "_PORT = 8765" in out and not env_on_bind, {"env_lines": out2.splitlines()})
    rc, out, err = sh(["grep", "-riE", "Bearer|Authorization|Origin|CORS", "src/freecad_buddy/hosts/gui_external/entry.py"])
    log.check("Then no auth/Origin/CORS control in entry.py (gap = TC-99-01/02)", out.strip() == "", out.strip()[:300])
    log.check("Then (extra) proxy still serving after the rejected rebind", bool(netstat_port(8765)), netstat_port(8765))

    fa = fitall()
    time.sleep(1)
    log.check("Then (visual) framed by GUI Fit All", fa.get("route") == "accessibility", fa)
    log.check("Then (visual) after captured (pixel judgement by agent)", shot(f"{TAG}-after.png").get("exists"), f"{TAG}-after.png")
    log.save()


asyncio.run(main())
