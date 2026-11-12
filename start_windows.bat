@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem PY.cad 16.10 Windows launcher and runtime repair. Keep this file next to main.py.
rem Probe installed runtimes without triggering Python Manager auto-install.
set "PYLAUNCHER_ALLOW_INSTALL="
set "PYLAUNCHER_DRYRUN="
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
set "PYCAD_RUNTIME="
set "PYCAD_EXIT=1"
pushd "%~dp0"
if errorlevel 1 goto folder_failed
if not exist "main.py" goto missing_files
if not exist "requirements.txt" goto missing_files

set "PYCAD_LOGDIR=%LOCALAPPDATA%\PyCAD\logs"
if not defined LOCALAPPDATA set "PYCAD_LOGDIR=%TEMP%\PyCAD-logs"
if not exist "%PYCAD_LOGDIR%" mkdir "%PYCAD_LOGDIR%" 2>nul
set "PYCAD_LOG=%PYCAD_LOGDIR%\startup-%RANDOM%-%RANDOM%.log"
set "PYCAD_PROBE=%PYCAD_LOG%.probe"
>"%PYCAD_LOG%" echo PY.cad Windows startup log
if errorlevel 1 goto log_failed
echo PY.cad - checking Python...
echo Startup log: "%PYCAD_LOG%"

rem An existing environment may point at an uninstalled Python.
if exist ".venv\Scripts\python.exe" call :probe ".venv\Scripts\python.exe"
if defined PYCAD_RUNTIME goto environment_ready
call :find_python
if defined PYCAD_RUNTIME goto create_environment
if /i "%PYCAD_NO_INSTALL%"=="1" goto python_missing
where winget.exe >nul 2>&1
if errorlevel 1 goto python_missing

echo.
echo No usable 64-bit CPython 3.11, 3.12, 3.13 or 3.14 was found.
echo PY.cad can install Python 3.12 for your Windows user using WinGet.
echo This downloads Python and accepts its installer agreements.
choice /C YN /N /M "Install Python 3.12 now? [Y/N] "
if errorlevel 2 goto python_missing
if errorlevel 1 goto install_python
goto python_missing

:install_python
echo Installing Python 3.12. This may take several minutes...
winget.exe install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --silent --accept-package-agreements --accept-source-agreements --disable-interactivity >>"%PYCAD_LOG%" 2>&1
rem Search even if WinGet says the package was already installed.
call :find_python
if not defined PYCAD_RUNTIME goto python_missing

:create_environment
echo Using Python: "%PYCAD_RUNTIME%"
"%PYCAD_RUNTIME%" -I --version >>"%PYCAD_LOG%" 2>&1
if not exist ".venv" goto make_environment
set "PYCAD_BACKUP=.venv-backup-%RANDOM%-%RANDOM%"
echo Preserving the unusable environment as "%PYCAD_BACKUP%".
ren ".venv" "%PYCAD_BACKUP%" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto environment_failed

:make_environment
echo Creating PY.cad's local Python environment...
"%PYCAD_RUNTIME%" -I -m venv ".venv" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto environment_failed
set "PYCAD_RUNTIME="
call :probe ".venv\Scripts\python.exe"
if not defined PYCAD_RUNTIME goto environment_failed

:environment_ready
rem Run dependency checks every time, but only download when setup is needed.
".venv\Scripts\python.exe" -I -c "import hashlib,pathlib,sys; p=pathlib.Path('.venv/pycad-requirements.sha256'); h=hashlib.sha256(pathlib.Path('requirements.txt').read_bytes()).hexdigest(); sys.exit(0 if p.exists() and p.read_text(encoding='ascii').strip()==h else 1)" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto install_dependencies
".venv\Scripts\python.exe" -I -c "from PyQt6 import QtWidgets,QtSvg,QtPrintSupport; import ezdxf" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto install_dependencies
goto launch

:install_dependencies
echo Installing/checking PY.cad dependencies. Internet is needed for downloads...
".venv\Scripts\python.exe" -I -m pip --version >>"%PYCAD_LOG%" 2>&1
if not errorlevel 1 goto run_pip
".venv\Scripts\python.exe" -I -m ensurepip --upgrade >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto dependencies_failed

:run_pip
".venv\Scripts\python.exe" -I -m pip install --disable-pip-version-check --prefer-binary -r "requirements.txt" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto dependencies_failed
".venv\Scripts\python.exe" -I -c "from PyQt6 import QtWidgets,QtSvg,QtPrintSupport; import ezdxf" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 call :repair_runtime
if errorlevel 1 goto dependencies_failed
".venv\Scripts\python.exe" -I -c "import hashlib,pathlib; pathlib.Path('.venv/pycad-requirements.sha256').write_text(hashlib.sha256(pathlib.Path('requirements.txt').read_bytes()).hexdigest(),encoding='ascii')" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto dependencies_failed

