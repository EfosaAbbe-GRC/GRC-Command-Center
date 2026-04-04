@echo off
title GRC Command Center
color 0A
cls

echo ========================================================
echo   GRC COMMAND CENTER
echo   Starting Frontend Dashboard...
echo ========================================================
echo.

cd /d "%~dp0"

:: Check if node_modules exists, if not install dependencies
if not exist "node_modules" (
    echo [System] First run detected. Installing dependencies...
    call npm install
)

echo [System] Launching Dashboard...
npm run dev

pause
