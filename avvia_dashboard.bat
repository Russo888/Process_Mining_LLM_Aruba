@echo off
echo ============================================
echo   CASAS Aruba - Process Mining + AI
echo ============================================
echo.
echo Avvio dashboard Streamlit...
echo.
call .venv_new\Scripts\activate.bat
streamlit run dashboard.py
pause
