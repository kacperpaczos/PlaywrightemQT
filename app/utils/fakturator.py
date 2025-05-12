#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        
        # Logger z różnymi poziomami logowania
        self.log_queue = []  # Kolejka wiadomości
    
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
                    await self._process_date_range(page, date_range, i, total_date_ranges)
                    
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
    
    async def _process_date_range(self, page, date_range, range_index, total_ranges):
        self.log(f"\n📅 Przetwarzam tydzień {range_index + 1}/{total_ranges}: {date_range['startDate'].strftime('%d.%m.%Y')} - {date_range['endDate'].strftime('%d.%m.%Y')}", 'minimal')
        await self._go_to_invoice_list(page)
        all_rows = []
        try:
            self.log(f"🔍 Pobieranie wierszy tabeli zamówień...", 'normal')
            all_rows = await page.locator('table tbody tr').all()
            await page.wait_for_timeout(2000)
            self.log(f"✅ Pobrano wiersze tabeli zamówień: {len(all_rows)}", 'normal')
        except Exception as e:
            self.log(f"⚠️ Problem z pobraniem wierszy tabeli: {str(e)}, wykonuję przeładowanie", 'normal')
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
            await self._process_order(page, order, i, len(weeks_orders), date_range)
    
    async def _process_order(self, page, order, order_index, total_orders, date_range):
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
        
        pobrano_dokumenty = False
        document_processing_errors = 0
        
        for j, doc_row in enumerate(document_rows):
            # Sprawdź, czy nie przekroczyliśmy limitu czasu dla tego zamówienia
            if check_timeout():
                self.log(f"⏱️ Limit czasu przekroczony podczas przetwarzania dokumentu {j+1}/{len(document_rows)}", 'minimal')
                break
            
            try:
                row_text = await doc_row.text_content() or ''
                await page.wait_for_timeout(100)
                
                if row_text and "faktura" in row_text.lower():
                    self.log(f"💰 Znaleziono fakturę w wierszu {j+1}", 'minimal')
                    
                    # Pobierz fakturę - próbuj kilka razy z limitem czasu
                    try:
                        with page.expect_download(timeout=self.config["timeouts"]["downloadTimeout"]) as download_info:
                            # Najpierw spróbuj kliknąć przycisk w wierszu
                            clicked = False
                            try:
                                await doc_row.get_by_role('button', name='Pobierz').click()
                                clicked = True
                            except Exception:
                                # Jeśli nie zadziała, spróbuj alternatywną metodę
                                try:
                                    await page.get_by_role('button', name='Pobierz').nth(j).click()
                                    clicked = True
                                except Exception:
                                    self.log(f"❌ Nie udało się kliknąć przycisku Pobierz w wierszu {j+1}", 'normal')
                            
                            if clicked:
                                try:
                                    # Pobranie pliku z limitem czasu
                                    download = await download_info.value
                                    
                                    # Przenieś pobrany plik do odpowiedniego katalogu
                                    download_path = await download.path()
                                    if download_path:
                                        file_name = download.suggested_filename
                                        new_path = os.path.join(date_range["folderPath"], file_name)
                                        
                                        try:
                                            await download.save_as(new_path)
                                            self.stats["downloadedInvoices"] += 1
                                            pobrano_dokumenty = True
                                            self.log(f"✅ Pobrano fakturę: {file_name}", 'minimal')
                                        except Exception as e:
                                            self.log(f"❌ Błąd zapisu faktury: {str(e)}", 'minimal')
                                            document_processing_errors += 1
                                except Exception as download_timeout_error:
                                    self.log(f"⏱️ Błąd podczas pobierania pliku: {str(download_timeout_error)}", 'minimal')
                                    document_processing_errors += 1
                    except Exception as e:
                        self.log(f"❌ Błąd pobierania faktury: {str(e)}", 'normal')
                        document_processing_errors += 1
            except Exception:
                # Ignoruj błędy pojedynczych wierszy
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