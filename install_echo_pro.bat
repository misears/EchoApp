@echo off
setlocal

echo === Echo Pro Dependency Manager ===

setlocal EnableExtensions EnableDelayedExpansion

set "ACTION=%~1"
if /I "%ACTION%"=="" set "ACTION=install"
if /I not "%ACTION%"=="install" if /I not "%ACTION%"=="update" (
    echo Usage: %~nx0 [install^|update]
    exit /b 1
)

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "ECHO_HOME=%ECHO_PRO_HOME%"
if not defined ECHO_HOME set "ECHO_HOME=%APPDATA%\EchoPro"

set "TOOLS=%APP_ROOT%\tools"
set "VENV_DIR=%APP_ROOT%\runtime\venv"

echo Action: %ACTION%
echo App root: %APP_ROOT%
echo Data root: %ECHO_HOME%

echo Creating directories...
mkdir "%ECHO_HOME%\projects" "%ECHO_HOME%\voices" "%ECHO_HOME%\generated" 2>nul
mkdir "%TOOLS%" 2>nul

call :ensure_ffmpeg
if errorlevel 1 goto :fail

call :ensure_python
if errorlevel 1 goto :fail

call :ensure_demucs
if errorlevel 1 goto :fail

echo.
echo Dependencies are ready.
echo ffmpeg: %TOOLS%\ffmpeg\current\bin\ffmpeg.exe
echo demucs: %VENV_DIR%\Scripts\demucs.exe
echo.
echo Tip: Use EchoPro_Portable.bat for portable launches.
exit /b 0

:fail
echo Dependency setup failed. See messages above.
exit /b 1

:ensure_python
set "PY_CMD="
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PY_CMD=%VENV_DIR%\Scripts\python.exe"
    echo Using existing runtime Python: %PY_CMD%
    exit /b 0
)

set "SYSTEM_PY="
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.10"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 set "SYSTEM_PY=python"
)

if not defined SYSTEM_PY (
    echo Python 3.10+ not found.
    echo Install Python, then run this script again.
    echo Suggested command: winget install Python.Python.3.10
    exit /b 1
)

echo Creating local runtime venv...
%SYSTEM_PY% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo Failed creating virtual environment.
    exit /b 1
)

set "PY_CMD=%VENV_DIR%\Scripts\python.exe"
"%PY_CMD%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip in local runtime.
    exit /b 1
)
exit /b 0

:ensure_ffmpeg
echo.
echo Checking ffmpeg...
set "FFMPEG_EXE=%TOOLS%\ffmpeg\current\bin\ffmpeg.exe"
if exist "%FFMPEG_EXE%" (
    echo ffmpeg already available locally.
    exit /b 0
)

echo Downloading portable ffmpeg build...
set "FFMPEG_ROOT=%TOOLS%\ffmpeg"
set "FFMPEG_ZIP=%TEMP%\ffmpeg-release-essentials.zip"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $zip=$env:FFMPEG_ZIP; $root=$env:FFMPEG_ROOT; New-Item -ItemType Directory -Force -Path $root | Out-Null; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $root -Force;"
if errorlevel 1 (
    echo Failed to download or extract ffmpeg.
    exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=$env:FFMPEG_ROOT; $folder=Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -like 'ffmpeg-*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($folder) { Join-Path $folder.FullName 'bin' }"`) do set "FFMPEG_BIN=%%I"

if not defined FFMPEG_BIN (
    echo Could not locate ffmpeg bin folder after extraction.
    exit /b 1
)

if not exist "%FFMPEG_BIN%\ffmpeg.exe" (
    echo ffmpeg.exe not found in %FFMPEG_BIN%.
    exit /b 1
)

if exist "%FFMPEG_ROOT%\current" rmdir /s /q "%FFMPEG_ROOT%\current"
mklink /D "%FFMPEG_ROOT%\current" "%FFMPEG_BIN%\.." >nul 2>&1
if errorlevel 1 (
    xcopy /E /I /Y "%FFMPEG_BIN%\.." "%FFMPEG_ROOT%\current\" >nul
)

echo ffmpeg ready: %FFMPEG_ROOT%\current\bin\ffmpeg.exe
exit /b 0

:ensure_demucs
echo.
echo Installing/updating demucs in local runtime...
if /I "%ACTION%"=="update" (
    "%PY_CMD%" -m pip install --upgrade demucs
) else (
    "%PY_CMD%" -m pip install demucs
)
if errorlevel 1 (
    echo Failed to install demucs.
    exit /b 1
)
if not exist "%VENV_DIR%\Scripts\demucs.exe" (
    echo demucs executable was not found in local runtime.
    exit /b 1
)

echo demucs ready: %VENV_DIR%\Scripts\demucs.exe
exit /b 0