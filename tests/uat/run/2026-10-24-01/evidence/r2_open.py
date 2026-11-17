"""Open a file in the GUI over :8765 and print its handle: r2_open.py <tag> <path>."""
import sys

from r2_p5_lib import Run5

with Run5(sys.argv[1]) as run:
    result = run.call("document_open", {"path": sys.argv[2]}, "given open")
    print("DOC", (result.get("structured_content") or {}).get("doc"))
