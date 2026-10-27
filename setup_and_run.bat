@echo off
setlocal
cd /d "%~dp0"
echo Setup Process Mining + LLM Aruba
if not exist ".venv_new\Scripts\python.exe" (
    python -m venv .venv_new
    if errorlevel 1 goto fail
)
.venv_new\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv_new\Scripts\python.exe -m streamlit run dashboard.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo [ERRORE] Setup o avvio fallito. Verifica Python 3.10+ e il messaggio precedente.
pause
exit /b 1
