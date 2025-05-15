#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import tempfile
from loguru import logger

def setup_logger():
    # Sprawdzenie czy aplikacja jest uruchomiona jako plik wykonywalny (frozen)
    is_frozen = getattr(sys, 'frozen', False)
    
    # Określenie ścieżki bazowej
    if is_frozen:
        # Dla aplikacji skompilowanej przez PyInstaller
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        logs_dir = os.path.join(tempfile.gettempdir(), "Fakturator_e-urtica", "logs")
    else:
        # Dla aplikacji w trybie deweloperskim
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        logs_dir = os.path.join(base_path, "logs")
    
    # Upewnij się, że katalog logów istnieje
    try:
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "app.log")
    except Exception as e:
        print(f"Nie można utworzyć katalogu logów: {e}")
        # Awaryjnie użyj katalogu tymczasowego
        logs_dir = tempfile.gettempdir()
        log_file = os.path.join(logs_dir, "fakturator_app.log")
    
    # Konfiguracja loggera
    logger.remove()  # Usunięcie domyślnego handlera
    
    # Format dla pliku - z obsługą wyjątków przy dodawaniu handlera
    try:
        logger.add(
            log_file,
            rotation="10 MB",
            retention="30 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )
    except Exception as e:
        print(f"Nie można dodać handlera pliku: {e}")
    
    # Format dla konsoli - zawsze powinien działać
    try:
        logger.add(
            sys.stderr,
            level="INFO",
            format="{time:HH:mm:ss} | <level>{level: <8}</level> | {message}",
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    except Exception as e:
        print(f"Nie można dodać handlera konsoli: {e}")
    
    return logger
