# -*- coding: utf-8 -*-
# Runtime hook dla PyInstaller

import os
import sys

# Dodaj ścieżkę do katalogu bieżącego na początek sys.path
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Upewnij się, że ipaddress jest dostępny
try:
    import ipaddress
except ImportError:
    sys.stderr.write("OSTRZEŻENIE: Nie można zaimportować 'ipaddress'. Próba naprawy...\n")
    # Dodaj ścieżkę do base_library.zip
    if hasattr(sys, '_MEIPASS'):
        sys.path.append(os.path.join(sys._MEIPASS, 'base_library.zip'))
