# Complete Rebuild and Restart Script for Windows
# Run with: .\rebuild_and_restart.ps1

Write-Host "🛑 COMPLETE REBUILD AND RESTART SCRIPT" -ForegroundColor Yellow
Write-Host "=======================================" -ForegroundColor Yellow

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

# Remove all containers (including stopped ones)
Write-Host "🗑️  Removing all containers..." -ForegroundColor Cyan
docker-compose rm -f

# Remove all images to force rebuild
Write-Host "🧹 Removing old images..." -ForegroundColor Cyan
$images = docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Select-String "codelupe"
foreach ($image in $images) {
    $imageId = ($image -split '\s+')[1]
    docker rmi -f $imageId
}

# Remove dangling images and build cache
Write-Host "🧽 Cleaning up dangling images and build cache..." -ForegroundColor Cyan
docker image prune -f
docker builder prune -f

# Ask about removing volumes
Write-Host "⚠️  WARNING: About to remove volumes (this will delete data!)" -ForegroundColor Red
$removeVolumes = Read-Host "Do you want to remove volumes? (y/N)"
if ($removeVolumes -eq "y" -or $removeVolumes -eq "Y") {
    Write-Host "🗑️  Removing volumes..." -ForegroundColor Cyan
    docker-compose down -v
    docker volume prune -f
} else {
    Write-Host "ℹ️  Keeping volumes..." -ForegroundColor Green
}

# Rebuild all images
Write-Host "🔨 Rebuilding all images..." -ForegroundColor Cyan
docker-compose build --no-cache --parallel

# Start the infrastructure services first
Write-Host "🚀 Starting infrastructure services..." -ForegroundColor Green
docker-compose up -d postgres elasticsearch redis mongodb

# Wait for services to be healthy
Write-Host "⏳ Waiting for infrastructure to be ready..." -ForegroundColor Yellow
$timeout = 300
$counter = 0
while ($counter -lt $timeout) {
    $postgresStatus = docker-compose ps postgres | Select-String "healthy"
    $elasticsearchStatus = docker-compose ps elasticsearch | Select-String "healthy"
    
    if ($postgresStatus -and $elasticsearchStatus) {
        Write-Host "✅ Infrastructure is ready!" -ForegroundColor Green
        break
    }
    
    Write-Host "Waiting... ($counter/$timeout seconds)" -ForegroundColor Yellow
    Start-Sleep 5
    $counter += 5
}

if ($counter -ge $timeout) {
    Write-Host "❌ Infrastructure failed to start within $timeout seconds" -ForegroundColor Red
    exit 1
}

# Start the processing services
Write-Host "🔄 Starting processing services..." -ForegroundColor Cyan
docker-compose up -d downloader processor

# Wait a bit then start trainer
Write-Host "⏳ Waiting before starting trainer..." -ForegroundColor Yellow
Start-Sleep 30

Write-Host "🤖 Starting trainer..." -ForegroundColor Cyan
docker-compose up -d trainer

# Start monitoring services
Write-Host "📊 Starting monitoring services..." -ForegroundColor Cyan
docker-compose up -d grafana prometheus kibana adminer mongo-express metrics-exporter

Write-Host "✅ All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Service Status:" -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "🔗 Service URLs:" -ForegroundColor Yellow
Write-Host "  - Grafana: http://localhost:3000 (admin/admin123)" -ForegroundColor White
Write-Host "  - Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "  - Kibana: http://localhost:5601" -ForegroundColor White
Write-Host "  - Adminer: http://localhost:8080" -ForegroundColor White
Write-Host "  - Mongo Express: http://localhost:8081" -ForegroundColor White
Write-Host "  - Trainer Metrics: http://localhost:8090/metrics" -ForegroundColor White
Write-Host "  - Pipeline Metrics: http://localhost:9091/metrics" -ForegroundColor White

Write-Host ""
Write-Host "🏆 Rebuild complete! Monitor logs with:" -ForegroundColor Green
Write-Host "  docker-compose logs -f" -ForegroundColor White
Write-Host ""
Write-Host "📁 NAS Storage Location: P:\codelupe\repos" -ForegroundColor Cyan