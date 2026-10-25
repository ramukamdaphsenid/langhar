@echo off
setlocal

cd /d "%~dp0"
set "IMAGE_NAME=langhar:latest"
set "BUILD_CTX=."
set "OUTPUT_DIR=%~dp0docker-share"
set "ARCHIVE=%OUTPUT_DIR%\langhar-image.tar"

echo ============================================================
echo Build and export Langhar for sharing
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

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if errorlevel 1 (
    echo ERROR: Could not create "%OUTPUT_DIR%".
    exit /b 1
)

echo.
echo [1/3] Building %IMAGE_NAME% ...
docker build --tag "%IMAGE_NAME%" --file "%~dp0Dockerfile" "%BUILD_CTX%"
if errorlevel 1 (
    echo ERROR: Docker image build failed.
    exit /b 1
)

echo.
echo [2/3] Saving image to "%ARCHIVE%" ...
docker save --output "%ARCHIVE%" "%IMAGE_NAME%"
if errorlevel 1 (
    echo ERROR: Could not save the Docker image.
    exit /b 1
)

echo.
echo [3/3] Adding the recipient run script ...
copy /y "%~dp0run-shared-image.bat" "%OUTPUT_DIR%\run-langhar.bat" >nul
if errorlevel 1 (
    echo ERROR: Could not copy the recipient run script.
    exit /b 1
)

echo.
echo ============================================================
echo Share the folder:
echo   %OUTPUT_DIR%
echo.
echo It contains the image archive and run-langhar.bat.
echo Do NOT put serviceAccountKey.json in this folder unless you
echo intend to share that private credential separately and securely.
echo ============================================================
endlocal
