#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
from pathlib import Path

def create_directory(path):
    """Tworzy katalog, jeśli nie istnieje."""
    os.makedirs(path, exist_ok=True)

def build_executable():
    """Buduje plik wykonywalny za pomocą PyInstaller."""
    print("🚀 Budowanie aplikacji...")
    
    # Upewnij się, że PyInstaller jest zainstalowany w najnowszej wersji
    try:
        import PyInstaller
        print(f"✅ Znaleziono PyInstaller w wersji {PyInstaller.__version__}")
        # Aktualizuj PyInstaller do najnowszej wersji
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"], check=True)
        print("✅ Zaktualizowano PyInstaller do najnowszej wersji")
    except ImportError:
        print("⚠️ Instaluję PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Upewnij się, że wszystkie wymagane pakiety są zainstalowane
    print("📦 Instaluję/aktualizuję wszystkie wymagane pakiety...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"], check=True)
    
    # Upewnij się, że ipaddress jest zainstalowany (czasem jest problematyczny)
    print("📦 Instaluję pakiet ipaddress...")
    subprocess.run([sys.executable, "-m", "pip", "install", "ipaddress"], check=True)
    
    # Tworzenie katalogu dla plików tymczasowych
    build_dir = "build"
    dist_dir = "dist"
    create_directory(build_dir)
    create_directory(dist_dir)
    
    # Upewnij się, że katalog scripts istnieje
    create_directory("scripts")
    
    # Utwórz plik runtime_hook.py, który zostanie uruchomiony przy starcie aplikacji
    runtime_hook_path = os.path.join("scripts", "runtime_hook.py")
    with open(runtime_hook_path, "w", encoding="utf-8") as f:
        f.write("""# -*- coding: utf-8 -*-
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
    sys.stderr.write("OSTRZEŻENIE: Nie można zaimportować 'ipaddress'. Próba naprawy...\\n")
    # Dodaj ścieżkę do base_library.zip
    if hasattr(sys, '_MEIPASS'):
        sys.path.append(os.path.join(sys._MEIPASS, 'base_library.zip'))
""")
    print(f"✅ Utworzono plik runtime hook: {runtime_hook_path}")
    
    # Ścieżki do zasobów i ikon
    icon_path = Path(__file__).parent.parent / "app" / "resources" / "icon.ico"
    if not icon_path.exists():
        print("⚠️ Nie znaleziono ikony aplikacji!")
        icon_path = None
    
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
        "urllib.error",
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
        "encodings",
        "encodings.idna",
        "encodings.utf_8",
        "encodings.ascii"
    ]
    
    # Dodaj ukryte importy jako argumenty
    hidden_imports_args = [f"--hidden-import={imp}" for imp in hidden_imports]
    
    # Ustawienia PyInstaller - używamy typu folder zamiast onefile dla lepszej zgodności
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Fakturator_e-urtica",
        "--noconfirm",
        "--clean",
        "--distpath=" + dist_dir,
        "--workpath=" + build_dir,
        f"--runtime-hook={runtime_hook_path}",
    ]
    
    # Dodaj ikonę, jeśli istnieje
    if icon_path:
        cmd.append(f"--icon={icon_path}")
    
    # Dodaj plik główny
    cmd.append("app/main.py")
    
    # Użyj odpowiedniego separatora ścieżek w zależności od systemu operacyjnego
    # Windows używa średnika (;), a Linux/macOS dwukropka (:)
    separator = ";" if sys.platform == "win32" else ":"
    print(f"System operacyjny: {sys.platform}, używam separatora: '{separator}'")
    
    # Dodaj pliki danych i konfiguracji z właściwym separatorem
    cmd.append(f"--add-data=config/{separator}config/")
    cmd.append(f"--add-data=app/resources/{separator}app/resources/")
    
    # Dodaj ukryte importy
    cmd.extend(hidden_imports_args)
    
    # Dodaj dodatkowe opcje
    cmd.append("--log-level=DEBUG")  # Więcej informacji diagnostycznych
    cmd.append("--windowed")  # Bez konsoli
    
    # Uruchom PyInstaller
    try:
        print("Wykonuję komendę:")
        print(" ".join(cmd))
        subprocess.run(cmd, check=True)
        print("✅ Aplikacja została zbudowana pomyślnie!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Błąd podczas budowania aplikacji: {e}")
        return False
    
    # Kopiowanie gotowego executable do głównego katalogu
    try:
        # Sprawdź, czy mamy folder czy pojedynczy plik
        folder_path = Path(dist_dir) / "Fakturator_e-urtica"
        exe_path = None
        
        if folder_path.exists() and folder_path.is_dir():
            print(f"✅ Znaleziono katalog z aplikacją: {folder_path}")
            try:
                # Kopiuj cały katalog do głównego folderu
                if os.path.exists("Fakturator_e-urtica"):
                    shutil.rmtree("Fakturator_e-urtica")
                shutil.copytree(folder_path, "Fakturator_e-urtica")
                print("✅ Katalog z aplikacją skopiowany do katalogu głównego")
                exe_path = os.path.join("Fakturator_e-urtica", "Fakturator_e-urtica")
            except Exception as e:
                print(f"❌ Błąd podczas kopiowania katalogu: {e}")
        else:
            # Używamy odpowiedniej nazwy pliku w zależności od systemu operacyjnego
            exe_name = "Fakturator_e-urtica.exe" if sys.platform == "win32" else "Fakturator_e-urtica"
            exe_path = Path(dist_dir) / exe_name
            
            if exe_path.exists():
                shutil.copy(exe_path, ".")
                print(f"✅ Plik wykonawczy skopiowany do katalogu głównego: {os.path.abspath(exe_name)}")
                exe_path = exe_name
            else:
                print(f"⚠️ Nie znaleziono pliku wykonywalnego: {exe_path}")
                return False
    except Exception as e:
        print(f"❌ Błąd podczas kopiowania pliku wykonawczego: {e}")
        return False
    
    # Zapytaj o utworzenie skrótu na pulpicie
    create_shortcut = input("Czy chcesz utworzyć skrót na pulpicie? (T/n): ").lower() != 'n'
    
    if create_shortcut and exe_path:
        try:
            create_desktop_shortcut(exe_path)
        except Exception as e:
            print(f"❌ Błąd podczas tworzenia skrótu: {e}")
    
    return True

