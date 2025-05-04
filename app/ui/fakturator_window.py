#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import threading
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton, 
                           QComboBox, QLabel, QTextEdit, QHBoxLayout, 
                           QGroupBox, QLineEdit, QMessageBox, QFileDialog,
                           QTabWidget, QProgressBar, QSpinBox, QInputDialog,
                           QMenu, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDir, QTimer, QEvent
from PyQt6.QtGui import QIcon, QFont

from app.utils.logger import setup_logger
from app.utils.config_manager import ConfigManager
from app.utils.fakturator import download_invoices
from app.utils.playwright_manager import PlaywrightManager
from app.utils.email_sender import EmailSender

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
            # Funkcja zwrotna do aktualizacji postępu
            def progress_callback(value):
                self.progress_signal.emit(value)

            # Uruchomienie faktycznego pobierania faktur
            stats = download_invoices(self.custom_config, progress_callback)
            
            # Emitujemy sygnał zakończenia
            self.finished_signal.emit(stats)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Błąd podczas pobierania faktur: {str(e)}")


class PlaywrightInstallThread(QThread):
    """Wątek do instalacji Playwright i przeglądarek."""
    finished_signal = pyqtSignal(bool, str)  # (success, message)
    progress_signal = pyqtSignal(str)  # message

    def __init__(self, playwright_manager, browsers=None, reinstall=False, uninstall=False, uninstall_all=False):
        super().__init__()
        self.playwright_manager = playwright_manager
        self.browsers = browsers or ["chromium"]
        self.reinstall = reinstall
        self.uninstall = uninstall
        self.uninstall_all = uninstall_all
        
    def run(self):
        try:
            # Ustaw callback na sygnał postępu
            def progress_callback(message):
                self.progress_signal.emit(message)
                
            self.playwright_manager.set_progress_callback(progress_callback)
            
            success = False
            message = ""
            
            if self.reinstall:
                success, message = self.playwright_manager.reinstall_playwright(self.browsers)
            elif self.uninstall:
                success, message = self.playwright_manager.uninstall_playwright()
            elif self.uninstall_all:
                success, message = self.playwright_manager.uninstall_browsers()
            else:
                success, message = self.playwright_manager.install_playwright(self.browsers)
            
            self.finished_signal.emit(success, message)
            
        except Exception as e:
            self.finished_signal.emit(False, f"Wystąpił błąd: {str(e)}")
            logger.error(f"Błąd w wątku instalacji Playwright: {e}")


class PlaywrightStatusThread(QThread):
    """Wątek do sprawdzania statusu instalacji Playwright."""
    status_signal = pyqtSignal(dict)  # status dictionary
    progress_signal = pyqtSignal(str)  # message

    def __init__(self, playwright_manager):
        super().__init__()
        self.playwright_manager = playwright_manager
        
    def run(self):
        try:
            # Ustaw callback na sygnał postępu
            def progress_callback(message):
                self.progress_signal.emit(message)
                
            self.playwright_manager.set_progress_callback(progress_callback)
            
            # Pobierz status instalacji
            status = self.playwright_manager.get_installation_status()
            
            # Wyślij wynik
            self.status_signal.emit(status)
            
        except Exception as e:
            logger.error(f"Błąd w wątku sprawdzania statusu Playwright: {e}")
            # Wyślij minimalną informację o statusie
            self.status_signal.emit({"playwright_installed": False, "browsers": {}})


