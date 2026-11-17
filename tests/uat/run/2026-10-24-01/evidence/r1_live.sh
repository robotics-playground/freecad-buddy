# r1_live.sh <stem>: display liveness check after the capture <stem>.png. Clicks the property panel
# "View" tab (background UIA), captures <stem>-live.png, clicks the "Data" tab back, and prints the
# number of pixels and the box in which <stem>-live.png differs from <stem>.png. A live display shows
# a difference in the property panel (the tab change); a stale one shows none.
cd "$(dirname "$0")"
stem=$1
uv run python r1_gui.py click "View" TabItem > /dev/null
sleep 1
uv run python r1_gui1.py shot "$stem-live" > /dev/null
uv run python r1_gui.py click "Data" TabItem > /dev/null
uv run --with pillow python -c "
from PIL import Image, ImageChops
a = Image.open('$stem.png').convert('RGB'); b = Image.open('$stem-live.png').convert('RGB')
d = ImageChops.difference(a, b); box = d.getbbox()
n = sum(1 for p in d.getdata() if p != (0, 0, 0))
print('live-check $stem: differing pixels', n, 'box', box)
"
