@echo off
setlocal

cd /d "%~dp0"
set "BUILD_PYTHON=%CD%\.windows-build-venv\Scripts\python.exe"
set "ISCC="

where node.exe >nul 2>&1
if errorlevel 1 goto :missing_node
where npm.cmd >nul 2>&1
if errorlevel 1 goto :missing_node
goto :node_ready

:missing_node
echo Node.js and npm are required to build the Angular frontend.
choice /C YN /M "Install Node.js LTS with winget now"
if errorlevel 2 goto :node_download
where winget.exe >nul 2>&1
if errorlevel 1 goto :node_download
winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo ERROR: Node.js installation failed. Install it from https://nodejs.org/ and rerun this script.
    exit /b 1
)
echo Node.js was installed. Close this window and rerun build-windows-installer.bat so the updated PATH is loaded.
exit /b 0

:node_download
start "" "https://nodejs.org/en/download"
echo Install Node.js LTS, then rerun build-windows-installer.bat.
exit /b 1

:node_ready

where python.exe >nul 2>&1
if errorlevel 1 goto :missing_python
goto :python_ready

:missing_python
echo Python 3.12 x64 is required to build the Windows application.
choice /C YN /M "Install Python 3.12 with winget now"
if errorlevel 2 goto :python_download
where winget.exe >nul 2>&1
if errorlevel 1 goto :python_download
winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo ERROR: Python installation failed. Install Python 3.12 from https://www.python.org/downloads/windows/ and rerun this script.
    exit /b 1
)
echo Python was installed. Close this window and rerun build-windows-installer.bat so the updated PATH is loaded.
exit /b 0

:python_download
start "" "https://www.python.org/downloads/windows/"
echo Install Python 3.12 x64, then rerun build-windows-installer.bat.
exit /b 1

:python_ready
if not exist "%BUILD_PYTHON%" (
    python -m venv .windows-build-venv
    if errorlevel 1 exit /b 1
)

"%BUILD_PYTHON%" -m pip install -r packaging\windows\requirements.txt
if errorlevel 1 exit /b 1

call npm.cmd --prefix frontend ci
if errorlevel 1 exit /b 1

if exist "%CD%\frontend\dist\frontend\browser" rmdir /s /q "%CD%\frontend\dist\frontend\browser"
if exist "%CD%\frontend\dist\frontend\browser" (
    echo ERROR: Could not remove the previous Angular build.
    exit /b 1
)

call npm.cmd --prefix frontend run build
if errorlevel 1 exit /b 1

if exist "%CD%\dist\windows\Langhar" rmdir /s /q "%CD%\dist\windows\Langhar"
if exist "%CD%\dist\windows\Langhar" (
    echo ERROR: Could not remove the previous Windows application build.
    exit /b 1
)

"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --noconsole --name Langhar ^
    --paths "%CD%\backend" ^
    --distpath "%CD%\dist\windows" ^
    --specpath "%CD%\build\windows-pyinstaller" ^
    --workpath "%CD%\build\windows-pyinstaller" ^
    --icon "%CD%\frontend\public\langhar-app.ico" ^
    --add-data "%CD%\frontend\dist\frontend\browser;data\static" ^
    --add-data "%CD%\backend\config\company_profile.json;data" ^
    --hidden-import pyodbc ^
    --collect-all uvicorn ^
    --collect-all webview ^
    --collect-all pythonnet ^
    --collect-all clr_loader ^
    --hidden-import webview.platforms.edgechromium ^
    "%CD%\backend\launcher.py"
if errorlevel 1 exit /b 1

where ISCC.exe >nul 2>&1
if not errorlevel 1 set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo ERROR: Inno Setup 6 was not found. Install it, then rerun this script.
    exit /b 1
)

"%ISCC%" packaging\windows\Langhar.iss
if errorlevel 1 exit /b 1

echo.
echo Installer created at dist\installer\Langhar-Setup.exe
endlocal
