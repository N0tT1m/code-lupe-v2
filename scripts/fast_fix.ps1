# Fast fix - rebuild without flash attention issues

Write-Host "Stopping containers..."
docker-compose down

Write-Host "Removing trainer container and image..."
docker container rm -f codelupe-trainer 2>$null
docker image rm -f codelupe-trainer 2>$null

Write-Host "Rebuilding trainer (without flash-attention)..."
docker-compose build --no-cache trainer

Write-Host "Rebuilding processor and downloader..."
docker-compose build --no-cache processor downloader

Write-Host "Starting infrastructure..."
docker-compose up -d postgres elasticsearch redis

Write-Host "Waiting 20 seconds for infrastructure..."
Start-Sleep 20

Write-Host "Starting services..."
docker-compose up -d

Write-Host "Done! Check logs:"
Write-Host "docker-compose logs -f trainer"