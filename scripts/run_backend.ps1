Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "backend")
& ..\.venv\Scripts\python.exe run.py
