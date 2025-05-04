#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Dict, Any, Optional, Callable
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

class PlaywrightTest:
    def __init__(self, config: Dict[str, Any], progress_callback: Optional[Callable[[int], None]] = None):
        self.config = config
        self.progress_callback = progress_callback
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.stats = {
            "przetworzone_zamowienia": 0,
            "pobrane_elementy": 0,
            "bledy": 0
        }
    
    async def initialize(self):
        """Inicjalizuje Playwright i przeglądarkę."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.config["playwright"]["headless"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()
    
    async def close(self):
        """Zamyka przeglądarkę i Playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def run_test(self, url: str) -> Dict[str, Any]:
        """Uruchamia test dla podanego URL."""
        try:
            await self.initialize()
            await self.page.goto(url)
            
            if "e-urtica.pl" in url:
                return await self._run_urtica_test()
            else:
                return await self._run_generic_test()
        
        except Exception as e:
            self.stats["bledy"] += 1
            return {
                "sukces": False,
                "wiadomosc": f"Błąd podczas wykonywania testu: {str(e)}",
                "statystyki": self.stats
            }
        
        finally:
            await self.close()
    
    async def _run_urtica_test(self) -> Dict[str, Any]:
        """Uruchamia test dla e-urtica.pl."""
        try:
            # Logowanie
            await self._logowanie()
            
            # Pobieranie faktur
            await self._pobieranie_faktur()
            
            return {
                "sukces": True,
                "wiadomosc": "Test zakończony pomyślnie",
                "statystyki": self.stats
            }
        
        except Exception as e:
            self.stats["bledy"] += 1
            return {
                "sukces": False,
                "wiadomosc": f"Błąd podczas testu e-urtica: {str(e)}",
                "statystyki": self.stats
            }
    
    async def _run_generic_test(self) -> Dict[str, Any]:
        """Uruchamia ogólny test dla dowolnej strony."""
        try:
            # Sprawdzenie czy strona się załadowała
            await self.page.wait_for_load_state("networkidle")
            
            # Sprawdzenie tytułu strony
            title = await self.page.title()
            
            return {
                "sukces": True,
                "wiadomosc": f"Strona załadowana pomyślnie. Tytuł: {title}",
                "statystyki": self.stats
            }
        
        except Exception as e:
            self.stats["bledy"] += 1
            return {
                "sukces": False,
                "wiadomosc": f"Błąd podczas testu strony: {str(e)}",
                "statystyki": self.stats
            }
    
    async def _logowanie(self):
        """Logowanie do e-urtica.pl."""
        await self.page.fill('input[name="email"]', self.config["e_urtica"]["login"])
        await self.page.fill('input[name="password"]', self.config["e_urtica"]["haslo"])
        await self.page.click('button[type="submit"]')
        await self.page.wait_for_load_state("networkidle")
    
    async def _pobieranie_faktur(self):
        """Pobieranie faktur z e-urtica.pl."""
        # Przejście do listy faktur
        await self.page.click('text="Lista faktur i zamówień"')
        await self.page.wait_for_load_state("networkidle")
        
        # Obliczenie zakresu dat
        today = datetime.now()
        weeks = self.config["e_urtica"]["tygodnie_do_przetworzenia"]
        
        for week in range(weeks):
            start_date = today - timedelta(days=today.weekday() + (week * 7))
            end_date = start_date + timedelta(days=6)
            
            # Tworzenie folderu na faktury
            folder_name = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
            folder_path = Path(self.config["e_urtica"]["folder_faktur"]) / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            
            # Pobieranie faktur z danego tygodnia
            await self._pobierz_faktury_z_tygodnia(start_date, end_date, folder_path)
            
            if self.progress_callback:
                progress = int((week + 1) / weeks * 100)
                self.progress_callback(progress)
    
    async def _pobierz_faktury_z_tygodnia(self, start_date: datetime, end_date: datetime, folder_path: Path):
        """Pobiera faktury z danego tygodnia."""
        # Implementacja pobierania faktur
        # To jest uproszczona wersja - pełna implementacja wymagałaby więcej kodu
        pass 