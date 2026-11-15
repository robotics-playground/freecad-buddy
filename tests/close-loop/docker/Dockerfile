# syntax=docker/dockerfile:1
# Linux XFCE desktop with FreeCAD 1.1.4 and the FreeCAD Buddy release addon, driven by cua-driver.
# Build through compose (tests/close-loop/README.md) after
# `uv run python scripts/build_addon.py --release`, which leaves the current release tree in
# dist/addon/; compose passes that folder as the `addon` build context.

# trycua/cua-xfce:latest on 2026-11-15 (Debian Bookworm, TigerVNC :1, noVNC 6901, cua-driver in /opt/venv).
FROM trycua/cua-xfce@sha256:e188a008084e1034f5ff003e7983c58596d9c0e47adf5c34078b362aad2a57e7

ARG FREECAD_VERSION=1.1.4
ARG FREECAD_APPIMAGE=FreeCAD_1.1.4-Linux-x86_64-py311.AppImage
# Equal to the release's FreeCAD_1.1.4-Linux-x86_64-py311.AppImage-SHA256.txt and its GitHub asset digest.
ARG FREECAD_SHA256=f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434
USER root

# at-spi2-core: the accessibility bus cua-driver reads app widgets through. FreeCAD's AppImage Qt
# has no AT-SPI bridge, so FreeCAD shows only its top-level window there; other apps use it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends at-spi2-core libgl1 libglu1-mesa libegl1 libopengl0 \
 && rm -rf /var/lib/apt/lists/*

# --appimage-extract needs no FUSE, which a container does not have.
RUN curl -fsSL -o /tmp/freecad.AppImage \
      "https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/${FREECAD_APPIMAGE}" \
 && echo "${FREECAD_SHA256}  /tmp/freecad.AppImage" | sha256sum -c - \
 && chmod +x /tmp/freecad.AppImage \
 && cd /opt && /tmp/freecad.AppImage --appimage-extract >/dev/null \
 && mv /opt/squashfs-root /opt/freecad \
 && rm /tmp/freecad.AppImage

# Declared here, not at the top: a declared build argument joins the cache key of every later RUN,
# and the FreeCAD layer above is an 820 MB download.
# The base image bundles cua-driver 0.12.3; the host and the cua-driver skill use 0.28.1.
ARG CUA_DRIVER_VERSION=0.28.1
# Equal to the release's checksums.txt and its GitHub asset digest.
ARG CUA_DRIVER_SHA256=71aa92533de90a68a0a2af930243f1770d23e45b896b57d67a1763da4bfaeaf7
RUN curl -fsSL -o /tmp/cua-driver.tar.gz \
      "https://github.com/trycua/cua/releases/download/cua-driver-rs-v${CUA_DRIVER_VERSION}/cua-driver-rs-${CUA_DRIVER_VERSION}-linux-x86_64-binary.tar.gz" \
 && echo "${CUA_DRIVER_SHA256}  /tmp/cua-driver.tar.gz" | sha256sum -c - \
 && mkdir -p /opt/cua-driver \
 && tar -xzf /tmp/cua-driver.tar.gz -C /opt/cua-driver cua-driver cua-cursor-theme \
 && ln -sf /opt/cua-driver/cua-driver /usr/local/bin/cua-driver \
 && rm /tmp/cua-driver.tar.gz

COPY --chmod=0755 bin/ /usr/local/bin/
COPY supervisor/ /etc/supervisor/conf.d/
COPY --from=addon --chown=cua:cua . /tmp/FreeCADBuddy/

USER cua
# The addon goes where this FreeCAD build looks for user addons; asking FreeCAD avoids guessing
# the versioned user directory layout. A dev build of dist/addon/ has no wheels/ and would leave
# the proxy unstartable here, so the build stops on it.
RUN test -n "$(ls /tmp/FreeCADBuddy/wheels/*.whl)" \
 && moddir="$(fcb-freecad userdir)/Mod" \
 && mkdir -p "$moddir" \
 && mv /tmp/FreeCADBuddy "$moddir/FreeCADBuddy" \
 && test -f "$moddir/FreeCADBuddy/InitGui.py" \
 && /usr/local/bin/cua-driver telemetry disable

USER root
EXPOSE 18765
