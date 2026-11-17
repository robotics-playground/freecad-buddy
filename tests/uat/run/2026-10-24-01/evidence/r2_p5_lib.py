"""MCP helpers for phase P5 (TC-06, TC-08), on top of p4_lib.Run4.

Differences from p4_lib.Run4:
- every call also records the MCP content block types (``content_types``), so a Then about an
  ``images`` array or an image block is read from the wire, not inferred;
- ``render(result, stem)`` copies the PNG named by ``structured_content.render.resource_link`` to
  ``evidence/<stem>.png`` and prints its size;
- ``tempdocs(doc)`` is the TC-08 preview TempDoc check, listed in-process.

    from p5_lib import Run5
    with Run5("tc-06-01") as run:
        ...
"""

import json
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import mcp_client  # noqa: E402
import r2_p4_lib  # noqa: E402,F401  (installs the isError wrapper this module extends)
from r2_p4_lib import Run4, redact  # noqa: E402
from r2_p3_lib import q  # noqa: E402,F401

EVIDENCE = Path(__file__).resolve().parent

_wrapped = mcp_client.to_result


def _with_content(call_result):
    raw = _wrapped(call_result)
    raw["__content_types"] = [block.type for block in call_result.content]
    return raw


mcp_client.to_result = _with_content

TEMPDOC_CHECK = ("import glob, os; from freecad_buddy.usecases.documents import temp_dir; "
                 "result = glob.glob(os.path.join(temp_dir(), 'FCB_TMP_prev_*'))")


def link_path(link):
    if not link:
        return None
    if isinstance(link, dict):
        link = link.get("uri") or link.get("path") or link.get("resource_link")
    if link.startswith("file:"):
        parsed = urlparse(link)
        path = unquote(parsed.path)
        if len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return Path(path)
    return Path(link)


class Run5(Run4):
    def call(self, tool, args, label="", quiet=False):
        raw = self.client.call(tool, args)
        is_error, result, types = raw["__is_error"], raw["__result"], raw["__content_types"]
        self.log.write(json.dumps({"label": label, "mcp": tool, "args": redact(args), "is_error": is_error,
                                   "content_types": types, "result": redact(result)}, ensure_ascii=False) + "\n")
        self.log.flush()
        if quiet:
            print(f"== [{label}] {tool} -> {result.get('status')}")
        else:
            shown = {k: v for k, v in args.items() if k != "doc"}
            print(f"== [{label}] {tool} {json.dumps(redact(shown), ensure_ascii=False)[:300]}")
            print(f"   isError={is_error} content={types} "
                  f"{json.dumps(redact(result), ensure_ascii=False)[:self.limit]}")
        return result

    def render(self, result, stem):
        render = ((result.get("structured_content") or {}).get("render") or {})
        source = link_path(render.get("resource_link"))
        if source is None or not source.exists():
            print(f"   render {stem}: no file ({render.get('resource_link')!r})")
            return None
        target = EVIDENCE / f"{stem}.png"
        shutil.copyfile(source, target)
        try:
            from PIL import Image
            size = Image.open(target).size
        except Exception as exc:  # PIL missing is reported, not fatal
            size = f"size unknown: {exc}"
        print(f"   render {stem}: {source} -> {target.name} size={size} bytes={target.stat().st_size}")
        return target

    def tempdocs(self, doc, label="tempdoc check"):
        return self.py(doc, TEMPDOC_CHECK, label)
