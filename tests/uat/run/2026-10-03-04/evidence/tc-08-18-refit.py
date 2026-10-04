from tc08lib import *  # noqa


async def body(m, log):
    gdoc = json.loads((EVIDENCE / "tc-08-18-gui.json").read_text())["gdoc"]
    log.note("golden box opened hidden (known harness fact); View > Visibility > Show All Objects via cua-driver invoke_menu, then re-fit and re-capture before")
    mp = await m.call("query_mass_properties", {"doc": gdoc, "object": "Box"})
    log.note(f"GUI golden box volume before headless runs: {vol(mp)}")
    await frame_shot(m, gdoc, "tc-08-18-before.png")


go("tc-08-18-refit", body)
