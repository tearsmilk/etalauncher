"""Windows build metadata without extra dependencies: build/Eta.ico from assets/icon.png (via Qt, already a
runtime dependency) and build/version_info.txt for PyInstaller. Usage: python packaging/windows_meta.py [version]"""
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = (256, 128, 64, 48, 32, 16)


def png_bytes(image, size):
    from PySide6.QtCore import QBuffer, QIODevice, Qt

    scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    scaled.save(buf, "PNG")
    return bytes(buf.data())


def make_ico(src, dest):
    from PySide6.QtGui import QGuiApplication, QImage

    QGuiApplication.instance() or QGuiApplication([])
    image = QImage(str(src))
    if image.isNull():
        raise SystemExit(f"cannot read {src}")
    frames = [png_bytes(image, s) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    entries, blobs = b"", b""
    for size, data in zip(SIZES, frames):
        dim = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    dest.write_bytes(header + entries + blobs)


def make_version_file(dest, version):
    nums = [int(x) for x in (version.split(".") + ["0", "0", "0"])[:4] if x.isdigit()]
    nums = (nums + [0, 0, 0, 0])[:4]
    tup = ", ".join(str(n) for n in nums)
    dest.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Lotus'),
      StringStruct('FileDescription', 'Эта — Minecraft launcher'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'Eta'),
      StringStruct('LegalCopyright', 'Lotus. Not an official Minecraft product.'),
      StringStruct('OriginalFilename', 'Eta.exe'),
      StringStruct('ProductName', 'Эта'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", "utf-8")


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from eta import __version__

    version = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else __version__
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    make_ico(ROOT / "assets" / "icon.png", build / "Eta.ico")
    make_version_file(build / "version_info.txt", version)
    print(f"Eta.ico + version_info.txt ({version}) -> {build}")
