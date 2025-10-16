# Script per configurare l'ambiente virtuale Python
# Esegui con: .\setup_venv.ps1

Write-Host "Creazione ambiente virtuale..." -ForegroundColor Green

# Crea venv se non esiste
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "Ambiente virtuale creato." -ForegroundColor Green
} else {
    Write-Host "Ambiente virtuale già esistente." -ForegroundColor Yellow
}

# Attiva venv
Write-Host "Attivazione ambiente virtuale..." -ForegroundColor Green
.\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Aggiornamento pip..." -ForegroundColor Green
python -m pip install --upgrade pip

# Installa dipendenze
Write-Host "Installazione dipendenze..." -ForegroundColor Green
pip install -r requirements.txt

Write-Host "`nConfigurazione completata!" -ForegroundColor Green
Write-Host "Per attivare l'ambiente in futuro, esegui: .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan



