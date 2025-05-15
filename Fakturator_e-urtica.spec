# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('config/', 'config/'), ('app/resources/', 'app/resources/')],
    hiddenimports=['ipaddress', 'collections.abc', 'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip', 'playwright', 'pathlib', 'urllib.parse', 'urllib.error', 'xml.etree.ElementTree', 'logging', 'json', 'ssl', 'asyncio', 'nest_asyncio', 'email.mime.multipart', 'email.mime.text', 'email.mime.application', 'subprocess', 'importlib', 'importlib.util', 'pkg_resources.py2_warn', 'pkg_resources._vendor.appdirs', 'pkg_resources._vendor.packaging', 'pkg_resources._vendor.pyparsing', 'dill', 'websockets.client', 'websockets.connection', 'websockets.protocol', '_bootlocale', 'encodings', 'encodings.idna', 'encodings.utf_8', 'encodings.ascii'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['scripts\\runtime_hook.py'],
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
    name='Fakturator_e-urtica',
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
    icon=['C:\\Users\\szymo\\Desktop\\PlaywrightemQT\\app\\resources\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fakturator_e-urtica',
)
