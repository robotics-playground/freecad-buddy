"""r2_diff.py <a.png> <b.png> [x0 y0 x1 y1]: count differing pixels (whole image or the box) and
print the bounding box of the difference."""
import sys
from PIL import Image, ImageChops
a = Image.open(sys.argv[1]).convert("RGB")
b = Image.open(sys.argv[2]).convert("RGB")
if len(sys.argv) > 3:
    box = tuple(int(v) for v in sys.argv[3:7])
    a, b = a.crop(box), b.crop(box)
d = ImageChops.difference(a, b)
print("differing pixels", sum(1 for p in d.get_flattened_data() if p != (0, 0, 0)), "bbox", d.getbbox())
