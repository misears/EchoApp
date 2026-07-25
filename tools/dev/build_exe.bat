@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%..\..\"

echo === Echo Pro EXE Build ===

set PY_CMD=
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set PY_CMD=py -3.10
) else (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo Python 3.10 or default python was not found on PATH.
        exit /b 1
    )
    set PY_CMD=python
)

echo Using interpreter: %PY_CMD%

echo Installing build dependencies...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install pyinstaller PySide6 pydub sounddevice soundfile numpy
if errorlevel 1 (
    echo Failed to install dependencies.
    exit /b 1
)

echo Running PyInstaller...
pushd "%ROOT_DIR%"
%PY_CMD% -m PyInstaller --noconfirm --clean EchoPro.spec
set "BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT%"=="0" (
    echo Build failed.
    exit /b %BUILD_EXIT%
)

echo.
echo Build complete.
echo EXE path: %ROOT_DIR%dist\EchoPro\EchoPro.exe

endlocal
