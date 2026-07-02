@echo off
setlocal

echo === Echo Pro - Environment Setup ===

setlocal EnableExtensions EnableDelayedExpansion

set "PY_CMD="
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.10"
) else (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo Python not found. Install from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    set "PY_CMD=python"
)

echo Using interpreter: %PY_CMD%

set ECHO=%APPDATA%\EchoPro
set TOOLS=%LOCALAPPDATA%\EchoPro\tools

echo Creating directories...
mkdir "%ECHO%\projects" "%ECHO%\voices" "%ECHO%\generated" 2>nul
mkdir "%TOOLS%" 2>nul

call :ensure_ffmpeg
if errorlevel 1 goto :fail

call :ensure_demucs
if errorlevel 1 goto :fail

echo Echo Pro data root is at: %ECHO%
echo Environment setup complete.
exit /b 0

:fail
echo Setup failed. See messages above.
exit /b 1

:ensure_ffmpeg
echo.
echo Checking ffmpeg...
set "FFMPEG_EXE="
set "FFMPEG_BIN="

where ffmpeg >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where ffmpeg') do (
        set "FFMPEG_EXE=%%I"
        goto :ffmpeg_found
    )
)

echo ffmpeg not found. Downloading portable ffmpeg build...
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

set "FFMPEG_EXE=%FFMPEG_BIN%\ffmpeg.exe"

:ffmpeg_found
for %%I in ("%FFMPEG_EXE%") do set "FFMPEG_BIN=%%~dpI"
if "%FFMPEG_BIN:~-1%"=="\" set "FFMPEG_BIN=%FFMPEG_BIN:~0,-1%"

call :add_to_path "%FFMPEG_BIN%"
if errorlevel 1 exit /b 1

echo ffmpeg ready: %FFMPEG_EXE%
exit /b 0

:ensure_demucs
echo.
echo Checking demucs...
set "DEMUCS_EXE="
set "DEMUCS_DIR="

where demucs >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where demucs') do (
        set "DEMUCS_EXE=%%I"
        goto :demucs_found
    )
)

echo demucs not found. Installing with pip...
%PY_CMD% -m pip install --upgrade demucs
if errorlevel 1 (
    echo Failed to install demucs.
    exit /b 1
)

where demucs >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where demucs') do (
        set "DEMUCS_EXE=%%I"
        goto :demucs_found
    )
)

for /f "usebackq delims=" %%I in (`%PY_CMD% -m site --user-base`) do set "PY_USER_BASE=%%I"
if defined PY_USER_BASE if exist "%PY_USER_BASE%\Scripts\demucs.exe" set "DEMUCS_EXE=%PY_USER_BASE%\Scripts\demucs.exe"

if not defined DEMUCS_EXE (
    echo demucs was installed but executable could not be located.
    exit /b 1
)

:demucs_found
for %%I in ("%DEMUCS_EXE%") do set "DEMUCS_DIR=%%~dpI"
if "%DEMUCS_DIR:~-1%"=="\" set "DEMUCS_DIR=%DEMUCS_DIR:~0,-1%"

call :add_to_path "%DEMUCS_DIR%"
if errorlevel 1 exit /b 1

echo demucs ready: %DEMUCS_EXE%
exit /b 0

:add_to_path
set "TARGET_DIR=%~1"
if not exist "%TARGET_DIR%" (
    echo Cannot add missing directory to PATH: %TARGET_DIR%
    exit /b 1
)

echo Adding to current session PATH: %TARGET_DIR%
set "PATH=%PATH%;%TARGET_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $target=$env:TARGET_DIR; $current=[Environment]::GetEnvironmentVariable('Path','User'); $items=@(); if ($current) { $items=$current -split ';' | Where-Object { $_ -and $_.Trim() } }; $normalized=@($items | ForEach-Object { $_.TrimEnd('\') }); if ($normalized -notcontains $target.TrimEnd('\')) { $items += $target }; $newPath=($items | Select-Object -Unique) -join ';'; [Environment]::SetEnvironmentVariable('Path',$newPath,'User')"
if errorlevel 1 (
    echo Failed to persist PATH update for: %TARGET_DIR%
    exit /b 1
)

exit /b 0