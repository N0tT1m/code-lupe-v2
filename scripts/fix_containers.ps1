# Fix duplicate/identical container issue

Write-Host "Stopping everything..."
docker-compose down

Write-Host "Removing ALL containers (including stopped ones)..."
docker container prune -f

Write-Host "Removing ALL codelupe images..."
docker images | Select-String "codelupe" | ForEach-Object {
    $imageId = ($_ -split '\s+')[2]
    docker rmi -f $imageId
}

Write-Host "Cleaning everything..."
docker system prune -f
docker builder prune -f

Write-Host "Rebuilding with no cache..."
docker-compose build --no-cache --parallel

Write-Host "Starting infrastructure first..."
docker-compose up -d postgres elasticsearch redis

Write-Host "Waiting 30 seconds..."
Start-Sleep 30

Write-Host "Starting processing services..."
docker-compose up -d downloader processor trainer

Write-Host "Done. Check status:"
docker-compose ps