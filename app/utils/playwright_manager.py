#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import importlib.util
from typing import List, Dict, Tuple, Callable, Optional
from pathlib import Path
from app.utils.logger import setup_logger

logger = setup_logger()

class PlaywrightManager:
    """Klasa do zarządzania instalacją, konfiguracją i usuwaniem Playwright."""
    
    def __init__(self):
        """Inicjalizacja menedżera Playwright."""
        self.playwright_path = Path.home() / ".cache" / "ms-playwright"
        self.installed_browsers = self._get_installed_browsers()
        self.cache_dir = self._get_cache_dir()
        self.progress_callback = None
    
    def set_progress_callback(self, callback: Optional[Callable[[str], None]]):
        """Ustawia callback do raportowania postępu operacji.
        
        Args:
            callback: Funkcja przyjmująca komunikat tekstowy jako argument, lub None żeby wyłączyć powiadomienia
        """
        self.progress_callback = callback
    
    def _report_progress(self, message: str):
        """Raportuje postęp operacji."""
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)
    
    def _get_cache_dir(self) -> str:
        """Zwraca ścieżkę do katalogu cache ms-playwright."""
        # Domyślna lokalizacja katalogu cache
        home_dir = os.path.expanduser("~")
        cache_dir = os.path.join(home_dir, ".cache", "ms-playwright")
        
        if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
            logger.info(f"Znaleziono katalog ms-playwright: {cache_dir}")
            return cache_dir
        
        # Alternatywne lokalizacje do sprawdzenia
        alt_locations = [
            os.path.join(home_dir, "AppData", "Local", "ms-playwright"),  # Windows
            os.path.join("/", "ms-playwright"),  # Niektóre instalacje Linux
        ]
        
        for location in alt_locations:
            if os.path.exists(location) and os.path.isdir(location):
                logger.info(f"Znaleziono katalog ms-playwright: {location}")
                return location
        
        logger.warning("Nie znaleziono katalogu ms-playwright, używam domyślnej lokalizacji")
        return cache_dir
    
    def _get_installed_browsers(self):
        """Sprawdza zainstalowane przeglądarki."""
        browsers = {
            "chromium": False,
            "firefox": False,
            "webkit": False
        }
        
        # Sprawdź bezpośrednio w katalogu ~/.cache/ms-playwright
        try:
            cache_dir = Path.home() / ".cache" / "ms-playwright"
            if cache_dir.exists():
                logger.info(f"Znaleziono katalog ms-playwright: {cache_dir}")
                
                # Sprawdź listę plików w katalogu
                for item in cache_dir.iterdir():
                    item_name = item.name.lower()
                    for browser in browsers.keys():
                        if item_name.startswith(browser):
                            browsers[browser] = True
                            logger.info(f"Znaleziono przeglądarkę {browser} w katalogu cache: {item}")
            else:
                logger.warning(f"Katalog ms-playwright nie istnieje: {cache_dir}")
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania katalogu ms-playwright: {e}")
        
        # Standardowa metoda poprzez ścieżki (tylko jeśli nie znaleziono)
        if not any(browsers.values()) and self.playwright_path.exists():
            for browser in browsers.keys():
                browser_path = self.playwright_path / browser
                if browser_path.exists():
                    browsers[browser] = True
                    logger.info(f"Znaleziono przeglądarkę {browser} w standardowej lokalizacji")
        
        # Alternatywna metoda - użyj --dry-run (tylko jeśli nadal nie znaleziono)
        if not any(browsers.values()):
            try:
                # Sprawdźmy najpierw czy komenda playwright istnieje
                try:
                    result = subprocess.run(
                        ['which', 'playwright'], 
                        capture_output=True, 
                        text=True
                    )
                    
                    if result.returncode != 0:
                        logger.warning("Komenda playwright nie jest dostępna w systemie")
                        return browsers
                        
                    result = subprocess.run(
                        ['playwright', 'install', '--dry-run'], 
                        capture_output=True, 
                        text=True
                    )
                    output = result.stdout.lower()
                    
                    # Logowanie pełnego outputu
                    logger.info(f"Wynik komendy playwright install --dry-run: {output}")
                    
                    # Analizuj output dla każdej przeglądarki
                    for browser in browsers.keys():
                        if f"browser: {browser}" in output:
                            install_path = None
                            for line in output.split('\n'):
                                if line.strip().startswith("install location:") and browser in output.split('\n')[output.split('\n').index(line) - 1].lower():
                                    install_path = line.strip().split("install location:")[1].strip()
                                    break
                            
                            if install_path and os.path.exists(install_path):
                                browsers[browser] = True
                                logger.info(f"Przeglądarka {browser} wykryta przez dry-run: {install_path}")
                except FileNotFoundError:
                    logger.warning("Komenda playwright nie jest dostępna w systemie")
            except Exception as e:
                logger.error(f"Błąd przy sprawdzaniu przeglądarek przez dry-run: {e}")
        
        return browsers
    
    def _check_playwright_import(self) -> bool:
        """Sprawdza, czy możliwy jest import playwright i czy pakiet rzeczywiście działa."""
        try:
            # Sprawdź czy pakiet jest dostępny
            spec = importlib.util.find_spec("playwright")
            if spec is None:
                logger.warning("Pakiet playwright nie jest zainstalowany (brak specyfikacji modułu)")
                return False

            # Spróbuj zaimportować
            import playwright
            
            # Sprawdź czy można zaimportować główne komponenty
            try:
                from playwright.sync_api import sync_playwright
                # Wykonaj prosty test aby sprawdzić czy pakiet działa
                try:
                    with sync_playwright() as p:
                        # Samo stworzenie obiektu jest wystarczającym testem
                        # Nie tworzymy przeglądarki, tylko sprawdzamy, czy moduł działa
                        if hasattr(p, 'chromium'):
                            logger.info("Import playwright.sync_api działa poprawnie i pakiet jest funkcjonalny")
                            return True
                        else:
                            logger.warning("Import playwright.sync_api działa, ale pakiet nie jest w pełni funkcjonalny")
                            return False
                except Exception as e:
                    logger.warning(f"Pakiet playwright jest zainstalowany, ale nie działa poprawnie: {e}")
                    return False
            except ImportError as e:
                logger.warning(f"Import playwright.sync_api nie działa: {e}")
                return False
            except Exception as e:
                logger.error(f"Niespodziewany błąd podczas testowania playwright: {e}")
                return False
        except ImportError:
            logger.warning("Import playwright nie działa")
            return False
        except Exception as e:
            logger.error(f"Niespodziewany błąd podczas importu playwright: {e}")
            return False
    
    def check_playwright_installation(self):
        """Sprawdza czy Playwright i przeglądarki są zainstalowane."""
        try:
            # Sprawdź najpierw czy pakiet jest dostępny
            import_works = self._check_playwright_import()
            if not import_works:
                logger.warning("Pakiet playwright nie działa poprawnie")
                return False
            
            # Sprawdź czy przeglądarki są zainstalowane
            self.installed_browsers = self._get_installed_browsers()
            any_browser_installed = any(self.installed_browsers.values())
            
            if not any_browser_installed:
                logger.warning("Playwright zainstalowany, ale nie wykryto przeglądarek")
            
            logger.info(f"Status instalacji Playwright: pakiet={import_works}, przeglądarki={self.installed_browsers}")
            
            # Uznajemy, że Playwright jest zainstalowany, jeśli pakiet jest dostępny
            # Przeglądarki można doinstalować osobno
            return import_works
            
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd podczas sprawdzania Playwright: {str(e)}")
            return False
    
    def get_installation_status(self):
        """
        Zwraca status instalacji Playwright.
        
        Returns:
            dict: Słownik ze statusem instalacji i przeglądarek.
        """
        self._report_progress("Sprawdzanie statusu instalacji Playwright...")
        
        # Najpierw sprawdź czy pakiet można zaimportować i czy działa
        try:
            import_works = self._check_playwright_import()
        except Exception:
            import_works = False
        
        # Sprawdź czy komenda playwright jest dostępna
        try:
            cmd_works, version = self._check_playwright_command()
        except Exception:
            cmd_works = False
            version = "nieznana"
        
        # Playwright jest zainstalowany tylko jeśli import działa
        # Sama komenda CLI może nie działać, zwłaszcza w środowisku pyinstaller/exe
        playwright_installed = import_works
        
        # Sprawdzenie, czy jesteśmy w środowisku PyInstaller
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen and playwright_installed:
            self._report_progress("Wykryto środowisko PyInstaller, sprawdzam ścieżki przeglądarek...")
            try:
                # Próba naprawy ścieżek przed sprawdzeniem przeglądarek
                fix_result = self.fix_executable_browser_path()
                if fix_result:
                    self._report_progress("✅ Pomyślnie skonfigurowano ścieżki przeglądarek")
                else:
                    self._report_progress("⚠️ Nie udało się automatycznie skonfigurować ścieżek przeglądarek")
            except Exception as e:
                self._report_progress(f"❌ Błąd podczas konfiguracji ścieżek: {e}")
        
        # Zaktualizuj informacje o przeglądarkach
        try:
            browsers = self._check_browser_installations()
        except Exception:
            browsers = {"chromium": False, "firefox": False, "webkit": False}
        
        # Ostateczny status
        status = {
            "playwright_installed": playwright_installed,
            "playwright_version": version if cmd_works else "nieznana",
            "browsers": browsers,
            "command_available": cmd_works
        }
        
        logger.info(f"Status instalacji Playwright: pakiet={playwright_installed}, przeglądarki={browsers}")
        self._report_progress("Status instalacji Playwright sprawdzony")
        
        return status
    
    def install_playwright(self, browsers=None):
        """Instaluje Playwright i wybrane przeglądarki."""
        self._report_progress("Rozpoczynam instalację Playwright...")
        
        try:
            # Sprawdź aktualny stan instalacji
            status = self.get_installation_status()
            
            # Jeśli już zainstalowany, instaluj tylko przeglądarki
            if status["playwright_installed"]:
                self._report_progress("Pakiet playwright jest już zainstalowany")
                logger.info("Pakiet playwright jest już zainstalowany, wersja: " + status["playwright_version"])
                
                # Instalacja wybranych przeglądarek
                success, message = self._install_browsers(browsers)
                
                # Po instalacji przeglądarek, spróbuj naprawić ścieżki dla PyInstaller
                if success:
                    self._report_progress("Konfigurowanie ścieżek przeglądarek po instalacji...")
                    self.configure_playwright_paths()
                    
                return success, message
            
            # Instalacja pakietu playwright
            self._report_progress("Instalowanie pakietu playwright...")
            try:
                # Usuń stare moduły z pamięci, jeśli istnieją
                to_remove = [m for m in sys.modules if m.startswith('playwright')]
                for module_name in to_remove:
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                        logger.info(f"Usunięto z pamięci moduł: {module_name}")
                
                # Zainstaluj pakiet
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    error_msg = f"Błąd instalacji playwright: {result.stderr}"
                    logger.error(error_msg)
                    self._report_progress(f"Błąd: {error_msg}")
                    return False, error_msg
                
                self._report_progress("Pakiet playwright zainstalowany pomyślnie")
                logger.info("Pakiet playwright zainstalowany pomyślnie")
                
                # Instalacja przeglądarek
                success, message = self._install_browsers(browsers)
                
                # Po instalacji przeglądarek, spróbuj naprawić ścieżki dla PyInstaller
                if success:
                    self._report_progress("Konfigurowanie ścieżek przeglądarek po instalacji...")
                    self.configure_playwright_paths()
                    
                return success, message
                
            except Exception as e:
                error_msg = f"Nieoczekiwany błąd podczas instalacji playwright: {str(e)}"
                logger.error(error_msg)
                self._report_progress(f"Błąd: {error_msg}")
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Nieoczekiwany błąd podczas instalacji: {str(e)}"
            logger.error(error_msg)
            self._report_progress(f"Błąd: {error_msg}")
            return False, error_msg
    
    def _install_browsers(self, browsers=None):
        """Instaluje wybrane przeglądarki."""
        if browsers is None:
            browsers = ["chromium"]  # Domyślnie tylko Chromium
            
        if "all" in browsers:
            browsers = ["chromium", "firefox", "webkit"]
        
        success = True
        messages = []
        
        # Sprawdź czy mamy dostęp do komendy playwright
        cmd_success, _ = self._check_playwright_command()
        
        for browser in browsers:
            self._report_progress(f"Instalowanie przeglądarki {browser}...")
            logger.info(f"Instalowanie przeglądarki {browser}...")
            
            try:
                if cmd_success:
                    # Użyj standardowej komendy playwright install
                    cmd = ["playwright", "install", browser]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                else:
                    # Użyj python -m playwright install
                    cmd = [sys.executable, "-m", "playwright", "install", browser]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if result.returncode == 0:
                    browser_msg = f"Przeglądarka {browser} została zainstalowana"
                    messages.append(browser_msg)
                    self._report_progress(browser_msg)
                else:
                    error_msg = f"Błąd instalacji przeglądarki {browser}: {result.stderr}"
                    logger.error(error_msg)
                    messages.append(error_msg)
                    self._report_progress(f"Błąd: {error_msg}")
                    success = False
                    
                    # Dodatkowa informacja diagnostyczna
                    logger.error(f"Komenda: {' '.join(cmd)}")
                    logger.error(f"Kod wyjścia: {result.returncode}")
                    logger.error(f"Wyjście standardowe: {result.stdout}")
                    logger.error(f"Wyjście błędów: {result.stderr}")
                    
                    # Sprawdź czy pakiet jest dostępny mimo błędu
                    if importlib.util.find_spec("playwright") is None:
                        logger.error("Pakiet playwright nie jest dostępny, co uniemożliwia instalację przeglądarek")
                        return False, "Nie udało się zainstalować Playwright, co uniemożliwia instalację przeglądarek"
                    
            except Exception as e:
                error_msg = f"Nieoczekiwany błąd podczas instalacji przeglądarki {browser}: {str(e)}"
                logger.error(error_msg)
                messages.append(error_msg)
                self._report_progress(f"Błąd: {error_msg}")
                success = False
        
        # Odśwież status przeglądarek
        self.installed_browsers = self._get_installed_browsers()
        
        if success:
            return True, "Przeglądarki zostały zainstalowane pomyślnie: " + "; ".join(messages)
        else:
            return False, "Wystąpiły błędy podczas instalacji przeglądarek: " + "; ".join(messages)
    
    def update_playwright(self):
        """Aktualizuje Playwright i przeglądarki do najnowszej wersji."""
        try:
            # Aktualizacja pakietu playwright
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'playwright'], 
                         check=True)
            
            # Aktualizacja przeglądarek
            subprocess.run(['playwright', 'install', '--force'], check=True)
            
            # Odśwież status instalacji
            self.installed_browsers = self._get_installed_browsers()
            
            return True, "Playwright i przeglądarki zostały zaktualizowane pomyślnie."
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Błąd podczas aktualizacji: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Niespodziewany błąd: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def uninstall_browsers(self, browsers=None):
        """
        Usuwa wybrane przeglądarki Playwright z systemu.
        
        Args:
            browsers (list, optional): Lista przeglądarek do usunięcia. 
                                     Jeśli None, usuwa wszystkie przeglądarki.
        
        Returns:
            tuple: (sukces, wiadomość)
        """
        try:
            if browsers is None:
                browsers = list(self.installed_browsers.keys())
            
            removed_browsers = []
            
            # Usuwanie katalogów przeglądarek
            for browser in browsers:
                browser_paths = []
                
                # Znajdź wszystkie wersje danej przeglądarki
                try:
                    cache_dir = Path.home() / ".cache" / "ms-playwright"
                    if cache_dir.exists():
                        for item in cache_dir.iterdir():
                            if item.is_dir() and item.name.lower().startswith(browser.lower()):
                                browser_paths.append(item)
                except Exception as e:
                    logger.error(f"Błąd podczas wyszukiwania ścieżek przeglądarki {browser}: {e}")
                    continue
                
                # Usuń znalezione katalogi
                for path in browser_paths:
                    try:
                        import shutil
                        logger.info(f"Usuwanie katalogu przeglądarki: {path}")
                        shutil.rmtree(path)
                        removed_browsers.append(browser)
                    except Exception as e:
                        logger.error(f"Błąd podczas usuwania katalogu {path}: {e}")
            
            # Aktualizuj status instalacji
            self.installed_browsers = self._get_installed_browsers()
            
            if removed_browsers:
                return True, f"Usunięto przeglądarki: {', '.join(set(removed_browsers))}"
            else:
                return False, "Nie udało się usunąć żadnych przeglądarek"
            
        except Exception as e:
            error_msg = f"Błąd podczas usuwania przeglądarek: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def uninstall_playwright(self):
        """
        Usuwa pakiet Playwright z systemu.
        
        Returns:
            tuple: (sukces, wiadomość)
        """
        self._report_progress("Przygotowanie do usunięcia Playwright...")
        
        try:
            # Sprawdź aktualny stan instalacji
            status = self.get_installation_status()
            
            # Najpierw usuń wszystkie przeglądarki
            self._report_progress("Usuwanie wszystkich przeglądarek...")
            browser_success, browser_msg = self.uninstall_browsers()
            
            # Usuń katalog cache, jeśli istnieje
            if os.path.exists(self.cache_dir):
                self._report_progress("Usuwanie katalogu cache ms-playwright...")
                try:
                    shutil.rmtree(self.cache_dir)
                    logger.info(f"Usunięto katalog cache: {self.cache_dir}")
                except Exception as e:
                    logger.error(f"Błąd usuwania katalogu cache {self.cache_dir}: {e}")
            
            # Jeśli Playwright nie jest zainstalowany, nie próbuj go usuwać
            if not status["playwright_installed"]:
                logger.info("Pakiet Playwright już został usunięty")
                return True, "Playwright już jest usunięty"
            
            # Odinstaluj pakiet playwright
            self._report_progress("Usuwanie pakietu playwright...")
            try:
                # Usuń pakiet playwright
                subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", "-y", "playwright"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Sprawdź czy moduł został usunięty
                spec = importlib.util.find_spec("playwright")
                if spec is not None:
                    logger.warning("Pakiet playwright nadal jest wykrywalny mimo usunięcia")
                    
                    # Wyczyść z pamięci zaimportowane moduły jeśli były używane
                    to_remove = [m for m in sys.modules if m.startswith('playwright')]
                    for module_name in to_remove:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                            logger.info(f"Usunięto z pamięci moduł: {module_name}")
                
                # Dodatkowa weryfikacja po usunięciu
                try:
                    import playwright
                    logger.warning("Mimo usunięcia, pakiet playwright nadal można zaimportować")
                    return False, "Nie udało się całkowicie usunąć pakietu playwright"
                except ImportError:
                    logger.info("Pakiet playwright został pomyślnie usunięty")
                    return True, "Playwright został całkowicie usunięty"
                
            except subprocess.CalledProcessError as e:
                # Sprawdź czy błąd dotyczy braku pakietu
                if "not installed" in str(e) or "as it is not installed" in str(e):
                    logger.warning("Pakiet Playwright już został usunięty wcześniej")
                    return True, "Playwright już był usunięty"
                error_msg = f"Błąd podczas usuwania Playwright: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Niespodziewany błąd podczas usuwania Playwright: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def reinstall_playwright(self, browsers=None):
        """
        Usuwa i ponownie instaluje Playwright wraz z wybranymi przeglądarkami.
        
        Args:
            browsers (list, optional): Lista przeglądarek do zainstalowania.
                                       Jeśli None, instaluje tylko Chromium.
        
        Returns:
            tuple: (sukces, wiadomość)
        """
        try:
            # Usuń istniejącą instalację
            uninstall_success, uninstall_msg = self.uninstall_playwright()
            if not uninstall_success:
                logger.warning(f"Nie udało się całkowicie usunąć poprzedniej instalacji: {uninstall_msg}")
            
            # Zainstaluj Playwright i przeglądarki na nowo
            success, msg = self.install_playwright(browsers)
            
            if success:
                return True, "Playwright został pomyślnie zainstalowany ponownie"
            else:
                return False, f"Nie udało się ponownie zainstalować Playwright: {msg}"
                
        except Exception as e:
            error_msg = f"Błąd podczas reinstalacji Playwright: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _check_playwright_command(self) -> Tuple[bool, str]:
        """Sprawdza, czy komenda playwright jest dostępna."""
        try:
            result = subprocess.run(
                ["playwright", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"Komenda playwright działa, wersja: {version}")
                return True, version
            else:
                # Sprawdź, czy możemy uruchomić playwright poprzez python -m
                python_cmd = sys.executable
                alt_result = subprocess.run(
                    [python_cmd, "-m", "playwright", "--version"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if alt_result.returncode == 0:
                    version = alt_result.stdout.strip()
                    logger.info(f"Komenda playwright działa przez python -m, wersja: {version}")
                    return True, version
                else:
                    logger.warning("Komenda playwright nie działa")
                    return False, "nie zainstalowany"
        except FileNotFoundError:
            # Sprawdź czy możemy uruchomić przez python -m
            try:
                python_cmd = sys.executable
                alt_result = subprocess.run(
                    [python_cmd, "-m", "playwright", "--version"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if alt_result.returncode == 0:
                    version = alt_result.stdout.strip()
                    logger.info(f"Komenda playwright działa przez python -m, wersja: {version}")
                    return True, version
                else:
                    logger.warning("Komenda playwright nie jest dostępna")
                    return False, "nie zainstalowany"
            except Exception as e:
                logger.error(f"Błąd podczas sprawdzania komendy playwright przez python -m: {e}")
                return False, "nie zainstalowany"
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania komendy playwright: {e}")
            return False, "nieznana"
    
    def _check_browser_installations(self) -> Dict[str, bool]:
        """Sprawdza zainstalowane przeglądarki i próbuje naprawić ścieżki w środowisku PyInstaller."""
        browsers = {
            "chromium": False,
            "firefox": False,
            "webkit": False
        }
        
        self._report_progress("🔍 DIAGNOSTYKA PRZEGLĄDAREK: Rozpoczynam szczegółowe sprawdzanie przeglądarek")
        
        # Najpierw sprawdź, czy jesteśmy w środowisku PyInstaller i napraw ścieżki
        is_frozen = getattr(sys, 'frozen', False)
        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Aplikacja w trybie frozen/PyInstaller: {is_frozen}")
        
        if is_frozen:
            # Jesteśmy w środowisku PyInstaller, próbujemy naprawić ścieżki
            self._report_progress("🔍 DIAGNOSTYKA PRZEGLĄDAREK: Próbuję naprawić ścieżki w środowisku PyInstaller")
            
            # Zawsze próbuj naprawić ścieżki przy sprawdzaniu przeglądarek
            try:
                self._report_progress("🔧 NAPRAWA: Sprawdzam i naprawiam ścieżki przeglądarek...")
                fix_success = self.fix_executable_browser_path()
                if fix_success:
                    self._report_progress("✅ NAPRAWA: Ścieżki przeglądarek zostały naprawione")
                else:
                    self._report_progress("⚠️ NAPRAWA: Automatyczna naprawa ścieżek przeglądarek nie powiodła się")
            except Exception as e:
                self._report_progress(f"❌ NAPRAWA: Błąd podczas naprawiania ścieżek: {e}")
            
            # Wypisz ścieżkę aplikacji
            app_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka aplikacji: {app_path}")
            
            # Sprawdź ścieżki wewnątrz aplikacji
            internal_path = os.path.join(app_path, "_internal")
            playwright_path = os.path.join(internal_path, "playwright")
            driver_path = os.path.join(playwright_path, "driver")
            package_path = os.path.join(driver_path, "package")
            local_browsers_path = os.path.join(package_path, ".local-browsers")
            
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka _internal: {internal_path}, istnieje: {os.path.exists(internal_path)}")
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka playwright: {playwright_path}, istnieje: {os.path.exists(playwright_path)}")
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka driver: {driver_path}, istnieje: {os.path.exists(driver_path)}")
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka package: {package_path}, istnieje: {os.path.exists(package_path)}")
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka .local-browsers: {local_browsers_path}, istnieje: {os.path.exists(local_browsers_path)}")
            
            # Sprawdź plik browsers.json
            browsers_json_path = os.path.join(package_path, "browsers.json")
            if os.path.exists(browsers_json_path):
                try:
                    import json
                    with open(browsers_json_path, 'r') as f:
                        browsers_json = json.load(f)
                    browser_revisions = {}
                    for browser_info in browsers_json.get('browsers', []):
                        if 'name' in browser_info and 'revision' in browser_info:
                            browser_revisions[browser_info['name']] = browser_info['revision']
                    
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Informacje o przeglądarkach z browsers.json: {browser_revisions}")
                except Exception as e:
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Błąd odczytu browsers.json: {str(e)}")
            
            # Sprawdź ścieżki do chrome.exe
            expected_chrome_exe_paths = []
            if os.path.exists(local_browsers_path):
                try:
                    browser_dirs = os.listdir(local_browsers_path)
                    for browser_dir in browser_dirs:
                        if browser_dir.startswith('chromium-'):
                            chrome_win_dir = os.path.join(local_browsers_path, browser_dir, 'chrome-win')
                            chrome_exe = os.path.join(chrome_win_dir, 'chrome.exe')
                            expected_chrome_exe_paths.append({
                                'path': chrome_exe,
                                'exists': os.path.exists(chrome_exe),
                                'size': os.path.getsize(chrome_exe) if os.path.exists(chrome_exe) else 0
                            })
                except Exception as e:
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas sprawdzania katalogów przeglądarek: {str(e)}")
            
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Oczekiwane ścieżki chrome.exe: {expected_chrome_exe_paths}")
            
            # Sprawdź czy chrome.exe jest dostępny bezpośrednio w PATH
            try:
                chrome_in_path = shutil.which('chrome.exe') or shutil.which('chrome')
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Chrome w PATH: {chrome_in_path}")
            except Exception as e:
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas sprawdzania chrome w PATH: {str(e)}")
            
            # Sprawdź ścieżki w AppData
            try:
                appdata_local = os.environ.get('LOCALAPPDATA', '')
                appdata_playwright = os.path.join(appdata_local, 'ms-playwright')
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Ścieżka AppData Playwright: {appdata_playwright}, istnieje: {os.path.exists(appdata_playwright)}")
                
                if os.path.exists(appdata_playwright):
                    appdata_contents = os.listdir(appdata_playwright)
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Zawartość AppData Playwright: {appdata_contents}")
            except Exception as e:
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas sprawdzania AppData: {str(e)}")
        
        # Kontynuuj standardowe sprawdzanie przeglądarek
        if not os.path.exists(self.cache_dir):
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Katalog ms-playwright nie istnieje: {self.cache_dir}")
        else:
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Katalog ms-playwright istnieje: {self.cache_dir}")
        
        # Sprawdź na podstawie katalogów przeglądarek
        try:
            if os.path.exists(self.cache_dir):
                cache_contents = os.listdir(self.cache_dir)
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Zawartość katalogu cache: {cache_contents}")
                
                for item in cache_contents:
                    path = os.path.join(self.cache_dir, item)
                    if os.path.isdir(path):
                        item_name = item.lower()
                        if item_name.startswith("chromium"):
                            browsers["chromium"] = True
                            self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Znaleziono przeglądarkę chromium w katalogu cache: {path}")
                            
                            # Sprawdź czy chrome.exe istnieje w tym katalogu
                            chrome_win_dir = os.path.join(path, 'chrome-win')
                            chrome_exe = os.path.join(chrome_win_dir, 'chrome.exe')
                            if os.path.exists(chrome_exe):
                                self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Znaleziono chrome.exe: {chrome_exe}, rozmiar: {os.path.getsize(chrome_exe)} bajtów")
                            else:
                                self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Nie znaleziono chrome.exe w {chrome_exe}")
                                
                                # Sprawdź zawartość katalogu
                                if os.path.exists(chrome_win_dir):
                                    try:
                                        chrome_win_contents = os.listdir(chrome_win_dir)
                                        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Zawartość katalogu chrome-win: {chrome_win_contents}")
                                    except Exception as e:
                                        self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas listowania chrome-win: {str(e)}")
                                else:
                                    self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Katalog chrome-win nie istnieje: {chrome_win_dir}")
                        elif item_name.startswith("firefox"):
                            browsers["firefox"] = True
                            self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Znaleziono przeglądarkę firefox w katalogu cache: {path}")
                        elif item_name.startswith("webkit"):
                            browsers["webkit"] = True
                            self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Znaleziono przeglądarkę webkit w katalogu cache: {path}")
            else:
                self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Katalog cache {self.cache_dir} nie istnieje")
        except Exception as e:
            self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas sprawdzania katalogu ms-playwright: {str(e)}")
        
        # Sprawdź dodatkowo poprzez komendę dry-run, jeśli nie znaleziono przeglądarek
        if not any(browsers.values()):
            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Nie znaleziono przeglądarek w katalogu cache, próbuję dry-run")
            try:
                # Sprawdź czy komenda playwright jest dostępna
                cmd_works, _ = self._check_playwright_command()
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Komenda playwright jest dostępna: {cmd_works}")
                
                if cmd_works:
                    # Wykonaj komendę dry-run
                    dry_run_cmd = ["playwright", "install", "--dry-run"]
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Uruchamiam komendę: {' '.join(dry_run_cmd)}")
                    
                    result = subprocess.run(
                        dry_run_cmd, 
                        capture_output=True, 
                        text=True,
                        check=False
                    )
                    
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Kod wyjścia dry-run: {result.returncode}")
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Wyjście dry-run: {result.stdout}")
                    
                    if result.returncode == 0:
                        output = result.stdout.lower()
                        
                        # Sprawdź informacje o przeglądarkach w outputcie
                        for browser in browsers.keys():
                            if f"browser: {browser}" in output:
                                # Sprawdź ścieżkę instalacji
                                for line in output.split('\n'):
                                    if "install location:" in line and browser in output.split('\n')[output.split('\n').index(line) - 1].lower():
                                        install_path = line.strip().split("install location:")[1].strip()
                                        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Wykryto ścieżkę dla {browser}: {install_path}")
                                        
                                        if install_path and os.path.exists(install_path):
                                            browsers[browser] = True
                                            self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Przeglądarka {browser} wykryta przez dry-run: {install_path}")
                                            
                                            # Sprawdź czy chrome.exe istnieje
                                            if browser == "chromium":
                                                chrome_win_dir = os.path.join(install_path, 'chrome-win')
                                                chrome_exe = os.path.join(chrome_win_dir, 'chrome.exe')
                                                if os.path.exists(chrome_exe):
                                                    self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Znaleziono chrome.exe przez dry-run: {chrome_exe}")
                                                else:
                                                    self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Nie znaleziono chrome.exe przez dry-run w {chrome_exe}")
                else:
                    # Spróbuj przez python -m
                    dry_run_cmd = [sys.executable, "-m", "playwright", "install", "--dry-run"]
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Uruchamiam komendę przez python -m: {' '.join(dry_run_cmd)}")
                    
                    result = subprocess.run(
                        dry_run_cmd, 
                        capture_output=True, 
                        text=True,
                        check=False
                    )
                    
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Kod wyjścia python -m dry-run: {result.returncode}")
                    self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Wyjście python -m dry-run: {result.stdout}")
                    
                    if result.returncode == 0:
                        output = result.stdout.lower()
                        
                        # Sprawdź informacje o przeglądarkach w outputcie
                        for browser in browsers.keys():
                            if f"browser: {browser}" in output:
                                # Sprawdź ścieżkę instalacji
                                for line in output.split('\n'):
                                    if "install location:" in line and browser in output.split('\n')[output.split('\n').index(line) - 1].lower():
                                        install_path = line.strip().split("install location:")[1].strip()
                                        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Wykryto ścieżkę dla {browser} przez python -m: {install_path}")
                                        
                                        if install_path and os.path.exists(install_path):
                                            browsers[browser] = True
                                            self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Przeglądarka {browser} wykryta przez python -m dry-run: {install_path}")
            except Exception as e:
                self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas sprawdzania przeglądarek przez dry-run: {str(e)}")
        
        # Sprawdź systemowe ścieżki przeglądarek dla dodatkowej weryfikacji
        system_browser_paths = self._get_browser_paths_from_system()
        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Systemowe ścieżki przeglądarek: {system_browser_paths}")
        
        # Jeśli nadal nie znaleziono chromium, spróbuj użyć systemowej przeglądarki
        if not browsers["chromium"] and is_frozen:
            if "chromium" in system_browser_paths or "chromium_appdata" in system_browser_paths or "chrome_system" in system_browser_paths:
                self._report_progress("🔍 DIAGNOSTYKA PRZEGLĄDAREK: Nie znaleziono chromium w aplikacji, próbuję użyć systemowej przeglądarki")
                
                if "chromium" in system_browser_paths:
                    browsers["chromium"] = True
                    chromium_path = system_browser_paths["chromium"]
                    chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(chromium_path))))
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                    self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Użyto systemowego Chromium: {chromium_path}, PLAYWRIGHT_BROWSERS_PATH={chromium_parent}")
                elif "chromium_appdata" in system_browser_paths:
                    # Alternatywnie, użyj ścieżki z AppData
                    chromium_path = system_browser_paths["chromium_appdata"]
                    # Poprawka - wskazujemy na katalog ms-playwright w AppData, a nie na cały AppData\Local
                    # Ścieżka zawiera: AppData\Local\ms-playwright\chromium-XXXX\chrome-win\chrome.exe
                    # Potrzebujemy wskazać na: AppData\Local\ms-playwright
                    chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(chromium_path)))
                    
                    self._report_progress(f"🔧 NAPRAWA: Ustawiam PLAYWRIGHT_BROWSERS_PATH={chromium_parent} (z AppData)")
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                    return True
                elif "chrome_system" in system_browser_paths:
                    browsers["chromium"] = True
                    chrome_path = system_browser_paths["chrome_system"]
                    os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = chrome_path
                    self._report_progress(f"✅ DIAGNOSTYKA PRZEGLĄDAREK: Użyto systemowego Chrome: {chrome_path}, PLAYWRIGHT_CHROMIUM_EXECUTABLE={chrome_path}")
        
        # Podsumowanie
        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Podsumowanie wykrytych przeglądarek: {browsers}")
        
        # Spróbuj użyć playwright API do sprawdzenia przeglądarek
        try:
            import importlib
            if importlib.util.find_spec("playwright") is not None:
                self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Sprawdzam przeglądarki przez Playwright API")
                
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        # Sprawdź czy API chromium jest dostępne
                        has_chromium = hasattr(p, 'chromium')
                        self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Playwright API ma dostęp do chromium: {has_chromium}")
                        
                        # Spróbuj pobrać listę przeglądarek przez API
                        try:
                            browser_types = [name for name in dir(p) if not name.startswith('_') and name in ['chromium', 'firefox', 'webkit']]
                            self._report_progress(f"🔍 DIAGNOSTYKA PRZEGLĄDAREK: Wykryte typy przeglądarek przez API: {browser_types}")
                        except Exception as e:
                            self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas pobierania typów przeglądarek: {str(e)}")
                except Exception as e:
                    self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas inicjalizacji Playwright API: {str(e)}")
        except Exception as e:
            self._report_progress(f"❌ DIAGNOSTYKA PRZEGLĄDAREK: Błąd podczas importu playwright: {str(e)}")
        
        return browsers

    def fix_executable_browser_path(self):
        """
        Naprawia ścieżki do przeglądarek w środowisku PyInstaller.
        Ta metoda jest używana, gdy aplikacja jest uruchomiona jako plik wykonywalny.
        """
        self._report_progress("Sprawdzanie i naprawianie ścieżek przeglądarek w środowisku wykonywalnym...")
        
        try:
            # Dokładne sprawdzenie wszystkich ścieżek
            self._report_progress("🔍 DIAGNOSTYKA: Rozpoczynam szczegółową diagnostykę...")
            
            # Sprawdź, czy jesteśmy w środowisku PyInstaller
            is_frozen = getattr(sys, 'frozen', False)
            self._report_progress(f"🔍 DIAGNOSTYKA: Aplikacja w trybie frozen/PyInstaller: {is_frozen}")
            
            if not is_frozen:
                # Jeśli nie jesteśmy w środowisku PyInstaller, to nie ma potrzeby naprawiania
                self._report_progress("🔍 DIAGNOSTYKA: Nie jesteśmy w środowisku PyInstaller, pomijam naprawę")
                return
            
            # Ustal bazową ścieżkę do katalogu z wbudowanym Playwright
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            self._report_progress(f"🔍 DIAGNOSTYKA: Ścieżka bazowa aplikacji: {base_path}")
            
            # KOREKCJA: problem podwójnego _internal
            # Wiemy, że w ścieżkach może występować problem z podwójnym "_internal"
            # To się dzieje, gdy _MEIPASS już zawiera _internal, a my próbujemy dodać kolejny
            # Prawidłowo wykrywamy i naprawiamy ten problem
            
            # 1. Sprawdź, czy _internal występuje już w ścieżce bazowej
            if base_path.endswith('_internal'):
                # Jeśli ścieżka już kończy się na _internal, nie dodawaj tego ponownie
                internal_path = base_path
                self._report_progress(f"🔍 DIAGNOSTYKA: Ścieżka bazowa już zawiera _internal, używam bezpośrednio: {internal_path}")
            else:
                # Normalny przypadek - dodaj _internal do ścieżki bazowej
                internal_path = os.path.join(base_path, "_internal")
                self._report_progress(f"🔍 DIAGNOSTYKA: Dodaję _internal do ścieżki bazowej: {internal_path}")
            
            # 2. Budujemy i sprawdzamy wszystkie możliwe ścieżki
            playwright_path = os.path.join(internal_path, "playwright")
            driver_path = os.path.join(playwright_path, "driver")
            package_path = os.path.join(driver_path, "package")
            local_browsers_path = os.path.join(package_path, ".local-browsers")
            
            # Sprawdź i wypisz wszystkie ścieżki
            paths = {
                "internal_path": internal_path,
                "playwright_path": playwright_path,
                "driver_path": driver_path,
                "package_path": package_path,
                "local_browsers_path": local_browsers_path
            }
            
            for name, path in paths.items():
                exists = os.path.exists(path)
                self._report_progress(f"🔍 DIAGNOSTYKA: Ścieżka {name}: {path}, istnieje: {exists}")
                
                # Jeśli katalog istnieje, sprawdź jego zawartość
                if exists and os.path.isdir(path):
                    try:
                        contents = os.listdir(path)
                        self._report_progress(f"🔍 DIAGNOSTYKA: Zawartość {name}: {contents}")
                    except Exception as e:
                        self._report_progress(f"🔍 DIAGNOSTYKA: Błąd listowania {name}: {e}")
            
            # 3. Sprawdź konkretne ścieżki przeglądarek
            if os.path.exists(local_browsers_path):
                for browser_dir in os.listdir(local_browsers_path):
                    if browser_dir.startswith('chromium-'):
                        chrome_win_dir = os.path.join(local_browsers_path, browser_dir, 'chrome-win')
                        chrome_exe = os.path.join(chrome_win_dir, 'chrome.exe')
                        
                        if os.path.exists(chrome_exe):
                            self._report_progress(f"✅ DIAGNOSTYKA: Znaleziono chrome.exe: {chrome_exe}")
                            # Wszystko wygląda prawidłowo, po prostu zwróć True
                            return True
                        else:
                            self._report_progress(f"❌ DIAGNOSTYKA: Nie znaleziono chrome.exe w oczekiwanej lokalizacji: {chrome_exe}")
            
            # 4. Jeśli nie znaleziono żadnej przeglądarki w aplikacji, musimy podjąć działania naprawcze
            self._report_progress("🔧 NAPRAWA: Brak przeglądarek w aplikacji, próbuję znaleźć alternatywne rozwiązania...")
            
            # Priorytet 1: Sprawdź czy istnieje plik przekierowania i użyj go
            redirection_success = self._try_load_browser_redirection()
            if redirection_success:
                self._report_progress("✅ NAPRAWA: Pomyślnie załadowano przekierowanie przeglądarki")
                return True
            
            # Priorytet 2: Ustawienie zmiennej środowiskowej PLAYWRIGHT_BROWSERS_PATH
            # Wskazujemy systemowy katalog z przeglądarkami
            system_browser_paths = self._get_browser_paths_from_system()
            self._report_progress(f"🔧 NAPRAWA: Znalezione systemowe ścieżki przeglądarek: {system_browser_paths}")
            
            if "chromium" in system_browser_paths:
                # Znajdź katalog nadrzędny względem pliku chrome.exe
                chromium_path = system_browser_paths["chromium"]
                # Potrzebujemy wskazać na katalog ms-playwright w .cache, a nie na całe .cache
                # Ścieżka zawiera: .cache\ms-playwright\chromium-XXXX\chrome-win\chrome.exe
                # Potrzebujemy wskazać na: .cache\ms-playwright
                chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(chromium_path)))
                
                # Ustaw zmienną środowiskową 
                self._report_progress(f"🔧 NAPRAWA: Ustawiam PLAYWRIGHT_BROWSERS_PATH={chromium_parent}")
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                return True
            elif "chromium_appdata" in system_browser_paths:
                # Alternatywnie, użyj ścieżki z AppData
                chromium_path = system_browser_paths["chromium_appdata"]
                # Poprawka - wskazujemy na katalog ms-playwright w AppData, a nie na cały AppData\Local
                # Ścieżka zawiera: AppData\Local\ms-playwright\chromium-XXXX\chrome-win\chrome.exe
                # Potrzebujemy wskazać na: AppData\Local\ms-playwright
                chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(chromium_path)))
                
                self._report_progress(f"🔧 NAPRAWA: Ustawiam PLAYWRIGHT_BROWSERS_PATH={chromium_parent} (z AppData)")
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                return True
            elif "chrome_system" in system_browser_paths:
                # Użyj systemowego Chrome - ustawienie zmiennej na plik wykonywalny
                chrome_path = system_browser_paths["chrome_system"]
                
                self._report_progress(f"🔧 NAPRAWA: Ustawiam PLAYWRIGHT_CHROMIUM_EXECUTABLE={chrome_path}")
                os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = chrome_path
                
                # Stwórz tymczasowy katalog z plikiem przekierowania
                import tempfile
                import json
                temp_dir = os.path.join(tempfile.gettempdir(), "ms-playwright-redirect")
                os.makedirs(temp_dir, exist_ok=True)
                
                # Utwórz plik wskazujący na Chrome
                chrome_json = os.path.join(temp_dir, "chrome_system.json")
                with open(chrome_json, 'w', encoding='utf-8') as f:
                    json.dump({
                        "executable": chrome_path,
                        "type": "chrome"
                    }, f, indent=2)
                
                self._report_progress(f"🔧 NAPRAWA: Ustawiam PLAYWRIGHT_BROWSERS_PATH={temp_dir}")
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = temp_dir
                return True
            
            # Priorytet 3: Skopiuj przeglądarki z systemu do aplikacji
            copy_success = self._try_copy_system_browser_to_app()
            if copy_success:
                self._report_progress("✅ NAPRAWA: Pomyślnie skopiowano przeglądarkę z systemu do aplikacji")
                return True
            
            # Jeśli wszystko inne zawiedzie, wypisz informacje diagnostyczne
            self._report_progress("❌ NAPRAWA: Nie udało się naprawić ścieżek przeglądarek. Aplikacja może nie działać poprawnie.")
            
            # Sprawdź, czy w ogóle playwright jest zainstalowany
            try:
                import importlib
                has_playwright = importlib.util.find_spec("playwright") is not None
                self._report_progress(f"🔧 DIAGNOSTYKA: Moduł playwright jest dostępny: {has_playwright}")
                
                if has_playwright:
                    # Ostatnia próba - użyj domyślnej ścieżki Playwright
                    self._report_progress("🔧 NAPRAWA: Ostatnia próba - ustawiam domyślną ścieżkę Playwright")
                    from playwright.path_utils import get_playwright_browsers_path
                    try:
                        browsers_path = get_playwright_browsers_path()
                        self._report_progress(f"🔧 NAPRAWA: Domyślna ścieżka przeglądarek Playwright: {browsers_path}")
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
                        return True
                    except Exception as e:
                        self._report_progress(f"❌ NAPRAWA: Błąd podczas pobierania domyślnej ścieżki Playwright: {e}")
            except ImportError:
                self._report_progress("❌ DIAGNOSTYKA: Moduł playwright nie jest dostępny w tym środowisku")
            
            return False
                
        except Exception as e:
            self._report_progress(f"❌ DIAGNOSTYKA: Nieoczekiwany błąd podczas naprawiania ścieżek: {e}")
            
            # Nawet w przypadku błędu, spróbuj ustawić zmienną środowiskową
            try:
                # Ostatnia próba - załaduj plik przekierowania
                if self._try_load_browser_redirection():
                    self._report_progress("✅ NAPRAWA AWARYJNA: Pomyślnie załadowano przekierowanie przeglądarki mimo błędu")
                    return True
                
                # Jeśli nie zadziałało, spróbuj ustawić zmienną ręcznie
                system_browser_paths = self._get_browser_paths_from_system()
                if "chromium" in system_browser_paths:
                    chromium_path = system_browser_paths["chromium"]
                    # Poprawka - wskazujemy na katalog ms-playwright w .cache, a nie na całe .cache
                    # Ścieżka zawiera: .cache\ms-playwright\chromium-XXXX\chrome-win\chrome.exe
                    # Potrzebujemy wskazać na: .cache\ms-playwright
                    chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(chromium_path)))
                    self._report_progress(f"🔧 NAPRAWA AWARYJNA: Ustawiam PLAYWRIGHT_BROWSERS_PATH={chromium_parent}")
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                    return True
                elif "chrome_system" in system_browser_paths:
                    # Użyj systemowego Chrome w awaryjnym trybie
                    chrome_path = system_browser_paths["chrome_system"]
                    self._report_progress(f"🔧 NAPRAWA AWARYJNA: Ustawiam PLAYWRIGHT_CHROMIUM_EXECUTABLE={chrome_path}")
                    os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = chrome_path
                    return True
            except Exception:
                pass
                
            return False

    def configure_playwright_paths(self):
        """
        Konfiguruje ścieżki do przeglądarek Playwright dla bieżącego środowiska.
        Ta metoda powinna być wywoływana przy starcie aplikacji.
        
        Returns:
            bool: True, jeśli konfiguracja się powiodła, False w przeciwnym przypadku.
        """
        self._report_progress("Konfiguracja ścieżek Playwright przy starcie aplikacji...")
        
        try:
            # Sprawdź, czy jesteśmy w środowisku PyInstaller
            is_frozen = getattr(sys, 'frozen', False)
            
            if is_frozen:
                # Używamy specjalnej metody dla środowiska PyInstaller
                self._report_progress("Wykryto środowisko PyInstaller, używam dedykowanej metody naprawy ścieżek")
                return self.fix_executable_browser_path()
            else:
                # W normalnym środowisku sprawdzamy, czy mamy dostęp do przeglądarek
                self._report_progress("Standardowe środowisko Python, sprawdzam dostępność przeglądarek")
                
                # Sprawdź status instalacji
                installation_status = self.get_installation_status()
                
                if not installation_status["playwright_installed"]:
                    self._report_progress("❌ Pakiet playwright nie jest zainstalowany lub nie działa poprawnie")
                    return False
                
                if not any(installation_status["browsers"].values()):
                    self._report_progress("❌ Nie wykryto zainstalowanych przeglądarek Playwright")
                    return False
                
                # Wszystko wygląda dobrze w standardowym środowisku
                self._report_progress("✅ Playwright i przeglądarki są poprawnie skonfigurowane")
                return True
        
        except Exception as e:
            self._report_progress(f"❌ Błąd podczas konfiguracji ścieżek Playwright: {e}")
            return False

    def _get_browser_paths_from_system(self):
        """Zwraca ścieżki przeglądarek z systemu."""
        browser_paths = {}
        
        try:
            # Standardowa ścieżka cache Playwright
            cache_dir = Path.home() / ".cache" / "ms-playwright"
            if cache_dir.exists():
                for item in os.listdir(cache_dir):
                    if item.startswith("chromium-"):
                        chrome_win_dir = os.path.join(cache_dir, item, "chrome-win")
                        chrome_exe = os.path.join(chrome_win_dir, "chrome.exe")
                        if os.path.exists(chrome_exe):
                            browser_paths["chromium"] = str(chrome_exe)
                            self._report_progress(f"📁 Znaleziono chrome.exe w systemowym cache: {chrome_exe}")
                        else:
                            self._report_progress(f"⚠️ Nie znaleziono chrome.exe w oczekiwanej ścieżce: {chrome_exe}")
                    elif item.startswith("firefox-"):
                        if os.name == 'nt':
                            firefox_exe = os.path.join(cache_dir, item, "firefox", "firefox.exe")
                        else:
                            firefox_exe = os.path.join(cache_dir, item, "firefox", "firefox")
                        if os.path.exists(firefox_exe):
                            browser_paths["firefox"] = str(firefox_exe)
                    elif item.startswith("webkit-"):
                        if os.name == 'nt':
                            webkit_exe = os.path.join(cache_dir, item, "minibrowser", "MiniBrowser.exe")
                        else:
                            webkit_exe = os.path.join(cache_dir, item, "minibrowser", "MiniBrowser")
                        if os.path.exists(webkit_exe):
                            browser_paths["webkit"] = str(webkit_exe)
            
            # Ścieżka w AppData dla Windows
            if os.name == 'nt':
                appdata_path = Path(os.environ.get('LOCALAPPDATA', '')) / "ms-playwright"
                if appdata_path.exists():
                    for item in os.listdir(appdata_path):
                        if item.startswith("chromium-"):
                            chrome_win_dir = os.path.join(appdata_path, item, "chrome-win")
                            chrome_exe = os.path.join(chrome_win_dir, "chrome.exe")
                            if os.path.exists(chrome_exe):
                                browser_paths["chromium_appdata"] = str(chrome_exe)
                                self._report_progress(f"📁 Znaleziono chrome.exe w AppData: {chrome_exe}")
                            else:
                                self._report_progress(f"⚠️ Nie znaleziono chrome.exe w AppData: {chrome_exe}")
                        elif item.startswith("firefox-"):
                            firefox_exe = os.path.join(appdata_path, item, "firefox", "firefox.exe")
                            if os.path.exists(firefox_exe):
                                browser_paths["firefox_appdata"] = str(firefox_exe)
                        elif item.startswith("webkit-"):
                            webkit_exe = os.path.join(appdata_path, item, "minibrowser", "MiniBrowser.exe")
                            if os.path.exists(webkit_exe):
                                browser_paths["webkit_appdata"] = str(webkit_exe)
            
            # Sprawdź również instalację Chromium poza Playwright
            try:
                # Sprawdź systemową przeglądarkę Chrome
                if os.name == 'nt':
                    # Standardowe lokalizacje na Windows
                    program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
                    program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
                    chrome_locations = [
                        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(os.environ.get('LOCALAPPDATA', ''), "Google", "Chrome", "Application", "chrome.exe")
                    ]
                    
                    for location in chrome_locations:
                        if os.path.exists(location):
                            browser_paths["chrome_system"] = location
                            self._report_progress(f"📁 Znaleziono systemowy Chrome: {location}")
                            break
            except Exception as e:
                self._report_progress(f"⚠️ Błąd podczas sprawdzania systemowego Chrome: {e}")
            
        except Exception as e:
            self._report_progress(f"⚠️ Błąd podczas sprawdzania ścieżek przeglądarek: {e}")
        
        return browser_paths

    def _try_copy_system_browser_to_app(self):
        """
        Próbuje skopiować przeglądarkę z systemowego katalogu cache do katalogu aplikacji.
        Ta metoda jest używana jako ostatnia deska ratunku, gdy nie można zainstalować przeglądarki.
        """
        self._report_progress("📋 OPERACJA KOPIOWANIA: Próbuję skopiować przeglądarkę z systemowego katalogu")
        
        try:
            # Sprawdź czy jesteśmy w środowisku PyInstaller
            if not getattr(sys, 'frozen', False):
                self._report_progress("📋 OPERACJA KOPIOWANIA: Nie jesteśmy w środowisku PyInstaller, pomijam")
                return False
            
            # Ustal ścieżkę docelową w aplikacji
            app_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            
            # Sprawdź, czy _internal występuje już w ścieżce
            if app_path.endswith('_internal'):
                internal_path = app_path
                self._report_progress(f"📋 OPERACJA KOPIOWANIA: Ścieżka już zawiera _internal: {internal_path}")
            else:
                internal_path = os.path.join(app_path, "_internal")
                self._report_progress(f"📋 OPERACJA KOPIOWANIA: Dodaję _internal do ścieżki: {internal_path}")
            
            # Możliwe ścieżki dla katalogu przeglądarek
            possible_target_paths = []
            
            # Standardowa struktura katalogów
            playwright_path = os.path.join(internal_path, "playwright")
            driver_path = os.path.join(playwright_path, "driver")
            package_path = os.path.join(driver_path, "package")
            target_browsers_path = os.path.join(package_path, ".local-browsers")
            possible_target_paths.append(target_browsers_path)
            
            # Alternatywna struktura (bez katalogu _internal)
            alt_playwright_path = os.path.join(app_path, "playwright")
            alt_driver_path = os.path.join(alt_playwright_path, "driver")
            alt_package_path = os.path.join(alt_driver_path, "package")
            alt_target_browsers_path = os.path.join(alt_package_path, ".local-browsers")
            possible_target_paths.append(alt_target_browsers_path)
            
            # Alternatywna struktura (z podwójnym _internal)
            alt2_internal_path = os.path.join(internal_path, "_internal")
            alt2_playwright_path = os.path.join(alt2_internal_path, "playwright")
            alt2_driver_path = os.path.join(alt2_playwright_path, "driver")
            alt2_package_path = os.path.join(alt2_driver_path, "package")
            alt2_target_browsers_path = os.path.join(alt2_package_path, ".local-browsers")
            possible_target_paths.append(alt2_target_browsers_path)
            
            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Sprawdzam możliwe ścieżki docelowe: {possible_target_paths}")
            
            # Znajdź pierwszą istniejącą ścieżkę docelową
            target_browsers_path = None
            for path in possible_target_paths:
                if os.path.exists(os.path.dirname(path)):
                    target_browsers_path = path
                    self._report_progress(f"📋 OPERACJA KOPIOWANIA: Znaleziono ścieżkę docelową: {target_browsers_path}")
                    break
            
            # Jeśli nie znaleziono żadnej ścieżki, użyj pierwszej i utwórz katalogi
            if target_browsers_path is None:
                target_browsers_path = possible_target_paths[0]
                self._report_progress(f"📋 OPERACJA KOPIOWANIA: Nie znaleziono istniejących katalogów, tworzę nowe: {target_browsers_path}")
                os.makedirs(os.path.dirname(target_browsers_path), exist_ok=True)
            
            # Utwórz katalog .local-browsers jeśli nie istnieje
            os.makedirs(target_browsers_path, exist_ok=True)
            
            # Lista możliwych lokalizacji przeglądarek
            possible_source_locations = []
            
            # 1. Standardowy katalog cache
            cache_dir = Path.home() / ".cache" / "ms-playwright"
            if cache_dir.exists():
                possible_source_locations.append(str(cache_dir))
            
            # 2. Katalog AppData dla Windows
            if os.name == 'nt':
                appdata_path = Path(os.environ.get('LOCALAPPDATA', '')) / "ms-playwright"
                if appdata_path.exists():
                    possible_source_locations.append(str(appdata_path))
            
            # 3. Katalog systemowy dla Linux
            if os.name == 'posix':
                system_path = Path("/usr/local/share/playwright")
                if system_path.exists():
                    possible_source_locations.append(str(system_path))
            
            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Możliwe lokalizacje źródłowe: {possible_source_locations}")
            
            # Szukaj przeglądarki chromium we wszystkich lokalizacjach
            for location in possible_source_locations:
                self._report_progress(f"📋 OPERACJA KOPIOWANIA: Przeszukuję lokalizację: {location}")
                
                try:
                    for item in os.listdir(location):
                        if item.startswith("chromium-"):
                            source_dir = os.path.join(location, item)
                            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Znaleziono katalog chromium: {source_dir}")
                            
                            # Szczegółowe sprawdzenie zawartości katalogu źródłowego
                            if os.path.isdir(source_dir):
                                chrome_win_dir = os.path.join(source_dir, "chrome-win")
                                chrome_exe = os.path.join(chrome_win_dir, "chrome.exe")
                                
                                # Sprawdź czy katalog chrome-win istnieje
                                if not os.path.exists(chrome_win_dir):
                                    self._report_progress(f"📋 OPERACJA KOPIOWANIA: Katalog chrome-win nie istnieje: {chrome_win_dir}")
                                    # Sprawdź zawartość katalogu źródłowego
                                    if os.path.exists(source_dir):
                                        contents = os.listdir(source_dir)
                                        self._report_progress(f"📋 OPERACJA KOPIOWANIA: Zawartość katalogu: {contents}")
                                    continue
                                
                                # Sprawdź czy chrome.exe istnieje
                                self._report_progress(f"📋 OPERACJA KOPIOWANIA: Sprawdzam chrome.exe: {chrome_exe}, istnieje: {os.path.exists(chrome_exe)}")
                                
                                if os.path.exists(chrome_exe) and os.path.getsize(chrome_exe) > 1000000:  # Upewnij się, że plik ma odpowiedni rozmiar
                                    # To poprawny katalog z przeglądarką
                                    target_dir = os.path.join(target_browsers_path, item)
                                    self._report_progress(f"📋 OPERACJA KOPIOWANIA: Kopiuję z {source_dir} do {target_dir}")
                                    
                                    try:
                                        # Usuń istniejący katalog docelowy, jeśli istnieje
                                        if os.path.exists(target_dir):
                                            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Usuwam istniejący katalog: {target_dir}")
                                            shutil.rmtree(target_dir)
                                        
                                        # Kopiuj katalog
                                        self._report_progress(f"📋 OPERACJA KOPIOWANIA: Rozpoczynam kopiowanie katalogu...")
                                        
                                        # Na systemie Windows, użyj robustcopy z nakładaniem czasowego limitu
                                        if os.name == 'nt':
                                            # Utwórz główny katalog celu
                                            os.makedirs(target_dir, exist_ok=True)
                                            
                                            # Kopiowanie katalogu chrome-win
                                            chrome_win_target = os.path.join(target_dir, "chrome-win")
                                            os.makedirs(chrome_win_target, exist_ok=True)
                                            
                                            # Kopiuj pliki z chrome-win
                                            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Kopiuję pliki chrome-win...")
                                            for filename in os.listdir(chrome_win_dir):
                                                src_file = os.path.join(chrome_win_dir, filename)
                                                dst_file = os.path.join(chrome_win_target, filename)
                                                
                                                if os.path.isfile(src_file):
                                                    try:
                                                        shutil.copy2(src_file, dst_file)
                                                    except Exception as e:
                                                        self._report_progress(f"📋 OPERACJA KOPIOWANIA: Błąd kopiowania pliku {filename}: {e}")
                                                elif os.path.isdir(src_file):
                                                    try:
                                                        shutil.copytree(src_file, dst_file, dirs_exist_ok=True)
                                                    except Exception as e:
                                                        self._report_progress(f"📋 OPERACJA KOPIOWANIA: Błąd kopiowania katalogu {filename}: {e}")
                                        else:
                                            # Na innych systemach użyj standardowego copytree
                                            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
                                        
                                        # Sprawdź czy kopiowanie powiodło się
                                        target_chrome_exe = os.path.join(target_dir, "chrome-win", "chrome.exe")
                                        if os.path.exists(target_chrome_exe):
                                            self._report_progress(f"✅ OPERACJA KOPIOWANIA: Pomyślnie skopiowano przeglądarkę! Rozmiar chrome.exe: {os.path.getsize(target_chrome_exe)} bajtów")
                                            
                                            # Ustaw zmienną środowiskową, aby Playwright odnalazł przeglądarkę
                                            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.dirname(target_browsers_path)
                                            self._report_progress(f"📋 OPERACJA KOPIOWANIA: Ustawiono PLAYWRIGHT_BROWSERS_PATH={os.path.dirname(target_browsers_path)}")
                                            
                                            return True
                                        else:
                                            self._report_progress(f"❌ OPERACJA KOPIOWANIA: Kopiowanie nie powiodło się, chrome.exe nie istnieje w katalogu docelowym {target_chrome_exe}")
                                    except Exception as e:
                                        self._report_progress(f"❌ OPERACJA KOPIOWANIA: Błąd podczas kopiowania: {str(e)}")
                except Exception as e:
                    self._report_progress(f"❌ OPERACJA KOPIOWANIA: Błąd podczas przeszukiwania lokalizacji {location}: {str(e)}")
            
            # Jeśli przeszukaliśmy wszystkie lokalizacje i nie znaleźliśmy przeglądarki, spróbujmy ostatni sposób
            self._report_progress("📋 OPERACJA KOPIOWANIA: Nie znaleziono odpowiedniej przeglądarki do skopiowania, próbuję alternatywne podejście...")
            
            # Alternatywne podejście - ustaw zmienną środowiskową by wskazywała na systemową przeglądarkę
            # Nie kopiujemy plików, tylko mówimy Playwright gdzie ich szukać
            system_browser_paths = self._get_browser_paths_from_system()
            if "chromium" in system_browser_paths or "chromium_appdata" in system_browser_paths:
                browser_key = "chromium" if "chromium" in system_browser_paths else "chromium_appdata"
                browser_path = system_browser_paths[browser_key]
                
                # Znajdź katalog który zawiera folder .local-browsers
                # chrome.exe jest w .local-browsers/chromium-XXXX/chrome-win/chrome.exe
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(browser_path))))
                
                self._report_progress(f"📋 OPERACJA KOPIOWANIA (ALT): Ustawiam PLAYWRIGHT_BROWSERS_PATH={parent_dir}")
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = parent_dir
                return True
                
            self._report_progress("❌ OPERACJA KOPIOWANIA: Wszystkie próby zawiodły, nie udało się skopiować przeglądarki")
            return False
            
        except Exception as e:
            self._report_progress(f"❌ OPERACJA KOPIOWANIA: Nieoczekiwany błąd: {str(e)}")
            return False

    def _try_load_browser_redirection(self):
        """
        Próbuje załadować informacje o przekierowaniu przeglądarek z pliku.
        Ta metoda jest używana, gdy nie można znaleźć wbudowanej przeglądarki.
        """
        self._report_progress("📖 PRZEKIEROWANIE: Próbuję załadować informacje o przekierowaniu przeglądarek")
        
        try:
            # Sprawdź czy jesteśmy w środowisku PyInstaller
            if not getattr(sys, 'frozen', False):
                self._report_progress("📖 PRZEKIEROWANIE: Nie jesteśmy w środowisku PyInstaller, pomijam")
                return False
            
            # Ustal ścieżkę do pliku przekierowania
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            
            # Sprawdź, czy _internal występuje już w ścieżce
            if base_path.endswith('_internal'):
                internal_path = base_path
            else:
                internal_path = os.path.join(base_path, "_internal")
            
            # Możliwe ścieżki do pliku przekierowania
            possible_paths = [
                os.path.join(internal_path, "browser_paths.json"),
                os.path.join(base_path, "browser_paths.json"),
                os.path.join(os.path.dirname(base_path), "browser_paths.json")
            ]
            
            self._report_progress(f"📖 PRZEKIEROWANIE: Sprawdzam możliwe ścieżki: {possible_paths}")
            
            # Szukaj pliku przekierowania
            redirection_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    redirection_path = path
                    self._report_progress(f"📖 PRZEKIEROWANIE: Znaleziono plik przekierowania: {redirection_path}")
                    break
            
            # Jeśli nie znaleziono pliku, zakończ
            if redirection_path is None:
                self._report_progress("📖 PRZEKIEROWANIE: Nie znaleziono pliku przekierowania")
                return False
            
            # Załaduj plik
            import json
            with open(redirection_path, 'r', encoding='utf-8') as f:
                redirection_data = json.load(f)
            
            # Sprawdź czy dane zawierają ścieżki przeglądarek
            if 'browser_paths' not in redirection_data:
                self._report_progress("📖 PRZEKIEROWANIE: Plik przekierowania nie zawiera ścieżek przeglądarek")
                return False
            
            browser_paths = redirection_data['browser_paths']
            self._report_progress(f"📖 PRZEKIEROWANIE: Załadowano ścieżki przeglądarek: {browser_paths}")
            
            # Sprawdź czy któraś z przeglądarek jest dostępna
            for key, path in browser_paths.items():
                if os.path.exists(path):
                    self._report_progress(f"📖 PRZEKIEROWANIE: Znaleziono przeglądarkę {key}: {path}")
                    
                    # W zależności od typu przeglądarki, ustaw odpowiednią zmienną środowiskową
                    if key.startswith("chromium"):
                        # Znajdź katalog nadrzędny przeglądarki
                        chromium_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                        self._report_progress(f"📖 PRZEKIEROWANIE: Ustawiam PLAYWRIGHT_BROWSERS_PATH={chromium_parent}")
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chromium_parent
                        return True
                    elif key == "chrome_system" or key == "edge_system":
                        # Dla systemowego Chrome/Edge, ustaw zmienną na katalog tymczasowy i dodaj wpis dla Chromium
                        import tempfile
                        temp_dir = os.path.join(tempfile.gettempdir(), "ms-playwright-redirect")
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Utwórz katalog browsers z odnośnikiem do systemowej przeglądarki
                        browsers_dir = os.path.join(temp_dir, ".local-browsers")
                        os.makedirs(browsers_dir, exist_ok=True)
                        
                        # Utwórz plik wskazujący na systemową przeglądarkę
                        system_browser_json = os.path.join(temp_dir, "system_browser.json")
                        with open(system_browser_json, 'w', encoding='utf-8') as f:
                            json.dump({
                                "executable": path,
                                "browser": "chromium" if key == "chrome_system" else "msedge"
                            }, f, indent=2)
                        
                        # Ustaw zmienną środowiskową
                        self._report_progress(f"📖 PRZEKIEROWANIE: Ustawiam PLAYWRIGHT_BROWSERS_PATH={temp_dir}")
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = temp_dir
                        
                        # Dodatkowo można ustawić PLAYWRIGHT_CHROMIUM_EXECUTABLE
                        self._report_progress(f"📖 PRZEKIEROWANIE: Ustawiam PLAYWRIGHT_CHROMIUM_EXECUTABLE={path}")
                        os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = path
                        
                        return True
            
            self._report_progress("📖 PRZEKIEROWANIE: Nie znaleziono dostępnych przeglądarek w pliku przekierowania")
            return False
            
        except Exception as e:
            self._report_progress(f"📖 PRZEKIEROWANIE: Błąd podczas ładowania pliku przekierowania: {e}")
            return False

# Funkcja pomocnicza do sprawdzenia, czy playwright jest dostępny
def check_playwright_availability() -> bool:
    """Sprawdza, czy pakiet playwright jest dostępny w systemie."""
    mgr = PlaywrightManager()
    status = mgr.get_installation_status()
    return status["playwright_installed"] and any(status["browsers"].values()) 