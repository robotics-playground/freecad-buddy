#!/bin/bash
# usage: iso_fit_shot.sh <png name>: Isometric and Fit All toolbar buttons by element token, then a capture.
set -u
cd "$(dirname "$0")"
C=./cua.sh
W='"pid":506,"window_id":37748829'
$C get_window_state "{$W,\"include_screenshot\":false}" > is1.json
$C click "{\"pid\":506,\"element_token\":\"$(python tok.py is1.json "push button" "Isometric")\"}" | grep -E '"effect"'
$C get_window_state "{$W,\"include_screenshot\":false}" > is2.json
$C click "{\"pid\":506,\"element_token\":\"$(python tok.py is2.json "push button" "Fit All")\"}" | grep -E '"effect"'
$C get_window_state "{$W,\"screenshot_out_file\":\"/repo/tests/uat/run/13-5-r1/evidence/$1\"}" > is3.json
python -c "
import json;d=json.load(open('is3.json'))
print([e['label'] for e in d['elements'] if str(e.get('label','')).startswith('Python 3')][0][-400:])"
