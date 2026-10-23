#!/bin/bash
# Build "Eta.app" (Эта) and Eta-<version>-macOS-x64.dmg on an Intel Mac / macOS runner
# with python.org Python 3.11 (universal2, macOS 10.9+).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${APP_VERSION:-$(python3 -c 'import eta; print(eta.__version__)')}"
export APP_VERSION="$VERSION"
# bake the CurseForge key (GitHub secret ETA_CURSEFORGE_KEY) into the bundle; eta/_keys.py is gitignored
printf 'CURSEFORGE_KEY = %s\n' "$(python3 -c 'import json,os; print(json.dumps(os.environ.get("ETA_CURSEFORGE_KEY","")))')" > eta/_keys.py
export MACOSX_DEPLOYMENT_TARGET=11.0
PY="${PYTHON:-python3}"

rm -rf build dist
mkdir -p build
ICONSET=build/Eta.iconset
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/Eta.icns

"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyi packaging/Eta.spec
APP="dist/Eta.app"
xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

"$PY" packaging/check_min_macos.py "$APP" 11.0
HOME="$(mktemp -d)" "$APP/Contents/MacOS/Eta" --selftest

STAGE=build/dmg
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/README-dmg.txt "$STAGE/Прочти меня.txt"
DMG="dist/Eta-$VERSION-macOS-x64.dmg"
hdiutil create -volname "Эта" -srcfolder "$STAGE" -ov -format UDZO -fs HFS+ "$DMG"
hdiutil verify "$DMG"
ls -lh "$DMG"
