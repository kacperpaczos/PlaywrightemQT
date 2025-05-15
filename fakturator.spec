# -*- mode: python ; coding: utf-8 -*-
import sys
import platform
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# Dodatkowe moduły potrzebne dla aplikacji
hidden_imports = [
    'ipaddress',
    'collections.abc',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.sip',
    'playwright',
    'pathlib',
    'urllib.parse',
    'urllib.error',
    'xml.etree.ElementTree',
    'logging',
    'json',
    'ssl',
    'asyncio',
    'nest_asyncio',
    'email.mime.multipart',
    'email.mime.text',
    'email.mime.application',
    'subprocess',
    'importlib',
    'importlib.util',
    'pkg_resources.py2_warn',
    'pkg_resources._vendor.appdirs',
    'pkg_resources._vendor.packaging',
    'pkg_resources._vendor.pyparsing',
    'dill',
    'websockets.client',
    'websockets.connection',
    'websockets.protocol',
    '_bootlocale',
    'encodings',
    'encodings.idna',
    'encodings.utf_8',
    'encodings.ascii'
]

# Dodatkowe moduły potrzebne dla Playwright
playwright_modules = collect_submodules('playwright')
hidden_imports.extend(playwright_modules)

# Zbieranie wszystkich zależności playwright
playwright_data, playwright_binaries, playwright_hiddenimports = collect_all('playwright')

# Dodanie plików DLL Python dla systemu Windows
extra_binaries = []
if platform.system() == 'Windows':
    python_paths = [
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python\Python313'),
        os.path.expandvars(r'%PROGRAMFILES%\Python\Python313'),
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Python\Python313')
    ]
    
    # Sprawdź, która ścieżka istnieje
    for python_path in python_paths:
        python_dll = os.path.join(python_path, 'python313.dll')
        if os.path.exists(python_dll):
            extra_binaries.append((python_dll, '.'))
            # Dodaj też inne potrzebne DLL
            dll_files = ['python3.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
            for dll in dll_files:
                dll_path = os.path.join(python_path, dll)
                if os.path.exists(dll_path):
                    extra_binaries.append((dll_path, '.'))
            break

# Pliki danych
datas = [
    ('app/resources/*', 'app/resources'),
    ('config/', 'config/'),
]

# Dodaj potrzebne pliki danych z playwright
datas.extend(playwright_data)
datas.extend(collect_data_files('playwright'))

# Utwórz runtime hook
runtime_hook_content = """
# -*- coding: utf-8 -*-
# Runtime hook dla PyInstaller

import os
import sys
import platform

# Dodaj ścieżkę do DLL Pythona dla systemów Windows
if platform.system() == 'Windows':
    python_home = os.environ.get('PYTHONHOME')
    if not python_home:
        # Próbuj znaleźć instalację Pythona
        possible_paths = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python313'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Python', 'Python313'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Python', 'Python313')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                python_home = path
                os.environ['PYTHONHOME'] = python_home
                break
    
    if python_home:
        # Dodaj ścieżkę Pythona do PATH
        os.environ['PATH'] = python_home + os.pathsep + os.environ.get('PATH', '')
        print(f"Dodano ścieżkę Pythona do PATH: {python_home}")

# Dodaj ścieżkę do katalogu bieżącego na początek sys.path
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Upewnij się, że ipaddress jest dostępny
try:
    import ipaddress
except ImportError:
    sys.stderr.write("OSTRZEŻENIE: Nie można zaimportować 'ipaddress'. Próba naprawy...\\n")
    if hasattr(sys, '_MEIPASS'):
        sys.path.append(os.path.join(sys._MEIPASS, 'base_library.zip'))
"""

with open('runtime_hook.py', 'w', encoding='utf-8') as f:
    f.write(runtime_hook_content)

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=playwright_binaries + extra_binaries,
    datas=datas,
    hiddenimports=hidden_imports + playwright_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    icon='app/resources/icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fakturator',
)

# Dla macOS, dodaj tworzenie pakietu .app (tylko na platformie macOS)
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Fakturator.app',
        icon='app/resources/icon.ico',
        bundle_identifier=None,
    ) 