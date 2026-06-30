@echo off
setlocal

echo === Echo Pro - Data Setup ===

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install from https://www.python.org/downloads/windows/
    pause
    exit /b
)

set ECHO=%APPDATA%\EchoPro

echo Creating directories...
mkdir "%ECHO%\projects" "%ECHO%\voices" "%ECHO%\generated" 2>nul

echo Echo Pro data root is at: %ECHO%
pause