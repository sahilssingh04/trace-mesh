@echo off
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
 echo Python 3.12 is required for this tested setup.
 echo Install it: winget install --exact --id Python.Python.3.12
 echo Then reopen this launcher.
 pause
 exit /b 1
)
if exist .venv\Scripts\python.exe (
 .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)"
 if errorlevel 1 (
  echo Existing .venv uses a different Python version.
  echo Close all project windows, rename .venv to .venv-backup, and rerun.
  pause
  exit /b 1
 )
)
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python scripts\bootstrap.py
if errorlevel 1 goto fail
.venv\Scripts\python scripts\seed_demo.py
if errorlevel 1 goto fail
start "Evidence Weave worker" .venv\Scripts\python -m app.worker
echo Open http://127.0.0.1:8000 and use the owner key from secrets\users.json
.venv\Scripts\python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
goto :eof
:fail
echo Setup failed. Read the error above.
pause
exit /b 1
