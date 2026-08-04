@echo off
setlocal
set "ROOT=%~dp0..\.."
"%ROOT%\.venv\Scripts\python.exe" -m py_compile "%ROOT%\echo_pro_app.py"
if errorlevel 1 exit /b 1
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\tools\dev\ui_runtime_smoke.py"