class FakturatorWindow(QMainWindow):
    """Główne okno aplikacji fakturatora."""
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.playwright_manager = PlaywrightManager()
        self.init_ui()
        
        # Inicjalizacja przycisku manager_playwright_button
        self._initial_button_setup = True
        
        logger.info("Uruchomiono okno fakturatora")
        
        # Sprawdź czy Playwright jest zainstalowany
        QTimer.singleShot(500, self.check_playwright_installation)
    
    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika."""
        self.setWindowTitle("Fakturator e-urtica")
        self.setGeometry(100, 100, 900, 700)
        
        # Ikona aplikacji
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Główny widget i layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Sekcja konfiguracji
        config_group = QGroupBox("Konfiguracja")
        config_layout = QVBoxLayout()
        
        # Login
        login_layout = QHBoxLayout()
        login_label = QLabel("Login:")
        self.login_input = QLineEdit()
        self.login_input.setText(self.config.get_scenario_value("urtica", "login", "apteka@pcrsopot.pl"))
        login_layout.addWidget(login_label)
        login_layout.addWidget(self.login_input)
        
        # Hasło
        password_layout = QHBoxLayout()
        password_label = QLabel("Hasło:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setText(self.config.get_scenario_value("urtica", "password", "Apteka2025!!"))
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        
        # Liczba tygodni
        weeks_layout = QHBoxLayout()
        weeks_label = QLabel("Liczba tygodni do pobrania:")
        self.weeks_spinbox = QSpinBox()
        self.weeks_spinbox.setMinimum(1)
        self.weeks_spinbox.setMaximum(8)
        self.weeks_spinbox.setValue(int(self.config.get_scenario_value("urtica", "weeks_to_process", 2)))
        weeks_layout.addWidget(weeks_label)
        weeks_layout.addWidget(self.weeks_spinbox)
        weeks_layout.addStretch()
        
        # Ścieżka zapisu
        path_layout = QHBoxLayout()
        path_label = QLabel("Ścieżka zapisu faktur:")
        self.path_input = QLineEdit()
        self.path_input.setText(self.config.get_scenario_value("urtica", "download_path", "./faktury"))
        self.path_button = QPushButton("Przeglądaj...")
        self.path_button.clicked.connect(self.browse_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.path_button)
        
        # Ustawienia email
        email_group = QGroupBox("Konfiguracja email")
        email_layout = QVBoxLayout()
        
        # Email odbiorcy
        email_recipient_layout = QHBoxLayout()
        email_recipient_label = QLabel("Adres email odbiorcy:")
        self.email_recipient_input = QLineEdit()
        self.email_recipient_input.setText(self.config.get_scenario_value("urtica", "email_recipient", "odbiorca@example.com"))
        email_recipient_layout.addWidget(email_recipient_label)
        email_recipient_layout.addWidget(self.email_recipient_input)
        
        # Wysyłanie maili
        send_emails_layout = QHBoxLayout()
        send_emails_label = QLabel("Wysyłaj maile:")
        self.send_emails_combo = QComboBox()
        self.send_emails_combo.addItems(["Nie", "Tak"])
        self.send_emails_combo.setCurrentIndex(1 if self.config.get_scenario_value("urtica", "send_emails", True) else 0)
        self.send_emails_combo.currentTextChanged.connect(self.toggle_email_settings)
        send_emails_layout.addWidget(send_emails_label)
        send_emails_layout.addWidget(self.send_emails_combo)
        
        # Zaawansowana konfiguracja email
        advanced_email_layout = QHBoxLayout()
        advanced_email_label = QLabel("Zaawansowana konfiguracja email:")
        self.advanced_email_combo = QComboBox()
        self.advanced_email_combo.addItems(["Nie", "Tak"])
        self.advanced_email_combo.setCurrentIndex(0)
        self.advanced_email_combo.currentTextChanged.connect(self.toggle_advanced_email_settings)
        advanced_email_layout.addWidget(advanced_email_label)
        advanced_email_layout.addWidget(self.advanced_email_combo)
        
        # Zaawansowane ustawienia email (początkowo ukryte)
        self.advanced_email_group = QGroupBox("Zaawansowane ustawienia email")
        self.advanced_email_group.setVisible(False)
        advanced_email_settings_layout = QVBoxLayout()
        
        # Serwer SMTP
        smtp_server_layout = QHBoxLayout()
        smtp_server_label = QLabel("Serwer SMTP:")
        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setText(self.config.get_scenario_value("urtica", "email_smtp_server", "smtp.example.com"))
        smtp_server_layout.addWidget(smtp_server_label)
        smtp_server_layout.addWidget(self.smtp_server_input)
        
        # Port SMTP
        smtp_port_layout = QHBoxLayout()
        smtp_port_label = QLabel("Port SMTP:")
        self.smtp_port_spinbox = QSpinBox()
        self.smtp_port_spinbox.setMinimum(1)
        self.smtp_port_spinbox.setMaximum(65535)
        self.smtp_port_spinbox.setValue(self.config.get_scenario_value("urtica", "email_smtp_port", 587))
        smtp_port_layout.addWidget(smtp_port_label)
        smtp_port_layout.addWidget(self.smtp_port_spinbox)
        
        # Adres nadawcy
        email_sender_layout = QHBoxLayout()
        email_sender_label = QLabel("Adres email nadawcy:")
        self.email_sender_input = QLineEdit()
        self.email_sender_input.setText(self.config.get_scenario_value("urtica", "email_sender", "tester@example.com"))
        email_sender_layout.addWidget(email_sender_label)
        email_sender_layout.addWidget(self.email_sender_input)
        
        # Hasło email
        email_password_layout = QHBoxLayout()
        email_password_label = QLabel("Hasło email:")
        self.email_password_input = QLineEdit()
        self.email_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.email_password_input.setText(self.config.get_scenario_value("urtica", "email_password", ""))
        email_password_layout.addWidget(email_password_label)
        email_password_layout.addWidget(self.email_password_input)
        
        # Użyj TLS
        email_tls_layout = QHBoxLayout()
        email_tls_label = QLabel("Użyj TLS:")
        self.email_tls_combo = QComboBox()
        self.email_tls_combo.addItems(["Nie", "Tak"])
        self.email_tls_combo.setCurrentIndex(1 if self.config.get_scenario_value("urtica", "email_use_tls", True) else 0)
        email_tls_layout.addWidget(email_tls_label)
        email_tls_layout.addWidget(self.email_tls_combo)
        
        # Dodanie zaawansowanych ustawień do grupy
        advanced_email_settings_layout.addLayout(smtp_server_layout)
        advanced_email_settings_layout.addLayout(smtp_port_layout)
        advanced_email_settings_layout.addLayout(email_sender_layout)
        advanced_email_settings_layout.addLayout(email_password_layout)
        advanced_email_settings_layout.addLayout(email_tls_layout)
        self.advanced_email_group.setLayout(advanced_email_settings_layout)
        
        # Dodawanie wszystkich pól do layoutu email
        email_layout.addLayout(email_recipient_layout)
        email_layout.addLayout(send_emails_layout)
        email_layout.addLayout(advanced_email_layout)
        email_layout.addWidget(self.advanced_email_group)
        email_group.setLayout(email_layout)
        
        # Inicjalizacja widoczności elementów
        self.toggle_email_settings()
        self.toggle_advanced_email_settings()
        
        # Opcje
        options_layout = QHBoxLayout()
        
        # Opcja headless
        headless_layout = QHBoxLayout()
        headless_label = QLabel("Tryb headless:")
        self.headless_combo = QComboBox()
        self.headless_combo.addItems(["Nie", "Tak"])
        self.headless_combo.setCurrentIndex(0)
        headless_layout.addWidget(headless_label)
        headless_layout.addWidget(self.headless_combo)
        
        # Opcja zapisywania konfiguracji
        save_config_layout = QHBoxLayout()
        save_config_label = QLabel("Zapisz konfigurację:")
        self.save_config_combo = QComboBox()
        self.save_config_combo.addItems(["Nie", "Tak"])
        self.save_config_combo.setCurrentIndex(1)
        save_config_layout.addWidget(save_config_label)
        save_config_layout.addWidget(self.save_config_combo)
        
        # Manager Playwright - przycisk z dynamiczną funkcjonalnością
        self.manager_playwright_button = QPushButton("Manager Playwright")
        self.manager_playwright_button.clicked.connect(self.handle_playwright_button)
        # Instalacja filtra zdarzeń do obsługi prawego przycisku myszy
        self.manager_playwright_button.installEventFilter(self)
        
        options_layout.addLayout(headless_layout)
        options_layout.addLayout(save_config_layout)
        options_layout.addWidget(self.manager_playwright_button)
        options_layout.addStretch()
        
        # Dodanie wszystkich sekcji do layoutu konfiguracji
        config_layout.addLayout(login_layout)
        config_layout.addLayout(password_layout)
        config_layout.addLayout(weeks_layout)
        config_layout.addLayout(path_layout)
        config_layout.addWidget(email_group)
        config_layout.addLayout(options_layout)
        config_group.setLayout(config_layout)
        
        # Sekcja przycisków akcji
        action_group = QGroupBox("Akcje")
        action_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Pobierz faktury")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_button.clicked.connect(self.start_download)
        
        self.stop_button = QPushButton("Zatrzymaj")
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.open_folder_button = QPushButton("Otwórz folder z fakturami")
        self.open_folder_button.clicked.connect(self.open_folder)
        
        # Przycisk wysyłki e-mail
        self.send_email_button = QPushButton("Wyślij faktury na e-mail")
        self.send_email_button.clicked.connect(self.send_invoices_email)
        self.send_email_button.setEnabled(False)
        
        # Przycisk zamknij
        self.close_button = QPushButton("Zamknij")
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #337ab7;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #286090;
            }
        """)
        self.close_button.clicked.connect(self.close)
        
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.stop_button)
        action_layout.addWidget(self.open_folder_button)
        action_layout.addWidget(self.send_email_button)
        action_layout.addWidget(self.close_button)
        action_group.setLayout(action_layout)
        
        # Pasek postępu
        progress_group = QGroupBox("Postęp")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Gotowy do pobierania faktur")
        font = QFont()
        font.setBold(True)
        self.status_label.setFont(font)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        
        # Logi
        log_group = QGroupBox("Logi")
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        log_buttons_layout = QHBoxLayout()
        self.clear_log_button = QPushButton("Wyczyść logi")
        self.clear_log_button.clicked.connect(self.clear_logs)
        self.save_log_button = QPushButton("Zapisz logi")
        self.save_log_button.clicked.connect(self.save_logs)
        
        # Przycisk do uruchomienia osobnego okna managera Playwright
        self.playwright_manager_button = QPushButton("Uruchom manager Playwright")
        self.playwright_manager_button.clicked.connect(self.run_playwright_manager)
        
        log_buttons_layout.addWidget(self.clear_log_button)
        log_buttons_layout.addWidget(self.save_log_button)
        log_buttons_layout.addWidget(self.playwright_manager_button)
        log_buttons_layout.addStretch()
        
        log_layout.addWidget(self.log_output)
        log_layout.addLayout(log_buttons_layout)
        log_group.setLayout(log_layout)
        
        # Dodanie wszystkich sekcji do głównego layoutu
        main_layout.addWidget(config_group)
        main_layout.addWidget(action_group)
        main_layout.addWidget(progress_group)
        main_layout.addWidget(log_group)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Zainicjalizuj wątek
        self.fakturator_thread = None
    
    def browse_path(self):
        """Otwiera okno dialogowe do wyboru ścieżki zapisu faktur."""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Wybierz katalog do zapisu faktur", 
            self.path_input.text(), 
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.path_input.setText(directory)
    
    def open_folder(self):
        """Otwiera folder z fakturami w eksploratorze plików."""
        path = self.path_input.text()
        
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie można utworzyć katalogu: {str(e)}")
                return
        
        # Otwórz folder w eksploratorze plików
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', path])
        else:  # Linux/Unix
            subprocess.run(['xdg-open', path])
    
    def clear_logs(self):
        """Czyści pole logów."""
        self.log_output.clear()
    
    def save_logs(self):
        """Zapisuje logi do pliku."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz logi", "", "Pliki tekstowe (*.txt);;Wszystkie pliki (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_output.toPlainText())
                self.log(f"Logi zapisane do pliku: {file_path}")
                logger.info(f"Logi zapisane do pliku: {file_path}")
            except Exception as e:
                self.log(f"Błąd podczas zapisywania logów: {str(e)}")
                logger.error(f"Błąd podczas zapisywania logów: {str(e)}")
    
    def save_current_config(self):
        """Zapisuje bieżącą konfigurację do pliku config."""
        if not self.save_config_combo.currentText() == "Tak":
            return
            
        try:
            self.config.set_scenario_value("urtica", "login", self.login_input.text())
            self.config.set_scenario_value("urtica", "password", self.password_input.text())
            self.config.set_scenario_value("urtica", "weeks_to_process", str(self.weeks_spinbox.value()))
            self.config.set_scenario_value("urtica", "download_path", self.path_input.text())
            
            self.config.save_config()
            self.log("✅ Zapisano konfigurację")
        except Exception as e:
            self.log(f"❌ Błąd podczas zapisywania konfiguracji: {str(e)}")
    
    def log(self, message):
        """Dodaje wiadomość do pola z logami."""
        self.log_output.append(message)
        # Przewiń do końca
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
    def update_status(self, message, progress_value=None):
        """Aktualizuje etykietę statusu i opcjonalnie pasek postępu."""
        self.status_label.setText(message)
        if progress_value is not None:
            # Jeśli wartość to None, ustaw tryb nieskończony od lewej do prawej
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress_value)
        else:
            # Ustaw tryb nieskończony
            self.progress_bar.setRange(0, 0)
            # Dodajemy styl dla animacji od lewej do prawej
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid grey;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #337ab7;
                    width: 10px;
                    margin: 0.5px;
                }
            """)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat("Proszę czekać...")
        QApplication.processEvents()  # Odśwież UI
    
    def toggle_email_settings(self):
        """Włącza/wyłącza widoczność ustawień email w zależności od wybranej opcji."""
        is_enabled = self.send_emails_combo.currentText() == "Tak"
        self.email_recipient_input.setEnabled(is_enabled)
        self.advanced_email_combo.setEnabled(is_enabled)
        self.advanced_email_group.setVisible(is_enabled and self.advanced_email_combo.currentText() == "Tak")

    def toggle_advanced_email_settings(self):
        """Włącza/wyłącza widoczność zaawansowanych ustawień email."""
        is_visible = (self.send_emails_combo.currentText() == "Tak" and 
                     self.advanced_email_combo.currentText() == "Tak")
        self.advanced_email_group.setVisible(is_visible)
    
    def start_download(self):
        """Rozpoczyna pobieranie faktur."""
        try:
            # Sprawdź czy już nie uruchomiliśmy wątku
            if self.fakturator_thread and self.fakturator_thread.isRunning():
                QMessageBox.warning(self, "Ostrzeżenie", "Pobieranie faktur już trwa.")
                return
            
            # Przygotuj konfigurację
            custom_config = {
                "login": self.login_input.text(),
                "password": self.password_input.text(),
                "weeks_to_process": self.weeks_spinbox.value(),
                "download_path": self.path_input.text(),
                "headless": self.headless_combo.currentText() == "Tak"
            }
            
            # Sprawdź poprawność konfiguracji
            if not custom_config["login"] or not custom_config["password"]:
                QMessageBox.warning(self, "Brak danych", "Podaj login i hasło do systemu e-urtica.")
                return
            
            # Zapisz konfigurację jeśli zaznaczono opcję
            if self.save_config_combo.currentText() == "Tak":
                self.save_current_config()
            
            # Upewnij się, że ścieżka zapisu istnieje
            os.makedirs(custom_config["download_path"], exist_ok=True)
            
            # Utwórz i uruchom wątek
            self.fakturator_thread = FakturatorThread(custom_config)
            self.fakturator_thread.log_signal.connect(self.log)
            self.fakturator_thread.progress_signal.connect(self.update_progress)
            self.fakturator_thread.finished_signal.connect(self.download_finished)
            self.fakturator_thread.start()
            
            # Aktualizuj UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.update_status("Pobieranie faktur w toku...", 0)
            self.log("🚀 Uruchomiono pobieranie faktur")
            
            # Zawsze wymuszaj tryb widoczny Playwrighta
            custom_config = {
                'login': self.login_input.text(),
                'password': self.password_input.text(),
                'weeks_to_process': self.weeks_spinbox.value(),
                'download_path': self.path_input.text(),
                'headless': False
            }
            self.config.set_scenario_value("urtica", **custom_config)
            
            self.send_email_button.setEnabled(False)
            
        except Exception as e:
            self.log(f"❌ Błąd podczas uruchamiania pobierania faktur: {str(e)}")
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd: {str(e)}")
    
    def stop_download(self):
        """Zatrzymuje pobieranie faktur."""
        if self.fakturator_thread and self.fakturator_thread.isRunning():
            # Nie ma bezpośredniej metody do przerwania wątku Playwright, więc używamy terminate
            self.fakturator_thread.terminate()
            self.fakturator_thread.wait()  # Poczekaj na zakończenie wątku
            
            # Aktualizuj UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.update_status("Pobieranie przerwane przez użytkownika", self.progress_bar.value())
            self.log("⚠️ Pobieranie faktur zostało przerwane przez użytkownika")
        else:
            self.log("⚠️ Brak aktywnego pobierania do zatrzymania")
    
    def update_progress(self, value):
        """Aktualizuje pasek postępu."""
        self.progress_bar.setValue(value)
    
    def check_playwright_installation(self):
        """Sprawdza czy Playwright jest zainstalowany i wyświetla odpowiedni komunikat przy starcie aplikacji."""
        try:
            # Ustaw pasek postępu w trybie nieskończonym podczas sprawdzania
            self.update_status("Sprawdzanie instalacji Playwright...", None)
            
            # Stwórz i uruchom wątek sprawdzania statusu
            self.status_thread = PlaywrightStatusThread(self.playwright_manager)
            self.status_thread.progress_signal.connect(self.update_progress_message)
            self.status_thread.status_signal.connect(self.handle_playwright_status)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek sprawdzania statusu
            self.status_thread.start()
            
        except Exception as e:
            self.log(f"❌ Błąd podczas sprawdzania instalacji Playwright: {str(e)}")
            self.start_button.setEnabled(False)
            self.progress_bar.setStyleSheet("")  # Usuń styl nieskończonego paska
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.update_status(f"Błąd sprawdzania instalacji: {str(e)}", 0)
            
            # Aktualizacja przycisku na podstawie domyślnego statusu (brak instalacji)
            self.update_playwright_button({"playwright_installed": False})
    
    def handle_playwright_status(self, installation_status):
        """Obsługuje otrzymany status instalacji Playwright."""
        self.log(f"Status instalacji Playwright: {installation_status}")
        
        # Przywróć pasek postępu do normalnego stanu
        self.progress_bar.setStyleSheet("")  # Usuń styl nieskończonego paska
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        QApplication.processEvents()
        
        # Mały delay aby użytkownik zauważył zakończenie
        QTimer.singleShot(500, lambda: self.progress_bar.setValue(0))
        
        # Aktualizacja przycisku na podstawie statusu instalacji
        self.update_playwright_button(installation_status)
        
        if not installation_status["playwright_installed"]:
            reply = QMessageBox.question(
                self,
                "Playwright nie jest zainstalowany",
                "Aby korzystać z funkcji pobierania faktur, wymagany jest Playwright. Czy chcesz go zainstalować teraz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._install_playwright()
            else:
                self.log("❌ Playwright nie jest zainstalowany. Pobieranie faktur będzie niemożliwe.")
                self.start_button.setEnabled(False)
                self.update_status("Playwright nie jest zainstalowany", 0)
        else:
            # Sprawdź brakujące przeglądarki
            missing_browsers = [browser for browser, installed in installation_status["browsers"].items() 
                              if not installed and browser == "chromium"]
            
            if missing_browsers:
                reply = QMessageBox.question(
                    self,
                    "Brak przeglądarki Chromium",
                    "Playwright jest zainstalowany, ale brakuje przeglądarki Chromium. Czy chcesz ją zainstalować teraz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._install_browser("chromium")
                else:
                    self.log("❌ Brak przeglądarki Chromium. Pobieranie faktur będzie niemożliwe.")
                    self.start_button.setEnabled(False)
                    self.update_status("Brak przeglądarki Chromium", 0)
            else:
                self.log("✅ Playwright i przeglądarka Chromium są zainstalowane.")
                self.start_button.setEnabled(True)
                self.update_status("Gotowy do pobierania faktur", 0)
        
        # Przywróć dostępność przycisków
        self.set_action_buttons_enabled(True)
    
    def _install_playwright(self):
        """Instaluje Playwright i przeglądarkę Chromium."""
        reply = QMessageBox.question(
            self,
            "Instalacja Playwright",
            "Czy chcesz zainstalować Playwright wraz z przeglądarką Chromium?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("🔄 Instalowanie Playwright...")
            
            # Ustaw pasek postępu w trybie nieskończonym
            self.update_status("Instalowanie Playwright i przeglądarki Chromium...", None)
            
            # Stwórz i uruchom wątek instalacji
            self.install_thread = PlaywrightInstallThread(self.playwright_manager, browsers=["chromium"])
            self.install_thread.progress_signal.connect(self.update_progress_message)
            self.install_thread.finished_signal.connect(self.installation_finished)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek instalacji
            self.install_thread.start()
    
    def installation_finished(self, success, message):
        """Obsługuje zakończenie instalacji/odinstalowania Playwright."""
        # Przywróć pasek w trybie normalnym i pokaż 100%
        self.progress_bar.setStyleSheet("")  # Usuń styl nieskończonego paska
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        QApplication.processEvents()  # Odśwież UI
        
        # Dodajemy opóźnienie aby użytkownik mógł zauważyć zakończenie
        QTimer.singleShot(2000, self._complete_installation_ui)
        
        if success:
            QMessageBox.information(self, "Operacja Playwright", message)
            self.log(f"✅ {message}")
            self.check_playwright_installation()  # Odśwież status
            # Aktualizacja przycisku po instalacji
            self.update_playwright_button({"playwright_installed": True})
        else:
            QMessageBox.critical(self, "Błąd operacji", message)
            self.log(f"❌ {message}")
            # Aktualizacja przycisku po nieudanej instalacji
            self.update_playwright_button({"playwright_installed": False})
    
    def set_action_buttons_enabled(self, enabled):
        """Włącza/wyłącza przyciski akcji, zachowując responsywność UI."""
        self.start_button.setEnabled(enabled)
        self.stop_button.setEnabled(False)
        self.open_folder_button.setEnabled(enabled)
        self.send_email_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)
        self.manager_playwright_button.setEnabled(enabled)
        
        # Odśwież UI
        QApplication.processEvents()
    
    def _install_browser(self, browser):
        """Instaluje wybraną przeglądarkę."""
        self.log(f"🔄 Instalowanie przeglądarki {browser}...")
        
        # Ustaw pasek postępu w trybie nieskończonym
        self.update_status(f"Instalowanie przeglądarki {browser}...", None)
        
        # Stwórz i uruchom wątek instalacji
        self.install_thread = PlaywrightInstallThread(self.playwright_manager, browsers=[browser])
        self.install_thread.progress_signal.connect(self.update_progress_message)
        self.install_thread.finished_signal.connect(self.installation_finished)
        
        # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
        self.set_action_buttons_enabled(False)
        
        # Uruchom wątek instalacji
        self.install_thread.start()
    
    def _reinstall_playwright(self):
        """Przeinstalowuje Playwright wraz z przeglądarką Chromium."""
        reply = QMessageBox.question(
            self,
            "Reinstalacja Playwright",
            "Ta operacja usunie i ponownie zainstaluje Playwright wraz z przeglądarką Chromium. Kontynuować?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("🔄 Reinstalacja Playwright...")
            
            # Ustaw pasek postępu w trybie nieskończonym
            self.update_status("Reinstalacja Playwright i przeglądarki Chromium...", None)
            
            # Stwórz i uruchom wątek reinstalacji
            self.install_thread = PlaywrightInstallThread(
                self.playwright_manager, 
                browsers=["chromium"], 
                reinstall=True
            )
            self.install_thread.progress_signal.connect(self.update_progress_message)
            self.install_thread.finished_signal.connect(self.installation_finished)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek reinstalacji
            self.install_thread.start()
    
    def _uninstall_browser(self, browser):
        """Usuwa wybraną przeglądarkę."""
        reply = QMessageBox.question(
            self,
            f"Usuwanie przeglądarki {browser}",
            f"Czy na pewno chcesz usunąć przeglądarkę {browser}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log(f"🔄 Usuwanie przeglądarki {browser}...")
            
            # Ustaw pasek postępu w trybie nieskończonym
            self.update_status(f"Usuwanie przeglądarki {browser}...", None)
            
            # Stwórz specjalny wątek do usuwania konkretnej przeglądarki
            class BrowserUninstallThread(PlaywrightInstallThread):
                def run(self):
                    try:
                        callback = self.playwright_manager.set_progress_callback
                        callback(lambda msg: self.progress_signal.emit(msg))
                        success, message = self.playwright_manager.uninstall_browsers([self.browsers[0]])
                        self.finished_signal.emit(success, message)
                    except Exception as e:
                        self.finished_signal.emit(False, f"Wystąpił błąd: {str(e)}")
            
            # Stwórz i uruchom wątek odinstalowania
            self.install_thread = BrowserUninstallThread(self.playwright_manager, browsers=[browser])
            self.install_thread.progress_signal.connect(self.update_progress_message)
            self.install_thread.finished_signal.connect(self.installation_finished)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek odinstalowania
            self.install_thread.start()
    
    def _uninstall_all_browsers(self):
        """Usuwa wszystkie przeglądarki Playwright."""
        reply = QMessageBox.question(
            self,
            "Usuwanie wszystkich przeglądarek",
            "Czy na pewno chcesz usunąć wszystkie przeglądarki Playwright?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("🔄 Usuwanie wszystkich przeglądarek...")
            
            # Ustaw pasek postępu w trybie nieskończonym
            self.update_status("Usuwanie wszystkich przeglądarek...", None)
            
            # Stwórz i uruchom wątek odinstalowania wszystkich przeglądarek
            self.install_thread = PlaywrightInstallThread(
                self.playwright_manager,
                uninstall_all=True
            )
            self.install_thread.progress_signal.connect(self.update_progress_message)
            self.install_thread.finished_signal.connect(self.installation_finished)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek odinstalowania
            self.install_thread.start()
    
    def _uninstall_playwright(self):
        """Usuwa całkowicie Playwright."""
        reply = QMessageBox.warning(
            self,
            "Usuwanie Playwright",
            "Ta operacja całkowicie usunie Playwright i wszystkie przeglądarki. Czy na pewno chcesz kontynuować?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Domyślna odpowiedź to No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("🔄 Usuwanie Playwright i wszystkich przeglądarek...")
            
            # Ustaw pasek postępu w trybie nieskończonym
            self.update_status("Usuwanie Playwright...", None)
            
            # Stwórz i uruchom wątek odinstalowania Playwright
            self.install_thread = PlaywrightInstallThread(
                self.playwright_manager,
                uninstall=True
            )
            self.install_thread.progress_signal.connect(self.update_progress_message)
            self.install_thread.finished_signal.connect(self.installation_finished)
            
            # Wyłącz tylko przyciski akcji, ale nie cały interfejs, aby zachować responsywność
            self.set_action_buttons_enabled(False)
            
            # Uruchom wątek odinstalowania
            self.install_thread.start()
    
    def _complete_installation_ui(self):
        """Kompletnie przywraca UI po instalacji."""
        # Przywróć dostępność przycisków
        self.set_action_buttons_enabled(True)
        
        # Przywróć normalny stan paska postępu
        self.update_status("Gotowy do pobierania faktur", 0)
        QApplication.processEvents()  # Odśwież UI
    
    def update_progress_message(self, message):
        """Aktualizuje wiadomość postępu podczas instalacji."""
        self.update_status(message, None)
        self.log(message)
        QApplication.processEvents()  # Odśwież UI
    
    def download_finished(self, stats):
        """Obsługuje zakończenie pobierania faktur."""
        self.fakturator_thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_status(f"Pobieranie zakończone. Pobrano {stats['downloadedInvoices']} faktur.", 100)
        self.log(f"✅ Pobieranie zakończone. Statystyki: {stats}")
        
        # Wyświetl podsumowanie pobierania i opcję wysłania maila
        if stats["downloadedInvoices"] == 0:
            QMessageBox.information(
                self,
                "Pobieranie zakończone",
                "Nie pobrano żadnych faktur.",
                QMessageBox.StandardButton.Ok
            )
        else:
            reply = QMessageBox.question(
                self,
                "Pobieranie zakończone",
                f"Pobrano {stats['downloadedInvoices']} faktur.\nCzy chcesz wysłać je teraz mailem?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Otwórz dialog do edycji adresu email przed wysyłką
                email, ok = QInputDialog.getText(
                    self, 
                    "Adres email", 
                    "Podaj adres email do wysyłki faktur:",
                    QLineEdit.Normal,
                    self.email_recipient_input.text()
                )
                
                if ok and email:
                    # Zaktualizuj adres i wyślij maila
                    self.email_recipient_input.setText(email)
                    self.send_invoices_email()
    
    def send_invoices_email(self):
        # Funkcja do wysyłania faktur na e-mail z katalogu download_path
        email = self.email_recipient_input.text()
        if not email:
            QMessageBox.warning(self, "Brak adresu e-mail", "Podaj adres e-mail do wysyłki faktur.")
            return
            
        faktury_dir = self.path_input.text()
        attachments = []
        for root, _, files in os.walk(faktury_dir):
            for f in files:
                if f.lower().endswith('.pdf') or f.lower().endswith('.xml'):
                    attachments.append(os.path.join(root, f))
                    
        if not attachments:
            QMessageBox.warning(self, "Brak faktur", "Nie znaleziono faktur do wysłania.")
            return
            
        # Przygotowanie konfiguracji email
        email_config = {
            "smtp_server": self.smtp_server_input.text(),
            "smtp_port": self.smtp_port_spinbox.value(),
            "sender": self.email_sender_input.text(),
            "password": self.email_password_input.text(),
            "use_tls": self.email_tls_combo.currentText() == "Tak"
        }
        
        # Inicjalizacja obiektu EmailSender z niestandardową konfiguracją
        sender = EmailSender(custom_config=email_config)
        ok = sender.send_email(email, "Faktury e-urtica", "W załączniku faktury pobrane przez aplikację.", attachments)
        
        if ok:
            QMessageBox.information(self, "Sukces", "Faktury zostały wysłane na podany adres e-mail.")
        else:
            QMessageBox.critical(self, "Błąd", "Nie udało się wysłać faktur na e-mail.")

    def handle_playwright_button(self):
        """Obsługuje kliknięcie przycisku Playwright - instaluje lub otwiera menedżera."""
        try:
            # Sprawdź aktualny stan instalacji
            status = self.playwright_manager.get_installation_status()
            
            if status["playwright_installed"]:
                # Jeśli Playwright jest zainstalowany, otwórz menedżera
                self.run_playwright_manager()
            else:
                # Jeśli Playwright nie jest zainstalowany, uruchom instalację
                self._install_playwright()
                
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd: {str(e)}")
            logger.error(f"Błąd podczas obsługi przycisku Playwright: {str(e)}")

    def run_playwright_manager(self):
        """Uruchamia okno menedżera Playwright."""
        try:
            from app.ui.playwright_manager_window import create_playwright_manager_window
            
            # Pokaż pasek postępu z informacją o ładowaniu
            self.progress_bar.setRange(0, 0)  # Tryb nieskończony
            self.update_status("Uruchamianie menedżera Playwright...", None)
            QApplication.processEvents()  # Odśwież UI
            
            # Utwórz i pokaż okno
            manager_window = create_playwright_manager_window(self)
            manager_window.show()
            
            # Przywróć pasek postępu do normalnego stanu po 500ms
            QTimer.singleShot(500, lambda: self.progress_bar.setRange(0, 100))
            QTimer.singleShot(500, lambda: self.progress_bar.setValue(100))
            QTimer.singleShot(700, lambda: self.update_status("Menedżer Playwright uruchomiony", 100))
            QTimer.singleShot(2000, lambda: self.update_status("Gotowy do pobierania faktur", 0))
            
            # Połącz sygnał zamknięcia okna z odświeżeniem statusu
            manager_window.finished.connect(self.check_playwright_installation)
            
        except Exception as e:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.log(f"❌ Błąd podczas uruchamiania menedżera Playwright: {str(e)}")
            QMessageBox.critical(self, "Błąd", f"Nie udało się uruchomić menedżera Playwright: {str(e)}")

    def update_playwright_button(self, installation_status=None):
        """Aktualizuje tekst i funkcję przycisku w zależności od stanu instalacji Playwright."""
        if installation_status is None:
            # Jeśli nie podano statusu, pobierz go
            try:
                installation_status = self.playwright_manager.get_installation_status()
            except Exception as e:
                logger.error(f"Błąd podczas pobierania statusu Playwright: {e}")
                installation_status = {"playwright_installed": False}
        
        if installation_status["playwright_installed"]:
            # Jeśli Playwright jest zainstalowany, przycisk otwiera menedżera
            self.manager_playwright_button.setText("Manager Playwright")
            self.manager_playwright_button.setStyleSheet("""
                QPushButton {
                    background-color: #337ab7;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #286090;
                }
            """)
            # Zmień funkcję przycisku na otwieranie menedżera
            if not self._initial_button_setup:
                self.manager_playwright_button.clicked.disconnect()
            self.manager_playwright_button.clicked.connect(self.run_playwright_manager)
        else:
            # Jeśli Playwright nie jest zainstalowany, przycisk instaluje Playwright
            self.manager_playwright_button.setText("Zainstaluj Playwright")
            self.manager_playwright_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            # Zmień funkcję przycisku na instalację Playwright
            if not self._initial_button_setup:
                self.manager_playwright_button.clicked.disconnect()
            self.manager_playwright_button.clicked.connect(self._install_playwright)
        
        # Po pierwszym wywołaniu, wyłączamy flagę initial setup
        self._initial_button_setup = False

    def show_playwright_menu(self):
        """Wyświetla menu zarządzania Playwright i jego przeglądarkami."""
        try:
            # Wyświetl menu kontekstowe z opcjami zarządzania Playwright
            context_menu = QMenu(self)
            
            # Sprawdź aktualny stan instalacji
            status = self.playwright_manager.get_installation_status()
            
            # Opcje menu
            install_action = context_menu.addAction("Zainstaluj Playwright")
            reinstall_action = context_menu.addAction("Przeinstaluj Playwright")
            
            # Podmenu dla przeglądarek
            browsers_menu = QMenu("Przeglądarki", self)
            install_chromium = browsers_menu.addAction("Zainstaluj Chromium")
            install_firefox = browsers_menu.addAction("Zainstaluj Firefox")
            install_webkit = browsers_menu.addAction("Zainstaluj WebKit")
            browsers_menu.addSeparator()
            uninstall_chromium = browsers_menu.addAction("Usuń Chromium")
            uninstall_firefox = browsers_menu.addAction("Usuń Firefox")
            uninstall_webkit = browsers_menu.addAction("Usuń WebKit")
            context_menu.addMenu(browsers_menu)
            
            context_menu.addSeparator()
            uninstall_all_browsers = context_menu.addAction("Usuń wszystkie przeglądarki")
            uninstall_playwright = context_menu.addAction("Usuń Playwright całkowicie")
            
            # Ustaw stan aktywności elementów menu na podstawie stanu instalacji
            install_action.setEnabled(not status["playwright_installed"])
            reinstall_action.setEnabled(status["playwright_installed"])
            
            uninstall_chromium.setEnabled(status["browsers"].get("chromium", False))
            uninstall_firefox.setEnabled(status["browsers"].get("firefox", False))
            uninstall_webkit.setEnabled(status["browsers"].get("webkit", False))
            uninstall_all_browsers.setEnabled(any(status["browsers"].values()))
            uninstall_playwright.setEnabled(status["playwright_installed"])
            
            # Wyświetl menu pod przyciskiem głównym Playwright
            action = context_menu.exec(self.manager_playwright_button.mapToGlobal(
                self.manager_playwright_button.rect().bottomLeft()
            ))
            
            # Obsługa wybranej akcji
            if action == install_action:
                self._install_playwright()
            elif action == reinstall_action:
                self._reinstall_playwright()
            elif action == install_chromium:
                self._install_browser("chromium")
            elif action == install_firefox:
                self._install_browser("firefox")
            elif action == install_webkit:
                self._install_browser("webkit")
            elif action == uninstall_chromium:
                self._uninstall_browser("chromium")
            elif action == uninstall_firefox:
                self._uninstall_browser("firefox")
            elif action == uninstall_webkit:
                self._uninstall_browser("webkit")
            elif action == uninstall_all_browsers:
                self._uninstall_all_browsers()
            elif action == uninstall_playwright:
                self._uninstall_playwright()
            
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd: {str(e)}")
            logger.error(f"Błąd podczas wyświetlania menu Playwright: {str(e)}")

    def eventFilter(self, obj, event):
        """Filtr zdarzeń do obsługi prawego przycisku myszy na przyciskach."""
        if obj == self.manager_playwright_button and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                # Prawy przycisk myszy na przycisku Manager Playwright
                self.show_playwright_menu()
                return True
        return super().eventFilter(obj, event)

# Funkcja do utworzenia okna fakturatora
def create_fakturator_window():
    """Tworzy i zwraca instancję okna fakturatora."""
    return FakturatorWindow() 