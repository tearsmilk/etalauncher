# PyInstaller spec — builds a single-file "Eta.exe" (Эта; Windows x64). Run packaging/windows_meta.py first.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BUILD = os.path.join(ROOT, "build")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets")],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "numpy", "PySide6.QtWebEngineCore", "PySide6.QtQml",
        "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtNetwork",
        "PySide6.QtOpenGL", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Eta", console=False, strip=False, upx=False,
    icon=os.path.join(BUILD, "Eta.ico"),
    version=os.path.join(BUILD, "version_info.txt"),
)
