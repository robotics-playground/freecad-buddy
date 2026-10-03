"""Capture the clean-control renders for the render-tone fault suite.

Run under FreeCADCmd, which is where the render stack lives::

    FreeCADCmd benchmarks/g0/render-fault-injection/capture_render_controls.py

One control per camera: the golden 10x20x30 box rendered by the shipped ``OffscreenRenderPort``.
A control must be a real render, never a synthesized image -- the false-alarm rate is the rate at
which the oracle rejects output the renderer actually produces, so a hand-made "clean" PNG would
measure nothing. Re-run this after any lighting change and commit the result.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import FreeCAD as App  # noqa: E402

from freecad_buddy.adapters.render_probe import OffscreenRenderPort, render_capability  # noqa: E402
from freecad_buddy.contracts.render import SceneSpec  # noqa: E402
from freecad_buddy.usecases import screenshot  # noqa: E402

BOX_L, BOX_W, BOX_H = 10.0, 20.0, 30.0
SIZE = 240

# The same explicit quaternion the in-FreeCAD camera sweep uses for `custom`.
CUSTOM_QUAT = (0.2, 0.3, 0.1, 0.9273618)

VIEW_PREFERENCES = "User parameter:BaseApp/Preferences/View"
SHAPE_COLOR_KEY = "DefaultShapeColor"
STOCK_SHAPE_COLOR = 0xCCCCE6FF


def main() -> int:
    mode, reason = render_capability()
    if mode == "none":
        sys.stderr.write(f"  no render context: {reason}\n")
        return 1

    # Pin FreeCAD's stock box color so the captures do not depend on the developer's profile.
    preferences = App.ParamGet(VIEW_PREFERENCES)
    saved_color = (
        preferences.GetUnsigned(SHAPE_COLOR_KEY)
        if SHAPE_COLOR_KEY in preferences.GetUnsigneds()
        else None
    )
    preferences.SetUnsigned(SHAPE_COLOR_KEY, STOCK_SHAPE_COLOR)
    try:
        document = App.newDocument("render_controls")
        box = document.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = BOX_L, BOX_W, BOX_H
        document.recompute()

        port = OffscreenRenderPort()
        cameras = dict(screenshot._CAMERA_QUATS)
        cameras["custom"] = CUSTOM_QUAT

        for name, orientation in sorted(cameras.items()):
            directory = HERE / f"clean-control-{name}"
            directory.mkdir(parents=True, exist_ok=True)
            scene = SceneSpec(objects=["Box"], orientation=orientation, width=SIZE, height=SIZE)
            port.render(document, scene, str(directory / "render.png"))
            sys.stderr.write(f"  captured clean-control-{name}/render.png\n")

        App.closeDocument(document.Name)
    finally:
        if saved_color is None:
            preferences.RemUnsigned(SHAPE_COLOR_KEY)
        else:
            preferences.SetUnsigned(SHAPE_COLOR_KEY, saved_color)
    return 0


def _is_top_level_script() -> bool:
    """Whether this file is the script the interpreter was launched with.

    FreeCADCmd runs a script with ``__name__`` set to the file stem rather than ``"__main__"``,
    so the standard guard alone silently skips the capture (mirrors ``tests/run_tests.py``).
    """
    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
    return False


if _is_top_level_script():
    sys.exit(main())
