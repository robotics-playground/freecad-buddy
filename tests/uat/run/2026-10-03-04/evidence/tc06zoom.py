"""Crop a region and upscale with nearest-neighbour: python tc06zoom.py in.png out.png x0 y0 x1 y1 scale"""
import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
x0, y0, x1, y1, k = map(int, sys.argv[3:8])
im = Image.open(src).convert("RGB").crop((x0, y0, x1, y1))
im = im.resize((im.width * k, im.height * k), Image.NEAREST)
im.save(dst)
# count distinct colours along the crop as an AA indicator
px = list(Image.open(src).convert("RGB").crop((x0, y0, x1, y1)).getdata())
print(dst, "distinct colours in crop:", len(set(px)))
