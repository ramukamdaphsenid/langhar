@echo off
setlocal

cd /d "%~dp0"

echo Building and starting Langhar with Docker Compose...
docker compose up -d --build
if errorlevel 1 (
    echo ERROR: Failed to build or start Langhar.
    exit /b 1
)

echo.
echo Langhar is running at http://localhost:8000
echo Logs: docker compose logs -f langhar
echo Stop: docker compose down
endlocal