def create_desktop_shortcut(exe_path):
    """Tworzy skrót na pulpicie."""
    # Różne systemy operacyjne
    if sys.platform == 'win32':
        # Windows - użyj PowerShell do utworzenia skrótu
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        app_path = os.path.abspath(exe_path)
        
        # Komenda PowerShell do utworzenia skrótu
        ps_command = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{desktop_path}\\Fakturator e-urtica.lnk")
        $Shortcut.TargetPath = "{app_path}"
        $Shortcut.WorkingDirectory = "{os.path.dirname(app_path)}"
        $Shortcut.Save()
        '''
        
        # Wykonaj komendę PowerShell
        subprocess.run(["powershell", "-Command", ps_command], check=True)
        print(f"✅ Skrót utworzony na pulpicie: {desktop_path}\\Fakturator e-urtica.lnk")
    
    elif sys.platform == 'linux':
        # Linux - utwórz plik .desktop
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        app_path = os.path.abspath(exe_path)
        icon_path = os.path.abspath(os.path.join("app", "resources", "icon.ico"))
        
        # Zawartość pliku .desktop
        desktop_file_content = f'''[Desktop Entry]
Type=Application
Name=Fakturator e-urtica
Comment=Aplikacja do pobierania faktur e-urtica
Exec="{app_path}"
Icon={icon_path}
Terminal=false
Categories=Office;
'''
        
        # Zapisz plik .desktop
        desktop_file_path = os.path.join(desktop_path, "fakturator-e-urtica.desktop")
        with open(desktop_file_path, 'w') as f:
            f.write(desktop_file_content)
        
        # Ustaw uprawnienia wykonywania
        os.chmod(desktop_file_path, 0o755)
        print(f"✅ Skrót utworzony na pulpicie: {desktop_file_path}")
    
    elif sys.platform == 'darwin':
        # macOS - utwórz plik .command
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        app_path = os.path.abspath(exe_path)
        
        # Zawartość pliku .command
        command_file_content = f'''#!/bin/bash
cd "{os.path.dirname(app_path)}"
"{app_path}"
'''
        
        # Zapisz plik .command
        command_file_path = os.path.join(desktop_path, "Fakturator e-urtica.command")
        with open(command_file_path, 'w') as f:
            f.write(command_file_content)
        
        # Ustaw uprawnienia wykonywania
        os.chmod(command_file_path, 0o755)
        print(f"✅ Skrót utworzony na pulpicie: {command_file_path}")
    
    else:
        print(f"⚠️ Nieobsługiwany system operacyjny: {sys.platform}")

if __name__ == "__main__":
    # Upewnij się, że katalog scripts istnieje
    create_directory("scripts")
    
    # Ustawienie katalogu roboczego
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Budowanie aplikacji
    build_executable() 