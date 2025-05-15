#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import platform
import shutil
import sys
from pathlib import Path
import logging

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("build.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("build")

def find_system_browser_path():
    """Znajduje ścieżkę do przeglądarki w systemie."""
    try:
        # Standardowa ścieżka cache Playwright
        cache_dir = Path.home() / ".cache" / "ms-playwright"
        if cache_dir.exists():
            logger.info(f"Znaleziono katalog cache ms-playwright: {cache_dir}")
            for item in os.listdir(cache_dir):
                if item.startswith("chromium-"):
                    chrome_win_dir = os.path.join(cache_dir, item, "chrome-win")
                    chrome_exe = os.path.join(chrome_win_dir, "chrome.exe")
                    
                    if os.path.exists(chrome_exe):
                        logger.info(f"Znaleziono chrome.exe w systemowym katalogu cache: {chrome_exe}")
                        return item, os.path.join(cache_dir, item)
        
        # Ścieżka w AppData dla Windows
        if os.name == 'nt':
            appdata_path = Path(os.environ.get('LOCALAPPDATA', '')) / "ms-playwright"
            if appdata_path.exists():
                logger.info(f"Znaleziono katalog AppData ms-playwright: {appdata_path}")
                for item in os.listdir(appdata_path):
                    if item.startswith("chromium-"):
                        chrome_win_dir = os.path.join(appdata_path, item, "chrome-win")
                        chrome_exe = os.path.join(chrome_win_dir, "chrome.exe")
                        
                        if os.path.exists(chrome_exe):
                            logger.info(f"Znaleziono chrome.exe w AppData: {chrome_exe}")
                            return item, os.path.join(appdata_path, item)
        
        return None, None
    except Exception as e:
        logger.error(f"Błąd podczas szukania przeglądarki: {e}")
        return None, None

def copy_browser_to_build(chromium_version, source_dir, target_dir):
    """Kopiuje przeglądarkę do katalogu buildu."""
    try:
        logger.info(f"Kopiuję przeglądarkę Chromium {chromium_version} z {source_dir} do {target_dir}")
        
        if not os.path.exists(source_dir):
            logger.error(f"Katalog źródłowy nie istnieje: {source_dir}")
            return False
        
        # Utwórz katalog docelowy
        os.makedirs(target_dir, exist_ok=True)
        
        # Kopiuj przeglądarkę
        shutil.copytree(source_dir, os.path.join(target_dir, chromium_version), dirs_exist_ok=True)
        
        # Sprawdź czy kopiowanie się powiodło
        chrome_exe = os.path.join(target_dir, chromium_version, "chrome-win", "chrome.exe")
        if os.path.exists(chrome_exe):
            logger.info(f"Przeglądarka skopiowana pomyślnie: {chrome_exe}")
            return True
        else:
            logger.error(f"Nie znaleziono chrome.exe po kopiowaniu: {chrome_exe}")
            return False
    except Exception as e:
        logger.error(f"Błąd podczas kopiowania przeglądarki: {e}")
        return False

def build_executable():
    """Buduje plik wykonywalny za pomocą PyInstaller."""
    logger.info("Rozpoczynam proces budowania pliku wykonywalnego...")
    
    # Upewnij się, że PyInstaller jest zainstalowany w najnowszej wersji
    try:
        import PyInstaller
        logger.info(f"Znaleziono PyInstaller w wersji {PyInstaller.__version__}")
        # Aktualizuj PyInstaller do najnowszej wersji
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"], check=True)
        logger.info("Zaktualizowano PyInstaller do najnowszej wersji")
    except ImportError:
        logger.info("Instaluję PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Upewnij się, że wszystkie wymagane pakiety są zainstalowane
    logger.info("Instaluję/aktualizuję wszystkie wymagane pakiety...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"], check=True)
    
    # Upewnij się, że ipaddress jest zainstalowany (czasem jest problematyczny)
    subprocess.run([sys.executable, "-m", "pip", "install", "ipaddress"], check=True)
    
    # Zainstaluj Playwright i przeglądarki
    logger.info("Instaluję Playwright i przeglądarki...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        logger.info("Playwright i Chromium zainstalowane pomyślnie")
    except subprocess.CalledProcessError as e:
        logger.error(f"Błąd podczas instalacji Playwright: {e}")
        logger.info("Kontynuuję budowanie mimo to...")
    
    # Upewnij się, że mamy wygenerowaną ikonę
    if not os.path.exists("app/resources/icon.ico"):
        logger.info("Generuję ikonę aplikacji...")
        try:
            import generate_icon
            generate_icon.generate_app_icon()
        except Exception as e:
            logger.error(f"Błąd podczas generowania ikony: {e}")
            logger.info("Kontynuuję bez ikony...")
    
    # Próba usunięcia poprzednich buildów, ale pomiń jeśli są błędy
    for dir_name in ["build", "dist"]:
        if os.path.exists(dir_name):
            logger.info(f"Próbuję usunąć poprzedni katalog {dir_name}...")
            try:
                shutil.rmtree(dir_name)
                logger.info(f"Usunięto katalog {dir_name}")
            except Exception as e:
                logger.error(f"Nie udało się usunąć katalogu {dir_name}: {e}")
                logger.info(f"Kontynuuję budowanie bez usuwania {dir_name}...")
    
    # Określ separator ścieżek dla systemu operacyjnego
    separator = ";" if platform.system() == "Windows" else ":"
    
    # Upewnij się, że katalog config istnieje
    os.makedirs("config", exist_ok=True)
    
    # Znajdź ścieżkę do przeglądarki w systemie - będzie potrzebna później do kopiowania
    chromium_version, chromium_path = find_system_browser_path()
    logger.info(f"Wykryty Chromium: wersja={chromium_version}, ścieżka={chromium_path}")
    
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
    
    logger.info("Uruchamiam PyInstaller z komendą:")
    logger.info(" ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True)
        
        if result.returncode == 0:
            logger.info("\nBudowanie zakończone pomyślnie!")
            
            # Określ ścieżkę do pliku wykonywalnego
            if platform.system() == "Windows":
                exe_path = os.path.join("dist", "Fakturator_e-urtica.exe")
                app_dir = os.path.join("dist", "Fakturator_e-urtica")
            elif platform.system() == "Darwin":  # macOS
                exe_path = os.path.join("dist", "Fakturator_e-urtica.app")
                app_dir = exe_path
            else:  # Linux
                exe_path = os.path.join("dist", "Fakturator_e-urtica")
                app_dir = exe_path
            
            logger.info(f"\nPlik wykonywalny został utworzony w: {os.path.abspath(exe_path)}")
            
            # Kopiowanie przeglądarki z systemu
            if chromium_version and chromium_path:
                internal_path = os.path.join(app_dir, "_internal")
                playwright_path = os.path.join(internal_path, "playwright")
                driver_path = os.path.join(playwright_path, "driver")
                package_path = os.path.join(driver_path, "package")
                browsers_path = os.path.join(package_path, ".local-browsers")
                
                logger.info(f"Kopiowanie przeglądarki do: {browsers_path}")
                os.makedirs(browsers_path, exist_ok=True)
                
                # Kopiuj przeglądarkę
                if copy_browser_to_build(chromium_version, chromium_path, browsers_path):
                    logger.info("Przeglądarka skopiowana pomyślnie do dystrybucji")
                else:
                    logger.error("Błąd podczas kopiowania przeglądarki do dystrybucji")
            else:
                logger.warning("Nie znaleziono przeglądarki w systemie do skopiowania")
            
            logger.info("\nAby uruchomić aplikację, po prostu kliknij na plik wykonywalny.")
        else:
            logger.error("\nBłąd podczas budowania pliku wykonywalnego!")
    except subprocess.CalledProcessError as e:
        logger.error(f"\n❌ Błąd podczas budowania aplikacji: {e}")

if __name__ == "__main__":
    build_executable()
    
    # Próba automatycznej instalacji przeglądarek Playwright w zbudowanej aplikacji
    logger.info("\nPróbuję zainstalować przeglądarki Playwright w zbudowanej aplikacji...")
    
    try:
        import platform
        import os
        import subprocess
        
        # Określ ścieżkę do pliku wykonywalnego
        if platform.system() == "Windows":
            exe_path = os.path.abspath(os.path.join("dist", "Fakturator_e-urtica"))
        else:
            exe_path = os.path.abspath(os.path.join("dist", "Fakturator_e-urtica"))
        
        if not os.path.exists(exe_path):
            logger.warning(f"Nie znaleziono katalogu aplikacji: {exe_path}")
        else:
            # Znajdź ścieżkę do node.exe i playwright CLI
            node_exe = os.path.join(exe_path, "_internal", "playwright", "driver", "node.exe")
            cli_js = os.path.join(exe_path, "_internal", "playwright", "driver", "package", "cli.js")
            
            if os.path.exists(node_exe) and os.path.exists(cli_js):
                # Utwórz katalog .local-browsers jeśli nie istnieje
                local_browsers_dir = os.path.join(exe_path, "_internal", "playwright", "driver", "package", ".local-browsers")
                os.makedirs(local_browsers_dir, exist_ok=True)
                
                # Uruchom instalację przeglądarki
                logger.info(f"Uruchamiam instalację przeglądarki Chromium...")
                cmd = [node_exe, cli_js, "install", "chromium"]
                result = subprocess.run(cmd, check=False)
                
                if result.returncode == 0:
                    logger.info("\n✅ Pomyślnie zainstalowano przeglądarkę Chromium w zbudowanej aplikacji!")
                else:
                    logger.warning("\n❌ Nie udało się zainstalować przeglądarki Chromium przez Playwright CLI.")
                    logger.info("Sprawdzanie systemu pod kątem przeglądarek do skopiowania...")
                    
                    # Alternatywne podejście - kopiuj z systemowego katalogu
                    chromium_version, chromium_path = find_system_browser_path()
                    if chromium_version and chromium_path:
                        if copy_browser_to_build(chromium_version, chromium_path, local_browsers_dir):
                            logger.info("\n✅ Pomyślnie skopiowano przeglądarkę Chromium z systemu!")
                        else:
                            logger.error("\n❌ Nie udało się skopiować przeglądarki z systemu.")
                    else:
                        logger.error("\n❌ Nie znaleziono przeglądarki Chromium w systemie.")
            else:
                logger.warning(f"\n❌ Nie znaleziono plików Playwright w zbudowanej aplikacji.")
                logger.warning(f"node.exe istnieje: {os.path.exists(node_exe)}")
                logger.warning(f"cli.js istnieje: {os.path.exists(cli_js)}")
                
                # Alternatywne podejście - utwórz ścieżki ręcznie
                internal_path = os.path.join(exe_path, "_internal")
                playwright_path = os.path.join(internal_path, "playwright")
                driver_path = os.path.join(playwright_path, "driver")
                package_path = os.path.join(driver_path, "package")
                local_browsers_dir = os.path.join(package_path, ".local-browsers")
                
                # Utwórz katalogi
                os.makedirs(local_browsers_dir, exist_ok=True)
                
                # Kopiuj z systemu
                chromium_version, chromium_path = find_system_browser_path()
                if chromium_version and chromium_path:
                    if copy_browser_to_build(chromium_version, chromium_path, local_browsers_dir):
                        logger.info("\n✅ Pomyślnie skopiowano przeglądarkę Chromium z systemu do ręcznie utworzonego katalogu!")
                    else:
                        logger.error("\n❌ Nie udało się skopiować przeglądarki z systemu do ręcznie utworzonego katalogu.")
    except Exception as e:
        logger.error(f"\n❌ Wystąpił błąd podczas instalacji przeglądarek Playwright: {e}") 