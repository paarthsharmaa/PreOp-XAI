@echo off
REM PreOp-XAI MOVER study - one-click runner (Windows). Needs Python 3.11 or newer from python.org or Anaconda.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Creating a private Python environment in this folder ...
    py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 ( echo Could not find Python 3.11+. Install it from python.org and tick "Add to PATH". & pause & exit /b 1 )
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 ( echo Package installation failed - see the messages above. & pause & exit /b 1 )
)
.venv\Scripts\python.exe mover_run.py %*
pause
