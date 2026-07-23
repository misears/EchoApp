@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Error: Python virtual environment not found at "%PYTHON_EXE%"
  echo Run a workspace setup first, then re-run this script.
  exit /b 1
)

pushd "%SCRIPT_DIR%"
"%PYTHON_EXE%" p5a_regression_runner.py
set "EXIT_CODE=%ERRORLEVEL%"
popd

if "%EXIT_CODE%"=="0" (
  echo P5A checks passed.
) else (
  echo P5A checks failed.
)

exit /b %EXIT_CODE%
