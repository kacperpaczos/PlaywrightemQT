#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.fakturator_window import FakturatorWindow

def main():
    """Uruchamia główne okno aplikacji (MainWindow)."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

def run_fakturator():
    """Uruchamia okno fakturatora (FakturatorWindow)."""
    app = QApplication(sys.argv)
    window = FakturatorWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # Uruchamiaj domyślnie okno fakturatora jako główne okno aplikacji
    run_fakturator()
