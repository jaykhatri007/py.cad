@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "PYCAD_SETUP=installer\packages\PY.cad-Setup-16.45.0-Windows-x64.exe"
if not exist "%PYCAD_SETUP%" set "PYCAD_SETUP=PY.cad-Setup-16.45.0-Windows-x64.exe"
if not exist "%PYCAD_SETUP%" goto missing
rem Normal setup has its own native window; this launcher exits immediately.
start "" "%PYCAD_SETUP%"
set "PYCAD_SETUP_EXIT=%errorlevel%"
popd
exit /b %PYCAD_SETUP_EXIT%
:missing
echo Extract the complete ZIP. This launcher needs its matching setup EXE.
pause
popd
exit /b 1
