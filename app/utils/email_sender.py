#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app.utils.config_manager import ConfigManager
from app.utils.logger import setup_logger

logger = setup_logger()

class EmailSender:
    """Klasa do wysyłania wiadomości e-mail."""
    
    def __init__(self, scenario_id="urtica", custom_config=None):
        if custom_config:
            # Używamy niestandardowej konfiguracji
            self.smtp_server = custom_config.get("smtp_server", "smtp.example.com")
            self.smtp_port = custom_config.get("smtp_port", 587)
            self.sender_email = custom_config.get("sender", "tester@example.com")
            self.password = custom_config.get("password", "")
            self.use_tls = custom_config.get("use_tls", True)
        else:
            # Pobieranie konfiguracji ze scenariusza
            config = ConfigManager()
            self.smtp_server = config.get_scenario_value(scenario_id, "email_smtp_server", "smtp.example.com")
            self.smtp_port = config.get_scenario_value(scenario_id, "email_smtp_port", 587)
            self.sender_email = config.get_scenario_value(scenario_id, "email_sender", "tester@example.com")
            self.password = config.get_scenario_value(scenario_id, "email_password", "")
            self.use_tls = config.get_scenario_value(scenario_id, "email_use_tls", True)
    
    def send_email(self, receiver_email, subject, message, attachments=None):
        """
        Wysyła e-mail z opcjonalnymi załącznikami.
        
        Args:
            receiver_email (str): Adres e-mail odbiorcy
            subject (str): Temat wiadomości
            message (str): Treść wiadomości
            attachments (list, optional): Lista ścieżek do plików załączników
        
        Returns:
            bool: True jeśli e-mail został wysłany pomyślnie, False w przeciwnym razie
        """
        try:
            # Sprawdzenie, czy hasło jest ustawione
            if not self.password:
                logger.error("Nie skonfigurowano hasła do konta e-mail")
                return False
                
            # Tworzenie wiadomości
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = receiver_email
            msg["Subject"] = subject
            
            # Dodanie treści wiadomości
            msg.attach(MIMEText(message, "plain"))
            
            # Dodanie załączników
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            attachment = MIMEApplication(file.read(), _subtype="txt")
                            attachment.add_header(
                                "Content-Disposition", 
                                f"attachment; filename={os.path.basename(file_path)}"
                            )
                            msg.attach(attachment)
                    else:
                        logger.warning(f"Nie znaleziono załącznika: {file_path}")
            
            # Nawiązanie połączenia z serwerem SMTP
            context = ssl.create_default_context() if self.use_tls else None
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls(context=context)
                
                server.login(self.sender_email, self.password)
                server.send_message(msg)
            
            logger.info(f"E-mail wysłany pomyślnie do: {receiver_email}")
            return True
            
        except Exception as e:
            logger.error(f"Błąd podczas wysyłania e-maila: {str(e)}")
            return False
    
    def send_test_report(self, receiver_email, test_results, screenshot_path=None):
        """
        Wysyła raport z testu.
        
        Args:
            receiver_email (str): Adres e-mail odbiorcy
            test_results (str): Wyniki testu
            screenshot_path (str, optional): Ścieżka do zrzutu ekranu
        
        Returns:
            bool: True jeśli e-mail został wysłany pomyślnie, False w przeciwnym razie
        """
        subject = "Raport z testu Playwright"
        message = f"""
Raport z testu Playwright

{test_results}

---
Wiadomość wygenerowana automatycznie przez Tester Playwright.
        """
        
        attachments = []
        if screenshot_path and os.path.exists(screenshot_path):
            attachments.append(screenshot_path)
        
        return self.send_email(receiver_email, subject, message, attachments) 