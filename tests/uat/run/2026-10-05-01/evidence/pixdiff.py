"""Compare two PNGs: changed-pixel share, mean RGB and HSV of non-white pixels. Run: uv run --with pillow python pixdiff.py A B"""
import sys, colorsys
from PIL import Image, ImageChops
a = Image.open(sys.argv[1]).convert("RGB"); b = Image.open(sys.argv[2]).convert("RGB")
print("sizes", a.size, b.size)
if a.size == b.size:
    d = ImageChops.difference(a, b).convert("L")
    changed = sum(1 for v in d.getdata() if v > 8)
    print("changed pixels (>8)", changed, "of", a.size[0] * a.size[1])
for name, img in (("A", a), ("B", b)):
    px = [p for p in img.getdata() if not (p[0] > 245 and p[1] > 245 and p[2] > 245)]
    if not px:
        print(name, "all white"); continue
    m = tuple(sum(c[i] for c in px) / len(px) for i in range(3))
    hsv = colorsys.rgb_to_hsv(*(v / 255 for v in m))
    print(name, "non-white px", len(px), "mean rgb", tuple(round(v, 1) for v in m), "hsv", tuple(round(v, 3) for v in hsv))
