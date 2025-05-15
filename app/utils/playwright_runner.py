#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import tempfile
import nest_asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from app.utils.logger import setup_logger
from app.utils.config_loader import config

# Zastosowanie nest_asyncio pozwala na zagnieżdżanie pętli zdarzeń asyncio,
# co rozwiązuje problem z "There is no current event loop in thread"
nest_asyncio.apply()

# Inicjalizacja loggera w bloku try-except dla bezpieczeństwa
try:
    logger = setup_logger()
except Exception as e:
    import logging
    print(f"Nie można zainicjalizować loggera Loguru: {e}")
    # Fallback do standardowego logging w przypadku problemów z Loguru
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("PlaywrightRunner")

class PlaywrightRunner:
    def __init__(self):
        self.results = []
        self.screenshot_path = None
        
        try:
            # Pobieranie konfiguracji
            self.timeout = config.get_int("PLAYWRIGHT", "timeout", 30000)
            
            # Określ katalog dla zrzutów ekranu w zależności od środowiska
            if getattr(sys, 'frozen', False):
                # W środowisku PyInstaller
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
                self.screenshot_dir = os.path.join(
                    tempfile.gettempdir(), 
                    "Fakturator_e-urtica", 
                    "screenshots"
                )
            else:
                # W środowisku deweloperskim
                self.screenshot_dir = config.get_value(
                    "PLAYWRIGHT", 
                    "screenshot_path", 
                    "logs/screenshots"
                )
                
            # Upewniamy się, że katalog na zrzuty ekranu istnieje
            os.makedirs(self.screenshot_dir, exist_ok=True)
            
        except Exception as e:
            logger.error(f"Błąd inicjalizacji PlaywrightRunner: {e}")
            # Ustaw wartości domyślne
            self.timeout = 30000
            self.screenshot_dir = tempfile.gettempdir()
            os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def run_test(self, url, headless=False):
        """
        Uruchamia test Playwright dla podanego URL.
        
        Args:
            url (str): Adres URL do przetestowania
            headless (bool): Czy uruchomić przeglądarkę w trybie headless
            
        Returns:
            tuple: (wyniki testu, ścieżka do zrzutu ekranu)
        """
        # Utworzenie nowej pętli zdarzeń dla tego wątku
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(self._run_test_async(url, headless))
        except Exception as e:
            error_msg = f"Nieprzewidziany błąd podczas wykonywania testu: {e}"
            logger.error(error_msg)
            self.results.append(error_msg)
            return "\n".join(self.results), None
        finally:
            loop.close()
    
    async def _run_test_async(self, url, headless=False):
        logger.info(f"Uruchamianie testu Playwright dla {url} (headless: {headless})")
        self.results = []
        self.screenshot_path = None
        
        try:
            async with async_playwright() as p:
                self._log("Uruchamianie przeglądarki...")
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Ustawienie timeoutu
                page.set_default_timeout(self.timeout)
                
                try:
                    self._log(f"Otwieranie strony: {url}")
                    await page.goto(url)
                    
                    self._log("Pobieranie tytułu strony...")
                    title = await page.title()
                    self._log(f"Tytuł strony: {title}")
                    
                    # Dodatkowe informacje o stronie
                    self._log("Pobieranie informacji o stronie...")
                    dimensions = await page.evaluate("""() => {
                        return {
                            width: window.innerWidth,
                            height: window.innerHeight,
                            devicePixelRatio: window.devicePixelRatio
                        }
                    }""")
                    self._log(f"Wymiary okna: {dimensions['width']}x{dimensions['height']}")
                    
                    # Wykonanie zrzutu ekranu
                    self._log("Robienie zrzutu ekranu...")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_url = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
                    filename = f"screenshot_{clean_url}_{timestamp}.png"
                    self.screenshot_path = os.path.join(self.screenshot_dir, filename)
                    
                    # Upewnij się, że katalog istnieje
                    os.makedirs(os.path.dirname(self.screenshot_path), exist_ok=True)
                    
                    await page.screenshot(path=self.screenshot_path)
                    self._log(f"Zrzut ekranu zapisany: {self.screenshot_path}")
                    
                    # Analiza strony
                    self._log("Pobieranie elementów strony...")
                    # Liczenie linków
                    links_count = await page.evaluate("document.querySelectorAll('a').length")
                    self._log(f"Liczba linków na stronie: {links_count}")
                    
                    # Liczenie obrazów
                    images_count = await page.evaluate("document.querySelectorAll('img').length")
                    self._log(f"Liczba obrazów na stronie: {images_count}")
                    
                    # Liczenie formularzy
                    forms_count = await page.evaluate("document.querySelectorAll('form').length")
                    self._log(f"Liczba formularzy na stronie: {forms_count}")
                    
                    # Liczenie przycisków
                    buttons_count = await page.evaluate("document.querySelectorAll('button').length")
                    self._log(f"Liczba przycisków na stronie: {buttons_count}")
                    
                    # Sprawdzanie wydajności strony
                    self._log("Sprawdzanie wydajności strony...")
                    try:
                        performance = await page.evaluate("""() => {
                            const performance = window.performance;
                            const timing = performance.timing;
                            return {
                                loadTime: timing.loadEventEnd - timing.navigationStart,
                                domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                                firstPaint: timing.responseEnd - timing.navigationStart
                            }
                        }""")
                        
                        self._log(f"Czas ładowania strony: {performance['loadTime']} ms")
                        self._log(f"Czas ładowania DOM: {performance['domContentLoaded']} ms")
                        self._log(f"Czas pierwszego renderowania: {performance['firstPaint']} ms")
                    except Exception as e:
                        self._log(f"Nie udało się pobrać informacji o wydajności: {str(e)}")
                    
                except Exception as e:
                    error_message = f"Błąd podczas testowania strony: {str(e)}"
                    self._log(error_message)
                    logger.error(error_message)
                    
                    # Spróbuj zrobić zrzut ekranu błędu, jeśli to możliwe
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        clean_url = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
                        filename = f"error_{clean_url}_{timestamp}.png"
                        self.screenshot_path = os.path.join(self.screenshot_dir, filename)
                        await page.screenshot(path=self.screenshot_path)
                        self._log(f"Zrzut ekranu błędu zapisany: {self.screenshot_path}")
                    except Exception as screenshot_error:
                        self._log(f"Nie udało się zrobić zrzutu ekranu błędu: {screenshot_error}")
                
                finally:
                    self._log("Zamykanie przeglądarki...")
                    await browser.close()
        except Exception as e:
            error_message = f"Nieoczekiwany błąd Playwright: {str(e)}"
            self._log(error_message)
            logger.error(error_message)
            
        return "\n".join(self.results), self.screenshot_path
    
    def _log(self, message):
        self.results.append(message)
        logger.info(message)
