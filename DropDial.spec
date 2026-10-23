# PyInstaller spec. ONEFILE=1 -> portable single exe; otherwise a folder for the installer.
import os
from PyInstaller.utils.hooks import collect_all

onefile = os.environ.get("ONEFILE") == "1"
heif_datas, heif_bins, heif_hidden = collect_all("pillow_heif")
# bundled ffmpeg for video/audio (imageio-ffmpeg ships a static binary per platform)
ff_datas, ff_bins, ff_hidden = collect_all("imageio_ffmpeg")
# file families in dropdial/formats import their libraries lazily, so name them here
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
family_hidden = (["yaml", "defusedxml.ElementTree", "defusedxml.minidom", "tomli_w", "tomllib", "plistlib",
                  "openpyxl", "openpyxl.cell._writer", "xlrd", "rawpy", "vtracer"] + collect_submodules("py7zr") + collect_submodules("fontTools") + ["brotli"]
                 + [f"dropdial.formats.{m}" for m in ("sheets", "data", "markup", "subtitles", "archives",
                                                      "fonts", "models", "geo", "rawimages")])
family_hidden += ["lxml.etree", "networkx", "fast_simplification"] + collect_submodules("trimesh.exchange")
family_bins = collect_dynamic_libs("rawpy")
from PyInstaller.utils.hooks import collect_data_files
family_datas = collect_data_files("trimesh")      # PLY export templates
du_datas, du_bins, du_hidden = collect_all("docutils")   # writers and templates load by name
family_datas += du_datas
family_hidden += du_hidden + ["markdown", "shapefile", "defusedxml"]

a = Analysis(
    ["run.py"],
    datas=[("dropdial/assets", "dropdial/assets"), ("dropdial/locales", "dropdial/locales"), ("LICENSE", ".")]
    + heif_datas + ff_datas + family_datas,
    binaries=heif_bins + ff_bins + family_bins,
    hiddenimports=["win32com.client", "PySide6.QtNetwork", "PySide6.QtSvg", "AppKit", "Quartz", "objc"] + heif_hidden + ff_hidden + family_hidden,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtPdf", "pandas", "PySide6.QtSql", "PySide6.QtTest",
              "PySide6.QtOpenGL", "PySide6.QtSvgWidgets", "PySide6.QtDesigner", "matplotlib", "scipy",
              # PyMuPDF 2 pulls in an AI layout add-on (onnxruntime, ~100 MB) DropDial never uses;
              # left out, `import pymupdf.layout` fails and PyMuPDF quietly carries on without it
              "pymupdf.layout", "pymupdf_layout", "pymupdf4llm", "onnxruntime"],
)

DROP = ("Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6WebEngine", "Qt63D", "Qt6Multimedia", "Qt6Charts",
        "Qt6VirtualKeyboard", "Qt6Designer", "Qt6ShaderTools", "Qt6Sql", "Qt6Test", "opengl32sw",
        "Qt6OpenGL", "Qt6DataVisualization", "Qt6Positioning", "Qt6Sensors", "Qt6SerialPort",
        "Qt6Bluetooth", "Qt6Nfc", "Qt6RemoteObjects", "Qt6Scxml", "Qt6SpatialAudio", "Qt6TextToSpeech",
        "Qt6WebChannel", "Qt6WebSockets", "Qt6SvgWidgets", "qtquick", "qml",
        "libgtk-3", "libgdk-3", "libqgtk3", "libatk-")
a.binaries = [b for b in a.binaries if not any(d.lower() in b[0].lower() for d in DROP)]
a.datas = [d for d in a.datas if "translations" not in d[0].replace("\\", "/")]

pyz = PYZ(a.pure)
import sys
IS_MAC = sys.platform == "darwin"
common = dict(name="DropDial", console=False, upx=False)
IS_LINUX = sys.platform.startswith("linux")
if IS_MAC:
    common.update(icon="dropdial/assets/dropdial.icns")
elif IS_LINUX:
    common.update(name="dropdial")       # icon comes from the .desktop file / hicolor theme
else:
    common.update(icon="dropdial/assets/dropdial.ico", version="installer/version_info.txt")

if IS_MAC:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, argv_emulation=False, **common)
    coll = COLLECT(exe, a.binaries, a.datas, name="DropDial", upx=False)
    app = BUNDLE(
        coll,
        name="DropDial.app",
        icon="dropdial/assets/dropdial.icns",
        bundle_identifier="com.prithwirajmukherjee.dropdial",
        info_plist={
            "CFBundleName": "DropDial",
            "CFBundleDisplayName": "DropDial",
            "CFBundleShortVersionString": "1.1.0",
            "CFBundleVersion": "1.1.0",
            "NSHumanReadableCopyright": "© 2026 Prithwiraj Mukherjee. Made by Prithwiraj Mukherjee.",
            "CFBundleGetInfoString": "DropDial 1.1.0, made by Prithwiraj Mukherjee",
            "LSUIElement": True,                 # menu-bar app, no Dock icon
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            # show up in Finder's "Open With" for any file, and accept drops on the app icon
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Any file",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.item", "public.content", "public.data"],
            }],
        },
    )
elif IS_LINUX:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, name="dropdial", upx=False)  # no strip: breaks OpenBLAS with Debian 12 binutils
elif onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, name="DropDial", upx=False)
