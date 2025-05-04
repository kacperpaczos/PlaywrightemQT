#!/bin/bash

# Kolory dla lepszej czytelności
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funkcja do wyświetlania nagłówków
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Funkcja do wyświetlania komunikatów o sukcesie
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Funkcja do wyświetlania komunikatów o błędach
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Funkcja do wyświetlania ostrzeżeń
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Funkcja do sprawdzania czy komenda się powiodła
check_command() {
    if [ $? -eq 0 ]; then
        print_success "$1"
        return 0
    else
        print_error "$2"
        return 1
    fi
}

# Funkcja do sprawdzania czy środowisko wirtualne istnieje
check_venv() {
    if [ ! -d ".venv" ]; then
        print_warning "Środowisko wirtualne nie istnieje. Tworzenie..."
        python3 -m venv .venv
        check_command "Środowisko wirtualne utworzone" "Błąd podczas tworzenia środowiska wirtualnego"
    fi
}

# Funkcja do aktywacji środowiska wirtualnego
activate_venv() {
    source .venv/bin/activate
    check_command "Środowisko wirtualne aktywowane" "Błąd podczas aktywacji środowiska wirtualnego"
}

# Funkcja do instalacji zależności
install_dependencies() {
    print_header "Instalacja zależności"
    pip install -r requirements.txt
    check_command "Zależności zainstalowane" "Błąd podczas instalacji zależności"
}

# Funkcja do uruchamiania aplikacji w trybie deweloperskim
run_dev() {
    print_header "Uruchamianie aplikacji w trybie deweloperskim"
    python -m app.main
    check_command "Aplikacja uruchomiona" "Błąd podczas uruchamiania aplikacji"
}

# Funkcja do budowania aplikacji
build_app() {
    print_header "Budowanie aplikacji"
    python -m scripts.build_app
    check_command "Aplikacja zbudowana" "Błąd podczas budowania aplikacji"
}

# Funkcja do czyszczenia projektu
clean_project() {
    print_header "Czyszczenie projektu"
    
    # Lista katalogów i plików do usunięcia
    items_to_remove=(
        ".venv"
        "__pycache__"
        "*.pyc"
        "*.pyo"
        "*.pyd"
        "*.so"
        "build"
        "dist"
        "*.egg-info"
        ".pytest_cache"
        ".coverage"
        "htmlcov"
        "*.log"
        "logs"
        "hooks"
        "tests"
        "PlaywrightTester.spec"
        "run.py"
    )
    
    # Potwierdzenie przed usunięciem
    print_warning "UWAGA: Ta operacja usunie wszystkie pliki tymczasowe, środowisko wirtualne oraz niepotrzebne katalogi!"
    print_warning "Zostaną tylko pliki niezbędne do funkcjonowania aplikacji:"
    print_warning "- app/"
    print_warning "- config/"
    print_warning "- requirements.txt"
    print_warning "- README.md"
    print_warning "- run.sh"
    print_warning "- run.ps1"
    print_warning "- scripts/build_app.py"
    print_warning "- scripts/runtime_hook.py"
    print_warning "- fakturator.spec"
    read -p "Czy na pewno chcesz kontynuować? (t/N): " confirm
    
    if [[ $confirm == [tT] ]]; then
        # Tworzenie kopii plików do zachowania
        print_warning "Tworzenie kopii zapasowych ważnych plików..."
        mkdir -p temp_backup/scripts

        # Kopiowanie ważnych plików
        if [ -f "fakturator.spec" ]; then
            cp "fakturator.spec" temp_backup/
        fi
        
        if [ -f "scripts/build_app.py" ]; then
            cp "scripts/build_app.py" temp_backup/scripts/
        fi
        
        if [ -f "scripts/runtime_hook.py" ]; then
            cp "scripts/runtime_hook.py" temp_backup/scripts/
        fi
        
        # Usuwanie plików i katalogów
        for item in "${items_to_remove[@]}"; do
            find . -name "$item" -exec rm -rf {} + 2>/dev/null
        done
        
        # Usuwanie plików .DS_Store (tylko dla macOS)
        find . -name ".DS_Store" -delete 2>/dev/null
        
        # Usuwanie plików z katalogu logs, ale zachowanie struktury katalogów
        if [ -d "logs" ]; then
            find logs -type f -delete
        fi
        
        # Przywracanie ważnych plików
        print_warning "Przywracanie ważnych plików..."
        mkdir -p scripts
        
        # Przywracanie plików
        if [ -f "temp_backup/fakturator.spec" ]; then
            cp "temp_backup/fakturator.spec" ./
        fi
        
        if [ -f "temp_backup/scripts/build_app.py" ]; then
            cp "temp_backup/scripts/build_app.py" scripts/
        fi
        
        if [ -f "temp_backup/scripts/runtime_hook.py" ]; then
            cp "temp_backup/scripts/runtime_hook.py" scripts/
        fi
        
        # Usuwanie kopii zapasowej
        rm -rf temp_backup
        
        print_success "Projekt wyczyszczony"
    else
        print_warning "Operacja anulowana"
    fi
}

# Funkcja do wyświetlania menu
show_menu() {
    clear
    print_header "Playwright Tester - Menu główne"
    echo "1. Uruchom aplikację w trybie deweloperskim"
    echo "2. Zbuduj aplikację"
    echo "3. Wyczyść projekt"
    echo "4. Wyjdź"
    echo -e "\nWybierz opcję (1-4): "
}

# Główna pętla programu
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1)
            check_venv
            activate_venv
            install_dependencies
            run_dev
            ;;
        2)
            check_venv
            activate_venv
            install_dependencies
            build_app
            ;;
        3)
            clean_project
            ;;
        4)
            print_header "Do widzenia!"
            exit 0
            ;;
        *)
            print_error "Nieprawidłowy wybór. Spróbuj ponownie."
            ;;
    esac
    
    echo -e "\nNaciśnij Enter, aby kontynuować..."
    read -r
done 