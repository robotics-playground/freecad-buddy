"""Pixel difference of two captures: p0_diff.py <a.png> <b.png>. Prints the count of differing pixels and their bounding box."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import png  # noqa: E402

a, b = png.read(Path(sys.argv[1])), png.read(Path(sys.argv[2]))
if (a.width, a.height) != (b.width, b.height):
    raise SystemExit(f"size differs: {a.width}x{a.height} vs {b.width}x{b.height}")
diff = [(x, y) for y in range(a.height) for x in range(a.width) if a.rgb(x, y) != b.rgb(x, y)]
box = (min(x for x, _ in diff), min(y for _, y in diff), max(x for x, _ in diff), max(y for _, y in diff)) if diff else None
print(f"{len(diff)} of {a.width * a.height} pixels differ; bbox {box}")
