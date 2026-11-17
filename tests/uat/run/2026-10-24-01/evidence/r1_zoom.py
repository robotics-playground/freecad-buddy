"""Crop a box of a PNG and scale it up with nearest-neighbour, and count the distinct colours in the
crop: r1_zoom.py <in.png> <out.png> x0 y0 x1 y1 [scale]. The count separates a blended (anti-aliased)
edge from a hard two-colour stair."""
import sys
from PIL import Image

src, out, x0, y0, x1, y1 = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 8
crop = Image.open(src).convert("RGB").crop((x0, y0, x1, y1))
colours = crop.getcolors(1 << 20)
print(f"size={Image.open(src).size} crop={crop.size} distinct colours={len(colours)}")
print("top colours:", sorted(colours, reverse=True)[:8])
crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST).save(out)
