@echo off
echo ==============================================================================
echo [Local Launcher] Starting Langhar Enterprise Platform (Native Windows Mode)
echo ==============================================================================

cd /d "%~dp0"

where node.exe >nul 2>&1
if errorlevel 1 goto :missing_node
where npm.cmd >nul 2>&1
if errorlevel 1 goto :missing_node
goto :node_ready

:missing_node
echo Node.js and npm are required to start the Angular frontend.
choice /C YN /M "Install Node.js LTS with winget now"
if errorlevel 2 goto :node_download
where winget.exe >nul 2>&1
if errorlevel 1 goto :node_download
winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Node.js installation failed. Install it from https://nodejs.org/ and rerun this script.
    exit /b 1
)
echo Node.js was installed. Close this window and rerun start-local.bat so the updated PATH is loaded.
exit /b 0

:node_download
start "" "https://nodejs.org/en/download"
echo Install Node.js LTS, then rerun start-local.bat.
exit /b 1

:missing_python
echo Python 3.12 is required to run the backend.
choice /C YN /M "Install Python 3.12 with winget now"
if errorlevel 2 goto :python_download
where winget.exe >nul 2>&1
if errorlevel 1 goto :python_download
winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Python installation failed. Install Python 3.12 from https://www.python.org/downloads/windows/ and rerun this script.
    exit /b 1
)
echo Python was installed. Close this window and rerun start-local.bat so the updated PATH is loaded.
exit /b 0

:python_download
start "" "https://www.python.org/downloads/windows/"
echo Install Python 3.12, then rerun start-local.bat.
exit /b 1

:node_ready
where python.exe >nul 2>&1
if errorlevel 1 goto :missing_python

if not exist "backend\venv\Scripts\python.exe" (
    python -m venv backend\venv
    if errorlevel 1 (
        echo ERROR: Could not create the backend Python environment.
        pause
        exit /b 1
    )
)
set "BACKEND_PYTHON=%CD%\backend\venv\Scripts\python.exe"
"%BACKEND_PYTHON%" -c "import fastapi, uvicorn, requests, xmltodict, pydantic, dotenv, rich, pyodbc" >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies...
    "%BACKEND_PYTHON%" -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo ERROR: Backend dependency installation failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

if not exist "frontend\node_modules\.bin\ng.cmd" (
    echo Installing frontend dependencies...
    call npm.cmd --prefix frontend ci
    if errorlevel 1 (
        echo ERROR: Frontend dependency installation failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

echo [1/2] Starting FastAPI Backend on http://localhost:8000 ...
start "Langhar Backend" cmd /k "cd /d ""%CD%\backend"" && call venv\Scripts\activate.bat && python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting Angular Frontend on http://localhost:4200 ...
start "Langhar Frontend" cmd /k "cd /d ""%CD%\frontend"" && call npm start"

echo.
echo Launching browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:4200

echo Services are running in separate terminal windows.
echo Close those windows to stop the servers.
