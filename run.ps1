# Kolory dla lepszej czytelności
$RED = [System.ConsoleColor]::Red
$GREEN = [System.ConsoleColor]::Green
$YELLOW = [System.ConsoleColor]::Yellow
$BLUE = [System.ConsoleColor]::Blue

# Funkcja do wyświetlania nagłówków
function Print-Header {
    param($text)
    Write-Host "`n========================================" -ForegroundColor $BLUE
    Write-Host $text -ForegroundColor $BLUE
    Write-Host "========================================`n" -ForegroundColor $BLUE
}

# Funkcja do wyświetlania komunikatów o sukcesie
function Print-Success {
    param($text)
    Write-Host "✓ $text" -ForegroundColor $GREEN
}

# Funkcja do wyświetlania komunikatów o błędach
function Print-Error {
    param($text)
    Write-Host "âś— $text" -ForegroundColor $RED
}

# Funkcja do wyświetlania ostrzeń
function Print-Warning {
    param($text)
    Write-Host "âš  $text" -ForegroundColor $YELLOW
}

# Funkcja do sprawdzania czy komenda się powiodła
function Check-Command {
    param($successMessage, $errorMessage)
    if ($LASTEXITCODE -eq 0) {
        Print-Success $successMessage
        return $true
    } else {
        Print-Error $errorMessage
        return $false
    }
}

# Funkcja do sprawdzania czy środowisko wirtualne istnieje
function Check-Venv {
    if (-not (Test-Path ".venv")) {
        Print-Warning "Środowisko wirtualne nie istnieje. Tworzenie..."
        python -m venv .venv
        Check-Command "Środowisko wirtualne utworzone" "Błąd podczas tworzenia środowiska wirtualnego"
    }
}

# Funkcja do aktywacji środowiska wirtualnego
function Activate-Venv {
    & .\.venv\Scripts\Activate.ps1
    Check-Command "Środowisko wirtualne aktywowane" "Błąd podczas aktywacji środowiska wirtualnego"
}

# Funkcja do instalacji zależności
function Install-Dependencies {
    Print-Header "Instalacja zależności"
    pip install -r requirements.txt
    Check-Command "Zależności zainstalowane" "Błąd podczas instalacji zależności"
}

# Funkcja do uruchamiania aplikacji w trybie deweloperskim
function Run-Dev {
    Print-Header "Uruchamianie aplikacji w trybie deweloperskim"
    python -m app.main
    Check-Command "Aplikacja uruchomiona" "Błąd podczas uruchamiania aplikacji"
}

# Funkcja do budowania aplikacji
function Build-App {
    Print-Header "Budowanie aplikacji"
    python -m scripts.build_app
    Check-Command "Aplikacja zbudowana" "Błąd podczas budowania aplikacji"
}

# Funkcja do czyszczenia projektu
function Clean-Project {
    Print-Header "Czyszczenie projektu"
    
    # Lista katalogów i plików do usunięcia
    $itemsToRemove = @(
        ".venv",
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "build",
        "dist",
        "*.egg-info",
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        "*.log",
        "logs",
        "hooks",
        "tests",
        "PlaywrightTester.spec",
        "run.py"
    )
    
    # Potwierdzenie przed usunięciem
    Print-Warning "UWAGA: Ta operacja usunie wszystkie pliki tymczasowe, środowisko wirtualne oraz niepotrzebne katalogi!"
    Print-Warning "Zostaną tylko pliki niezbędne do funkcjonowania aplikacji:"
    Print-Warning "- app/"
    Print-Warning "- config/"
    Print-Warning "- requirements.txt"
    Print-Warning "- README.md"
    Print-Warning "- run.sh"
    Print-Warning "- run.ps1"
    $confirm = Read-Host "Czy na pewno chcesz kontynuować? (t/N)"
    
    if ($confirm -eq "t" -or $confirm -eq "T") {
        # Usuwanie plików i katalogów
        foreach ($item in $itemsToRemove) {
            Get-ChildItem -Path . -Include $item -Recurse -Force | Remove-Item -Recurse -Force
        }
        
        # Usuwanie plików z katalogu logs, ale zachowanie struktury katalogów
        if (Test-Path "logs") {
            Get-ChildItem -Path "logs" -File | Remove-Item -Force
        }
        
        Print-Success "Projekt wyczyszczony"
    } else {
        Print-Warning "Operacja anulowana"
    }
}

# Funkcja do wyświetlania menu
function Show-Menu {
    Clear-Host
    Print-Header "Playwright Tester - Menu główne"
    Write-Host "1. Uruchom aplikację w trybie deweloperskim"
    Write-Host "2. Zbuduj aplikację"
    Write-Host "3. Wyczyść projekt"
    Write-Host "4. Wyjdź"
    Write-Host "`nWybierz opcję (1-4): "
}

# Główna pętla programu
while ($true) {
    Show-Menu
    $choice = Read-Host
    
    switch ($choice) {
        "1" {
            Check-Venv
            Activate-Venv
            Install-Dependencies
            Run-Dev
        }
        "2" {
            Check-Venv
            Activate-Venv
            Install-Dependencies
            Build-App
        }
        "3" {
            Clean-Project
        }
        "4" {
            Print-Header "Do widzenia!"
            exit 0
        }
        default {
            Print-Error "Nieprawidłowy wybór. Spróbuj ponownie."
        }
    }
    
    Write-Host "`nNaciśnij Enter, aby kontynuować..."
    Read-Host
} 