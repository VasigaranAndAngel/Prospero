# prospero.spec
a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=['pydantic_settings'],  # pydantic sometimes needs explicit hints
    hookspath=[],
    excludes=[],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Prospero',
    console=False,
    icon='assets/icon/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='Prospero',
)