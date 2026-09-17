@echo off
echo ===================================================
echo   Setup Automatico - Process Mining + LLM Aruba
echo ===================================================
echo.

:: Verifica se l'ambiente esiste gia'
if exist ".venv_new\Scripts\activate.bat" (
    echo [INFO] Ambiente virtuale trovato. Avvio della dashboard...
    goto run
)

echo [1/3] Creazione dell'ambiente virtuale (.venv_new)...
python -m venv .venv_new
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Impossibile creare l'ambiente virtuale. Assicurati che Python sia installato.
    pause
    exit /b %ERRORLEVEL%
)

echo [2/3] Attivazione ambiente e aggiornamento pip...
call .venv_new\Scripts\activate.bat
python -m pip install --upgrade pip

echo [3/3] Installazione delle dipendenze...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Si e' verificato un problema durante l'installazione dei pacchetti.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo   Setup completato con successo!
echo ===================================================
echo.

:run
echo Avvio della Dashboard Streamlit in corso...
call .venv_new\Scripts\activate.bat
streamlit run dashboard.py

pause
