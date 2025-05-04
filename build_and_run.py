#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess
import argparse

def generate_icon():
    """Generuje ikonę aplikacji."""
    try:
        import generate_icon
        print("Generuję ikonę aplikacji...")
        generate_icon.generate_app_icon()
        print("Ikona została wygenerowana pomyślnie.")
    except Exception as e:
        print(f"Błąd podczas generowania ikony: {e}")
        return False
    return True

def build_app(use_spec=True, debug=False):
    """Buduje aplikację używając PyInstaller."""
    print("Rozpoczynam proces budowania aplikacji...")
    
    # Sprawdź czy PyInstaller jest zainstalowany
    try:
        import PyInstaller
        print(f"Znaleziono PyInstaller w wersji {PyInstaller.__version__}")
    except ImportError:
        print("Instaluję PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Generuj ikonę, jeśli nie istnieje
    if not os.path.exists("app/resources/icon.ico"):
        if not generate_icon():
            print("Kontynuuję bez ikony...")
    
    # Wybierz komendę do budowania
    if use_spec:
        cmd = ["pyinstaller", "fakturator.spec"]
    else:
        cmd = ["python", "build.py"]
    
    if debug:
        cmd.append("--debug")
    
    print(f"Uruchamiam: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("Aplikacja została zbudowana pomyślnie!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Błąd podczas budowania aplikacji: {e}")
        return False

def run_app():
    """Uruchamia zbudowaną aplikację."""
    print("Uruchamiam aplikację...")
    
    # Określ ścieżkę do pliku wykonywalnego
    if platform.system() == "Windows":
        exe_path = os.path.join("dist", "Fakturator_e-urtica.exe")
    elif platform.system() == "Darwin":  # macOS
        exe_path = os.path.join("dist", "Fakturator_e-urtica.app")
    else:  # Linux
        exe_path = os.path.join("dist", "Fakturator_e-urtica")
    
    if not os.path.exists(exe_path):
        print(f"Nie znaleziono pliku wykonywalnego: {exe_path}")
        return False
    
    try:
        if platform.system() == "Windows":
            subprocess.Popen([exe_path])
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", exe_path])
        else:  # Linux
            subprocess.Popen([exe_path])
        print("Aplikacja została uruchomiona.")
        return True
    except Exception as e:
        print(f"Błąd podczas uruchamiania aplikacji: {e}")
        return False

def main():
    """Główna funkcja skryptu."""
    parser = argparse.ArgumentParser(description="Budowanie i uruchamianie aplikacji Fakturator e-urtica")
    parser.add_argument("--build", action="store_true", help="Tylko zbuduj aplikację")
    parser.add_argument("--run", action="store_true", help="Tylko uruchom aplikację")
    parser.add_argument("--debug", action="store_true", help="Buduj w trybie debug (więcej informacji)")
    parser.add_argument("--no-spec", action="store_true", help="Nie używaj pliku spec, użyj build.py")
    
    args = parser.parse_args()
    
    # Domyślnie buduj i uruchamiaj, jeśli nie podano specyficznej opcji
    if not (args.build or args.run):
        args.build = True
        args.run = True
    
    success = True
    
    if args.build:
        success = build_app(use_spec=not args.no_spec, debug=args.debug)
    
    if args.run and success:
        run_app()

if __name__ == "__main__":
    main() 