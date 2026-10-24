@echo off
echo ==============================================================================
echo [Docker] Building & Starting Langhar Enterprise Platform Unified Container
echo ==============================================================================

cd /d "%~dp0"

:: Enable BuildKit for parallel stage execution and cache mounts
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1

echo [1/3] Building unified container image with Docker (BuildKit enabled)...
docker build -t langhar -f Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] Docker build failed. Please ensure Docker Desktop is running.
    pause
    exit /b %errorlevel%
)

echo [2/3] Stopping previous container if running...
docker stop langhar >nul 2>&1
docker rm langhar >nul 2>&1

:: Ensure sync state file exists as a file (not auto-created by Docker as a directory)
if exist "%cd%\backend\.sync_state.json\" (
    rmdir /s /q "%cd%\backend\.sync_state.json"
)
if not exist "%cd%\backend\.sync_state.json" (
    echo {} > "%cd%\backend\.sync_state.json"
)

echo [3/3] Launching container on http://localhost:8000 ...
docker run -d ^
    --name langhar ^
    -p 8000:8000 ^
    --add-host=host.docker.internal:host-gateway ^
    -e TALLY_HOST=http://host.docker.internal ^
    -e TALLY_PORT=9000 ^
    -v "%cd%\backend\serviceAccountKey.json:/app/serviceAccountKey.json:ro" ^
    -v "%cd%\backend\.sync_state.json:/app/.sync_state.json" ^
    langhar

echo.
echo ==============================================================================
echo Langhar container is active! Access the unified UI at:
echo    http://localhost:8000
echo.
echo Logs can be inspected with: docker logs -f langhar
echo Stop container with:        docker stop langhar
echo ==============================================================================

timeout /t 2 >nul
start http://localhost:8000
