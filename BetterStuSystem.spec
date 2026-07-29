# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

flet_datas = collect_data_files('flet')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('SHIEP-Pipeline-v2.0.0-windows-x64.exe', '.')],
    datas=[
        ('Image_1763040610208.jpg', '.'),
        ('509e691a73ef7ce9cc08e7dbe27b2864.jpg', '.'),
        *flet_datas,
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BetterStuSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BetterStuSystem',
)
