@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv_new\Scripts\python.exe" (
    call setup_and_run.bat
    exit /b
)
.venv_new\Scripts\python.exe -m streamlit run dashboard.py
if errorlevel 1 (
    echo Esegui setup_and_run.bat per installare o aggiornare le dipendenze.
    pause
    exit /b 1
)
