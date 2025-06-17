@echo off
REM ── Adjust this path if your folder name differs ──
set "APP_DIR=%USERPROFILE%\Desktop\CSV_APP-main"

REM ── Switch to the app directory ──
cd /d "%APP_DIR%"

REM ── Create virtual env if missing ──
if not exist venv (
    python -m venv venv
)

REM ── Activate & install deps ──
call venv\Scripts\activate
pip install -r requirements.txt

REM ── Launch the Streamlit app ──
streamlit run "%APP_DIR%\app.py"

pause