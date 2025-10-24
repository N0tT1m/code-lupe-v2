@echo off
echo ========================================
echo Stopping Codelupe Windows Pipeline
echo ========================================

REM Gracefully stop the ultra trainer first
echo 🛑 Stopping Ultra Trainer (saving checkpoints)...
docker-compose -f docker-compose.windows.yml stop ultra-trainer

echo ⏳ Waiting for checkpoint save...
timeout /t 15 /nobreak >nul

REM Stop all other services
echo 🛑 Stopping all pipeline services...
docker-compose -f docker-compose.windows.yml down

echo.
echo ✅ Pipeline stopped successfully!
echo.
echo 📊 Your data is preserved in:
echo   Models:      \\\\192.168.1.66\plex3\codelupe\models
echo   Checkpoints: \\\\192.168.1.66\plex3\codelupe\checkpoints
echo   Datasets:    \\\\192.168.1.66\plex3\codelupe\datasets
echo   Repositories: \\\\192.168.1.66\plex3\codelupe\repos
echo   Logs:        \\\\192.168.1.66\plex3\codelupe\logs
echo.

REM Ask about cleanup
echo 🧹 Clean up Docker resources? (Y/N)
set /p choice=
if /i "%choice%"=="Y" (
    echo Cleaning up...
    docker system prune -f
    docker volume prune -f
    echo ✅ Cleanup complete!
)

echo.
echo Pipeline fully stopped.
pause