# prospero.spec
a = Analysis(
    ["src/main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=["pydantic_settings"],  # pydantic sometimes needs explicit hints
    hookspath=[],
    excludes=[
        "PySide6.QtPdf",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngine",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtSql",
        # "PySide6.QtNetwork",
        "PySide6.QtXml",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
    ],
)

# Dlls to be excluded
exclude_dlls = (
    # These dlls are included by pyinstaller's QtNetwork hook. but they aren't shipped by PySide6.
    # So pyinstaller tries to load the dll's from the environment. Which will crash QNetwork if the
    # dlls are mismatching. Since Prospero using only GET to fetch updates, qopensslbackend.dll is
    # enough to my knowledge.
    "libssl-3.dll",
    "libssl-3-x64.dll",
    "libcrypto-3.dll",
    "libcrypto-3-x64.dll",
)

a.binaries = [
    entry for entry in a.binaries if entry[0].lower() not in {dll.lower() for dll in exclude_dlls}
]


pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Prospero",
    console=False,
    icon="assets/icon/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Prospero",
)
