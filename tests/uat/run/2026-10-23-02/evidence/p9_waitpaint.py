"""Every 120 s, capture FreeCAD window 661808 (pid 36140) to the scratchpad and test whether its body is painted:
the unpainted frame has a black left strip (x 70, y 500). Stops at the first painted frame or after 30 min.
Each probe is logged to evidence/tc-11-19-paint-probes.txt."""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import png  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
PROBE = Path(sys.argv[1])
deadline = time.monotonic() + 30 * 60
with (EVIDENCE / "tc-11-19-paint-probes.txt").open("a", encoding="utf-8") as log:
    while True:
        subprocess.run(["cua-driver", "get_window_state",
                        f'{{"pid":36140,"window_id":661808,"include_screenshot":true,"screenshot_out_file":"{PROBE.as_posix()}"}}'],
                       capture_output=True)
        image = png.read(PROBE)
        painted = image.rgb(70, 500) != (0, 0, 0)
        log.write(f"{datetime.now().strftime('%H:%M:%S')} pixel(70,500)={image.rgb(70, 500)} painted={painted}\n")
        log.flush()
        if painted or time.monotonic() > deadline:
            print("painted" if painted else "still covered after 30 min")
            break
        time.sleep(120)
