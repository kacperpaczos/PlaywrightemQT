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
                return self._install_browsers(browsers)
            
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
                return self._install_browsers(browsers)
                
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
        """Sprawdza, które przeglądarki są zainstalowane."""
        browsers = {"chromium": False, "firefox": False, "webkit": False}
        
        # Sprawdź bezpośrednio w katalogu cache
        if not os.path.exists(self.cache_dir):
            logger.warning(f"Katalog ms-playwright nie istnieje: {self.cache_dir}")
            return browsers
        
        # Sprawdź na podstawie katalogów przeglądarek
        try:
            for item in os.listdir(self.cache_dir):
                path = os.path.join(self.cache_dir, item)
                if os.path.isdir(path):
                    item_name = item.lower()
                    if item_name.startswith("chromium"):
                        browsers["chromium"] = True
                        logger.info(f"Znaleziono przeglądarkę chromium w katalogu cache: {path}")
                    elif item_name.startswith("firefox"):
                        browsers["firefox"] = True
                        logger.info(f"Znaleziono przeglądarkę firefox w katalogu cache: {path}")
                    elif item_name.startswith("webkit"):
                        browsers["webkit"] = True
                        logger.info(f"Znaleziono przeglądarkę webkit w katalogu cache: {path}")
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania katalogu ms-playwright: {e}")
        
        # Sprawdź dodatkowo poprzez komendę dry-run, jeśli nie znaleziono przeglądarek
        if not any(browsers.values()):
            try:
                # Sprawdź czy komenda playwright jest dostępna
                cmd_works, _ = self._check_playwright_command()
                
                if cmd_works:
                    # Wykonaj komendę dry-run
                    result = subprocess.run(
                        ["playwright", "install", "--dry-run"], 
                        capture_output=True, 
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        output = result.stdout.lower()
                        logger.info(f"Wynik komendy playwright install --dry-run: {output}")
                        
                        # Sprawdź informacje o przeglądarkach w outputcie
                        for browser in browsers.keys():
                            if f"browser: {browser}" in output:
                                # Sprawdź ścieżkę instalacji
                                for line in output.split('\n'):
                                    if "install location:" in line and browser in output.split('\n')[output.split('\n').index(line) - 1].lower():
                                        install_path = line.strip().split("install location:")[1].strip()
                                        if install_path and os.path.exists(install_path):
                                            browsers[browser] = True
                                            logger.info(f"Przeglądarka {browser} wykryta przez dry-run: {install_path}")
                else:
                    # Spróbuj przez python -m
                    result = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "--dry-run"], 
                        capture_output=True, 
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        output = result.stdout.lower()
                        logger.info(f"Wynik komendy python -m playwright install --dry-run: {output}")
                        
                        # Sprawdź informacje o przeglądarkach w outputcie
                        for browser in browsers.keys():
                            if f"browser: {browser}" in output:
                                # Sprawdź ścieżkę instalacji
                                for line in output.split('\n'):
                                    if "install location:" in line and browser in output.split('\n')[output.split('\n').index(line) - 1].lower():
                                        install_path = line.strip().split("install location:")[1].strip()
                                        if install_path and os.path.exists(install_path):
                                            browsers[browser] = True
                                            logger.info(f"Przeglądarka {browser} wykryta przez dry-run: {install_path}")
            except Exception as e:
                logger.error(f"Błąd podczas sprawdzania przeglądarek przez dry-run: {e}")
        
        return browsers

# Funkcja pomocnicza do sprawdzenia, czy playwright jest dostępny
def check_playwright_availability() -> bool:
    """Sprawdza, czy pakiet playwright jest dostępny w systemie."""
    mgr = PlaywrightManager()
    status = mgr.get_installation_status()
    return status["playwright_installed"] and any(status["browsers"].values()) 