"""Pixel diff of two window captures: count of differing pixels."""
import sys
from PIL import Image, ImageChops
a, b = (Image.open(p).convert("RGB") for p in sys.argv[1:3])
print(sys.argv[1], sys.argv[2], "sizes", a.size, b.size, end=" ")
if a.size == b.size:
    d = ImageChops.difference(a, b); bbox = d.getbbox()
    n = sum(1 for px in d.getdata() if px != (0, 0, 0))
    print("differing_pixels", n, "bbox", bbox)
