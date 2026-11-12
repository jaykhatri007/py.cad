@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "PYCAD_SETUP=installer\packages\PY.cad-Setup-16.45.0-Windows-x64.exe"
if not exist "%PYCAD_SETUP%" set "PYCAD_SETUP=PY.cad-Setup-16.45.0-Windows-x64.exe"
if not exist "%PYCAD_SETUP%" goto missing
if not defined LOCALAPPDATA goto missing_profile
set "PYCAD_LOGDIR=%LOCALAPPDATA%\PyCAD\logs"
if not exist "%PYCAD_LOGDIR%" mkdir "%PYCAD_LOGDIR%"
set "PYCAD_SETUP_LOG=%PYCAD_LOGDIR%\setup-console-%RANDOM%-%RANDOM%.log"
echo PY.cad 16.19 setup. Keep this window open until setup finishes.
echo The first 3D dependency download may take several minutes.
echo A missing Microsoft runtime can ask for Windows authorization.
echo Log: "%PYCAD_SETUP_LOG%"
rem The GUI executable must be waited for explicitly by cmd.exe.
start "" /b /wait "%PYCAD_SETUP%" --no-browser >"%PYCAD_SETUP_LOG%" 2>&1
set "PYCAD_SETUP_EXIT=%errorlevel%"
type "%PYCAD_SETUP_LOG%"
echo.
if "%PYCAD_SETUP_EXIT%"=="0" (echo Setup finished. PY.cad should open.) else (echo Setup failed. Send the log shown above.)
pause
popd
exit /b %PYCAD_SETUP_EXIT%
:missing
echo Extract the complete ZIP. Setup-Windows.cmd needs its matching setup EXE.
goto failed
:missing_profile
echo LOCALAPPDATA is unavailable. Run from a normal Windows user account.
:failed
pause
popd
exit /b 1
