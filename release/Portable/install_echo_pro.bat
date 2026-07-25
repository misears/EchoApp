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
if not defined ECHO_HOME if exist "%APP_ROOT%\echo_home.txt" set /p ECHO_HOME=<"%APP_ROOT%\echo_home.txt"
if not defined ECHO_HOME set "ECHO_HOME=%LOCALAPPDATA%\EchoProData"

set "TOOLS=%ECHO_HOME%\tools"
set "VENV_DIR=%ECHO_HOME%\runtime\venv"
set "MODELS_DIR=%ECHO_HOME%\models"

set "SEEDS_DIR=%APP_ROOT%\seeds"
if defined ECHO_SEEDS_DIR set "SEEDS_DIR=%ECHO_SEEDS_DIR%"

set "RVC_SOURCE=%SEEDS_DIR%\Retrieval-based-Voice-Conversion-WebUI-main"
if not exist "%RVC_SOURCE%" set "RVC_SOURCE=%SEEDS_DIR%\rvc"
set "DEMUCS_SOURCE=%SEEDS_DIR%\demucs-main"
if not exist "%DEMUCS_SOURCE%" set "DEMUCS_SOURCE=%SEEDS_DIR%\demucs"
set "FFMPEG_SOURCE=%SEEDS_DIR%\FFmpeg-master"
if not exist "%FFMPEG_SOURCE%" set "FFMPEG_SOURCE=%SEEDS_DIR%\ffmpeg"
set "ACE_SOURCE=%SEEDS_DIR%\ACE-Step-1.5-main"
if not exist "%ACE_SOURCE%" set "ACE_SOURCE=%SEEDS_DIR%\ace_step_1_5"

if defined ECHO_RVC_SEED_PATH set "RVC_SOURCE=%ECHO_RVC_SEED_PATH%"
if defined ECHO_DEMUCS_SEED_PATH set "DEMUCS_SOURCE=%ECHO_DEMUCS_SEED_PATH%"
if defined ECHO_FFMPEG_SEED_PATH set "FFMPEG_SOURCE=%ECHO_FFMPEG_SEED_PATH%"
if defined ECHO_ACE_SEED_PATH set "ACE_SOURCE=%ECHO_ACE_SEED_PATH%"

echo Action: %ACTION%
echo App root: %APP_ROOT%
echo Data root: %ECHO_HOME%
echo Seeds root: %SEEDS_DIR%

echo Creating directories...
mkdir "%ECHO_HOME%\projects" "%ECHO_HOME%\voices" "%ECHO_HOME%\generated" 2>nul
mkdir "%TOOLS%" 2>nul
mkdir "%ECHO_HOME%\runtime" 2>nul
mkdir "%MODELS_DIR%" 2>nul

call :ensure_ffmpeg
if errorlevel 1 goto :fail

call :ensure_python
if errorlevel 1 goto :fail

call :ensure_demucs
if errorlevel 1 goto :fail

call :ensure_rvc_model
if errorlevel 1 goto :fail

call :ensure_ace_step_15
if errorlevel 1 goto :fail

