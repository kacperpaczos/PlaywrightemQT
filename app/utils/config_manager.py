#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

class ConfigManager:
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Wczytuje konfigurację z pliku JSON."""
        if not self.config_path.exists():
            self._create_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Błąd podczas wczytywania konfiguracji: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Tworzy domyślną konfigurację."""
        default_config = {
            "app": {
                "name": "Playwright Tester",
                "width": 900,
                "height": 700
            },
            "general": {
                "log_level": "INFO",
                "screenshot_path": "logs/screenshots",
                "default_timeout": 30000
            },
            "scenarios": [
                {
                    "id": "urtica",
                    "name": "E-urtica faktury",
                    "description": "Pobieranie faktur z e-urtica.pl",
                    "active": True,
                    "url": "https://e-urtica.pl/authorization/login",
                    "settings": {
                        "login": "apteka@pcrsopot.pl",
                        "password": "Apteka2025!!",
                        "weeks_to_process": 2,
                        "download_path": "./faktury",
                        "send_emails": True,
                        "email_recipient": "odbiorca@example.com",
                        "email_smtp_server": "smtp.example.com",
                        "email_smtp_port": 587,
                        "email_sender": "tester@example.com",
                        "email_password": "",
                        "email_use_tls": True,
                        "headless": False
                    }
                }
            ],
            "playwright": {
                "headless": False,
                "page_timeout": 10000,
                "test_timeout": 600000,
                "extra_delay": 1000,
                "download_timeout": 15000,
                "processing_timeout": 30000,
                "log_level": "minimal",
                "max_network_retries": 3,
                "network_retry_delay": 5000
            }
        }
        
        # Zapisanie domyślnej konfiguracji
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_config(default_config)
        
        return default_config
    
    def save_config(self, config: Dict[str, Any] = None) -> None:
        """Zapisuje konfigurację do pliku JSON."""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Błąd podczas zapisywania konfiguracji: {e}")
    
    def get_value(self, section: str, key: str, default: Any = None) -> Any:
        """Pobiera wartość z konfiguracji dla podstawowych sekcji."""
        try:
            return self.config[section][key]
        except (KeyError, TypeError):
            return default
    
    def get_scenario_value(self, scenario_id: str, key: str, default: Any = None) -> Any:
        """Pobiera wartość z ustawień scenariusza."""
        scenario = self.get_scenario_by_id(scenario_id)
        if scenario and "settings" in scenario and key in scenario["settings"]:
            return scenario["settings"][key]
        return default
            
    def set_value(self, section: str, key: str, value: Any) -> None:
        """Ustawia wartość w konfiguracji dla podstawowych sekcji."""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save_config()
    
    def set_scenario_value(self, scenario_id: str, key: str, value: Any) -> None:
        """Ustawia wartość w ustawieniach scenariusza."""
        scenario = self.get_scenario_by_id(scenario_id)
        if scenario:
            if "settings" not in scenario:
                scenario["settings"] = {}
            scenario["settings"][key] = value
            self.save_config()
    
    def get_scenarios(self) -> List[Dict[str, Any]]:
        """Pobiera listę scenariuszy."""
        return self.config.get("scenarios", [])
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Pobiera scenariusz o podanym ID."""
        for scenario in self.get_scenarios():
            if scenario.get("id") == scenario_id:
                return scenario
        return None
    
    def add_scenario(self, scenario: Dict[str, Any]) -> None:
        """Dodaje nowy scenariusz do konfiguracji."""
        if "scenarios" not in self.config:
            self.config["scenarios"] = []
        self.config["scenarios"].append(scenario)
        self.save_config()
    
    def update_scenario(self, scenario_id: str, scenario: Dict[str, Any]) -> None:
        """Aktualizuje scenariusz w konfiguracji."""
        for i, existing_scenario in enumerate(self.get_scenarios()):
            if existing_scenario.get("id") == scenario_id:
                self.config["scenarios"][i] = scenario
                self.save_config()
                break
    
    def remove_scenario(self, scenario_id: str) -> None:
        """Usuwa scenariusz z konfiguracji."""
        self.config["scenarios"] = [
            scenario for scenario in self.get_scenarios()
            if scenario.get("id") != scenario_id
        ]
        self.save_config() 