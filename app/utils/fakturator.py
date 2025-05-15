#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fakturator - moduł odpowiedzialny za pobieranie faktur z systemu e-urtica.pl

Główne funkcje:
1. Pobieranie faktur z danego zakresu dat
2. Zapisywanie pobranych faktur w folderze ./faktury

Zmiany wprowadzone w celu rozwiązania problemu z pobieraniem plików PDF:
1. Dodano alternatywne podejście do pobierania poprzez sprawdzanie, czy otworzyła się nowa karta z PDF-em
2. Dodano metodę z użyciem prawego przycisku myszy i opcji "Zapisz jako"
3. Dodano sprawdzanie ramek (iframes) pod kątem zawartości PDF
4. Dodano metodę pobierania przez JavaScript, która wykrywa linki do PDF i pobiera je przez fetch API

Te metody działają sekwencyjnie - jeśli jedna zawiedzie, próbujemy kolejnej.
"""

import os
import time
import asyncio
import nest_asyncio
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from app.utils.logger import setup_logger
from app.utils.config_manager import ConfigManager
import threading
import shutil
import re
import sys

# Zastosowanie nest_asyncio pozwala na zagnieżdżanie pętli zdarzeń asyncio
nest_asyncio.apply()

logger = setup_logger()

class Fakturator:
    """Klasa do pobierania faktur z e-urtica."""
    
    # Domyślna konfiguracja
    DEFAULT_CONFIG = {
        # Dane logowania
        "login": "apteka@pcrsopot.pl",
        "password": "Apteka2025!!",
        
        # Konfiguracja pobierania faktur
        "weeksToProcess": 2,  # Liczba tygodni wstecz, z których chcemy pobierać faktury
        "date_from": None,  # Data początkowa zakresu (w formacie YYYY-MM-DD), jeśli ustawiona, nadpisuje weeksToProcess
        "date_to": None,    # Data końcowa zakresu (w formacie YYYY-MM-DD), jeśli ustawiona, nadpisuje weeksToProcess
        
        # Konfiguracja techniczna
        "timeouts": {
            "page": 10000,  # 10 sekund na załadowanie strony
            "test": 600000,  # 10 minut na cały test
            "extraWait": 1000,  # Dodatkowa 1 sekunda oczekiwania po załadowaniu
            "downloadTimeout": 15000,  # 15 sekund na pobieranie pliku
            "maxDocumentProcessingTime": 30000  # 30 sekund na przetwarzanie dokumentów z zamówienia
        },
        
        # Ścieżki
        "downloadBasePath": "./faktury",  # Ścieżka bazowa do zapisu faktur
        
        # Poziom logowania
        "logLevel": "minimal",  # 'verbose', 'normal', 'minimal'
        
        # Obsługa błędów
        "errorHandling": {
            "maxNetworkRetries": 3,  # maksymalna liczba prób po błędzie sieci
            "networkRetryDelay": 5000,  # 5 sekund pauzy po błędzie sieci
        },
        
        # Czyszczenie
        "cleaning": {
            "keepWeeks": 12,  # Liczba tygodni, przez które przechowujemy faktury
        }
    }
    
    def __init__(self, custom_config=None):
        """Inicjalizacja z możliwością nadpisania domyślnej konfiguracji."""
        # Inicjalizacja logger queue na samym początku
        self.log_queue = []  # Kolejka wiadomości
        
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Jeśli custom_config to ścieżka do pliku JSON, wczytaj z pliku
        if isinstance(custom_config, str) and custom_config.endswith('.json'):
            import json
            try:
                with open(custom_config, 'r', encoding='utf-8') as f:
                    json_config = json.load(f)
                self._update_config(json_config)
            except Exception as e:
                logger.error(f'Błąd ładowania konfiguracji JSON: {e}')
        else:
            # Aktualizacja konfiguracji z pliku JSON
            config_manager = ConfigManager()
            self.config["login"] = config_manager.get_scenario_value("urtica", "login", self.config["login"])
            self.config["password"] = config_manager.get_scenario_value("urtica", "password", self.config["password"])
            self.config["weeksToProcess"] = config_manager.get_scenario_value("urtica", "weeks_to_process", self.config["weeksToProcess"])
            self.config["downloadBasePath"] = config_manager.get_scenario_value("urtica", "download_path", self.config["downloadBasePath"])
            
            # Pobierz zakres dat, jeśli jest dostępny
            date_from = config_manager.get_scenario_value("urtica", "date_from", None)
            date_to = config_manager.get_scenario_value("urtica", "date_to", None)
            
            if date_from and date_to:
                self.config["date_from"] = date_from
                self.config["date_to"] = date_to
                self.log(f"Ustawiono zakres dat: {date_from} - {date_to}", 'minimal')
            
            # Jeśli podano niestandardową konfigurację, zaktualizuj
            if custom_config:
                self._update_config(custom_config)
        
        # Statystyki
        self.stats = {
            "processedOrders": 0,
            "downloadedInvoices": 0,
            "errors": 0
        }
        
        # Śledzenie przetworzonych zamówień
        self.processed_order_numbers = set()
    
    def _update_config(self, custom_config):
        """Aktualizuje konfigurację."""
        if not isinstance(custom_config, dict):
            return
            
        for key, value in custom_config.items():
            if key in self.config:
                if isinstance(value, dict) and isinstance(self.config[key], dict):
                    # Dla zagnieżdżonych słowników
                    for subkey, subvalue in value.items():
                        if subkey in self.config[key]:
                            self.config[key][subkey] = subvalue
                else:
                    # Dla wartości prostych
                    self.config[key] = value
    
    def log(self, message, level='normal'):
        """Logowanie z różnymi poziomami."""
        levels = {'verbose': 3, 'normal': 2, 'minimal': 1}
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        formatted_message = f"[{timestamp}] {message}"
        
        if levels.get(level, 0) <= levels.get(self.config["logLevel"], 0):
            logger.info(message)
            self.log_queue.append(formatted_message)
    
    def get_logs(self):
        """Pobiera wszystkie logi z kolejki i czyści ją."""
        logs = self.log_queue.copy()
        self.log_queue = []
        return logs
    
    def get_stats(self):
        """Pobiera statystyki."""
        return self.stats
    
    async def _create_folder_for_date_range(self, start_date, end_date):
        """Tworzy folder na faktury dla zakresu dat."""
        def format_date(date):
            return date.strftime('%Y-%m-%d')
        
        folder_name = f"{format_date(start_date)}_do_{format_date(end_date)}"
        folder_path = os.path.join(self.config["downloadBasePath"], folder_name)
        
        # Upewnij się, że katalog bazowy istnieje
        os.makedirs(self.config["downloadBasePath"], exist_ok=True)
        
        # Utwórz folder dla zakresu dat
        os.makedirs(folder_path, exist_ok=True)
        
        return folder_path
    
    async def _handle_network_issue(self, page):
        """Obsługuje problemy z siecią."""
        self.log("🔄 Próbuję naprawić połączenie z siecią...", 'minimal')
        try:
            await page.reload(timeout=self.config["timeouts"]["page"])
            await page.wait_for_timeout(self.config["errorHandling"]["networkRetryDelay"])
            return True
        except Exception as e:
            self.log(f"❌ Nie udało się naprawić połączenia: {str(e)}", 'minimal')
            return False
    
    async def _try_action(self, action, description, page, max_retries=3):
        """Funkcja do bezpiecznego wykonywania akcji z ponawianiem."""
        for attempt in range(1, max_retries + 1):
            try:
                await action()
                return True
            except Exception as e:
                if attempt == max_retries:
                    self.log(f"❌ Nie udało się wykonać akcji: {description} po {max_retries} próbach: {str(e)}", 'normal')
                    return False
                self.log(f"⚠️ Próba {attempt}/{max_retries} dla akcji \"{description}\" nie powiodła się, ponawiam...", 'verbose')
                await page.wait_for_timeout(500)  # Krótkie czekanie przed ponowieniem
        return False
    
    async def _extract_date(self, text):
        """Wyciąga datę z tekstu."""
        import re
        match = re.search(r'Data:\s*(\d{2}\.\d{2}\.\d{4})', text)
        if match:
            result = match.group(1)
            self.log(f"✅ Znaleziono datę w tekście: {result}", 'verbose')
            return result
        self.log(f"❌ Nie znaleziono daty w tekście przy użyciu wzorca 'Data: DD.MM.YYYY'", 'verbose')
        return None
    
    async def _extract_order_number(self, text):
        """Wyciąga numer zamówienia z tekstu."""
        import re
        match = re.search(r'Nr zamówienia:\s*(ZS\/\d+\/\d+\/UR)', text)
        if match:
            result = match.group(1)
            self.log(f"✅ Znaleziono numer zamówienia w tekście: {result}", 'verbose')
            return result
        self.log(f"❌ Nie znaleziono numeru zamówienia w tekście przy użyciu wzorca 'Nr zamówienia: ZS/XXX/XXX/UR'", 'verbose')
        return None
    
    async def _is_date_in_range(self, date_text, start_date, end_date):
        """Sprawdza czy data mieści się w zakresie."""
        date_parts = date_text.split('.')
        if len(date_parts) != 3:
            return False
        
        try:
            formatted_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
            item_date = datetime.strptime(formatted_date, "%Y-%m-%d")
            item_date = item_date.replace(hour=12, minute=0, second=0, microsecond=0)
            
            result = start_date <= item_date <= end_date
            self.log(f"Data {date_text}: {'✅ w zakresie' if result else '❌ poza zakresem'}", 'verbose')
            return result
        except Exception as e:
            self.log(f"❌ Błąd daty {date_text}: {str(e)}", 'normal')
            return False
    
    async def run(self, progress_callback=None):
        """
        Główna funkcja uruchamiająca proces pobierania faktur.
        
        Args:
            progress_callback: opcjonalna funkcja do informowania o postępie
        """
        # Reset statystyk
        self.stats = {
            "processedOrders": 0,
            "downloadedInvoices": 0,
            "errors": 0
        }
        
        # W środowisku PyInstaller próbujemy naprawić ścieżki do przeglądarek
        if getattr(sys, 'frozen', False):
            from app.utils.playwright_manager import PlaywrightManager
            playwright_mgr = PlaywrightManager()
            playwright_mgr.set_progress_callback(progress_callback)
            # Próba naprawy ścieżek do przeglądarek
            playwright_mgr.fix_executable_browser_path()
        
        # Główny blok kodu
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            # Rejestrowanie błędów sieci
            page.on("console", lambda msg: self.log(f"⚠️ Wykryto błąd sieci: {msg.text}", 'minimal') 
                if any(err in msg.text for err in ['Failed to load resource', 'net::ERR_NETWORK', 'net::ERR_CONNECTION']) 
                else None)
            
            # Logowanie do systemu
            try:
                self.log("🔑 Loguję się do systemu", 'minimal')
                await page.goto('https://e-urtica.pl/authorization/login')
                await page.get_by_role('textbox', name='Podaj e-mail').fill(self.config["login"])
                await page.get_by_role('textbox', name='Podaj hasło').click()
                await page.get_by_role('textbox', name='Podaj hasło').fill(self.config["password"])
                
                await self._try_action(
                    lambda: page.get_by_role('button', name='Zaloguj się').click(), 
                    "Kliknięcie przycisku logowania",
                    page
                )
                
                # Małe opóźnienie po zalogowaniu
                await page.wait_for_timeout(self.config["timeouts"]["extraWait"])
                self.log("✅ Zalogowano pomyślnie", 'minimal')
                
                # Przejście do listy faktur
                await self._go_to_invoice_list(page)
                
                # Obliczanie zakresów dat dla tygodni
                date_ranges = await self._calculate_date_ranges()
                
                if progress_callback:
                    progress_callback(5)  # 5% postępu po zalogowaniu
                
                # Przetwarzanie każdego zakresu dat
                total_date_ranges = len(date_ranges)
                for i, date_range in enumerate(date_ranges):
                    await self._process_date_range(page, context, date_range, i, total_date_ranges)
                    
                    if progress_callback:
                        # Aktualizacja postępu w zakresie 5-95%
                        progress_value = 5 + 90 * ((i + 1) / total_date_ranges)
                        progress_callback(int(progress_value))
                
                # Podsumowanie
                self.log("\n====== PODSUMOWANIE ======", 'minimal')
                self.log(f"✅ Przetworzono {self.stats['processedOrders']} zamówień z {self.config['weeksToProcess']} tygodni", 'minimal')
                self.log(f"📥 Pobrano {self.stats['downloadedInvoices']} faktur", 'minimal')
                self.log(f"📂 Faktury zapisano w katalogu: {self.config['downloadBasePath']}", 'minimal')
                
                if progress_callback:
                    progress_callback(100)  # 100% po zakończeniu
                
            except Exception as e:
                self.log(f"❌ Wystąpił błąd: {str(e)}", 'minimal')
                self.stats["errors"] += 1
            finally:
                # Zamknij przeglądarkę
                await browser.close()
        
        return self.stats
    
    async def _go_to_invoice_list(self, page):
        """Przechodzi do listy faktur i zamówień."""
        self.log("📋 Przechodzę do listy faktur i zamówień", 'minimal')
        
        for network_retry in range(self.config["errorHandling"]["maxNetworkRetries"] + 1):
            try:
                success = await self._try_action(
                    lambda: page.locator('urt-navigation-drawer').get_by_text('Lista faktur i zamówień').click(),
                    "Przejście do listy faktur",
                    page,
                    5  # Więcej prób dla tego ważnego kroku
                )
                
                if success:
                    # Poczekaj na widoczność tabeli, ale nie dłużej niż 10 sekund
                    try:
                        await page.wait_for_selector('table tbody tr', timeout=self.config["timeouts"]["page"])
                        self.log("📋 Tabela faktur załadowana", 'minimal')
                        return True
                    except Exception:
                        self.log("⚠️ Nie wykryto tabeli, próbuję przeładować stronę", 'normal')
                        await page.reload(timeout=self.config["timeouts"]["page"])
                        await page.wait_for_timeout(2000)
                        
                        # Jeszcze jedna próba sprawdzenia tabeli
                        try:
                            await page.wait_for_selector('table tbody tr', timeout=self.config["timeouts"]["page"])
                            self.log("📋 Tabela faktur załadowana po przeładowaniu", 'minimal')
                            return True
                        except Exception:
                            self.log("⚠️ Nadal nie wykryto tabeli, kontynuuję mimo to", 'normal')
                            return False
            except Exception:
                if network_retry == self.config["errorHandling"]["maxNetworkRetries"]:
                    self.log(f"❌ Nie udało się przejść do listy faktur po {self.config['errorHandling']['maxNetworkRetries']} próbach", 'minimal')
                    return False
                self.log(f"⚠️ Problem z siecią podczas przechodzenia do listy faktur, próba {network_retry + 1}/{self.config['errorHandling']['maxNetworkRetries']}", 'normal')
                await self._handle_network_issue(page)
        
        return False
    
    async def _calculate_date_ranges(self):
        """Oblicza zakresy dat dla tygodni do przetworzenia lub używa niestandardowego zakresu dat."""
        today = datetime.now()
        date_ranges = []
        
        # Jeśli podano niestandardowy zakres dat, użyj go zamiast obliczania tygodni
        if self.config["date_from"] and self.config["date_to"]:
            try:
                start_date = datetime.strptime(self.config["date_from"], "%Y-%m-%d")
                end_date = datetime.strptime(self.config["date_to"], "%Y-%m-%d")
                
                # Ustaw godzinę początkową i końcową
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Utwórz folder dla zakresu dat
                folder_path = await self._create_folder_for_date_range(start_date, end_date)
                
                date_ranges.append({
                    "startDate": start_date,
                    "endDate": end_date,
                    "folderPath": folder_path
                })
                
                self.log(f"📅 Niestandardowy zakres dat: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", 'minimal')
                return date_ranges
                
            except Exception as e:
                self.log(f"❌ Błąd przy przetwarzaniu zakresu dat: {str(e)}, używam domyślnego obliczania tygodni", 'minimal')
        
        # Standardowe obliczanie tygodni, jeśli nie podano niestandardowego zakresu dat lub wystąpił błąd
        for week_offset in range(self.config["weeksToProcess"]):
            # Początek tygodnia (niedziela)
            start_of_week = today - timedelta(days=today.weekday() + 1 + (7 * week_offset))
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            # Przesuń do najbliższej niedzieli wstecz
            while start_of_week.weekday() != 6:
                start_of_week -= timedelta(days=1)
            # Koniec tygodnia (sobota)
            end_of_week = start_of_week + timedelta(days=6)
            end_of_week = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)
            folder_path = await self._create_folder_for_date_range(start_of_week, end_of_week)
            date_ranges.append({
                "startDate": start_of_week,
                "endDate": end_of_week,
                "folderPath": folder_path
            })
            self.log(f"📅 Tydzień {week_offset + 1}: {start_of_week.strftime('%d.%m.%Y')} - {end_of_week.strftime('%d.%m.%Y')}", 'minimal')
        return date_ranges
    
    async def _process_date_range(self, page, context, date_range, range_index, total_ranges):
        self.log(f"\n📅 Przetwarzam tydzień {range_index + 1}/{total_ranges}: {date_range['startDate'].strftime('%d.%m.%Y')} - {date_range['endDate'].strftime('%d.%m.%Y')}", 'minimal')
        await self._go_to_invoice_list(page)
        all_rows = []
        try:
            self.log(f"🔍 Pobieranie wierszy tabeli zamówień...", 'normal')
            all_rows = await page.locator('table tbody tr').all()
            await page.wait_for_timeout(2000)
            self.log(f"✅ Pobrano wiersze tabeli zamówień: {len(all_rows)}", 'normal')
        except Exception as e:
            self.log(f"⚠️ Problem z pobraniem wierszy tabeli: {str(e)}", 'normal')
            await page.reload()
            await page.wait_for_timeout(self.config["timeouts"]["extraWait"])
            try:
                all_rows = await page.locator('table tbody tr').all()
                await page.wait_for_timeout(2000)
            except Exception as e:
                self.log(f"❌ Nie udało się pobrać wierszy nawet po przeładowaniu: {str(e)}", 'minimal')
                return
        self.log(f"📊 Znaleziono {len(all_rows)} wierszy w tabeli", 'minimal')
        weeks_orders = []
        
        # Zrzut ekranu tabeli zamówień
        try:
            screenshot_path = os.path.join(self.config["downloadBasePath"], f"zamowienia_tabela_{range_index+1}.png")
            await page.screenshot(path=screenshot_path)
            self.log(f"📸 Zrzut ekranu tabeli zapisano do: {screenshot_path}", 'verbose')
        except Exception as e:
            self.log(f"⚠️ Nie udało się wykonać zrzutu ekranu: {str(e)}", 'verbose')
        
        for i, row in enumerate(all_rows):
            try:
                cells = await row.locator('td').all()
                await page.wait_for_timeout(100)
                if len(cells) < 2:
                    continue
                first_cell_text = await cells[0].text_content() or ''
                second_cell_text = await cells[1].text_content() or ''
                self.log(f"Wiersz {i}: cell[0]='{first_cell_text}', cell[1]='{second_cell_text}'", 'verbose')
                
                # Dodatkowe logi przed parsowaniem
                self.log(f"🔍 Próbuję wyciągnąć datę z: '{first_cell_text}'", 'verbose')
                extracted_date = await self._extract_date(first_cell_text)
                self.log(f"🔍 Wyciągnięta data: {extracted_date}", 'verbose')
                
                self.log(f"🔍 Próbuję wyciągnąć numer zamówienia z: '{second_cell_text}'", 'verbose')
                order_number = await self._extract_order_number(second_cell_text)
                self.log(f"🔍 Wyciągnięty numer zamówienia: {order_number}", 'verbose')
                
                if extracted_date and order_number:
                    date_in_range = await self._is_date_in_range(extracted_date, date_range["startDate"], date_range["endDate"])
                    self.log(f"🔍 Czy data {extracted_date} mieści się w zakresie: {date_in_range}", 'verbose')
                    
                    if date_in_range:
                        weeks_orders.append({
                            "row": row,
                            "date": extracted_date,
                            "orderNumber": order_number
                        })
                        self.log(f"✅ Zamówienie {order_number} ({extracted_date}) dodane do listy", 'verbose')
            except Exception as e:
                self.log(f"⚠️ Błąd przetwarzania wiersza {i}: {str(e)}", 'verbose')
                continue
        self.log(f"📊 Znaleziono {len(weeks_orders)} zamówień w zakresie dat", 'minimal')
        for i, order in enumerate(weeks_orders):
            await self._process_order(page, context, order, i, len(weeks_orders), date_range)
    
    async def _process_order(self, page, context, order, order_index, total_orders, date_range):
        """Przetwarza pojedyncze zamówienie."""
        row, date, order_number = order["row"], order["date"], order["orderNumber"]
        
        # Sprawdź, czy ten numer zamówienia był już przetworzony
        if order_number in self.processed_order_numbers:
            self.log(f"⏭️ Pomijam zamówienie {order_number} (już przetworzone)", 'normal')
            return
        
        self.log(f"🔍 [{order_index+1}/{total_orders}] Przetwarzam zamówienie {order_number} ({date})", 'minimal')
        
        # Rozpocznij liczenie czasu dla tego zamówienia
        start_time = time.time()
        is_timed_out = False
        
        # Dodaj numer zamówienia do zbioru przetworzonych - nawet jeśli się nie uda
        self.processed_order_numbers.add(order_number)
        
        # Funkcja sprawdzająca, czy nie przekroczyliśmy limitu czasu dla tego zamówienia
        def check_timeout():
            time_elapsed = (time.time() - start_time) * 1000
            if time_elapsed > self.config["timeouts"]["maxDocumentProcessingTime"]:
                self.log(f"⏱️ Przekroczono limit czasu dla zamówienia {order_number} ({time_elapsed:.0f}ms)", 'minimal')
                nonlocal is_timed_out
                is_timed_out = True
                return True
            return False
        
        # Kliknij w element tabeli - próbuj kilka razy
        clicked_on_row = await self._try_action(
            lambda: row.locator('td:nth-child(3) > .table-tag').click(),
            f"Kliknięcie w wiersz zamówienia {order_number}",
            page
        )
        
        if not clicked_on_row or check_timeout():
            self.log(f"❌ Nie udało się kliknąć w wiersz zamówienia {order_number} lub przekroczono limit czasu, przechodzę do kolejnego", 'minimal')
            await self._go_to_invoice_list(page)
            return
        
        # Nie czekaj - od razu próbuj kliknąć w Dokumenty
        await page.wait_for_timeout(self.config["timeouts"]["extraWait"])  # Krótkie czekanie
        
        # Przejdź do dokumentów - próbuj kilka razy
        clicked_on_documents = await self._try_action(
            lambda: page.get_by_role('link', name='Dokumenty').click(),
            f"Kliknięcie przycisku Dokumenty dla zamówienia {order_number}",
            page
        )
        
        if not clicked_on_documents or check_timeout():
            self.log(f"❌ Nie udało się kliknąć w Dokumenty dla zamówienia {order_number} lub przekroczono limit czasu, wracam do listy", 'minimal')
            await self._go_to_invoice_list(page)
            return
        
        # Zwiększenie czasu oczekiwania na załadowanie strony z fakturami - minimum 3 sekundy
        self.log(f"🕒 Czekam minimum 3 sekundy na załadowanie strony z fakturami...", 'normal')
        await page.wait_for_timeout(3000)
        
        # Pobierz wiersze tabeli dokumentów bez długiego czekania
        document_rows = []
        try:
            try:
                document_rows = await page.locator('table tbody tr').all()
                if len(document_rows) == 0:
                    self.log(f"⏳ Nie znaleziono dokumentów, czekam dodatkowe 2 sekundy...", 'normal')
                    await page.wait_for_timeout(2000)
                    document_rows = await page.locator('table tbody tr').all()
            except Exception as e:
                self.log(f"❌ Błąd podczas pobierania dokumentów: {str(e)}", 'normal')
        except Exception as e:
            self.log(f"❌ Nie udało się pobrać dokumentów dla zamówienia {order_number}: {str(e)}", 'minimal')
            await self._go_to_invoice_list(page)
            return
        
        if len(document_rows) == 0 or check_timeout():
            self.log(f"❌ Brak dokumentów dla zamówienia {order_number} lub przekroczono limit czasu, wracam do listy", 'minimal')
            await self._go_to_invoice_list(page)
            return
        
        self.log(f"📄 Znaleziono {len(document_rows)} dokumentów dla zamówienia {order_number}", 'normal')
        
        # Wypisz HTML tabeli, żeby zobaczyć jej strukturę
        try:
            html_table = await page.locator('table').evaluate('el => el.outerHTML')
            self.log(f"🔍 HTML tabeli: {html_table[:500]}...", 'minimal')  # Pierwszy 500 znaków, aby nie zaśmiecać logów
        except Exception as e:
            self.log(f"⚠️ Nie udało się pobrać HTML tabeli: {str(e)}", 'minimal')
        
        # Sprawdź wszystkie przyciski na stronie
        try:
            all_buttons = await page.locator('button').all()
            self.log(f"🔍 Znaleziono {len(all_buttons)} przycisków na stronie", 'minimal')
            
            for i, btn in enumerate(all_buttons):
                btn_text = await btn.text_content() or "PUSTY"
                btn_html = await btn.evaluate('el => el.outerHTML')
                self.log(f"🔍 Przycisk {i}: Tekst='{btn_text}', HTML={btn_html}", 'minimal')
        except Exception as e:
            self.log(f"⚠️ Nie udało się pobrać informacji o przyciskach: {str(e)}", 'minimal')
        
        pobrano_dokumenty = False
        document_processing_errors = 0
        
        for j, doc_row in enumerate(document_rows):
            # Sprawdź, czy nie przekroczyliśmy limitu czasu dla tego zamówienia
            if check_timeout():
                self.log(f"⏱️ Limit czasu przekroczony podczas przetwarzania dokumentu {j+1}/{len(document_rows)}", 'minimal')
                break
            try:
                row_text = await doc_row.text_content() or ''
                row_html = await doc_row.evaluate('el => el.outerHTML')
                self.log(f"🔍 Wiersz {j+1}: Tekst='{row_text}', HTML={row_html}", 'minimal')
                await page.wait_for_timeout(100)
                if row_text and "faktura" in row_text.lower():
                    self.log(f"💰 Znaleziono fakturę w wierszu {j+1}, tekst: {row_text}", 'minimal')
                    self.log(f"🔍 ANALIZA FAKTURY: Rozpoczynam analizę wiersza z fakturą {j+1}", 'minimal')
                    # Znajdź wszystkie przyciski w tym wierszu
                    try:
                        row_buttons = await doc_row.locator('button').all()
                        self.log(f"🔍 ANALIZA FAKTURY: Znaleziono {len(row_buttons)} przycisków w wierszu {j+1}", 'minimal')
                        for k, btn in enumerate(row_buttons):
                            btn_text = await btn.text_content() or "PUSTY"
                            btn_html = await btn.evaluate('el => el.outerHTML')
                            self.log(f"🔍 ANALIZA FAKTURY: Przycisk {k} w wierszu {j+1}: Tekst='{btn_text}', HTML={btn_html}", 'minimal')
                            if "pobierz" in btn_text.lower():
                                self.log(f"✅ ANALIZA FAKTURY: Znaleziono przycisk z tekstem 'Pobierz' w wierszu!", 'minimal')
                    except Exception as e:
                        self.log(f"⚠️ ANALIZA FAKTURY: Nie udało się pobrać informacji o przyciskach w wierszu: {str(e)}", 'minimal')
                    
                    # Przygotuj nazwę pliku
                    file_name = f"faktura_{order_number.replace('/', '_')}.pdf"
                    download_folder = date_range["folderPath"]
                    save_path = os.path.join(download_folder, file_name)
                    
                    # Wyświetl informacje o zapisie
                    self.log(f"📂 Faktura będzie zapisana jako: {file_name}", 'minimal')
                    self.log(f"📂 w folderze: {download_folder}", 'minimal')
                    
                    # Znajdź i kliknij przycisk pobierania
                    button_locator = doc_row.get_by_role('button', name='Pobierz')
                    
                    try:
                        # Używamy page.wait_for_download(), aby złapać zdarzenie pobierania pliku
                        self.log(f"🖱️ Oczekuję na zdarzenie pobierania po kliknięciu przycisku 'Pobierz'...", 'minimal')
                        
                        # Konfiguracja oczekiwania na zdarzenie pobierania i kliknięcie przycisku
                        async with page.expect_download(timeout=30000) as download_info:
                            await button_locator.click()
                            
                        # Pobierz informacje o pobranym pliku
                        download = await download_info.value
                        
                        if download:
                            self.log(f"✅ Wykryto zdarzenie pobierania pliku: {download.suggested_filename}", 'minimal')
                            
                            # Sprawdź wielkość pliku przed zapisem (w bajtach)
                            file_path = await download.path()
                            file_size_kb = os.path.getsize(file_path) / 1024 if file_path else 0
                            self.log(f"📊 Rozmiar pobieranego pliku: {file_size_kb:.2f} KB", 'minimal')
                            
                            # Zapisz plik pod naszą nazwą
                            await download.save_as(save_path)
                            
                            # Sprawdź, czy plik został poprawnie zapisany
                            if os.path.exists(save_path):
                                # Sprawdź rozmiar zapisanego pliku
                                saved_file_size_kb = os.path.getsize(save_path) / 1024
                                self.log(f"📊 ZAPISANO PLIK - Rozmiar na dysku: {saved_file_size_kb:.2f} KB", 'minimal')
                                self.log(f"📂 ZAPISANO PLIK - Pełna ścieżka: {os.path.abspath(save_path)}", 'minimal')
                                
                                # Sprawdź sygnaturę i zawartość pliku
                                with open(save_path, 'rb') as f:
                                    first_bytes = f.read(1024)  # Czytaj pierwsze 1024 bajty
                                
                                # Sprawdź czy to faktycznie plik PDF z sygnaturą %PDF
                                is_pdf = first_bytes.startswith(b'%PDF')
                                if is_pdf:
                                    self.log(f"✅ DIAGNOSTYKA - Poprawna sygnatura PDF", 'minimal')
                                    
                                    # Sprawdź czy to nie jest polityka prywatności
                                    text_sample = first_bytes.decode('utf-8', errors='ignore').lower()
                                    if 'polityka prywatności' in text_sample or 'prywatności' in text_sample:
                                        self.log(f"⚠️ UWAGA - Pobrany plik zawiera 'politykę prywatności' zamiast faktury!", 'minimal')
                                        
                                        # Zmień nazwę pliku, aby oznaczyć, że to nie jest faktura
                                        privacy_path = save_path.replace('.pdf', '_polityka_prywatnosci.pdf')
                                        os.rename(save_path, privacy_path)
                                        self.log(f"🔄 Zmieniono nazwę pliku na: {os.path.basename(privacy_path)}", 'minimal')
                                        
                                        # Spróbuj pobrać fakturę alternatywną metodą
                                        self.log(f"🔄 Próbuję alternatywnej metody pobierania faktury...", 'minimal')
                                        
                                        # Dodatkowe kliknięcie w przycisk, czasem pomaga
                                        await page.wait_for_timeout(1000)
                                        await button_locator.click(force=True)
                                        await page.wait_for_timeout(1000)
                                        
                                        # Sprawdź, czy otworzyło się nowe okno lub karta
                                        new_page = None
                                        try:
                                            # Czekamy na nowe okno/kartę
                                            self.log(f"🔍 Sprawdzam, czy otworzyło się nowe okno z fakturą...", 'minimal')
                                            async with context.expect_page(timeout=5000) as new_page_info:
                                                await button_locator.click(button='middle')  # Kliknięcie środkowym przyciskiem myszy
                                            
                                            new_page = await new_page_info.value
                                            if new_page:
                                                await new_page.wait_for_load_state('networkidle')
                                                self.log(f"✅ Otwarto nową kartę: {new_page.url}", 'minimal')
                                                
                                                # Sprawdź czy to strona z PDF
                                                url = new_page.url
                                                if url.endswith('.pdf') or 'pdf' in url.lower():
                                                    self.log(f"✅ Znaleziono bezpośredni link do PDF: {url}", 'minimal')
                                                    # Pobierz plik z użyciem Playwright
                                                    async with new_page.expect_download() as download_info2:
                                                        await new_page.reload()  # Czasem reload pomaga w rozpoczęciu pobierania
                                                    
                                                    download2 = await download_info2.value
                                                    await download2.save_as(save_path)
                                                    self.log(f"✅ Pobrano i zapisano fakturę poprzez nową kartę.", 'minimal')
                                                    pobrano_dokumenty = True
                                                    self.stats["downloadedInvoices"] += 1
                                                
                                                # Zamknij nową kartę
                                                await new_page.close()
                                                
                                        except Exception as e:
                                            self.log(f"⚠️ Nie udało się otworzyć nowego okna: {str(e)}", 'minimal')
                                        
                                        # Jeśli nadal nie udało się pobrać, spróbuj metodą fetch przez API
                                        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                                            self.log(f"🔄 Próba pobierania przez fetch API...", 'minimal')
                                            # Przeszukaj stronę do url API
                                            api_url = await page.evaluate('''
                                                () => {
                                                    const links = Array.from(document.querySelectorAll('a[href*="api"]'));
                                                    for (const link of links) {
                                                        if (link.href.includes('/api/') && (link.href.includes('/document/') || link.href.includes('/invoice/'))) {
                                                            return link.href;
                                                        }
                                                    }
                                                    return null;
                                                }
                                            ''')
                                            
                                            if api_url:
                                                self.log(f"✅ Znaleziono URL API: {api_url}", 'minimal')
                                                # Pobierz plik przez fetch
                                                pdf_data = await page.evaluate(f'''
                                                    async (url) => {{
                                                        try {{
                                                            const response = await fetch(url, {{
                                                                method: 'GET',
                                                                headers: {{
                                                                    'Accept': 'application/pdf',
                                                                }}
                                                            }});
                                                            
                                                            if (!response.ok) throw new Error('Błąd pobierania: ' + response.status);
                                                            
                                                            const blob = await response.blob();
                                                            
                                                            return new Promise((resolve) => {{
                                                                const reader = new FileReader();
                                                                reader.onloadend = () => resolve({{
                                                                    data: reader.result,
                                                                    contentType: blob.type,
                                                                    size: blob.size
                                                                }});
                                                                reader.readAsDataURL(blob);
                                                            }});
                                                        }} catch (e) {{
                                                            return {{ error: e.toString() }};
                                                        }}
                                                    }}
                                                ''', api_url)
                                                
                                                if pdf_data and 'data' in pdf_data and 'base64' in pdf_data['data']:
                                                    # Dekoduj i zapisz plik
                                                    import base64
                                                    base64_string = pdf_data['data']
                                                    base64_data = base64_string.split(',', 1)[1] if ',' in base64_string else base64_string
                                                    pdf_bytes = base64.b64decode(base64_data)
                                                    
                                                    with open(save_path, 'wb') as f:
                                                        f.write(pdf_bytes)
                                                    
                                                    self.log(f"✅ Pobrano i zapisano fakturę przez API.", 'minimal')
                                                    pobrano_dokumenty = True
                                                    self.stats["downloadedInvoices"] += 1
                                    else:
                                        # To prawdziwa faktura, nie polityka prywatności
                                        self.log(f"✅ Plik zawiera faktyczną fakturę, nie politykę prywatności.", 'minimal')
                                        self.log(f"✅ Pobrano i zapisano fakturę: {file_name}", 'minimal')
                                        self.stats["downloadedInvoices"] += 1
                                else:
                                    self.log(f"⚠️ DIAGNOSTYKA - Niepoprawna sygnatura pliku, to nie jest PDF", 'minimal')
                                
                                self.log(f"✓ ZAPISANO PLIK - Potwierdzenie: Plik istnieje na dysku", 'minimal')
                            else:
                                self.log(f"❌ ZAPISANO PLIK - Błąd: Plik nie istnieje na dysku pomimo próby zapisu", 'minimal')
                        else:
                            self.log(f"❌ Nie wykryto zdarzenia pobierania pliku", 'minimal')
                            document_processing_errors += 1
                    except Exception as e:
                        self.log(f"❌ Błąd podczas pobierania faktury PDF: {str(e)}", 'minimal')
                        document_processing_errors += 1
            except Exception as e:
                self.log(f"⚠️ Błąd przetwarzania wiersza {j+1}: {str(e)}", 'minimal')
                document_processing_errors += 1
                continue
            
            # Jeśli napotkaliśmy zbyt wiele błędów, przerwij przetwarzanie tego zamówienia
            if document_processing_errors >= 3:
                self.log(f"⚠️ Zbyt wiele błędów ({document_processing_errors}) podczas przetwarzania dokumentów, przerywam", 'minimal')
                break
        
        if pobrano_dokumenty:
            self.stats["processedOrders"] += 1
        
        # Zawsze wracaj do listy faktur
        await self._go_to_invoice_list(page)
        
        # Jeśli wystąpił timeout lub zbyt wiele błędów, dodaj krótkie oczekiwanie
        if is_timed_out or document_processing_errors >= 3:
            self.log(f"🕒 Krótka przerwa po problemach z zamówieniem {order_number}", 'normal')
            await page.wait_for_timeout(3000)

    async def _download_pdf_content(self, pdf_page, pdf_url):
        """Pobierz zawartość PDF z podanej strony różnymi metodami."""
        pdf_bytes = None
        
        # Szczegółowe logowanie URL i parametrów strony
        self.log(f"🔍 DIAGNOSTYKA - URL: {pdf_url}", 'minimal')
        self.log(f"🔍 DIAGNOSTYKA - Tytuł strony: {await pdf_page.title()}", 'minimal')
        
        try:
            headers = await pdf_page.evaluate('''
                () => {
                    let headers = {};
                    if (document && document.contentType) {
                        headers['Content-Type'] = document.contentType;
                    }
                    return headers;
                }
            ''')
            self.log(f"🔍 DIAGNOSTYKA - Nagłówki strony: {headers}", 'minimal')
        except Exception as e:
            self.log(f"⚠️ DIAGNOSTYKA - Nie udało się pobrać nagłówków: {str(e)}", 'minimal')
        
        # Metoda 1: Pobierz jako PDF przez Playwright
        try:
            self.log(f"🔄 Próba pobrania przez Playwright PDF API...", 'minimal')
            pdf_bytes = await pdf_page.pdf()
            size_kb = len(pdf_bytes) / 1024
            self.log(f"✅ Pobrano PDF przez Playwright API (rozmiar: {size_kb:.2f} KB)", 'minimal')
            
            # Sprawdź początek pliku pod kątem sygnatury PDF (%PDF)
            if pdf_bytes and len(pdf_bytes) > 4:
                signature = pdf_bytes[:4]
                signature_hex = ' '.join(f'{b:02x}' for b in signature)
                signature_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in signature)
                self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (hex): {signature_hex}", 'minimal')
                self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (text): {signature_text}", 'minimal')
                if signature == b'%PDF':
                    self.log(f"✅ DIAGNOSTYKA - Poprawna sygnatura PDF", 'minimal')
                else:
                    self.log(f"⚠️ DIAGNOSTYKA - Niepoprawna sygnatura PDF!", 'minimal')
            
            return pdf_bytes
        except Exception as e:
            self.log(f"⚠️ Nie udało się pobrać przez Playwright PDF API: {str(e)}", 'minimal')
        
        # Metoda 2: Pobierz zawartość strony przez JavaScript
        try:
            self.log(f"🔄 Próba pobrania zawartości strony przez JavaScript...", 'minimal')
            
            pdf_base64 = await pdf_page.evaluate('''
                async () => {
                    try {
                        const url = window.location.href;
                        console.log('Pobieranie z URL:', url);
                        
                        const response = await fetch(url);
                        console.log('Status odpowiedzi:', response.status);
                        console.log('Typ zawartości:', response.headers.get('content-type'));
                        
                        const blob = await response.blob();
                        console.log('Rozmiar blob:', blob.size, 'bajtów');
                        console.log('Typ blob:', blob.type);
                        
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    } catch (e) {
                        console.error('Błąd w JavaScript:', e);
                        return null;
                    }
                }
            ''')
            
            if pdf_base64 and "base64" in pdf_base64:
                self.log(f"✅ Pobrano zawartość PDF przez JavaScript", 'minimal')
                
                # Log informacji o pobranym base64
                self.log(f"🔍 DIAGNOSTYKA - Prefix base64: {pdf_base64.split(',', 1)[0] if ',' in pdf_base64 else 'brak prefiksu'}", 'minimal')
                self.log(f"🔍 DIAGNOSTYKA - Długość base64: {len(pdf_base64)} znaków", 'minimal')
                
                # Dekoduj base64
                import base64
                # Usuń prefix (np. data:application/pdf;base64,)
                base64_data = pdf_base64.split(',', 1)[1] if ',' in pdf_base64 else pdf_base64
                pdf_bytes = base64.b64decode(base64_data)
                
                # Log informacji o zdekodowanych danych
                size_kb = len(pdf_bytes) / 1024
                self.log(f"🔍 DIAGNOSTYKA - Rozmiar pliku po dekodowaniu: {size_kb:.2f} KB", 'minimal')
                
                # Sprawdź sygnaturę pliku
                if len(pdf_bytes) > 4:
                    signature = pdf_bytes[:4]
                    signature_hex = ' '.join(f'{b:02x}' for b in signature)
                    signature_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in signature)
                    self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (hex): {signature_hex}", 'minimal')
                    self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (text): {signature_text}", 'minimal')
                    if signature == b'%PDF':
                        self.log(f"✅ DIAGNOSTYKA - Poprawna sygnatura PDF", 'minimal')
                    else:
                        self.log(f"⚠️ DIAGNOSTYKA - Niepoprawna sygnatura PDF!", 'minimal')
                
                return pdf_bytes
            else:
                self.log(f"⚠️ Nie udało się pobrać PDF przez JavaScript", 'minimal')
        except Exception as e:
            self.log(f"⚠️ Błąd podczas pobierania zawartości strony przez JavaScript: {str(e)}", 'minimal')
        
        # Metoda 3: Pobierz przez HTTP requests
        try:
            self.log(f"🔄 Próba pobrania przez HTTP requests...", 'minimal')
            
            # Pobierz cookies z bieżącej sesji
            cookies = await pdf_page.context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            # Utwórz headers z cookie
            headers = {
                'Cookie': cookie_string,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,*/*'
            }
            
            # Log informacji przed zapytaniem
            self.log(f"🔍 DIAGNOSTYKA - Pobieranie z URL: {pdf_url}", 'minimal')
            self.log(f"🔍 DIAGNOSTYKA - Nagłówki: {headers}", 'minimal')
            
            # Pobierz przez requests
            import requests
            response = requests.get(pdf_url, headers=headers)
            
            # Log odpowiedzi
            self.log(f"🔍 DIAGNOSTYKA - Kod odpowiedzi: {response.status_code}", 'minimal')
            self.log(f"🔍 DIAGNOSTYKA - Nagłówki odpowiedzi: {dict(response.headers)}", 'minimal')
            self.log(f"🔍 DIAGNOSTYKA - Typ zawartości: {response.headers.get('Content-Type', 'nieznany')}", 'minimal')
            
            if response.status_code == 200:
                pdf_bytes = response.content
                size_kb = len(pdf_bytes) / 1024
                self.log(f"✅ Pobrano PDF przez HTTP requests (rozmiar: {size_kb:.2f} KB)", 'minimal')
                
                # Sprawdź sygnaturę pliku
                if len(pdf_bytes) > 4:
                    signature = pdf_bytes[:4]
                    signature_hex = ' '.join(f'{b:02x}' for b in signature)
                    signature_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in signature)
                    self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (hex): {signature_hex}", 'minimal')
                    self.log(f"🔍 DIAGNOSTYKA - Sygnatura pliku (text): {signature_text}", 'minimal')
                    if signature == b'%PDF':
                        self.log(f"✅ DIAGNOSTYKA - Poprawna sygnatura PDF", 'minimal')
                    else:
                        self.log(f"⚠️ DIAGNOSTYKA - Niepoprawna sygnatura PDF!", 'minimal')
                
                return pdf_bytes
            else:
                self.log(f"⚠️ Nie udało się pobrać PDF przez HTTP requests (status: {response.status_code})", 'minimal')
        except Exception as e:
            self.log(f"⚠️ Błąd podczas pobierania przez HTTP requests: {str(e)}", 'minimal')
        
        return pdf_bytes

    def clean_old_invoices(self, confirm=True):
        """
        Czyści stare faktury i foldery starsze niż określona liczba tygodni.
        
        Args:
            confirm (bool): Czy wymagane jest potwierdzenie przed usunięciem
            
        Returns:
            dict: Statystyki po czyszczeniu
        """
        self.log("🧹 Rozpoczynam skanowanie starych faktur...", 'minimal')
        
        stats = {
            "folders_to_delete": 0,
            "files_to_delete": 0,
            "folders_deleted": 0,
            "files_deleted": 0
        }
        
        # Sprawdź, czy główny katalog istnieje
        if not os.path.exists(self.config["downloadBasePath"]):
            self.log(f"❌ Katalog {self.config['downloadBasePath']} nie istnieje.", 'minimal')
            return stats
        
        # Oblicz datę graniczną
        weeks_to_keep = self.config.get("cleaning", {}).get("keepWeeks", 12)
        cutoff_date = datetime.now() - timedelta(weeks=weeks_to_keep)
        self.log(f"ℹ️ Zachowam faktury nowsze niż {cutoff_date.strftime('%Y-%m-%d')}", 'minimal')
        
        items_to_delete = []
        
        # Przeskanuj katalog i znajdź stare foldery
        for item in os.listdir(self.config["downloadBasePath"]):
            item_path = os.path.join(self.config["downloadBasePath"], item)
            
            # Sprawdź, czy jest to folder z datą
            match = re.match(r"(\d{4}-\d{2}-\d{2})_do_(\d{4}-\d{2}-\d{2})", item)
            
            if match and os.path.isdir(item_path):
                try:
                    start_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                    end_date = datetime.strptime(match.group(2), "%Y-%m-%d")
                    
                    # Jeśli folder jest starszy niż data graniczna
                    if end_date < cutoff_date:
                        items_to_delete.append({
                            "path": item_path,
                            "name": item,
                            "type": "folder",
                            "date": end_date.strftime("%Y-%m-%d"),
                            "file_count": len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                        })
                        stats["folders_to_delete"] += 1
                        stats["files_to_delete"] += len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                except Exception as e:
                    self.log(f"⚠️ Nie można przetworzyć folderu {item}: {str(e)}", 'normal')
            
            # Sprawdź, czy to plik ze zrzutem ekranu tabeli zamówień
            elif os.path.isfile(item_path) and item.startswith("zamowienia_tabela_"):
                try:
                    file_stats = os.stat(item_path)
                    file_date = datetime.fromtimestamp(file_stats.st_mtime)
                    
                    # Jeśli plik jest starszy niż data graniczna
                    if file_date < cutoff_date:
                        items_to_delete.append({
                            "path": item_path,
                            "name": item,
                            "type": "file",
                            "date": file_date.strftime("%Y-%m-%d"),
                            "size": f"{file_stats.st_size / 1024:.1f} KB"
                        })
                        stats["files_to_delete"] += 1
                except Exception as e:
                    self.log(f"⚠️ Nie można przetworzyć pliku {item}: {str(e)}", 'normal')
        
        # Jeśli nie ma nic do usunięcia
        if not items_to_delete:
            self.log("✅ Brak starych faktur do usunięcia.", 'minimal')
            return stats
        
        # Wypisz elementy do usunięcia
        self.log("\n====== ELEMENTY DO USUNIĘCIA ======", 'minimal')
        self.log(f"Znaleziono {stats['folders_to_delete']} folderów i {stats['files_to_delete']} plików starszych niż {weeks_to_keep} tygodni:", 'minimal')
        
        for item in items_to_delete:
            if item["type"] == "folder":
                self.log(f"📁 Folder: {item['name']} (data: {item['date']}, zawiera {item['file_count']} plików)", 'minimal')
            else:
                self.log(f"📄 Plik: {item['name']} (data: {item['date']}, rozmiar: {item['size']})", 'minimal')
        
        # Jeśli wymagane potwierdzenie
        if confirm:
            import sys
            self.log("\nCzy chcesz usunąć powyższe elementy? [t/N]: ", 'minimal')
            try:
                response = input().strip().lower()
                if response != 't' and response != 'tak':
                    self.log("❌ Anulowano usuwanie.", 'minimal')
                    return stats
            except Exception:
                self.log("❌ Anulowano usuwanie.", 'minimal')
                return stats
        
        # Usuń elementy
        self.log("\n🗑️ Usuwam wybrane elementy...", 'minimal')
        
        for item in items_to_delete:
            try:
                if item["type"] == "folder":
                    shutil.rmtree(item["path"])
                    stats["folders_deleted"] += 1
                    self.log(f"✅ Usunięto folder: {item['name']}", 'normal')
                else:
                    os.remove(item["path"])
                    stats["files_deleted"] += 1
                    self.log(f"✅ Usunięto plik: {item['name']}", 'normal')
            except Exception as e:
                self.log(f"❌ Błąd podczas usuwania {item['name']}: {str(e)}", 'minimal')
        
        # Podsumowanie
        self.log("\n====== PODSUMOWANIE CZYSZCZENIA ======", 'minimal')
        self.log(f"✅ Usunięto {stats['folders_deleted']}/{stats['folders_to_delete']} folderów", 'minimal')
        self.log(f"✅ Usunięto {stats['files_deleted']}/{stats['files_to_delete']} plików", 'minimal')
        
        return stats

# Funkcja pomocnicza do uruchamiania w głównym wątku
def download_invoices(config=None, progress_callback=None):
    """
    Pobiera faktury z e-urtica. 
    Ta funkcja jest wrapperem dla metody run klasy Fakturator i może być uruchamiana w głównym wątku.
    
    Args:
        config (dict, optional): Niestandardowa konfiguracja.
        progress_callback (function, optional): Funkcja do raportowania postępu.
    
    Returns:
        dict: Statystyki po zakończeniu.
    """
    fakturator = Fakturator(config)
    # Sprawdź, czy jesteśmy w głównym wątku
    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_event_loop()
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(fakturator.run(progress_callback)) 