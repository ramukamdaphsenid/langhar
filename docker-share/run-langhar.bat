@echo off
setlocal

set "IMAGE_NAME=langhar:latest"
set "ARCHIVE=%~dp0langhar-image.tar"
set "CONTAINER_NAME=langhar-shared"
set "HEALTH_ATTEMPTS=0"

echo ============================================================
echo Load and run the shared Langhar image
echo ============================================================

where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker was not found. Install and start Docker Desktop first.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Start Docker Desktop and try again.
    exit /b 1
)

if not exist "%ARCHIVE%" (
    echo ERROR: "%ARCHIVE%" was not found.
    echo Keep this script in the same folder as langhar-image.tar.
    exit /b 1
)

echo.
echo Loading Docker image ...
docker load --input "%ARCHIVE%"
if errorlevel 1 (
    echo ERROR: Could not load the Docker image.
    exit /b 1
)

docker container inspect "%CONTAINER_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Replacing the existing container with the shared image ...
    docker rm -f "%CONTAINER_NAME%"
    if errorlevel 1 (
        echo ERROR: Could not remove the existing container.
        exit /b 1
    )
)

echo.
echo Starting Langhar on http://localhost:8000 ...
if exist "%~dp0serviceAccountKey.json" (
    docker run -d --name "%CONTAINER_NAME%" --restart unless-stopped -p 8000:8000 --add-host=host.docker.internal:host-gateway -e TALLY_HOST=http://host.docker.internal -e TALLY_PORT=9000 -e FIREBASE_CREDENTIALS_PATH=/app/serviceAccountKey.json -e SYNC_STATE_FILE=/app/data/.sync_state.json -v langhar-sync-state:/app/data -v "%~dp0serviceAccountKey.json:/app/serviceAccountKey.json:ro" "%IMAGE_NAME%"
) else (
    docker run -d --name "%CONTAINER_NAME%" --restart unless-stopped -p 8000:8000 --add-host=host.docker.internal:host-gateway -e TALLY_HOST=http://host.docker.internal -e TALLY_PORT=9000 -e SYNC_STATE_FILE=/app/data/.sync_state.json -v langhar-sync-state:/app/data "%IMAGE_NAME%"
)
if errorlevel 1 (
    echo ERROR: Could not start the container.
    echo Check whether port 8000 is already in use.
    exit /b 1
)

echo.
echo Waiting for Langhar to become healthy ...
:wait_for_health
set "HEALTH_STATUS="
for /f "delims=" %%H in ('docker inspect --format "{{.State.Health.Status}}" "%CONTAINER_NAME%" 2^>nul') do set "HEALTH_STATUS=%%H"
if /i "%HEALTH_STATUS%"=="healthy" goto :success
if /i "%HEALTH_STATUS%"=="unhealthy" goto :startup_failed
set /a HEALTH_ATTEMPTS+=1
if %HEALTH_ATTEMPTS% geq 45 goto :startup_timeout
timeout /t 2 /nobreak >nul
goto :wait_for_health

:startup_failed
echo ERROR: Langhar failed its health check. Container logs:
docker logs "%CONTAINER_NAME%"
exit /b 1

:startup_timeout
echo ERROR: Langhar did not become healthy within 90 seconds. Container logs:
docker logs "%CONTAINER_NAME%"
exit /b 1

:success
echo.
echo Langhar is running at http://localhost:8000
echo View logs: docker logs -f %CONTAINER_NAME%
echo Stop it:   docker stop %CONTAINER_NAME%
echo.
if not exist "%~dp0serviceAccountKey.json" (
    echo NOTE: No Firebase credentials were found beside this script.
    echo Add your own serviceAccountKey.json there and recreate the container
    echo to enable Firebase operations. Never share this key publicly.
)
endlocal
