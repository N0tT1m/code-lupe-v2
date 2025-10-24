# Quick Rebuild Script for Windows (Keeps Volumes)
# Run with: .\quick_rebuild.ps1

Write-Host "⚡ QUICK REBUILD (KEEPS VOLUMES)" -ForegroundColor Yellow
Write-Host "===============================" -ForegroundColor Yellow

# Check if P: drive exists
if (-not (Test-Path "P:\")) {
    Write-Host "❌ ERROR: P: drive not found! Please ensure your NAS is mounted to P:" -ForegroundColor Red
    Write-Host "   Map your NAS to P: drive before running this script" -ForegroundColor Red
    exit 1
}

# Check if codelupe directory exists
if (-not (Test-Path "P:\codelupe\repos")) {
    Write-Host "⚠️  Creating P:\codelupe\repos directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "P:\codelupe\repos" -Force
}

# Stop all running containers
Write-Host "🔄 Stopping all containers..." -ForegroundColor Cyan
docker-compose down

# Remove containers but keep volumes
Write-Host "🗑️  Removing containers (keeping data)..." -ForegroundColor Cyan
docker-compose rm -f

# Remove only the application images (not infrastructure)
Write-Host "🧹 Removing application images..." -ForegroundColor Cyan
$appImages = docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Select-String "codelupe.*(trainer|processor|downloader)"
foreach ($image in $appImages) {
    $imageId = ($image -split '\s+')[1]
    docker rmi -f $imageId
}

# Clean build cache
Write-Host "🧽 Cleaning build cache..." -ForegroundColor Cyan
docker builder prune -f

# Rebuild only the fixed services
Write-Host "🔨 Rebuilding fixed services..." -ForegroundColor Cyan
docker-compose build --no-cache trainer processor downloader

# Start everything
Write-Host "🚀 Starting all services..." -ForegroundColor Green
docker-compose up -d

Write-Host "✅ Quick rebuild complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Monitor the fixes:" -ForegroundColor Yellow
Write-Host "  docker-compose logs -f trainer processor downloader" -ForegroundColor White
Write-Host ""
Write-Host "📁 NAS Storage Location: P:\codelupe\repos" -ForegroundColor Cyan