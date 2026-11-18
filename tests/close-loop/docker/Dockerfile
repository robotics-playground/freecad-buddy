# syntax=docker/dockerfile:1
# Linux XFCE desktop with FreeCAD 1.1.4 and the FreeCAD Buddy release addon, driven by cua-driver.
# Build through compose (tests/close-loop/README.md) after
# `uv run python scripts/build_addon.py --release`, which leaves the current release tree in
# dist/addon/; compose passes that folder as the `addon` build context.

# Builder for libQt6Gui and libQt6XcbQpa with the AT-SPI bridge. The AppImage's Qt (conda-forge
# qt6-main 6.8.3) is configured without libatspi, so FreeCAD's widgets never reach the
# accessibility bus. Qt enables the bridge only when configure finds libatspi
# (qtbase 6.8.3 src/gui/configure.cmake: accessibility-atspi-bridge needs ATSPI2_FOUND), and
# -DFEATURE_accessibility_atspi_bridge=ON makes configure fail when it does not. Only the Gui and
# XcbQpa targets are built; the runtime stage swaps those two libraries into the AppImage and
# checks that each exports every symbol of the original.
FROM trycua/cua-xfce@sha256:e188a008084e1034f5ff003e7983c58596d9c0e47adf5c34078b362aad2a57e7 AS qt-build
ARG QT_VERSION=6.8.3
# Equal to download.qt.io/archive/qt/6.8/6.8.3/submodules/qtbase-everywhere-src-6.8.3.tar.xz.sha256.
ARG QTBASE_SHA256=56001b905601bb9023d399f3ba780d7fa940f3e4861e496a7c490331f49e0b80
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential cmake ninja-build perl python3 patchelf ca-certificates curl xz-utils \
      pkg-config libatspi2.0-dev libdbus-1-dev libglib2.0-dev libfontconfig-dev libfreetype-dev \
      libharfbuzz-dev libpng-dev zlib1g-dev libicu-dev libgl-dev libegl-dev libvulkan-dev \
      libxkbcommon-dev libx11-dev libx11-xcb-dev libxrender-dev libxi-dev libxext-dev \
      libxkbcommon-x11-dev libxcb1-dev libxcb-glx0-dev libxcb-keysyms1-dev libxcb-image0-dev \
      libxcb-shm0-dev libxcb-icccm4-dev libxcb-sync-dev libxcb-xfixes0-dev libxcb-shape0-dev \
      libxcb-randr0-dev libxcb-render-util0-dev libxcb-util-dev libxcb-xinerama0-dev \
      libxcb-xkb-dev libxcb-cursor-dev libxcb-render0-dev libxcb-present-dev libxcb-dri3-dev \
      libwayland-dev libglx-dev libdrm-dev libgbm-dev \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /tmp/qtbase.tar.xz \
      "https://download.qt.io/archive/qt/6.8/${QT_VERSION}/submodules/qtbase-everywhere-src-${QT_VERSION}.tar.xz" \
 && echo "${QTBASE_SHA256}  /tmp/qtbase.tar.xz" | sha256sum -c - \
 && mkdir /src \
 && tar -xJf /tmp/qtbase.tar.xz -C /src --strip-components=1 \
 && rm /tmp/qtbase.tar.xz
# Features follow the conda-forge qt-main-feedstock recipe (vulkan, egl, xcb, xcb_xlib, xkbcommon,
# wayland on) so that only the AT-SPI bridge differs from the AppImage's library. With xcb and
# wayland off, the library lacks the QNativeInterface X11, GLX and Wayland symbols (83 measured).
RUN cmake -G Ninja -S /src -B /build \
      -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
      -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF \
      -DFEATURE_vulkan=ON -DFEATURE_egl=ON -DFEATURE_xcb=ON -DFEATURE_xcb_xlib=ON \
      -DFEATURE_xkbcommon=ON -DFEATURE_wayland=ON \
      -DFEATURE_accessibility_atspi_bridge=ON \
 && cmake --build /build --target Gui \
 && mkdir /out \
 && cp -L /build/lib/libQt6Gui.so.${QT_VERSION} /out/libQt6Gui.so.${QT_VERSION} \
 && patchelf --set-rpath '$ORIGIN/.:$ORIGIN' /out/libQt6Gui.so.${QT_VERSION} \
 && strip --strip-unneeded /out/libQt6Gui.so.${QT_VERSION}
# A separate step, so the Gui build above stays cached. It reuses the configured /build tree.
# libQt6XcbQpa holds QXcbIntegration::accessibility(), which creates the AT-SPI bridge; the conda
# build returns a null member there, so FreeCAD stays off the accessibility bus.
RUN cmake --build /build --target XcbQpaPrivate \
 && cp -L /build/lib/libQt6XcbQpa.so.${QT_VERSION} /out/libQt6XcbQpa.so.${QT_VERSION} \
 && patchelf --set-rpath '$ORIGIN/.:$ORIGIN' /out/libQt6XcbQpa.so.${QT_VERSION} \
 && strip --strip-unneeded /out/libQt6XcbQpa.so.${QT_VERSION}

# trycua/cua-xfce:latest on 2026-11-15 (Debian Bookworm, TigerVNC :1, noVNC 6901, cua-driver in /opt/venv).
FROM trycua/cua-xfce@sha256:e188a008084e1034f5ff003e7983c58596d9c0e47adf5c34078b362aad2a57e7

ARG FREECAD_VERSION=1.1.4
ARG FREECAD_APPIMAGE=FreeCAD_1.1.4-Linux-x86_64-py311.AppImage
# Equal to the release's FreeCAD_1.1.4-Linux-x86_64-py311.AppImage-SHA256.txt and its GitHub asset digest.
ARG FREECAD_SHA256=f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434
USER root

# at-spi2-core: the accessibility bus cua-driver reads app widgets through.
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

# The AppImage's conda-forge libQt6Gui and libQt6XcbQpa have no AT-SPI bridge. Swap in the ones
# built by the qt-build stage; the script stops the build when one lacks an exported symbol of the
# original. The originals stay in /opt/qt-original for comparison runs.
COPY --from=qt-build /out/ /tmp/qt-out/
COPY --chmod=0755 swap-qt-gui.sh /tmp/swap-qt-gui.sh
RUN /tmp/swap-qt-gui.sh /tmp/qt-out/libQt6Gui.so.6.8.3 /opt/freecad/usr/lib /opt/qt-original \
 && /tmp/swap-qt-gui.sh /tmp/qt-out/libQt6XcbQpa.so.6.8.3 /opt/freecad/usr/lib /opt/qt-original \
 && rm -r /tmp/qt-out /tmp/swap-qt-gui.sh

# Third-party packages for the runner, the watchdog and the H1 host, run by the AppImage's Python:
# the uv.lock runtime tree with hashes (tests/close-loop/README.md, `fcb-py`).
COPY requirements-site.txt /tmp/requirements-site.txt
RUN /opt/freecad/AppRun python -m pip install --no-cache-dir --require-hashes --no-deps \
      --target /opt/fcb-site -r /tmp/requirements-site.txt \
 && rm /tmp/requirements-site.txt

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
# One launcher entry for the XFCE Applications menu and one for the desktop. It runs `fcb-freecad
# start`, not the AppImage, so the session environment, the log and the single-instance check apply.
COPY applications/fcb-freecad.desktop /usr/share/applications/fcb-freecad.desktop
COPY --chown=cua:cua --chmod=0755 applications/fcb-freecad.desktop /home/cua/Desktop/fcb-freecad.desktop
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
