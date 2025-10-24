# Start other services while trainer builds

Write-Host "Starting infrastructure and other services..."

# Stop everything first
docker-compose down

# Remove and rebuild processor and downloader (quick)
docker container rm -f codelupe-processor codelupe-downloader 2>$null
docker image rm -f codelupe-processor codelupe-downloader 2>$null

Write-Host "Building processor and downloader..."
docker-compose build --no-cache processor downloader

Write-Host "Starting infrastructure..."
docker-compose up -d postgres elasticsearch redis mongodb

Write-Host "Waiting for infrastructure..."
Start-Sleep 30

Write-Host "Starting processor and downloader..."
docker-compose up -d processor downloader

Write-Host "Starting monitoring..."
docker-compose up -d grafana prometheus kibana adminer mongo-express metrics-exporter

Write-Host "✅ All services except trainer are running"
Write-Host "Now run: .\build_with_flash_attention.ps1 to build trainer"