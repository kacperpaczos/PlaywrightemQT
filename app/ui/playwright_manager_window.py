#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton, 
                            QLabel, QHBoxLayout, QGroupBox, QMessageBox, 
                            QTabWidget, QGridLayout, QTableWidget, QTableWidgetItem,
                            QHeaderView, QButtonGroup, QRadioButton, QApplication,
                            QProgressBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from app.utils.logger import setup_logger
from app.utils.playwright_manager import PlaywrightManager

logger = setup_logger()

class PlaywrightManagerWindow(QMainWindow):
    """Okno managera Playwright."""
    
    # Dodajemy sygnał, który będzie emitowany przy zamknięciu okna
    finished = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.playwright_manager = PlaywrightManager()
        # Ustaw callback w PlaywrightManager
        self.playwright_manager.set_progress_callback(self.update_progress_message)
        self.init_ui()
        self.refresh_status()
        logger.info("Uruchomiono okno managera Playwright")
    
    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika."""
        self.setWindowTitle("Manager Playwright")
        self.setGeometry(200, 200, 800, 600)
        
        # Ikona aplikacji
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Główny widget i layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Utworzenie zakładek
        tab_widget = QTabWidget()
        
        # Zakładka statusu
        status_tab = QWidget()
        tab_widget.addTab(status_tab, "Status")
        
        # Zakładka instalacji
        install_tab = QWidget()
        tab_widget.addTab(install_tab, "Instalacja")
        
        # Zakładka zarządzania
        manage_tab = QWidget()
        tab_widget.addTab(manage_tab, "Zarządzanie")
        
        # Zawartość zakładki statusu
        status_layout = QVBoxLayout()
        
        # Sekcja statusu instalacji
        status_group = QGroupBox("Status instalacji Playwright")
        status_grid = QGridLayout()
        
        # Status Playwright
        self.playwright_status_label = QLabel("Sprawdzanie...")
        self.playwright_status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        status_grid.addWidget(QLabel("Pakiet Playwright:"), 0, 0)
        status_grid.addWidget(self.playwright_status_label, 0, 1)
        
        # Tabela przeglądarek
        browsers_group = QGroupBox("Zainstalowane przeglądarki")
        browsers_layout = QVBoxLayout()
        
        self.browsers_table = QTableWidget(3, 2)
        self.browsers_table.setHorizontalHeaderLabels(["Przeglądarka", "Status"])
        self.browsers_table.verticalHeader().setVisible(False)
        self.browsers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        browsers_layout.addWidget(self.browsers_table)
        browsers_group.setLayout(browsers_layout)
        
        status_grid.addWidget(browsers_group, 1, 0, 1, 2)
        
        # Przycisk odświeżania
        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("Odśwież status")
        refresh_button.clicked.connect(self.refresh_status)
        refresh_layout.addStretch()
        refresh_layout.addWidget(refresh_button)
        
        status_grid.addLayout(refresh_layout, 2, 0, 1, 2)
        status_group.setLayout(status_grid)
        status_layout.addWidget(status_group)
        status_tab.setLayout(status_layout)
        
        # Zawartość zakładki instalacji
        install_layout = QVBoxLayout()
        
        install_playwright_group = QGroupBox("Instalacja Playwright")
        install_playwright_layout = QVBoxLayout()
        
        install_text = QLabel("Wybierz przeglądarki do zainstalowania:")
        install_playwright_layout.addWidget(install_text)
        
        # Opcje przeglądarek
        browsers_select_layout = QGridLayout()
        self.chromium_checkbox = QRadioButton("Chromium")
        self.chromium_checkbox.setChecked(True)
        self.firefox_checkbox = QRadioButton("Firefox")
        self.webkit_checkbox = QRadioButton("WebKit")
        self.all_browsers_checkbox = QRadioButton("Wszystkie przeglądarki")
        
        # Grupa radio buttonów
        browser_group = QButtonGroup(self)
        browser_group.addButton(self.chromium_checkbox)
        browser_group.addButton(self.firefox_checkbox)
        browser_group.addButton(self.webkit_checkbox)
        browser_group.addButton(self.all_browsers_checkbox)
        
        browsers_select_layout.addWidget(self.chromium_checkbox, 0, 0)
        browsers_select_layout.addWidget(self.firefox_checkbox, 0, 1)
        browsers_select_layout.addWidget(self.webkit_checkbox, 1, 0)
        browsers_select_layout.addWidget(self.all_browsers_checkbox, 1, 1)
        
        install_playwright_layout.addLayout(browsers_select_layout)
        
        install_buttons_layout = QHBoxLayout()
        
        install_button = QPushButton("Zainstaluj Playwright")
        install_button.clicked.connect(self.install_playwright)
        install_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        reinstall_button = QPushButton("Przeinstaluj Playwright")
        reinstall_button.clicked.connect(self.reinstall_playwright)
        reinstall_button.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        
        install_buttons_layout.addWidget(install_button)
        install_buttons_layout.addWidget(reinstall_button)
        
        install_playwright_layout.addLayout(install_buttons_layout)
        install_playwright_group.setLayout(install_playwright_layout)
        install_layout.addWidget(install_playwright_group)
        install_tab.setLayout(install_layout)
        
        # Zawartość zakładki zarządzania
        manage_layout = QVBoxLayout()
        
        manage_group = QGroupBox("Zarządzanie przeglądarkami")
        manage_grid = QGridLayout()
        
        uninstall_text = QLabel("Usuwanie przeglądarek i Playwright:")
        manage_grid.addWidget(uninstall_text, 0, 0, 1, 2)
        
        # Przyciski usuwania
        uninstall_chromium_btn = QPushButton("Usuń Chromium")
        uninstall_chromium_btn.clicked.connect(lambda: self.uninstall_browser("chromium"))
        
        uninstall_firefox_btn = QPushButton("Usuń Firefox")
        uninstall_firefox_btn.clicked.connect(lambda: self.uninstall_browser("firefox"))
        
        uninstall_webkit_btn = QPushButton("Usuń WebKit")
        uninstall_webkit_btn.clicked.connect(lambda: self.uninstall_browser("webkit"))
        
        uninstall_all_browsers_btn = QPushButton("Usuń wszystkie przeglądarki")
        uninstall_all_browsers_btn.clicked.connect(self.uninstall_all_browsers)
        uninstall_all_browsers_btn.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")
        
        uninstall_playwright_btn = QPushButton("Usuń Playwright całkowicie")
        uninstall_playwright_btn.clicked.connect(self.uninstall_playwright)
        uninstall_playwright_btn.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        
        manage_grid.addWidget(uninstall_chromium_btn, 1, 0)
        manage_grid.addWidget(uninstall_firefox_btn, 1, 1)
        manage_grid.addWidget(uninstall_webkit_btn, 2, 0)
        manage_grid.addWidget(uninstall_all_browsers_btn, 2, 1)
        manage_grid.addWidget(uninstall_playwright_btn, 3, 0, 1, 2)
        
        manage_group.setLayout(manage_grid)
        manage_layout.addWidget(manage_group)
        
        # Status sekcja w zakładce zarządzania
        manage_status_group = QGroupBox("Informacje techniczne")
        manage_status_layout = QVBoxLayout()
        
        self.manage_status_label = QLabel("Status: Gotowy")
        manage_status_layout.addWidget(self.manage_status_label)
        
        manage_status_group.setLayout(manage_status_layout)
        manage_layout.addWidget(manage_status_group)
        
        manage_tab.setLayout(manage_layout)
        
        # Dodanie zakładek do głównego layoutu
        main_layout.addWidget(tab_widget)
        
        # Pasek postępu
        self.progress_group = QGroupBox("Postęp operacji")
        progress_layout = QVBoxLayout()
        
        self.operation_label = QLabel("Gotowy")
        progress_layout.addWidget(self.operation_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Nieskończony tryb ładowania
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Proszę czekać...")
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_group.setLayout(progress_layout)
        self.progress_group.setVisible(False)  # Domyślnie ukryty
        main_layout.addWidget(self.progress_group)
        
        # Przyciski na dole
        bottom_layout = QHBoxLayout()
        
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("background-color: #337ab7; color: white; font-weight: bold;")
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_button)
        
        main_layout.addLayout(bottom_layout)
        
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
        """Ukrywa pasek postępu."""
        # Przed ukryciem ustaw pasek na 100% aby zasygnalizować zakończenie
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Zakończono")
        QApplication.processEvents()  # Odśwież UI aby pokazać 100% przed ukryciem
        
        # Małe opóźnienie, aby użytkownik zauważył zmianę na 100%
        QTimer.singleShot(500, self._complete_hide_progress)
    
    def _complete_hide_progress(self):
        """Faktycznie ukrywa pasek postępu po małym opóźnieniu."""
        self.progress_group.setVisible(False)
        self.setEnabled(True)
        QApplication.processEvents()  # Odśwież UI
    
    def refresh_status(self):
        """Odświeża informacje o statusie instalacji Playwright."""
        try:
            # Pokazuje pasek ładowania
            self.show_progress("Odświeżanie statusu Playwright...")
            
            try:
                status = self.playwright_manager.get_installation_status()
                
                # Aktualizuj status Playwright
                if status["playwright_installed"]:
                    self.playwright_status_label.setText("Zainstalowany ✅")
                    self.playwright_status_label.setStyleSheet("color: green;")
                else:
                    self.playwright_status_label.setText("Niezainstalowany ❌")
                    self.playwright_status_label.setStyleSheet("color: red;")
                
                # Aktualizuj tabelę przeglądarek
                browsers = [("chromium", "Chromium"), ("firefox", "Firefox"), ("webkit", "WebKit")]
                
                for row, (browser_key, browser_name) in enumerate(browsers):
                    browser_name_item = QTableWidgetItem(browser_name)
                    browser_name_item.setFlags(browser_name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    if status["browsers"].get(browser_key, False):
                        browser_status_item = QTableWidgetItem("Zainstalowana ✅")
                        browser_status_item.setForeground(Qt.GlobalColor.green)
                    else:
                        browser_status_item = QTableWidgetItem("Niezainstalowana ❌")
                        browser_status_item.setForeground(Qt.GlobalColor.red)
                    
                    browser_status_item.setFlags(browser_status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    self.browsers_table.setItem(row, 0, browser_name_item)
                    self.browsers_table.setItem(row, 1, browser_status_item)
                
                self.manage_status_label.setText(f"Status: Playwright {'zainstalowany' if status['playwright_installed'] else 'niezainstalowany'}, " +
                                            f"Przeglądarki: {sum(1 for b in status['browsers'].values() if b)}/3")
                
            except Exception as e:
                logger.error(f"Błąd podczas aktualizacji statusu: {str(e)}")
                self.manage_status_label.setText(f"Status: Błąd odświeżania - {str(e)}")
                
                # Wyświetl podstawową informację o statusie Playwright
                try:
                    import playwright
                    self.playwright_status_label.setText("Pakiet zainstalowany ✅")
                    self.playwright_status_label.setStyleSheet("color: green;")
                except ImportError:
                    self.playwright_status_label.setText("Pakiet niezainstalowany ❌")
                    self.playwright_status_label.setStyleSheet("color: red;")
                    
                # Oznacz wszystkie przeglądarki jako nieznane
                browsers = [("chromium", "Chromium"), ("firefox", "Firefox"), ("webkit", "WebKit")]
                for row, (browser_key, browser_name) in enumerate(browsers):
                    browser_name_item = QTableWidgetItem(browser_name)
                    browser_name_item.setFlags(browser_name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    browser_status_item = QTableWidgetItem("Status nieznany ❓")
                    browser_status_item.setForeground(Qt.GlobalColor.darkGray)
                    browser_status_item.setFlags(browser_status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    self.browsers_table.setItem(row, 0, browser_name_item)
                    self.browsers_table.setItem(row, 1, browser_status_item)
                
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas aktualizacji statusu: {str(e)}")
            logger.error(f"Krytyczny błąd podczas aktualizacji statusu: {str(e)}")
        finally:
            # Zawsze ukryj pasek postępu
            self.hide_progress()
    
    def get_selected_browsers(self):
        """Zwraca wybrane przeglądarki do instalacji."""
        if self.all_browsers_checkbox.isChecked():
            return ["chromium", "firefox", "webkit"]
        elif self.chromium_checkbox.isChecked():
            return ["chromium"]
        elif self.firefox_checkbox.isChecked():
            return ["firefox"]
        elif self.webkit_checkbox.isChecked():
            return ["webkit"]
        else:
            return ["chromium"]  # domyślnie Chromium
    
    def install_playwright(self):
        """Instaluje Playwright z wybranymi przeglądarkami."""
        try:
            browsers = self.get_selected_browsers()
            
            reply = QMessageBox.question(
                self,
                "Instalacja Playwright",
                f"Czy chcesz zainstalować Playwright wraz z wybranymi przeglądarkami?\nWybrane przeglądarki: {', '.join(browsers)}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.show_progress(f"Instalowanie Playwright z przeglądarkami: {', '.join(browsers)}...")
                
                try:
                    success, message = self.playwright_manager.install_playwright(browsers)
                except Exception as e:
                    success = False
                    message = f"Wystąpił nieoczekiwany błąd: {str(e)}"
                    logger.error(f"Wyjątek podczas instalacji Playwright: {str(e)}")
                finally:
                    self.hide_progress()
                
                if success:
                    QMessageBox.information(self, "Instalacja Playwright", message)
                    self.manage_status_label.setText(f"Status: {message}")
                else:
                    QMessageBox.critical(self, "Błąd instalacji", message)
                    self.manage_status_label.setText(f"Status: Błąd: {message}")
                
                self.refresh_status()
                
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas instalacji Playwright: {str(e)}")
            logger.error(f"Błąd podczas instalacji Playwright: {str(e)}")
    
    def reinstall_playwright(self):
        """Przeinstalowuje Playwright z wybranymi przeglądarkami."""
        try:
            browsers = self.get_selected_browsers()
            
            reply = QMessageBox.question(
                self,
                "Reinstalacja Playwright",
                f"Ta operacja usunie i ponownie zainstaluje Playwright wraz z wybranymi przeglądarkami.\nWybrane przeglądarki: {', '.join(browsers)}\nKontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.show_progress(f"Reinstalacja Playwright z przeglądarkami: {', '.join(browsers)}...")
                
                try:
                    success, message = self.playwright_manager.reinstall_playwright(browsers)
                except Exception as e:
                    success = False
                    message = f"Wystąpił nieoczekiwany błąd: {str(e)}"
                    logger.error(f"Wyjątek podczas reinstalacji Playwright: {str(e)}")
                finally:
                    self.hide_progress()
                
                if success:
                    QMessageBox.information(self, "Reinstalacja Playwright", message)
                    self.manage_status_label.setText(f"Status: {message}")
                else:
                    QMessageBox.critical(self, "Błąd reinstalacji", message)
                    self.manage_status_label.setText(f"Status: Błąd: {message}")
                
                self.refresh_status()
                
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas reinstalacji Playwright: {str(e)}")
            logger.error(f"Błąd podczas reinstalacji Playwright: {str(e)}")
    
    def uninstall_browser(self, browser):
        """Usuwa wybraną przeglądarkę."""
        try:
            reply = QMessageBox.question(
                self,
                f"Usuwanie przeglądarki {browser}",
                f"Czy na pewno chcesz usunąć przeglądarkę {browser}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.show_progress(f"Usuwanie przeglądarki {browser}...")
                
                try:
                    success, message = self.playwright_manager.uninstall_browsers([browser])
                except Exception as e:
                    success = False
                    message = f"Wystąpił nieoczekiwany błąd: {str(e)}"
                    logger.error(f"Wyjątek podczas usuwania przeglądarki {browser}: {str(e)}")
                finally:
                    self.hide_progress()
                
                if success:
                    QMessageBox.information(self, "Usuwanie przeglądarki", message)
                    self.manage_status_label.setText(f"Status: {message}")
                else:
                    QMessageBox.critical(self, "Błąd usuwania", message)
                    self.manage_status_label.setText(f"Status: Błąd: {message}")
                
                self.refresh_status()
                
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas usuwania przeglądarki: {str(e)}")
            logger.error(f"Błąd podczas usuwania przeglądarki: {str(e)}")
    
    def uninstall_all_browsers(self):
        """Usuwa wszystkie przeglądarki Playwright."""
        try:
            reply = QMessageBox.question(
                self,
                "Usuwanie wszystkich przeglądarek",
                "Czy na pewno chcesz usunąć wszystkie przeglądarki Playwright?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.show_progress("Usuwanie wszystkich przeglądarek Playwright...")
                
                try:
                    success, message = self.playwright_manager.uninstall_browsers()
                except Exception as e:
                    success = False
                    message = f"Wystąpił nieoczekiwany błąd: {str(e)}"
                    logger.error(f"Wyjątek podczas usuwania wszystkich przeglądarek: {str(e)}")
                finally:
                    self.hide_progress()
                
                if success:
                    QMessageBox.information(self, "Usuwanie przeglądarek", message)
                    self.manage_status_label.setText(f"Status: {message}")
                else:
                    QMessageBox.critical(self, "Błąd usuwania", message)
                    self.manage_status_label.setText(f"Status: Błąd: {message}")
                
                self.refresh_status()
                
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas usuwania przeglądarek: {str(e)}")
            logger.error(f"Błąd podczas usuwania przeglądarek: {str(e)}")
    
    def uninstall_playwright(self):
        """Usuwa Playwright wraz ze wszystkimi przeglądarkami."""
        try:
            reply = QMessageBox.warning(
                self,
                "Usuwanie Playwright",
                "Ta operacja całkowicie usunie Playwright i wszystkie przeglądarki. Czy na pewno chcesz kontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Domyślnie wybrane No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.show_progress("Usuwanie Playwright i wszystkich przeglądarek...")
                
                try:
                    success, message = self.playwright_manager.uninstall_playwright()
                except Exception as e:
                    success = False
                    message = f"Wystąpił nieoczekiwany błąd: {str(e)}"
                    logger.error(f"Wyjątek podczas usuwania Playwright: {str(e)}")
                finally:
                    self.hide_progress()
                
                if success:
                    QMessageBox.information(self, "Usuwanie Playwright", message)
                    self.manage_status_label.setText(f"Status: {message}")
                else:
                    QMessageBox.critical(self, "Błąd usuwania", message)
                    self.manage_status_label.setText(f"Status: Błąd: {message}")
                
                self.refresh_status()
                
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas usuwania Playwright: {str(e)}")
            logger.error(f"Błąd podczas usuwania Playwright: {str(e)}")
    
    def update_progress_message(self, message: str):
        """Aktualizuje wiadomość w pasku postępu."""
        self.operation_label.setText(message)
        # Upewnij się, że pasek postępu jest widoczny
        if not self.progress_group.isVisible():
            self.show_progress(message)
        else:
            # Kontynuuj tryb nieskończony
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("Proszę czekać...")
            QApplication.processEvents()  # Odśwież UI
    
    def closeEvent(self, event):
        """Przechwytuje zdarzenie zamknięcia okna, aby emitować sygnał finished."""
        self.finished.emit()
        super().closeEvent(event)

# Funkcja do utworzenia okna managera Playwright
def create_playwright_manager_window(parent=None):
    """Tworzy i zwraca instancję okna managera Playwright."""
    return PlaywrightManagerWindow(parent) 