echo.
echo Dependencies are ready.
echo ffmpeg: %TOOLS%\ffmpeg\current\bin\ffmpeg.exe
echo demucs: %VENV_DIR%\Scripts\demucs.exe
echo rvc: %MODELS_DIR%\rvc\current
echo ace-step-1.5: %MODELS_DIR%\ace_step_1_5\current
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
"%PY_CMD%" -m pip install --upgrade setuptools wheel hatchling
if errorlevel 1 (
    echo Failed to install local Python build tooling.
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

set "FFMPEG_ROOT=%TOOLS%\ffmpeg"
if exist "%FFMPEG_SOURCE%" (
    echo Found ffmpeg seed assets: %FFMPEG_SOURCE%
    set "FFMPEG_SEED_ROOT="
    if exist "%FFMPEG_SOURCE%\bin\ffmpeg.exe" (
        set "FFMPEG_SEED_ROOT=%FFMPEG_SOURCE%"
    ) else (
        for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$seed=$env:FFMPEG_SOURCE; $bin=Get-ChildItem -Path $seed -Recurse -Filter ffmpeg.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1; if ($bin) { Split-Path $bin.DirectoryName -Parent }"`) do set "FFMPEG_SEED_ROOT=%%I"
    )

    if defined FFMPEG_SEED_ROOT (
        mkdir "%FFMPEG_ROOT%" 2>nul
        if exist "%FFMPEG_ROOT%\current" rmdir /s /q "%FFMPEG_ROOT%\current"
        xcopy /E /I /Y "%FFMPEG_SEED_ROOT%" "%FFMPEG_ROOT%\current\" >nul
        if errorlevel 1 (
            echo Failed to copy ffmpeg seed assets from %FFMPEG_SEED_ROOT%.
            exit /b 1
        )
        if exist "%FFMPEG_ROOT%\current\bin\ffmpeg.exe" (
            echo ffmpeg ready from seeds: %FFMPEG_ROOT%\current\bin\ffmpeg.exe
            exit /b 0
        )
        echo Copied ffmpeg seed assets, but ffmpeg.exe was not found under bin.
        echo Falling back to the bundled download path.
        goto download_ffmpeg
    )
    echo ffmpeg seed folder was found but no ffmpeg.exe could be discovered.
    echo Falling back to the bundled download path.
)

:download_ffmpeg
echo Downloading portable ffmpeg build...
set "FFMPEG_ZIP=%TEMP%\ffmpeg-release-essentials-%RANDOM%%RANDOM%.zip"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $zip=$env:FFMPEG_ZIP; $root=$env:FFMPEG_ROOT; New-Item -ItemType Directory -Force -Path $root | Out-Null; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $root -Force; Remove-Item $zip -Force -ErrorAction SilentlyContinue;"
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
if exist "%DEMUCS_SOURCE%" (
    echo Found demucs seed assets: %DEMUCS_SOURCE%
    echo Installing demucs from bundled seed source...
    if /I "%ACTION%"=="update" (
        "%PY_CMD%" -m pip install --upgrade --no-build-isolation "%DEMUCS_SOURCE%"
    ) else (
        "%PY_CMD%" -m pip install --no-build-isolation "%DEMUCS_SOURCE%"
    )
) else (
    if /I "%ACTION%"=="update" (
        "%PY_CMD%" -m pip install --upgrade demucs
    ) else (
        "%PY_CMD%" -m pip install demucs
    )
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

:ensure_rvc_model
echo.
echo Installing RVC reference model...
if not exist "%RVC_SOURCE%" (
    echo RVC seed folder not found locally, downloading upstream source...
    set "RVC_ZIP=%TEMP%\rvc-webui.zip"
    set "RVC_MODEL_URL=%RVC_MODEL_URL%"
    if "%RVC_MODEL_URL%"=="" set "RVC_MODEL_URL=https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/archive/refs/heads/main.zip"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $url=$env:RVC_MODEL_URL; $zip=$env:RVC_ZIP; $target=$env:MODELS_DIR + '\rvc'; Invoke-WebRequest -Uri $url -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $target -Force;"
    if errorlevel 1 (
        echo Could not download RVC source from %RVC_MODEL_URL%.
        echo Set RVC_MODEL_URL to a valid downloadable ZIP and rerun install.
        exit /b 1
    )
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$target=Join-Path $env:MODELS_DIR 'rvc'; $folder=Get-ChildItem -Path $target -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($folder) { $folder.FullName }"`) do set "RVC_LATEST=%%I"
    if not defined RVC_LATEST (
        echo RVC assets extracted but no folder was found.
        exit /b 1
    )
    if exist "%MODELS_DIR%\rvc\current" rmdir /s /q "%MODELS_DIR%\rvc\current"
    mklink /D "%MODELS_DIR%\rvc\current" "%RVC_LATEST%" >nul 2>&1
    if errorlevel 1 (
        xcopy /E /I /Y "%RVC_LATEST%" "%MODELS_DIR%\rvc\current\" >nul
    )
    echo RVC ready from download: %MODELS_DIR%\rvc\current
    exit /b 0
)

set "RVC_TARGET=%MODELS_DIR%\rvc"
mkdir "%RVC_TARGET%" 2>nul
if exist "%RVC_TARGET%\current" rmdir /s /q "%RVC_TARGET%\current"
xcopy /E /I /Y "%RVC_SOURCE%" "%RVC_TARGET%\current\" >nul
if errorlevel 1 (
    echo Failed to copy RVC assets from %RVC_SOURCE%.
    exit /b 1
)
echo RVC ready: %RVC_TARGET%\current
exit /b 0

:ensure_ace_step_15
echo.
echo Installing ACE Step 1.5 model assets...
set "ACE_TARGET=%MODELS_DIR%\ace_step_1_5"
set "ACE_ZIP=%TEMP%\ace-step-1.5.zip"
mkdir "%ACE_TARGET%" 2>nul

if exist "%ACE_TARGET%\current" (
    echo ACE Step 1.5 already present.
    exit /b 0
)

if exist "%ACE_SOURCE%" (
    echo Found ACE Step 1.5 seed assets: %ACE_SOURCE%
    if exist "%ACE_TARGET%\current" rmdir /s /q "%ACE_TARGET%\current"
    xcopy /E /I /Y "%ACE_SOURCE%" "%ACE_TARGET%\current\" >nul
    if errorlevel 1 (
        echo Failed to copy ACE Step seed assets from %ACE_SOURCE%.
        exit /b 1
    )
    echo ACE Step 1.5 ready from seeds: %ACE_TARGET%\current
    exit /b 0
)

set "ACE_MODEL_URL=%ACE_STEP15_MODEL_URL%"
if "%ACE_MODEL_URL%"=="" set "ACE_MODEL_URL=https://huggingface.co/ace-step/ace-step-1.5/resolve/main/ace-step-1.5.zip"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $url=$env:ACE_MODEL_URL; $zip=$env:ACE_ZIP; $target=$env:ACE_TARGET; Invoke-WebRequest -Uri $url -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $target -Force;"
if errorlevel 1 (
    echo Could not download ACE Step 1.5 from %ACE_MODEL_URL%.
    echo Set ACE_STEP15_MODEL_URL to a valid downloadable ZIP and rerun install.
    exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$target=$env:ACE_TARGET; $folder=Get-ChildItem -Path $target -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($folder) { $folder.FullName }"`) do set "ACE_LATEST=%%I"
if not defined ACE_LATEST (
    echo ACE assets extracted but no folder was found.
    exit /b 1
)

mklink /D "%ACE_TARGET%\current" "%ACE_LATEST%" >nul 2>&1
if errorlevel 1 (
    xcopy /E /I /Y "%ACE_LATEST%" "%ACE_TARGET%\current\" >nul
)
echo ACE Step 1.5 ready: %ACE_TARGET%\current
exit /b 0
