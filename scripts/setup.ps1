# One-time setup. Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env; Write-Host "Created backend\.env - EDIT IT (SQL_SERVER, TESSERACT_PATH) before continuing." -ForegroundColor Yellow }
Push-Location frontend; npm install; Pop-Location
Write-Host "`nSetup finished. Next: edit backend\.env, then run scripts\check_environment.py" -ForegroundColor Green
