#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from loguru import logger

def setup_logger():
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, "app.log")
    
    # Konfiguracja loggera
    logger.remove()  # Usunięcie domyślnego handlera
    
    # Format dla pliku
    logger.add(
        log_file,
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8"
    )
    
    # Format dla konsoli
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | <level>{level: <8}</level> | {message}",
        colorize=True
    )
    
    return logger
