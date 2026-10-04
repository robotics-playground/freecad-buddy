"""Corroboration: the shipped rpc_client liveness check (_pid_alive, GetExitCodeProcess at bece7ac) and discover()."""
import glob, json, os, subprocess
from freecad_buddy.adapters import rpc_client
print("rpc_client module:", rpc_client.__file__)
running = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
for path in sorted(glob.glob(os.path.expandvars(r"%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json"))):
    pid = json.load(open(path))["pid"]
    image = next((line.split(",")[0].strip('"') for line in running.splitlines() if line.split(",")[1].strip('"') == str(pid)), "-")
    print(f"{os.path.basename(path)}: _pid_alive={rpc_client._pid_alive(pid)} tasklist_image={image}")
rec = rpc_client.discover()
print("discover() ->", None if rec is None else {"pid": rec["pid"], "port": rec["port"]})
