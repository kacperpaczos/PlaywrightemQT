#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path


class ConfigLoader:
    """Klasa do ładowania i zarządzania konfiguracją aplikacji."""
    
    def __init__(self):
        self.config_path = self._get_config_path()
        self.config = self._load_config()
    
    def _get_config_path(self):
        """Określa ścieżkę do pliku konfiguracyjnego."""
        # Najpierw sprawdzamy ścieżkę względem bieżącego pliku
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(script_dir, "config", "settings.json")
        
        # Sprawdzamy, czy plik istnieje
        if os.path.exists(config_path):
            return config_path
        
        # Jeśli nie, to używamy ścieżki względem katalogu roboczego
        current_dir = os.getcwd()
        config_path = os.path.join(current_dir, "config", "settings.json")
        
        # Jeśli nadal nie istnieje, zwracamy domyślną ścieżkę
        return config_path
    
    def _load_config(self):
        """Ładuje konfigurację z pliku."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Plik konfiguracyjny nie istnieje: {self.config_path}")
                return {}
        except Exception as e:
            print(f"Błąd podczas ładowania konfiguracji: {str(e)}")
            return {}
    
    def get_value(self, section, key, default=None):
        """Pobiera wartość z konfiguracji."""
        try:
            if section in self.config and key in self.config[section]:
                return self.config[section][key]
            return default
        except Exception:
            return default
    
    def get_int(self, section, key, default=0):
        """Pobiera wartość liczbową z konfiguracji."""
        try:
            value = self.get_value(section, key)
            if value is not None:
                return int(value)
            return default
        except Exception:
            return default
    
    def get_bool(self, section, key, default=False):
        """Pobiera wartość logiczną z konfiguracji."""
        try:
            value = self.get_value(section, key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1')
            return bool(value)
        except Exception:
            return default
    
    def save_config(self):
        """Zapisuje konfigurację do pliku."""
        try:
            # Upewniamy się, że katalog konfiguracji istnieje
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as config_file:
                json.dump(self.config, config_file, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Błąd podczas zapisywania konfiguracji: {str(e)}")
            return False
    
    def set_value(self, section, key, value):
        """Ustawia wartość w konfiguracji."""
        try:
            if not section in self.config:
                self.config[section] = {}
            
            self.config[section][key] = value
            return self.save_config()
        except Exception as e:
            print(f"Błąd podczas ustawiania wartości konfiguracji: {str(e)}")
            return False


# Singleton do użycia w całej aplikacji
config = ConfigLoader() 