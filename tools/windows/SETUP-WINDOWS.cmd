@echo off
rem Rainbow tools - Windows setup. Double-click this file and answer Yes to the admin prompt.
rem Safe to run again any time; it skips what is already installed and re-runs the tests.
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
echo.
echo Log saved to %~dp0setup_log.txt
pause
