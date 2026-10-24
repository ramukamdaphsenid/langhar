@echo off
echo ==============================================================================
echo [Local Launcher] Starting Langhar Enterprise Platform (Native Windows Mode)
echo ==============================================================================

cd /d "%~dp0"

echo [1/2] Starting FastAPI Backend on http://localhost:8000 ...
start "Langhar Backend" cmd /k "cd backend && call venv\Scripts\activate && python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting Angular Frontend on http://localhost:4200 ...
start "Langhar Frontend" cmd /k "cd frontend && npm start"

echo.
echo Launching browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:4200

echo Services are running in separate terminal windows.
echo Close those windows to stop the servers.
