@echo off
echo ========================================
echo Codelupe Windows Pipeline Startup
echo ========================================

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running! Please start Docker Desktop.
    pause
    exit /b 1
)

REM Check for NVIDIA Docker support
docker info | findstr nvidia >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  NVIDIA Docker support not detected!
    echo    Make sure nvidia-container-toolkit is installed.
    echo    Continue anyway? (Y/N)
    set /p choice=
    if /i not "%choice%"=="Y" exit /b 1
)

REM Check GPU
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ NVIDIA GPU not detected!
    echo    Make sure NVIDIA drivers are installed.
    pause
    exit /b 1
)

echo ✅ Docker and GPU checks passed

REM Create necessary directories
echo 📁 Creating directories...
if not exist "\\192.168.1.66\plex3\codelupe\repos" mkdir "\\192.168.1.66\plex3\codelupe\repos"
if not exist "\\192.168.1.66\plex3\codelupe\datasets" mkdir "\\192.168.1.66\plex3\codelupe\datasets"
if not exist "\\192.168.1.66\plex3\codelupe\models" mkdir "\\192.168.1.66\plex3\codelupe\models"
if not exist "\\192.168.1.66\plex3\codelupe\checkpoints" mkdir "\\192.168.1.66\plex3\codelupe\checkpoints"
if not exist "\\192.168.1.66\plex3\codelupe\logs" mkdir "\\192.168.1.66\plex3\codelupe\logs"
if not exist "crawler_data" mkdir crawler_data
if not exist "download_cache" mkdir download_cache
if not exist "processing_cache" mkdir processing_cache
if not exist "training_cache" mkdir training_cache
if not exist "huggingface_cache" mkdir huggingface_cache
if not exist "monitoring\grafana\dashboards" mkdir monitoring\grafana\dashboards
if not exist "monitoring\grafana\datasources" mkdir monitoring\grafana\datasources

REM Set GitHub token if not set
if "%GITHUB_TOKEN%"=="" (
    echo ⚠️  GITHUB_TOKEN environment variable not set!
    echo    Set it for better API rate limits.
    echo    Continue without token? (Y/N)
    set /p choice=
    if /i not "%choice%"=="Y" exit /b 1
    set GITHUB_TOKEN=
)

echo 🐳 Starting Codelupe Pipeline...
echo.
echo Services starting:
echo   1. PostgreSQL Database (localhost:5432)
echo   2. Redis Cache (localhost:6379)
echo   3. Elasticsearch (localhost:9200)
echo   4. Repository Crawler
echo   5. Repository Downloader  
echo   6. Code Processor
echo   7. Ultra-Optimized Trainer (RTX 4090)
echo   8. Prometheus Metrics (localhost:9090)
echo   9. Grafana Dashboards (localhost:3000)
echo.

REM Start the pipeline
docker-compose -f docker-compose.windows.yml up -d

echo.
echo ⏳ Waiting for services to start...
timeout /t 30 /nobreak >nul

echo.
echo 🔍 Checking service status...
docker-compose -f docker-compose.windows.yml ps

echo.
echo ========================================
echo Pipeline Started Successfully!
echo ========================================
echo.
echo 🌐 Access Points:
echo   Grafana Dashboards: http://localhost:3000 (admin/admin123)
echo   Prometheus Metrics:  http://localhost:9090
echo   Database Admin:      http://localhost:8080 (Adminer)
echo   Elasticsearch:       http://localhost:9200
echo.
echo 📊 View logs:
echo   All services: docker-compose -f docker-compose.windows.yml logs -f
echo   Training only: docker-compose -f docker-compose.windows.yml logs -f ultra-trainer
echo.
echo 🛑 To stop pipeline: stop-windows-pipeline.bat
echo.
pause