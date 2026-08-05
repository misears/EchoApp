@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ACTION=%~1"
if /I "%ACTION%"=="" set "ACTION=check"
if /I not "%ACTION%"=="check" if /I not "%ACTION%"=="repair" if /I not "%ACTION%"=="reset" (
    echo Usage: %~nx0 [check^|repair^|reset]
    exit /b 1
)

set "APP_ROOT=%~dp0\..\.."
for %%I in ("%APP_ROOT%") do set "APP_ROOT=%%~fI"

set "ECHO_HOME=%ECHO_PRO_HOME%"
if not defined ECHO_HOME if exist "%APP_ROOT%\echo_home.txt" set /p ECHO_HOME=<"%APP_ROOT%\echo_home.txt"
if not defined ECHO_HOME set "ECHO_HOME=%LOCALAPPDATA%\EchoProData"

set "VENV_DIR=%ECHO_HOME%\runtime\venv"
set "PY_CMD=%VENV_DIR%\Scripts\python.exe"
set "DEMUCS_EXE=%VENV_DIR%\Scripts\demucs.exe"
set "FFMPEG_EXE=%ECHO_HOME%\tools\ffmpeg\current\bin\ffmpeg.exe"
set "DEMUCS_SENTINEL=%ECHO_HOME%\models\demucs\htdemucs.ready"
set "DEMUCS_REPO_YAML=%ECHO_HOME%\models\demucs\repo\htdemucs.yaml"
set "RVC_DIR=%ECHO_HOME%\models\rvc\current"
set "ACE_DIR=%ECHO_HOME%\models\ace_step_1_5\current"

echo === Echo Pro Runtime Health ===
echo Action: %ACTION%
echo App root: %APP_ROOT%
echo Data root: %ECHO_HOME%
echo.

if /I "%ACTION%"=="reset" (
    call :reset_runtime
    if errorlevel 1 exit /b 1
    set "ACTION=repair"
)

call :run_checks
if /I "%ACTION%"=="check" exit /b %ERRORLEVEL%

echo.
echo Repairing runtime with install_echo_pro.bat update...
call "%APP_ROOT%\install_echo_pro.bat" update
if errorlevel 1 (
    echo Runtime repair failed.
    exit /b 1
)

call :run_checks
exit /b %ERRORLEVEL%

:run_checks
set "HAS_FAILURE="
call :check_path "Runtime Python" "%PY_CMD%"
call :check_path "Demucs executable" "%DEMUCS_EXE%"
call :check_path "FFmpeg executable" "%FFMPEG_EXE%"
call :check_path "Demucs sentinel" "%DEMUCS_SENTINEL%"
call :check_path "Demucs model yaml" "%DEMUCS_REPO_YAML%"
call :check_path "RVC model directory" "%RVC_DIR%"
call :check_path "ACE-Step model directory" "%ACE_DIR%"

if not defined HAS_FAILURE if exist "%PY_CMD%" (
    "%PY_CMD%" -c "import PySide6, numpy, sounddevice, soundfile" >nul 2>&1
    if errorlevel 1 (
        echo [FAIL] Runtime package import check failed.
        set "HAS_FAILURE=1"
    ) else (
        echo [OK] Runtime package import check passed.
    )
)

if defined HAS_FAILURE (
    echo.
    echo Runtime health check failed.
    echo Suggested recovery: tools\dev\echo_runtime_health.bat repair
    exit /b 1
)

echo.
echo Runtime health check passed.
exit /b 0

:check_path
set "LABEL=%~1"
set "TARGET=%~2"
if exist "%TARGET%" (
    echo [OK] %LABEL%: %TARGET%
) else (
    echo [FAIL] %LABEL% missing: %TARGET%
    set "HAS_FAILURE=1"
)
exit /b 0

:reset_runtime
if not exist "%VENV_DIR%" (
    echo Runtime venv not found, nothing to reset.
    exit /b 0
)
for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "BACKUP_DIR=%ECHO_HOME%\runtime\venv_backup_%STAMP%"
echo Backing up runtime venv to: %BACKUP_DIR%
move "%VENV_DIR%" "%BACKUP_DIR%" >nul
if errorlevel 1 (
    echo Failed to move runtime venv for reset.
    exit /b 1
)
echo Runtime venv reset complete.
exit /b 0
