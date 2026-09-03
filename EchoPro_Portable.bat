@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "ECHO_PRO_HOME="
if defined ECHO_PRO_HOME set "ECHO_PRO_HOME=%ECHO_PRO_HOME%"
if exist "%APP_ROOT%\echo_home.txt" (
    set /p ECHO_PRO_HOME=<"%APP_ROOT%\echo_home.txt"
)
if not defined ECHO_PRO_HOME set "ECHO_PRO_HOME=%APP_ROOT%\EchoProData"

call "%APP_ROOT%\Start_Echo.bat" %*