:launch
if /i "%PYCAD_SETUP_ONLY%"=="1" goto success
echo Starting PY.cad...
".venv\Scripts\python.exe" main.py %* >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 goto app_failed

:success
set "PYCAD_EXIT=0"
goto cleanup

:find_python
rem Optional explicit interpreter path; no changes to the user's PATH.
if defined PYCAD_PYTHON call :probe "%PYCAD_PYTHON%"
if defined PYCAD_RUNTIME exit /b 0
rem Prefer 3.12 for the optional CAD kernel; allow newer core runtimes too.
for %%V in (3.12 3.11 3.13 3.14) do call :probe "py.exe" "-%%V"
if defined PYCAD_RUNTIME exit /b 0
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :probe_path "%%P"
for /f "delims=" %%P in ('where python3.exe 2^>nul') do call :probe_path "%%P"
if defined PYCAD_RUNTIME exit /b 0
rem These locations also work immediately after an install, before PATH refresh.
for %%V in (312 311 313 314) do call :probe "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
for %%V in (312 311 313 314) do call :probe "%ProgramFiles%\Python%%V\python.exe"
for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do call :probe "%%D\python.exe"
exit /b 0

:probe_path
if defined PYCAD_RUNTIME exit /b 0
rem Skip generic Microsoft Store aliases: they can open the Store, not Python.
set "PYCAD_CANDIDATE=%~1"
if not "%PYCAD_CANDIDATE:\WindowsApps\=%"=="%PYCAD_CANDIDATE%" exit /b 0
call :probe "%~1"
exit /b 0

:probe
if defined PYCAD_RUNTIME exit /b 0
rem Import venv/ensurepip too: embeddable Python is not a usable setup runtime.
rem Reject previews, 32-bit and free-threaded builds unsupported by this setup.
"%~1" %~2 -I -c "import sys,struct,sysconfig,venv,ensurepip; ok=sys.implementation.name=='cpython' and (3,11)<=sys.version_info[:2]<(3,15) and sys.version_info.releaselevel=='final' and struct.calcsize('P')==8 and not sysconfig.get_config_var('Py_GIL_DISABLED'); sys.exit(1) if not ok else print(sys.executable)" >"%PYCAD_PROBE%" 2>>"%PYCAD_LOG%"
if errorlevel 1 exit /b 0
set /p "PYCAD_RUNTIME="<"%PYCAD_PROBE%"
if not defined PYCAD_RUNTIME exit /b 0
if not exist "%PYCAD_RUNTIME%" set "PYCAD_RUNTIME="
exit /b 0


:repair_runtime
if not exist "scripts\repair_windows_runtime.py" exit /b 1
".venv\Scripts\python.exe" -I "scripts\repair_windows_runtime.py" "%PYCAD_LOG%" >>"%PYCAD_LOG%" 2>&1
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -I -c "from PyQt6 import QtWidgets,QtSvg,QtPrintSupport; import ezdxf" >>"%PYCAD_LOG%" 2>&1
exit /b %errorlevel%

:python_missing
echo.
echo Python setup is required.
echo Install 64-bit Python 3.12 from https://www.python.org/downloads/windows/
echo Include pip and the Python launcher in the installer.
echo If Python Install Manager is installed, you can instead run:
echo   pymanager install 3.12
echo Then double-click start_windows.bat again.
echo For a custom location, set PYCAD_PYTHON to the full path of python.exe.
goto failed

:environment_failed
echo.
echo Could not create PY.cad's Python environment.
echo Extract the complete build into a writable folder, for example Documents.
echo Close other PY.cad windows before retrying.
goto failed

:dependencies_failed
echo.
echo Python was found, but PY.cad's dependencies could not be installed or loaded.
echo Check your internet connection and the error in the log below.
goto failed

:app_failed
echo.
echo Python setup succeeded, but PY.cad reported a startup/application error.
goto failed

:failed
echo.
echo ----- Diagnostic log -----
type "%PYCAD_LOG%"
echo.
echo If the error continues, send this log: "%PYCAD_LOG%"
goto cleanup

:missing_files
echo Extract the WHOLE PY.cad ZIP before running this launcher.
echo Keep start_windows.bat beside main.py and requirements.txt.
goto cleanup

:log_failed
echo Cannot write the startup log. Check your Windows user's folder permissions.
goto cleanup

:folder_failed
echo Cannot open the PY.cad folder. Extract the ZIP into a writable folder.
if /i not "%PYCAD_NO_PAUSE%"=="1" pause
endlocal & exit /b 1

:cleanup
if defined PYCAD_PROBE if exist "%PYCAD_PROBE%" del /q "%PYCAD_PROBE%" >nul 2>&1
popd
if not "%PYCAD_EXIT%"=="0" if /i not "%PYCAD_NO_PAUSE%"=="1" pause
endlocal & exit /b %PYCAD_EXIT%
