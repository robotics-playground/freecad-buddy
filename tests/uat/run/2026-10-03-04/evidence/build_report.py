"""Rebuild the per-TC tables in report.md from evidence/tc-NN-results.json; keep head and tail."""
import glob, subprocess, sys
from pathlib import Path
run = Path(__file__).resolve().parent.parent
report = (run / "report.md").read_text(encoding="utf-8")
head = report.split("## TC-01 ")[0]
tail = report[report.index("## Gate 1 summary"):] if "## Gate 1 summary" in report else ""
parts = [head]
for n in sys.argv[1:]:
    case = glob.glob(str(run / f"../../testcases/TC-{n}-*.md"))[0]
    title = open(case, encoding="utf-8").readline().strip().split(": ", 1)[1]
    table = subprocess.run([sys.executable, "table.py", n], cwd=run / "evidence",
                           capture_output=True, text=True, encoding="utf-8").stdout
    parts.append(f"## TC-{n} — {title}\n\n{table}\n")
parts.append(tail)
(run / "report.md").write_text("".join(parts), encoding="utf-8")
