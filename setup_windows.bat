@echo off
setlocal
cd /d "%~dp0"
if exist ".python\python.exe" (
  set "ASSISTANT_PYTHON=%~dp0.python\python.exe"
  goto create_env
)
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Keep the .python folder beside this file.
  goto failed
)
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 goto failed
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto failed
goto install
:create_env
if not exist ".venv\Scripts\python.exe" "%ASSISTANT_PYTHON%" -m venv .venv
if errorlevel 1 goto failed
:install
if not exist ".install-temp" mkdir ".install-temp"
set "TEMP=%~dp0.install-temp"
set "TMP=%~dp0.install-temp"
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto failed
rem Account mode: no API key or .env setup required.
echo.
echo Setup complete. Uses your ChatGPT login in Codex. Double-click start.bat.
if /i not "%~1"=="--no-pause" pause
exit /b 0
:failed
echo [ERROR] Setup failed. Please share the error above.
if /i not "%~1"=="--no-pause" pause
exit /b 1