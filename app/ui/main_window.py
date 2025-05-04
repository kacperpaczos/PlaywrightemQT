#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton, 
                           QComboBox, QLabel, QTextEdit, QHBoxLayout, 
                           QGroupBox, QLineEdit, QMessageBox, QFileDialog,
                           QTabWidget, QProgressBar, QSpinBox, QStackedWidget,
                           QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap
import os
import sys
import asyncio
from typing import Dict, Any

from app.utils.logger import setup_logger
from app.utils.playwright_runner import PlaywrightRunner
from app.utils.config_manager import ConfigManager
from app.utils.email_sender import EmailSender
from app.utils.playwright_manager import PlaywrightManager, check_playwright_availability
from app.utils.fakturator import download_invoices
from app.utils.playwright_test import PlaywrightTest

logger = setup_logger()

class FakturatorThread(QThread):
    """Wątek do pobierania faktur z e-urtica."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)  # 0-100
    finished_signal = pyqtSignal(dict)  # Statystyki

    def __init__(self, custom_config=None):
        super().__init__()
        self.custom_config = custom_config

    def run(self):
        try:
            def progress_callback(value):
                self.progress_signal.emit(value)

            stats = download_invoices(self.custom_config, progress_callback)
            self.finished_signal.emit(stats)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Błąd podczas pobierania faktur: {str(e)}")

class TestThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    
    def __init__(self, config: Dict[str, Any], url: str):
        super().__init__()
        self.config = config
        self.url = url
    
    def run(self):
        try:
            # Tworzymy nową pętlę zdarzeń dla tego wątku
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Tworzymy instancję PlaywrightTest
            test = PlaywrightTest(self.config, self._progress_callback)
            
            # Uruchamiamy test
            result = loop.run_until_complete(test.run_test(self.url))
            
            # Emitujemy sygnał z wynikami
            self.finished.emit(result)
            
        except Exception as e:
            self.finished.emit({
                "sukces": False,
                "wiadomosc": f"Błąd podczas wykonywania testu: {str(e)}",
                "statystyki": {
                    "przetworzone_zamowienia": 0,
                    "pobrane_elementy": 0,
                    "bledy": 1
                }
            })
        
        finally:
            # Zamykamy pętlę zdarzeń
            loop.close()
    
    def _progress_callback(self, progress: int):
        """Callback dla aktualizacji postępu."""
        self.progress.emit(progress)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        
        # Inicjalizacja zmiennych
        self.playwright_manager = None
        self.test_results = ""
        self.screenshot_path = None
        self.email_sender = None
        self.fakturator_thread = None
        self.test_thread = None
        
        # Inicjalizacja UI
        self.init_ui()
        
        # Ładowanie zapisanych ustawień
        self.load_settings()
        
        # Sprawdzenie instalacji Playwright
        QApplication.processEvents()  # Odśwież UI przed rozpoczęciem sprawdzania
        self.check_playwright()
        
        logger.info("Uruchomiono okno fakturatora")

    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika."""
        self.setWindowTitle("Fakturator e-Urtica")
        self.setGeometry(100, 100, 1200, 800)
        
        # Ikona aplikacji
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Główny widget i layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Stos widgetów do przełączania między ekranami
        self.stacked_widget = QStackedWidget()
        
        # Ekran logowania
        login_widget = self.create_login_widget()
        self.stacked_widget.addWidget(login_widget)
        
        # Ekran główny aplikacji
        main_app_widget = self.create_main_app_widget()
        self.stacked_widget.addWidget(main_app_widget)
        
        # Dodanie stosu widgetów do głównego layoutu
        main_layout.addWidget(self.stacked_widget)
        
        # Pasek postępu operacji długotrwałych - główny pasek dla operacji systemowych
        self.progress_group = QGroupBox("Postęp operacji")
        progress_layout = QVBoxLayout()
        
        self.operation_label = QLabel("Gotowy")
        progress_layout.addWidget(self.operation_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # Domyślnie w trybie określonym
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_group.setLayout(progress_layout)
        self.progress_group.setVisible(False)  # Domyślnie ukryty
        main_layout.addWidget(self.progress_group)
        
        # Przyciski na dole
        button_layout = QHBoxLayout()
        
        manage_playwright_button = QPushButton("Zarządzaj Playwright")
        manage_playwright_button.clicked.connect(self.show_playwright_manager)
        
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.close)
        
        button_layout.addWidget(manage_playwright_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def show_progress(self, message):
        """Pokazuje pasek postępu z daną wiadomością w trybie nieskończonym."""
        self.operation_label.setText(message)
        self.progress_group.setVisible(True)
        
        # Ustawienie trybu nieskończonego (wartość 0 oznacza tryb nieskończony)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Proszę czekać...")
        
        self.setEnabled(False)  # Blokuje całe okno
        # Ustawia UI tylko dla widocznych elementów
        for widget in [self.progress_group, self.operation_label, self.progress_bar]:
            widget.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
    
    def hide_progress(self):
        """Ukrywa pasek postępu po pokazaniu informacji o zakończeniu."""
        # Przed ukryciem ustaw pasek na 100% aby zasygnalizować zakończenie
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Zakończono - 100%")
        QApplication.processEvents()  # Odśwież UI aby pokazać 100% przed ukryciem
        
        # Małe opóźnienie, aby użytkownik zauważył zmianę na 100%
        QTimer.singleShot(2000, self._complete_hide_progress)
    
    def _complete_hide_progress(self):
        """Faktycznie ukrywa pasek postępu po opóźnieniu."""
        self.progress_group.setVisible(False)
        self.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
    
    def update_progress_message(self, message: str):
        """Aktualizuje wiadomość w pasku postępu."""
        self.operation_label.setText(message)
        # Upewnij się, że pasek postępu jest widoczny i w trybie nieskończonym
        self.progress_group.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("W toku...")
        
        # Odśwież UI aby pokazać aktualizację
        for widget in [self.progress_group, self.operation_label, self.progress_bar]:
            widget.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
    
    def check_playwright(self):
        """Sprawdza, czy Playwright jest zainstalowany i skonfigurowany."""
        from app.utils.playwright_manager import PlaywrightManager
        
        # Pokazuje pasek postępu - upewnij się, że jest w trybie nieskończonym
        self.operation_label.setText("Sprawdzanie instalacji Playwright...")
        self.progress_group.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Tryb nieskończony
        self.progress_bar.setFormat("Proszę czekać...")
        
        # Wyłącz całe okno oprócz paska postępu
        self.setEnabled(False)
        self.progress_group.setEnabled(True)
        self.operation_label.setEnabled(True)
        self.progress_bar.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
        
        try:
            # Inicjalizacja managera i połączenie z paskiem postępu
            self.playwright_manager = PlaywrightManager()
            self.playwright_manager.set_progress_callback(self.update_progress_message)
            
            # Sprawdzenie statusu instalacji
            status = self.playwright_manager.get_installation_status()
            
            # Wypisz szczegółowe informacje w logach
            logger.info(f"Status Playwright - zainstalowany: {status['playwright_installed']}, "
                        f"wersja: {status['playwright_version']}, "
                        f"komenda dostępna: {status.get('command_available', False)}")
            
            browsers_status = []
            for browser, installed in status['browsers'].items():
                browsers_status.append(f"{browser}: {'✓' if installed else '✗'}")
            logger.info(f"Status przeglądarek: {', '.join(browsers_status)}")
            
            # Jeśli Playwright nie jest zainstalowany lub brak przeglądarek
            if not status["playwright_installed"] or not any(status["browsers"].values()):
                # Ustaw pasek postępu na 0% przed pokazaniem dialogu
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("%p%")
                QApplication.processEvents()  # Odśwież UI
                
                # Włącz okno na czas pokazania dialogu
                self.setEnabled(True)
                
                msg = ""
                if not status["playwright_installed"]:
                    msg += "Pakiet Playwright nie jest zainstalowany. "
                if not any(status["browsers"].values()):
                    msg += "Brak zainstalowanych przeglądarek. "
                
                msg += "Aplikacja wymaga Playwright i przeglądarki Chromium do działania. Czy chcesz zainstalować teraz?"
                
                reply = QMessageBox.question(
                    self,
                    "Wymagane komponenty",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Użytkownik potwierdził instalację - pasek znowu w trybie nieskończonym
                    self.install_playwright()
                else:
                    # Użytkownik odmówił instalacji
                    QMessageBox.warning(
                        self,
                        "Brak wymaganych komponentów",
                        "Aplikacja może nie działać poprawnie bez zainstalowanego Playwright. "
                        "Możesz zainstalować wymagane komponenty później klikając przycisk 'Zarządzaj Playwright'."
                    )
                    
                    # Pokaż pasek postępu na 0% po odmowie instalacji
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(0)
                    self.progress_bar.setFormat("%p%")
                    self.operation_label.setText("Brak wymaganych komponentów")
                    self.progress_group.setVisible(True)
                    QApplication.processEvents()  # Odśwież UI
                    
                    # Ukryj pasek po krótkim czasie
                    QTimer.singleShot(2000, self._complete_hide_progress)
            else:
                # Playwright jest już zainstalowany - pokaż pasek postępu na 100%
                browser_list = [b for b, installed in status['browsers'].items() if installed]
                log_msg = f"Playwright jest zainstalowany"
                if browser_list:
                    log_msg += f" z przeglądarkami: {', '.join(browser_list)}"
                logger.info(log_msg)
                
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Gotowe - 100%")
                self.operation_label.setText("Playwright jest zainstalowany")
                QApplication.processEvents()  # Odśwież UI
                
                # Ukryj pasek po krótkim czasie
                QTimer.singleShot(2000, self._complete_hide_progress)
        
        except Exception as e:
            # Wystąpił błąd podczas sprawdzania
            logger.error(f"Błąd podczas sprawdzania Playwright: {str(e)}")
            
            # Pokaż pasek błędu
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Błąd")
            self.operation_label.setText(f"Błąd: {str(e)}")
            QApplication.processEvents()  # Odśwież UI
            
            # Włącz okno na czas pokazania dialogu
            self.setEnabled(True)
            
            QMessageBox.critical(
                self,
                "Błąd",
                f"Wystąpił błąd podczas sprawdzania Playwright: {str(e)}"
            )
            
            # Ukryj pasek po krótkim czasie
            QTimer.singleShot(2000, self._complete_hide_progress)
    
    def install_playwright(self):
        """Instaluje Playwright z przeglądarką Chromium."""
        # Pokazuje pasek postępu w trybie nieskończonym
        self.operation_label.setText("Instalowanie Playwright i przeglądarki Chromium...")
        self.progress_group.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Tryb nieskończony
        self.progress_bar.setFormat("Instalacja w toku...")
        
        # Wyłącz całe okno oprócz paska postępu
        self.setEnabled(False)
        self.progress_group.setEnabled(True)
        self.operation_label.setEnabled(True)
        self.progress_bar.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
        
        try:
            # Inicjalizacja managera, jeśli jeszcze nie istnieje
            if not hasattr(self, 'playwright_manager') or self.playwright_manager is None:
                from app.utils.playwright_manager import PlaywrightManager
                self.playwright_manager = PlaywrightManager()
                self.playwright_manager.set_progress_callback(self.update_progress_message)
            
            # Instalacja Playwright i Chromium
            success, message = self.playwright_manager.install_playwright(["chromium"])
            
            # Sprawdź czy instalacja się powiodła
            if not success:
                logger.error(f"Instalacja Playwright nie powiodła się: {message}")
                
                # Spróbuj pozyskać dodatkowe informacje diagnostyczne
                self.operation_label.setText("Wykonywanie diagnostyki instalacji...")
                QApplication.processEvents()  # Odśwież UI
                
                try:
                    # Sprawdź, czy pakiet playwright jest dostępny
                    import importlib.util
                    playwright_spec = importlib.util.find_spec("playwright")
                    
                    if playwright_spec is None:
                        self.operation_label.setText("Pakiet playwright nie jest zainstalowany")
                        logger.error("Pakiet playwright nie jest zainstalowany")
                    else:
                        self.operation_label.setText("Pakiet playwright jest zainstalowany, sprawdzam ścieżkę...")
                        logger.info(f"Pakiet playwright znajduje się w: {playwright_spec.origin}")
                        
                        # Sprawdź, czy można zaimportować moduł
                        try:
                            import playwright
                            logger.info(f"Wersja playwright: {getattr(playwright, '__version__', 'nieznana')}")
                            
                            try:
                                # Sprawdź, czy można zaimportować sync_api
                                from playwright.sync_api import sync_playwright
                                logger.info("Import playwright.sync_api działa poprawnie")
                            except ImportError as e:
                                logger.error(f"Nie można zaimportować playwright.sync_api: {e}")
                        except ImportError as e:
                            logger.error(f"Nie można zaimportować playwright: {e}")
                except Exception as e:
                    logger.error(f"Błąd podczas diagnostyki pakietu: {e}")
            
            # Pokaż wynik instalacji na pasku postępu
            if success:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Zainstalowano - 100%")
                self.operation_label.setText("Playwright i przeglądarki zostały zainstalowane")
            else:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Błąd instalacji")
                self.operation_label.setText(f"Błąd: {message}")
            
            QApplication.processEvents()  # Odśwież UI
            
            # Włącz okno na czas pokazania dialogu
            self.setEnabled(True)
            
            # Informacja o wyniku instalacji
            if success:
                QMessageBox.information(
                    self,
                    "Instalacja zakończona",
                    "Playwright i przeglądarka Chromium zostały pomyślnie zainstalowane."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Błąd instalacji",
                    f"Nie udało się zainstalować Playwright: {message}\n\n"
                    "Sprawdź logi aplikacji, aby uzyskać więcej informacji."
                )
            
            # Ukryj pasek po krótkim czasie
            QTimer.singleShot(3000, self._complete_hide_progress)
        
        except Exception as e:
            # Wystąpił błąd podczas instalacji
            logger.error(f"Błąd podczas instalacji Playwright: {str(e)}")
            
            # Pokaż pasek błędu
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Błąd")
            self.operation_label.setText(f"Błąd: {str(e)}")
            QApplication.processEvents()  # Odśwież UI
            
            # Włącz okno na czas pokazania dialogu
            self.setEnabled(True)
            
            QMessageBox.critical(
                self,
                "Błąd",
                f"Wystąpił błąd podczas instalacji Playwright: {str(e)}"
            )
            
            # Ukryj pasek po krótkim czasie
            QTimer.singleShot(2000, self._complete_hide_progress)
    
    def show_playwright_manager(self):
        """Wyświetla okno zarządzania Playwright."""
        from app.ui.playwright_manager_window import create_playwright_manager_window
        
        playwright_window = create_playwright_manager_window(self)
        playwright_window.exec()

    def start_download(self):
        """Rozpoczęcie pobierania faktur."""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # Ustaw pasek postępu na tryb nieskończony podczas inicjalizacji
        self.download_status_label.setText("Inicjalizacja pobierania...")
        self.download_progress_bar.setRange(0, 0)
        self.download_progress_bar.setFormat("Proszę czekać...")
        QApplication.processEvents()  # Odśwież UI
        
        # Zapisz konfigurację przed uruchomieniem
        self.save_config()
        
        # Przygotowanie konfiguracji
        custom_config = {
            "login": self.login_input.text(),
            "password": self.password_input.text(),
            "weeks_to_process": self.weeks_spinbox.value(),
            "download_path": self.download_path_input.text(),
            "headless": self.headless_combo.currentText() == "Tak",
            "send_emails": self.email_enabled_combo.currentText() == "Tak",
            "email": {
                "recipient": self.email_recipient_input.text(),
                "smtp_server": self.smtp_server_input.text(),
                "smtp_port": self.smtp_port_spinbox.value(),
                "sender": self.email_sender_input.text(),
                "password": self.email_password_input.text(),
                "use_tls": self.email_tls_combo.currentText() == "Tak"
            }
        }
        
        self.fakturator_thread = FakturatorThread(custom_config)
        self.fakturator_thread.log_signal.connect(self.log_urtica)
        self.fakturator_thread.progress_signal.connect(self.update_download_progress)
        self.fakturator_thread.finished_signal.connect(self.download_finished)
        self.fakturator_thread.start()
        
        self.invoice_log.append("✅ Rozpoczęto pobieranie faktur")

    def stop_download(self):
        """Zatrzymanie pobierania faktur."""
        if hasattr(self, 'fakturator_thread') and self.fakturator_thread.isRunning():
            self.fakturator_thread.terminate()
            self.fakturator_thread.wait()
            self.invoice_log.append("⛔ Pobieranie zatrzymane przez użytkownika")
            
            # Po zatrzymaniu ustaw pasek na 0%
            self.download_progress_bar.setRange(0, 100)
            self.download_progress_bar.setValue(0)
            self.download_progress_bar.setFormat("%p%")
            self.download_status_label.setText("Pobieranie przerwane")
            
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def update_download_progress(self, value):
        """Aktualizacja paska postępu pobierania."""
        # Jeśli otrzymano wartość postępu, przejdź do trybu określonego
        if 0 <= value <= 100:
            self.download_progress_bar.setRange(0, 100)
            self.download_progress_bar.setValue(value)
            self.download_progress_bar.setFormat("%p%")
            
            if value > 0:
                self.download_status_label.setText(f"Pobieranie w toku... ({value}%)")
        else:
            # Dla nieoczekiwanych wartości, używamy trybu nieskończonego
            self.download_progress_bar.setRange(0, 0)
            self.download_progress_bar.setFormat("Proszę czekać...")
            self.download_status_label.setText("Pobieranie w toku...")
        
        QApplication.processEvents()  # Odśwież UI

    def download_finished(self, stats):
        """Obsługa zakończenia pobierania."""
        # Ustaw pasek na 100% aby zasygnalizować zakończenie
        self.download_progress_bar.setRange(0, 100)
        self.download_progress_bar.setValue(100)
        self.download_progress_bar.setFormat("Zakończono")
        self.download_status_label.setText("Pobieranie zakończone")
        
        # Odblokuj przyciski
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Dodaj informacje do logów
        success_msg = f"✅ Pobieranie zakończone pomyślnie. Statystyki: {stats}"
        self.invoice_log.append(success_msg)
        logger.info(success_msg)

    def run_test(self):
        """Uruchomienie testu Playwright."""
        url = self.url_combo.currentText()
        headless = self.headless_combo.currentText() == "Tak"
        selected_scenario_id = self.scenario_combo.currentData()
        
        # Zapisanie ustawień
        self.save_playwright_config()
        
        # Przygotowanie konfiguracji w odpowiednim formacie
        test_config = {
            "playwright": {
                "headless": headless,
                "timeout": self.timeout_spinbox.value(),
                "screenshot_path": self.screenshot_input.text()
            },
            "scenario": {
                "id": selected_scenario_id,
                "url": url
            },
            "general": {
                "log_level": self.config.get_value("general", "log_level", "INFO")
            }
        }
        
        # Dodanie ustawień scenariusza, jeśli istnieje
        scenario = self.config.get_scenario_by_id(selected_scenario_id)
        if scenario and "settings" in scenario:
            test_config["scenario"]["settings"] = scenario["settings"]
        
        self.test_thread = TestThread(test_config, url)
        self.test_thread.finished.connect(self.test_finished)
        self.test_thread.progress.connect(self.update_progress)
        self.test_thread.start()

    def test_finished(self, result):
        """Obsługa zakończenia testu."""
        self.update_playwright_log(result["wiadomosc"])
        
        # Jeśli test był udany i skonfigurowano wysyłanie raportów email
        selected_scenario_id = self.scenario_combo.currentData()
        send_report = self.config.get_scenario_value(selected_scenario_id, "send_emails", False)
        
        if send_report:
            recipient = self.config.get_scenario_value(selected_scenario_id, "email_recipient", "")
            if recipient:
                # Inicjalizacja EmailSender z aktualnym scenariuszem
                self.email_sender = EmailSender(selected_scenario_id)
                # Wysłanie raportu
                self.email_sender.send_test_report(recipient, result["wiadomosc"], self.screenshot_path)
                self.update_playwright_log(f"✉️ Raport wysłany na adres: {recipient}")
            else:
                self.update_playwright_log("⚠️ Nie wysłano raportu - brak adresu email odbiorcy")
        else:
            self.update_playwright_log("ℹ️ Wysyłanie raportów email jest wyłączone")

    def update_playwright_log(self, message):
        """Aktualizacja logów Playwright."""
        self.playwright_log.append(message)

    def update_screenshot_path(self, path):
        """Aktualizacja ścieżki do zrzutu ekranu."""
        self.screenshot_path = path
        self.update_playwright_log(f"Zrzut ekranu zapisany: {path}")

    def browse_screenshot_path(self):
        """Otwiera okno dialogowe do wyboru ścieżki zrzutów ekranu."""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Wybierz katalog na zrzuty ekranu", 
            self.screenshot_input.text(), 
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.screenshot_input.setText(directory)
    
    def save_playwright_config(self):
        """Zapisuje konfigurację Playwright."""
        try:
            # Zapisywanie ustawień
            self.config.set_value("playwright", "headless", str(self.headless_combo.currentText() == "Tak"))
            self.config.set_value("general", "default_timeout", str(self.timeout_spinbox.value()))
            self.config.set_value("general", "screenshot_path", self.screenshot_input.text())
            
            # Zapisywanie do pliku
            self.config.save_config()
            
            # Informacja o sukcesie
            self.update_playwright_log("✅ Konfiguracja została zapisana")
            
        except Exception as e:
            self.update_playwright_log(f"❌ Błąd podczas zapisywania konfiguracji: {str(e)}")

    def save_urtica_config(self):
        """Zapisuje konfigurację e-urtica."""
        try:
            # Zapisywanie podstawowych ustawień
            self.config.set_scenario_value("urtica", "login", self.login_input.text())
            self.config.set_scenario_value("urtica", "password", self.password_input.text())
            self.config.set_scenario_value("urtica", "weeks_to_process", self.weeks_spinbox.value())
            self.config.set_scenario_value("urtica", "download_path", self.download_path_input.text())
            
            # Zapisywanie ustawień email
            self.config.set_scenario_value("urtica", "email_recipient", self.email_recipient_input.text())
            self.config.set_scenario_value("urtica", "email_smtp_server", self.smtp_server_input.text())
            self.config.set_scenario_value("urtica", "email_smtp_port", self.smtp_port_spinbox.value())
            self.config.set_scenario_value("urtica", "email_sender", self.email_sender_input.text())
            self.config.set_scenario_value("urtica", "email_password", self.email_password_input.text())
            self.config.set_scenario_value("urtica", "email_use_tls", self.email_tls_combo.currentText() == "Tak")
            self.config.set_scenario_value("urtica", "send_emails", self.email_enabled_combo.currentText() == "Tak")
            
            # Zapisywanie do pliku
            self.config.save_config()
            
            # Informacja o sukcesie
            self.update_urtica_log("✅ Konfiguracja została zapisana")
            
        except Exception as e:
            self.update_urtica_log(f"❌ Błąd podczas zapisywania konfiguracji: {str(e)}")

    def update_urtica_log(self, message):
        """Dodanie wiadomości do logów e-urtica."""
        self.urtica_log.append(message)

    def browse_download_path(self):
        """Otwiera okno dialogowe do wyboru ścieżki zapisu faktur."""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Wybierz katalog na zapis faktur", 
            self.download_path_input.text(), 
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.download_path_input.setText(directory)

    def toggle_email_settings(self):
        """Włącza/wyłącza widoczność ustawień email w zależności od wybranej opcji."""
        is_enabled = self.email_enabled_combo.currentText() == "Tak"
        self.email_recipient_input.setEnabled(is_enabled)
        self.email_advanced_combo.setEnabled(is_enabled)
        
        # Aktualizuj widoczność zaawansowanych ustawień
        if is_enabled and self.email_advanced_combo.currentText() == "Tak":
            self.advanced_email_widget.setVisible(True)
        else:
            self.advanced_email_widget.setVisible(False)

    def toggle_advanced_email(self):
        """Włącza/wyłącza widoczność zaawansowanych ustawień email."""
        is_visible = self.email_advanced_combo.currentText() == "Tak"
        self.advanced_email_widget.setVisible(is_visible)

    def create_login_widget(self):
        """Tworzy widget ekranu logowania."""
        login_widget = QWidget()
        login_layout = QVBoxLayout()
        
        # Nagłówek
        header_label = QLabel("Fakturator e-Urtica")
        header_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_layout.addWidget(header_label)
        
        # Logo/Obraz aplikacji
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "logo.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            logo_pixmap = logo_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            login_layout.addWidget(logo_label)
        
        # Informacja o aplikacji
        info_label = QLabel("Aplikacja do automatycznego pobierania faktur z systemu e-Urtica")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_layout.addWidget(info_label)
        
        # Sekcja logowania
        login_group = QGroupBox("Logowanie")
        login_form_layout = QVBoxLayout()
        
        # Login
        login_input_layout = QHBoxLayout()
        login_label = QLabel("Login:")
        self.login_input = QLineEdit()
        login_input_layout.addWidget(login_label)
        login_input_layout.addWidget(self.login_input)
        login_form_layout.addLayout(login_input_layout)
        
        # Hasło
        password_input_layout = QHBoxLayout()
        password_label = QLabel("Hasło:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input_layout.addWidget(password_label)
        password_input_layout.addWidget(self.password_input)
        login_form_layout.addLayout(password_input_layout)
        
        # Przycisk logowania
        login_button = QPushButton("Zaloguj")
        login_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        login_button.clicked.connect(self.login)
        login_form_layout.addWidget(login_button)
        
        login_group.setLayout(login_form_layout)
        login_layout.addWidget(login_group)
        
        # Informacja o wersji
        version_label = QLabel("Wersja 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_layout.addWidget(version_label)
        
        login_layout.addStretch()
        login_widget.setLayout(login_layout)
        
        return login_widget
    
    def create_main_app_widget(self):
        """Tworzy główny widget aplikacji po zalogowaniu."""
        main_app_widget = QWidget()
        main_app_layout = QVBoxLayout()
        
        # Nagłówek z informacją o zalogowanym użytkowniku
        user_info_layout = QHBoxLayout()
        self.user_info_label = QLabel("Zalogowany: Użytkownik")
        logout_button = QPushButton("Wyloguj")
        logout_button.clicked.connect(self.logout)
        user_info_layout.addWidget(self.user_info_label)
        user_info_layout.addStretch()
        user_info_layout.addWidget(logout_button)
        main_app_layout.addLayout(user_info_layout)
        
        # Zakładki główne
        tabs = QTabWidget()
        
        # Zakładka faktur
        invoices_tab = self.create_invoices_tab()
        tabs.addTab(invoices_tab, "Faktury")
        
        # Zakładka ustawień
        settings_tab = self.create_settings_tab()
        tabs.addTab(settings_tab, "Ustawienia")
        
        # Zakładka logów
        logs_tab = self.create_logs_tab()
        tabs.addTab(logs_tab, "Logi")
        
        main_app_layout.addWidget(tabs)
        main_app_widget.setLayout(main_app_layout)
        
        return main_app_widget
    
    def create_invoices_tab(self):
        """Tworzy zakładkę do pobierania faktur."""
        invoices_tab = QWidget()
        invoices_layout = QVBoxLayout()
        
        # Konfiguracja faktur
        config_group = QGroupBox("Konfiguracja pobierania faktur")
        config_layout = QGridLayout()
        
        # Liczba tygodni
        config_layout.addWidget(QLabel("Liczba tygodni do pobrania:"), 0, 0)
        self.weeks_spinbox = QSpinBox()
        self.weeks_spinbox.setMinimum(1)
        self.weeks_spinbox.setMaximum(8)
        self.weeks_spinbox.setValue(4)
        config_layout.addWidget(self.weeks_spinbox, 0, 1)
        
        # Ścieżka zapisu
        config_layout.addWidget(QLabel("Ścieżka zapisu faktur:"), 1, 0)
        path_layout = QHBoxLayout()
        self.download_path_input = QLineEdit("./faktury")
        browse_button = QPushButton("Przeglądaj...")
        browse_button.clicked.connect(self.browse_download_path)
        path_layout.addWidget(self.download_path_input)
        path_layout.addWidget(browse_button)
        config_layout.addLayout(path_layout, 1, 1)
        
        config_group.setLayout(config_layout)
        invoices_layout.addWidget(config_group)
        
        # Konfiguracja email
        email_group = QGroupBox("Wysyłanie raportów email")
        email_layout = QGridLayout()
        
        # Włącz/wyłącz wysyłanie emaili
        email_layout.addWidget(QLabel("Wysyłaj emaile:"), 0, 0)
        self.email_enabled_combo = QComboBox()
        self.email_enabled_combo.addItems(["Nie", "Tak"])
        self.email_enabled_combo.currentTextChanged.connect(self.toggle_email_settings)
        email_layout.addWidget(self.email_enabled_combo, 0, 1)
        
        # Adres email odbiorcy
        email_layout.addWidget(QLabel("Adres email odbiorcy:"), 1, 0)
        self.email_recipient_input = QLineEdit()
        email_layout.addWidget(self.email_recipient_input, 1, 1)
        
        # Ustawienia zaawansowane
        email_layout.addWidget(QLabel("Zaawansowane ustawienia:"), 2, 0)
        self.email_advanced_combo = QComboBox()
        self.email_advanced_combo.addItems(["Nie", "Tak"])
        self.email_advanced_combo.currentTextChanged.connect(self.toggle_advanced_email)
        email_layout.addWidget(self.email_advanced_combo, 2, 1)
        
        # Zaawansowane opcje (domyślnie ukryte)
        self.advanced_email_widget = QWidget()
        advanced_layout = QGridLayout()
        
        advanced_layout.addWidget(QLabel("Serwer SMTP:"), 0, 0)
        self.smtp_server_input = QLineEdit("smtp.example.com")
        advanced_layout.addWidget(self.smtp_server_input, 0, 1)
        
        advanced_layout.addWidget(QLabel("Port SMTP:"), 1, 0)
        self.smtp_port_spinbox = QSpinBox()
        self.smtp_port_spinbox.setMinimum(1)
        self.smtp_port_spinbox.setMaximum(65535)
        self.smtp_port_spinbox.setValue(587)
        advanced_layout.addWidget(self.smtp_port_spinbox, 1, 1)
        
        advanced_layout.addWidget(QLabel("Email nadawcy:"), 2, 0)
        self.email_sender_input = QLineEdit()
        advanced_layout.addWidget(self.email_sender_input, 2, 1)
        
        advanced_layout.addWidget(QLabel("Hasło email:"), 3, 0)
        self.email_password_input = QLineEdit()
        self.email_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        advanced_layout.addWidget(self.email_password_input, 3, 1)
        
        advanced_layout.addWidget(QLabel("Użyj TLS:"), 4, 0)
        self.email_tls_combo = QComboBox()
        self.email_tls_combo.addItems(["Nie", "Tak"])
        self.email_tls_combo.setCurrentIndex(1)
        advanced_layout.addWidget(self.email_tls_combo, 4, 1)
        
        self.advanced_email_widget.setLayout(advanced_layout)
        self.advanced_email_widget.setVisible(False)
        
        email_layout.addWidget(self.advanced_email_widget, 3, 0, 1, 2)
        email_group.setLayout(email_layout)
        invoices_layout.addWidget(email_group)
        
        # Przyciski akcji
        buttons_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Rozpocznij pobieranie")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.clicked.connect(self.start_download)
        
        self.stop_button = QPushButton("Zatrzymaj")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_download)
        
        save_config_button = QPushButton("Zapisz konfigurację")
        save_config_button.clicked.connect(self.save_config)
        
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_config_button)
        
        invoices_layout.addLayout(buttons_layout)
        
        # Pasek postępu - ten jest używany do pobierania faktur
        download_progress_group = QGroupBox("Postęp pobierania")
        download_progress_layout = QVBoxLayout()
        
        self.download_status_label = QLabel("Gotowy do pobierania")
        download_progress_layout.addWidget(self.download_status_label)
        
        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setRange(0, 100)  # Domyślnie w trybie określonym
        self.download_progress_bar.setValue(0)
        self.download_progress_bar.setTextVisible(True)
        self.download_progress_bar.setFormat("%p%")
        download_progress_layout.addWidget(self.download_progress_bar)
        
        download_progress_group.setLayout(download_progress_layout)
        invoices_layout.addWidget(download_progress_group)
        
        # Logi pobierania
        log_group = QGroupBox("Logi pobierania")
        log_layout = QVBoxLayout()
        
        self.invoice_log = QTextEdit()
        self.invoice_log.setReadOnly(True)
        log_layout.addWidget(self.invoice_log)
        
        log_group.setLayout(log_layout)
        invoices_layout.addWidget(log_group)
        
        invoices_tab.setLayout(invoices_layout)
        return invoices_tab
    
    def create_settings_tab(self):
        """Tworzy zakładkę ustawień aplikacji."""
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        
        # Ustawienia Playwright
        playwright_group = QGroupBox("Ustawienia Playwright")
        playwright_layout = QGridLayout()
        
        playwright_layout.addWidget(QLabel("Tryb headless:"), 0, 0)
        self.headless_combo = QComboBox()
        self.headless_combo.addItems(["Nie", "Tak"])
        playwright_layout.addWidget(self.headless_combo, 0, 1)
        
        playwright_layout.addWidget(QLabel("Timeout (ms):"), 1, 0)
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setMinimum(1000)
        self.timeout_spinbox.setMaximum(60000)
        self.timeout_spinbox.setValue(30000)
        self.timeout_spinbox.setSingleStep(1000)
        playwright_layout.addWidget(self.timeout_spinbox, 1, 1)
        
        playwright_group.setLayout(playwright_layout)
        settings_layout.addWidget(playwright_group)
        
        # Ustawienia aplikacji
        app_settings_group = QGroupBox("Ustawienia aplikacji")
        app_settings_layout = QGridLayout()
        
        app_settings_layout.addWidget(QLabel("Automatyczne logowanie:"), 0, 0)
        self.auto_login_combo = QComboBox()
        self.auto_login_combo.addItems(["Nie", "Tak"])
        app_settings_layout.addWidget(self.auto_login_combo, 0, 1)
        
        app_settings_layout.addWidget(QLabel("Zapisuj logi do pliku:"), 1, 0)
        self.save_logs_combo = QComboBox()
        self.save_logs_combo.addItems(["Nie", "Tak"])
        app_settings_layout.addWidget(self.save_logs_combo, 1, 1)
        
        app_settings_layout.addWidget(QLabel("Poziom logowania:"), 2, 0)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["INFO", "DEBUG", "WARNING", "ERROR"])
        app_settings_layout.addWidget(self.log_level_combo, 2, 1)
        
        app_settings_group.setLayout(app_settings_layout)
        settings_layout.addWidget(app_settings_group)
        
        # Przyciski
        buttons_layout = QHBoxLayout()
        
        save_settings_button = QPushButton("Zapisz ustawienia")
        save_settings_button.clicked.connect(self.save_settings)
        
        reset_settings_button = QPushButton("Resetuj ustawienia")
        reset_settings_button.clicked.connect(self.reset_settings)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_settings_button)
        buttons_layout.addWidget(reset_settings_button)
        
        settings_layout.addLayout(buttons_layout)
        settings_layout.addStretch()
        
        settings_tab.setLayout(settings_layout)
        return settings_tab
    
    def create_logs_tab(self):
        """Tworzy zakładkę z logami aplikacji."""
        logs_tab = QWidget()
        logs_layout = QVBoxLayout()
        
        # Filtrowanie logów
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtruj logi:"))
        
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["Wszystkie", "Tylko błędy", "Tylko ostrzeżenia", "Tylko informacje"])
        self.log_filter_combo.currentTextChanged.connect(self.filter_logs)
        filter_layout.addWidget(self.log_filter_combo)
        
        filter_layout.addStretch()
        
        clear_logs_button = QPushButton("Wyczyść logi")
        clear_logs_button.clicked.connect(self.clear_logs)
        filter_layout.addWidget(clear_logs_button)
        
        logs_layout.addLayout(filter_layout)
        
        # Okno logów
        self.app_log = QTextEdit()
        self.app_log.setReadOnly(True)
        logs_layout.addWidget(self.app_log)
        
        logs_tab.setLayout(logs_layout)
        return logs_tab

    def login(self):
        """Obsługuje logowanie użytkownika."""
        login = self.login_input.text()
        password = self.password_input.text()
        
        if not login or not password:
            QMessageBox.warning(self, "Błąd logowania", "Wprowadź login i hasło")
            return
        
        # Tutaj będzie logika logowania do e-urtica
        # Na razie po prostu przechodzimy do głównego ekranu
        self.user_info_label.setText(f"Zalogowany: {login}")
        self.stacked_widget.setCurrentIndex(1)  # Przejście do głównego ekranu
    
    def logout(self):
        """Obsługuje wylogowanie użytkownika."""
        # Czyścimy dane logowania
        self.login_input.clear()
        self.password_input.clear()
        
        # Przechodzimy z powrotem do ekranu logowania
        self.stacked_widget.setCurrentIndex(0)
    
    def save_config(self):
        """Zapisuje konfigurację pobierania faktur."""
        try:
            # Zapisywanie podstawowych ustawień
            self.config.set_scenario_value("urtica", "weeks_to_process", self.weeks_spinbox.value())
            self.config.set_scenario_value("urtica", "download_path", self.download_path_input.text())
            
            # Zapisywanie ustawień email
            self.config.set_scenario_value("urtica", "send_emails", self.email_enabled_combo.currentText() == "Tak")
            self.config.set_scenario_value("urtica", "email_recipient", self.email_recipient_input.text())
            
            # Zaawansowane ustawienia email
            if self.email_advanced_combo.currentText() == "Tak":
                self.config.set_scenario_value("urtica", "email_smtp_server", self.smtp_server_input.text())
                self.config.set_scenario_value("urtica", "email_smtp_port", self.smtp_port_spinbox.value())
                self.config.set_scenario_value("urtica", "email_sender", self.email_sender_input.text())
                self.config.set_scenario_value("urtica", "email_password", self.email_password_input.text())
                self.config.set_scenario_value("urtica", "email_use_tls", self.email_tls_combo.currentText() == "Tak")
            
            # Zapisywanie do pliku
            self.config.save_config()
            
            # Informacja o sukcesie
            self.invoice_log.append("✅ Konfiguracja została zapisana")
            
        except Exception as e:
            self.invoice_log.append(f"❌ Błąd podczas zapisywania konfiguracji: {str(e)}")
    
    def save_settings(self):
        """Zapisuje ogólne ustawienia aplikacji."""
        try:
            # Zapisywanie ustawień Playwright
            self.config.set_value("playwright", "headless", self.headless_combo.currentText() == "Tak")
            self.config.set_value("general", "default_timeout", self.timeout_spinbox.value())
            
            # Zapisywanie ustawień aplikacji
            self.config.set_value("general", "auto_login", self.auto_login_combo.currentText() == "Tak")
            self.config.set_value("general", "save_logs", self.save_logs_combo.currentText() == "Tak")
            self.config.set_value("general", "log_level", self.log_level_combo.currentText())
            
            # Zapisywanie do pliku
            self.config.save_config()
            
            # Informacja o sukcesie
            self.app_log.append("✅ Ustawienia zostały zapisane")
            
        except Exception as e:
            self.app_log.append(f"❌ Błąd podczas zapisywania ustawień: {str(e)}")
    
    def reset_settings(self):
        """Resetuje ustawienia do wartości domyślnych."""
        try:
            # Wartości domyślne Playwright
            self.headless_combo.setCurrentText("Nie")
            self.timeout_spinbox.setValue(30000)
            
            # Wartości domyślne aplikacji
            self.auto_login_combo.setCurrentText("Nie")
            self.save_logs_combo.setCurrentText("Tak")
            self.log_level_combo.setCurrentText("INFO")
            
            # Informacja o sukcesie
            self.app_log.append("✅ Ustawienia zostały zresetowane do wartości domyślnych")
            
        except Exception as e:
            self.app_log.append(f"❌ Błąd podczas resetowania ustawień: {str(e)}")
    
    def filter_logs(self):
        """Filtruje logi na podstawie wybranej opcji."""
        # W przyszłości można zaimplementować rzeczywiste filtrowanie
        filter_type = self.log_filter_combo.currentText()
        self.app_log.append(f"ℹ️ Wybrano filtr logów: {filter_type}")
    
    def clear_logs(self):
        """Czyści zawartość okna logów."""
        self.app_log.clear()
        self.app_log.append("ℹ️ Logi zostały wyczyszczone")

    def load_settings(self):
        """Ładuje zapisane ustawienia z konfiguracji."""
        try:
            # Ustawienia logowania
            login = self.config.get_scenario_value("urtica", "login", "")
            if login:
                self.login_input.setText(login)
            
            # Ustawienia faktur
            self.weeks_spinbox.setValue(self.config.get_scenario_value("urtica", "weeks_to_process", 4))
            self.download_path_input.setText(self.config.get_scenario_value("urtica", "download_path", "./faktury"))
            
            # Ustawienia email
            send_emails = self.config.get_scenario_value("urtica", "send_emails", False)
            self.email_enabled_combo.setCurrentText("Tak" if send_emails else "Nie")
            self.email_recipient_input.setText(self.config.get_scenario_value("urtica", "email_recipient", ""))
            
            # Zaawansowane ustawienia email
            self.smtp_server_input.setText(self.config.get_scenario_value("urtica", "email_smtp_server", "smtp.example.com"))
            self.smtp_port_spinbox.setValue(self.config.get_scenario_value("urtica", "email_smtp_port", 587))
            self.email_sender_input.setText(self.config.get_scenario_value("urtica", "email_sender", ""))
            self.email_password_input.setText(self.config.get_scenario_value("urtica", "email_password", ""))
            self.email_tls_combo.setCurrentText("Tak" if self.config.get_scenario_value("urtica", "email_use_tls", True) else "Nie")
            
            # Aktywacja widoczności zaawansowanych ustawień email
            self.toggle_email_settings()
            
            # Ustawienia Playwright
            headless = self.config.get_value("playwright", "headless", False)
            self.headless_combo.setCurrentText("Tak" if headless else "Nie")
            self.timeout_spinbox.setValue(self.config.get_value("general", "default_timeout", 30000))
            
            # Ustawienia aplikacji
            auto_login = self.config.get_value("general", "auto_login", False)
            self.auto_login_combo.setCurrentText("Tak" if auto_login else "Nie")
            save_logs = self.config.get_value("general", "save_logs", True)
            self.save_logs_combo.setCurrentText("Tak" if save_logs else "Nie")
            self.log_level_combo.setCurrentText(self.config.get_value("general", "log_level", "INFO"))
            
            # Automatyczne logowanie, jeśli włączone
            if auto_login and login:
                password = self.config.get_scenario_value("urtica", "password", "")
                if password:
                    self.password_input.setText(password)
                    # Automatyczne logowanie tylko gdy są oba dane
                    QTimer.singleShot(500, self.login)
            
            logger.info("Załadowano ustawienia z konfiguracji")
            
        except Exception as e:
            logger.error(f"Błąd podczas ładowania ustawień: {str(e)}")
            self.app_log.append(f"❌ Błąd podczas ładowania ustawień: {str(e)}")

    def log_urtica(self, message):
        """Dodanie wiadomości do logów pobierania faktur."""
        self.invoice_log.append(message)
        logger.info(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
