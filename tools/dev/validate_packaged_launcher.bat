@echo off
setlocal EnableExtensions

set "BUNDLE_ROOT=%~1"
if /I "%BUNDLE_ROOT%"=="" set "BUNDLE_ROOT=%~dp0\..\..\release\Portable"
for %%I in ("%BUNDLE_ROOT%") do set "BUNDLE_ROOT=%%~fI"

echo === Echo Pro Packaged Launcher Validation ===
echo Bundle root: %BUNDLE_ROOT%
echo.

set "HAS_FAILURE="
call :check_path "Portable launcher" "%BUNDLE_ROOT%\EchoPro_Portable.bat"
call :check_path "Desktop launcher" "%BUNDLE_ROOT%\EchoPro_Desktop.bat"
call :check_path "Dependency installer" "%BUNDLE_ROOT%\install_echo_pro.bat"
call :check_path "Packaged executable" "%BUNDLE_ROOT%\EchoPro.exe"
call :check_path "PyInstaller internal folder" "%BUNDLE_ROOT%\_internal"

if defined HAS_FAILURE (
    echo.
    echo Validation failed: packaged files are incomplete.
    echo Recovery options:
    echo   1^) Build a new bundle: tools\dev\build_exe.bat
    echo   2^) Or copy a known-good Portable bundle into: release\Portable
    exit /b 1
)

echo.
echo Static bundle checks passed.
echo Next manual validation step:
echo   call "%BUNDLE_ROOT%\EchoPro_Portable.bat"
echo Confirm the tabbed UI opens: Mixer/Home/Recording/Stem Separation/Voice FX/AI Generation/Mastering/MIDI Mapping/Settings/Tools/Help.
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
