"""Sample pixel colours at given points: python tc06px.py file.png x,y x,y ..."""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
print(sys.argv[1].split("/")[-1], im.size)
for pt in sys.argv[2:]:
    x, y = map(int, pt.split(","))
    print(f"  ({x},{y}) -> {im.getpixel((x, y))}")
