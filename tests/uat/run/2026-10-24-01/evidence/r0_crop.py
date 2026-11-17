"""Crop and enlarge a region of a capture for reading: r0_crop.py <in.png> <out.png> x0 y0 x1 y1 [scale]."""
import sys
from PIL import Image

source, target = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(int, sys.argv[3:7])
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 4
region = Image.open(source).crop((x0, y0, x1, y1))
region.resize((region.width * scale, region.height * scale), Image.NEAREST).save(target)
