#!/bin/bash
# Build-time step: put an AT-SPI-enabled Qt library (libQt6Gui or libQt6XcbQpa) into the extracted
# FreeCAD AppImage.
#   swap-qt-gui.sh <rebuilt library> <AppImage library directory> <backup directory>
# The AppImage keeps its other Qt libraries, so the rebuilt library must export every symbol (with
# its version tag, Qt_6 and Qt_6_PRIVATE_API) that the original exports. The step fails when one is
# missing, and the build stops. The original goes to <backup directory> for comparison runs.
set -euo pipefail
new="$1"
libdir="$2"
backup="$3"
original="$libdir/$(basename "$new")"

exports() {
    readelf --dyn-syms -W "$1" | awk '$7 != "UND" && $8 != "" { print $8 }' | sort -u
}
versions() {
    objdump -p "$1" | awk '/^Version definitions:/ {on=1; next} /^Version References:/ {on=0} on && $4 != "" {print $4}' | sort -u
}

exports "$original" >/tmp/exports-original.txt
exports "$new" >/tmp/exports-new.txt
versions "$original" >/tmp/versions-original.txt
versions "$new" >/tmp/versions-new.txt
echo "swap-qt-gui: exported symbols original=$(wc -l </tmp/exports-original.txt) new=$(wc -l </tmp/exports-new.txt)"
echo "swap-qt-gui: version tags original=[$(tr '\n' ' ' </tmp/versions-original.txt)] new=[$(tr '\n' ' ' </tmp/versions-new.txt)]"
# The original, built by conda-forge against FreeType 2.13, exports two COLRv1 colour-glyph methods
# of QFontEngineFT that Debian's FreeType 2.12 cannot compile, plus the toolchain stubs _init and
# _fini. Measured on the AppImage (1980 ELF files under /opt/freecad, `nm -D --undefined-only`):
# no file imports any of these four names. Any other missing symbol stops the build.
allowed='^(_init(@@Qt_6)?|_fini(@@Qt_6)?|_ZNK13QFontEngineFT13traverseColr1E16FT_Opaque_Paint_PNS_14Colr1PaintInfoE@@Qt_6_PRIVATE_API|_ZNK13QFontEngineFT15loadColrv1GlyphEPNS_9QGlyphSetEPN11QFontEngine5GlyphEjRK6QColorb@@Qt_6_PRIVATE_API)$'
# grep exits 1 when every line is allowed; any other failure (a bad pattern) must stop the build.
missing="$(comm -23 /tmp/exports-original.txt /tmp/exports-new.txt | { grep -v -E "$allowed" || [ $? -eq 1 ]; })"
if [ -n "$missing" ]; then
    echo "swap-qt-gui: the rebuilt library lacks $(echo "$missing" | wc -l) exported symbols; first ten:" >&2
    echo "$missing" | head -n 10 >&2
    exit 1
fi
if ! diff -q /tmp/versions-original.txt /tmp/versions-new.txt >/dev/null; then
    echo "swap-qt-gui: version tags differ" >&2
    exit 1
fi
mkdir -p "$backup"
cp -p "$original" "$backup/"
install -m 0755 "$new" "$original"
