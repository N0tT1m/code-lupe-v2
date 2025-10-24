@echo off
echo 🔍 CodeLupe Dataset Analyzer
echo =============================

REM Check if Go is installed
go version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Go is not installed. Please install Go first.
    pause
    exit /b 1
)

REM Build the analyzer
echo 🏗️  Building dataset analyzer...
go build -o dataset_analyzer.exe dataset_analyzer.go

if %errorlevel% neq 0 (
    echo ❌ Build failed. Check for errors above.
    pause
    exit /b 1
)

echo ✅ Build successful!
echo.

REM Run the analyzer
echo 🚀 Running dataset analysis...
echo.
dataset_analyzer.exe

echo.
echo 📊 Analysis complete!
echo.
echo 💡 Pro Tips:
echo • Use this regularly to monitor dataset growth
echo • Check quality distribution to ensure good training data
echo • Monitor language balance for your specific use case
echo • Look for repositories that might need exclusion
echo.
echo 🔄 To run again: dataset_analyzer.exe
pause