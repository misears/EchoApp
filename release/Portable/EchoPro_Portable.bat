@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "ECHO_PRO_HOME=%APP_ROOT%\data"
set "PATH=%APP_ROOT%\tools\ffmpeg\current\bin;%APP_ROOT%\runtime\venv\Scripts;%PATH%"
set "ECHO_RVC_MODEL_PATH=%APP_ROOT%\models\rvc\current"
set "ECHO_ACE_MODEL_PATH=%APP_ROOT%\models\ace_step_1_5\current"

if not exist "%APP_ROOT%\.echo_portable" type nul > "%APP_ROOT%\.echo_portable"
mkdir "%ECHO_PRO_HOME%\projects" "%ECHO_PRO_HOME%\voices" "%ECHO_PRO_HOME%\generated" 2>nul

if not exist "%APP_ROOT%\EchoPro.exe" (
    echo EchoPro.exe not found in %APP_ROOT%
    exit /b 1
)

start "" "%APP_ROOT%\EchoPro.exe"
exit /b 0
