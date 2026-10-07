"""Start FreeCAD through cua-driver with environment variables and a macro to run.

cua-driver launch_app takes no environment, so it starts cmd.exe, which sets the variables and
starts FreeCAD with the macro as its argument; FreeCAD runs it once the main window is up.

    python launch_macro.py <macro path> NAME=value [NAME=value ...]
"""

import json
import subprocess
import sys

FREECAD = r"C:\Program Files\FreeCAD 1.1\bin\freecad.exe"

macro, assignments = sys.argv[1], sys.argv[2:]
command = "".join(f"set {assignment}&& " for assignment in assignments)
command += f'start "" "{FREECAD}" "{macro}"'
request = {"path": r"C:\Windows\System32\cmd.exe", "additional_arguments": ["/c", command]}
result = subprocess.run(
    ["cua-driver", "launch_app"], input=json.dumps(request), capture_output=True, text=True
)
print(result.stdout, result.stderr)
