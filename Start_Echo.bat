@echo off
setlocal

set "MODE=%~1"
if /I not "%MODE%"=="" if /I not "%MODE%"=="check" if /I not "%MODE%"=="update" (
    echo Usage: %~nx0 [check^|update]
    exit /b 1
)

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "ECHO_PRO_HOME="
if exist "%APP_ROOT%\echo_home.txt" (
    set /p ECHO_PRO_HOME=<"%APP_ROOT%\echo_home.txt"
)
if not defined ECHO_PRO_HOME set "ECHO_PRO_HOME=%LOCALAPPDATA%\EchoProData"

set "BOOTSTRAP_ACTION=install"
if /I "%MODE%"=="update" set "BOOTSTRAP_ACTION=update"
set "VENV_DIR=%ECHO_PRO_HOME%\runtime\venv"
set "PYTHONW_CMD=%VENV_DIR%\Scripts\pythonw.exe"
set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
set "NEEDS_BOOTSTRAP="

echo === Echo Pro One-Click Launcher ===
echo App root: %APP_ROOT%
echo Data root: %ECHO_PRO_HOME%

if /I "%MODE%"=="update" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\tools\ffmpeg\current\bin\ffmpeg.exe" set "NEEDS_BOOTSTRAP=1"
if not exist "%PYTHON_CMD%" set "NEEDS_BOOTSTRAP=1"
if not exist "%VENV_DIR%\Scripts\demucs.exe" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\demucs\htdemucs.ready" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\demucs\repo\htdemucs.yaml" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\rvc\current" set "NEEDS_BOOTSTRAP=1"
if not exist "%ECHO_PRO_HOME%\models\ace_step_1_5\current" set "NEEDS_BOOTSTRAP=1"
if not defined NEEDS_BOOTSTRAP (
    "%PYTHON_CMD%" -c "import PySide6, numpy, sounddevice, soundfile" >nul 2>&1
    if errorlevel 1 set "NEEDS_BOOTSTRAP=1"
)

if defined NEEDS_BOOTSTRAP (
    echo Preparing Echo Pro runtime and dependencies...
    call "%APP_ROOT%\install_echo_pro.bat" %BOOTSTRAP_ACTION%
    if errorlevel 1 (
        echo Echo Pro could not start because dependency setup failed.
        pause
        exit /b 1
    )
)

if not exist "%PYTHON_CMD%" (
    echo Runtime Python was not created at %PYTHON_CMD%
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate the runtime virtual environment.
    pause
    exit /b 1
)

set "PATH=%ECHO_PRO_HOME%\tools\ffmpeg\current\bin;%VENV_DIR%\Scripts;%PATH%"
set "ECHO_PRO_HOME=%ECHO_PRO_HOME%"
set "HF_HOME=%ECHO_PRO_HOME%\runtime\hf_cache"
set "TORCH_HOME=%ECHO_PRO_HOME%\runtime\torch_cache"
set "ECHO_RVC_MODEL_PATH=%ECHO_PRO_HOME%\models\rvc\current"
set "ECHO_ACE_MODEL_PATH=%ECHO_PRO_HOME%\models\ace_step_1_5\current"

mkdir "%ECHO_PRO_HOME%\projects" "%ECHO_PRO_HOME%\voices" "%ECHO_PRO_HOME%\generated" 2>nul

if /I "%MODE%"=="check" (
    echo Runtime environment is ready.
    echo Python: %PYTHON_CMD%
    exit /b 0
)

echo Launching Echo Pro...
if exist "%PYTHONW_CMD%" (
    start "" "%PYTHONW_CMD%" "%APP_ROOT%\echo_pro_app.py"
) else (
    start "" "%PYTHON_CMD%" "%APP_ROOT%\echo_pro_app.py"
)
exit /b 0
