@echo off
echo ==============================================================================
echo [Docker] Building ^& Starting Langhar Enterprise Platform Unified Container
echo ==============================================================================

cd /d "%~dp0"

:: Enable BuildKit for parallel stage execution and cache mounts
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1

echo [1/3] Ensuring sync state file exists as a file (not auto-created by Docker as a directory)...
if exist "%cd%\backend\.sync_state.json\" (
    rmdir /s /q "%cd%\backend\.sync_state.json"
)
if not exist "%cd%\backend\.sync_state.json" (
    echo {} > "%cd%\backend\.sync_state.json"
)

echo [2/3] Ensuring company_profile.json exists as a file...
if not exist "%cd%\backend\config" mkdir "%cd%\backend\config"
if not exist "%cd%\backend\config\company_profile.json" (
    echo {} > "%cd%\backend\config\company_profile.json"
)

echo [3/3] Building ^& starting unified container with Docker Compose on http://localhost:8000 ...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo [Docker] Failed to build or start the Langhar container.
    exit /b 1
)

echo.
echo ==============================================================================
echo Langhar container is active! Access the unified UI at:
echo    http://localhost:8000
echo.
echo Logs can be inspected with: docker compose logs -f langhar
echo Stop container with:        docker compose down
echo ==============================================================================
