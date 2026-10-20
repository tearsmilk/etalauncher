# PyInstaller spec — builds "Eta.app" (Эта; Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

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
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Eta", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Eta", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Eta.app",
    icon=os.path.join(ROOT, "build", "Eta.icns"),
    bundle_identifier="ink.eta.launcher",
    version=VERSION,
    info_plist={
        "CFBundleName": "Эта",
        "CFBundleDisplayName": "Эта",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.games",
    },
)
