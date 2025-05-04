#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import platform
import shutil
import sys

def build_executable():
    """Buduje plik wykonywalny za pomocą PyInstaller."""
    print("Rozpoczynam proces budowania pliku wykonywalnego...")
    
    # Upewnij się, że PyInstaller jest zainstalowany w najnowszej wersji
    try:
        import PyInstaller
        print(f"Znaleziono PyInstaller w wersji {PyInstaller.__version__}")
        # Aktualizuj PyInstaller do najnowszej wersji
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"], check=True)
        print("Zaktualizowano PyInstaller do najnowszej wersji")
    except ImportError:
        print("Instaluję PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Upewnij się, że wszystkie wymagane pakiety są zainstalowane
    print("Instaluję/aktualizuję wszystkie wymagane pakiety...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"], check=True)
    
    # Upewnij się, że ipaddress jest zainstalowany (czasem jest problematyczny)
    subprocess.run([sys.executable, "-m", "pip", "install", "ipaddress"], check=True)
    
    # Upewnij się, że mamy wygenerowaną ikonę
    if not os.path.exists("app/resources/icon.ico"):
        print("Generuję ikonę aplikacji...")
        try:
            import generate_icon
            generate_icon.generate_app_icon()
        except Exception as e:
            print(f"Błąd podczas generowania ikony: {e}")
            print("Kontynuuję bez ikony...")
    
    # Usuń poprzednie buildy, jeśli istnieją
    for dir_name in ["build", "dist"]:
        if os.path.exists(dir_name):
            print(f"Usuwam poprzedni katalog {dir_name}...")
            shutil.rmtree(dir_name)
    
    # Określ separator ścieżek dla systemu operacyjnego
    separator = ";" if platform.system() == "Windows" else ":"
    
    # Upewnij się, że katalog config istnieje
    os.makedirs("config", exist_ok=True)
    
    # Lista dodatkowych modułów do włączenia
    hidden_imports = [
        "ipaddress",
        "collections.abc",
        "PyQt6",
        "PyQt6.QtWidgets",
        "PyQt6.QtCore", 
        "PyQt6.QtGui",
        "PyQt6.sip",
        "playwright",
        "pathlib",
        "urllib.parse",
        "xml.etree.ElementTree",
        "logging",
        "json",
        "ssl",
        "asyncio",
        "nest_asyncio",
        "email.mime.multipart",
        "email.mime.text",
        "email.mime.application",
        "subprocess",
        "importlib",
        "importlib.util",
        "pkg_resources.py2_warn",
        "pkg_resources._vendor.appdirs",
        "pkg_resources._vendor.packaging",
        "pkg_resources._vendor.pyparsing",
        "dill",
        "websockets.client",
        "websockets.connection",
        "websockets.protocol",
        "_bootlocale",
        "urllib.error",
        "encodings",
        "encodings.idna",
        "encodings.utf_8",
        "encodings.ascii"
    ]
    
    hidden_imports_args = [f"--hidden-import={imp}" for imp in hidden_imports]
    
    # Uruchom PyInstaller z odpowiednimi parametrami
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Fakturator_e-urtica",
        "--noconfirm",
        "--clean",
        "--distpath=dist",
        "--workpath=build",
        f"--icon={os.path.abspath('app/resources/icon.ico')}",
        "--runtime-hook=scripts/runtime_hook.py",
        "--windowed",
        "--noconsole",
        "app/main.py",
        f"--add-data=config/{separator}config/",
        f"--add-data=app/resources/{separator}app/resources/",
    ]
    
    # Dodaj ukryte importy
    cmd.extend(hidden_imports_args)
    
    # Dodaj dodatkowe opcje
    cmd.append("--log-level=DEBUG")  # Więcej informacji diagnostycznych
    
    # Upewnij się, że katalog scripts istnieje
    os.makedirs("scripts", exist_ok=True)
    
    # Utwórz plik runtime_hook.py, który zostanie uruchomiony przy starcie aplikacji
    with open("scripts/runtime_hook.py", "w", encoding="utf-8") as f:
        f.write("""
# -*- coding: utf-8 -*-
# Runtime hook dla PyInstaller

import os
import sys

# Dodaj ścieżkę do katalogu bieżącego na początek sys.path
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Upewnij się, że ipaddress jest dostępny
try:
    import ipaddress
except ImportError:
    sys.stderr.write("OSTRZEŻENIE: Nie można zaimportować 'ipaddress'. Próba naprawy...\n")
    sys.path.append(os.path.join(sys._MEIPASS, 'base_library.zip'))
""")
    
    print("Uruchamiam PyInstaller z komendą:")
    print(" ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True)
        
        if result.returncode == 0:
            print("\nBudowanie zakończone pomyślnie!")
            
            # Określ ścieżkę do pliku wykonywalnego
            if platform.system() == "Windows":
                exe_path = os.path.join("dist", "Fakturator_e-urtica.exe")
            elif platform.system() == "Darwin":  # macOS
                exe_path = os.path.join("dist", "Fakturator_e-urtica.app")
            else:  # Linux
                exe_path = os.path.join("dist", "Fakturator_e-urtica")
            
            print(f"\nPlik wykonywalny został utworzony w: {os.path.abspath(exe_path)}")
            print("\nAby uruchomić aplikację, po prostu kliknij na plik wykonywalny.")
        else:
            print("\nBłąd podczas budowania pliku wykonywalnego!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Błąd podczas budowania aplikacji: {e}")

if __name__ == "__main__":
    build_executable() 