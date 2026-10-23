# Changelog

## [0.1.2](https://github.com/robotics-playground/freecad-buddy/compare/v0.1.1...v0.1.2) (2026-10-23)


### Bug Fixes

* **addon:** start the MCP proxy on macOS ([50e810e](https://github.com/robotics-playground/freecad-buddy/commit/50e810eeaecb6df3de4c2f202fbd11412c23cbfe))

## [0.1.1](https://github.com/robotics-playground/freecad-buddy/compare/v0.1.0...v0.1.1) (2026-10-22)


### Bug Fixes

* **skills:** close code-cad-conversion gaps found on the enclosure model ([c42c20a](https://github.com/robotics-playground/freecad-buddy/commit/c42c20ad276a5a8d18df195ee74382d1f523c6b1))

## [0.1.0](https://github.com/robotics-playground/freecad-buddy/compare/v0.0.1...v0.1.0) (2026-10-22)


### Features

* **headless:** bound every call in the front and quarantine the session on timeout ([d9895ce](https://github.com/robotics-playground/freecad-buddy/commit/d9895cee90179310a53a5afddbc5b545a5806e1f))
* **headless:** split the H1 stdio host into front and FreeCAD worker processes ([f040f5e](https://github.com/robotics-playground/freecad-buddy/commit/f040f5e79335cb5a45ecf186b90fd388ced62a2d))
* **mcp:** make script_exec an official tool, on by default ([4e6a682](https://github.com/robotics-playground/freecad-buddy/commit/4e6a68266eb498cfced2789110c7d161159037d4))
* **skills:** add code-cad-conversion skill for build123d/CadQuery to parametric FreeCAD ([a09c0d8](https://github.com/robotics-playground/freecad-buddy/commit/a09c0d8c77ca3dcf0f8b6a33dffafa6c4a750ffb))


### Bug Fixes

* **ci:** make render and G0 gates fail on real defects ([23eb932](https://github.com/robotics-playground/freecad-buddy/commit/23eb9320dc70a7b766769debc27bea659c6c8fbb))
* **gui:** bind the MCP proxy to its FreeCAD and never adopt a held :8765 ([b792cad](https://github.com/robotics-playground/freecad-buddy/commit/b792cad387b0eb30d1622cf1d8f5b2fd17b0e665))
* **rpc:** log each connection end once at the right level ([efadc01](https://github.com/robotics-playground/freecad-buddy/commit/efadc0125ad2ec37632b8e12bc9b321a153bbd77))
* **rpc:** refuse a second client with the AD-26 busy error ([feabd50](https://github.com/robotics-playground/freecad-buddy/commit/feabd506f53972999210370b688c062d5accceb1))


### Documentation

* **architecture:** make script_exec an official tool, on by default ([e1c977f](https://github.com/robotics-playground/freecad-buddy/commit/e1c977f9a7003a7ea3ab216db24d2a0e00c64926))
* **architecture:** split headless host into front and FreeCAD worker processes ([60b49d5](https://github.com/robotics-playground/freecad-buddy/commit/60b49d517d5aa0e31f4f264a97d2fa82ac56bbc7))
* **uat:** align UAT suite and GUI harness with the shipped bridge ([18a0b0f](https://github.com/robotics-playground/freecad-buddy/commit/18a0b0fd9893202d324b330f00883672aaddeaa6))


### Miscellaneous Chores

* **release:** release 0.1.0 ([ae0d814](https://github.com/robotics-playground/freecad-buddy/commit/ae0d814c5085aedbda09d4325a50bba4d040089f))

## 0.0.1 (2026-10-09)


### Features

* **release:** ship 0.0.1 as an installable addon with a preferences page and a Claude plugin ([a07929b](https://github.com/robotics-playground/freecad-buddy/commit/a07929ba74152766c4a0b8b12e591be2664f3fc8))
