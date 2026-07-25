@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%..\..\"
set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"

set "PY_CMD="
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=%PYTHON_EXE%"
  )
)

if not defined PY_CMD (
  py -3.10 --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -3.10"
  ) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
      set "PY_CMD=python"
    )
  )
)

if not defined PY_CMD (
  echo Error: No usable Python interpreter found.
  echo Install Python 3.10+ or repair the workspace virtual environment.
  exit /b 1
)

pushd "%ROOT_DIR%"
%PY_CMD% tools\dev\p5a_regression_runner.py
set "EXIT_CODE=%ERRORLEVEL%"
popd

if "%EXIT_CODE%"=="0" (
  echo P5A checks passed.
) else (
  echo P5A checks failed.
)

exit /b %EXIT_CODE%
