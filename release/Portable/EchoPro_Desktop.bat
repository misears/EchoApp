@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "ECHO_PRO_HOME="
if exist "%APP_ROOT%\echo_home.txt" (
    set /p ECHO_PRO_HOME=<"%APP_ROOT%\echo_home.txt"
)
if not defined ECHO_PRO_HOME set "ECHO_PRO_HOME=%LOCALAPPDATA%\EchoProData"

set "PATH=%ECHO_PRO_HOME%\tools\ffmpeg\current\bin;%ECHO_PRO_HOME%\runtime\venv\Scripts;%PATH%"
set "HF_HOME=%ECHO_PRO_HOME%\runtime\hf_cache"
set "TORCH_HOME=%ECHO_PRO_HOME%\runtime\torch_cache"
set "ECHO_RVC_MODEL_PATH=%ECHO_PRO_HOME%\models\rvc\current"
set "ECHO_ACE_MODEL_PATH=%ECHO_PRO_HOME%\models\ace_step_1_5\current"

set "NEEDS_BOOTSTRAP="
if not exist "%ECHO_PRO_HOME%\tools\ffmpeg\current\bin\ffmpeg.exe" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\runtime\venv\Scripts\demucs.exe" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\demucs\htdemucs.ready" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\rvc\current" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\ace_step_1_5\current" set "NEEDS_BOOTSTRAP=1"

mkdir "%ECHO_PRO_HOME%\projects" "%ECHO_PRO_HOME%\voices" "%ECHO_PRO_HOME%\generated" 2>nul

if not exist "%APP_ROOT%\EchoPro.exe" (
    echo EchoPro.exe not found in %APP_ROOT%
    exit /b 1
)

if defined NEEDS_BOOTSTRAP (
    echo Setting up Echo Pro dependencies before launch...
    call "%APP_ROOT%\install_echo_pro.bat" install
    if errorlevel 1 (
        echo Echo Pro could not start because dependency setup failed.
        pause
        exit /b 1
    )
)

start "" "%APP_ROOT%\EchoPro.exe"
exit /b 0
