# Debug script to check what's happening
Write-Host "=== CONTAINER STATUS ==="
docker-compose ps

Write-Host "`n=== CONTAINER IDs ==="
docker ps --format "table {{.Names}}\t{{.ID}}\t{{.Status}}"

Write-Host "`n=== INDIVIDUAL CONTAINER LOGS (last 10 lines) ==="

Write-Host "`n--- TRAINER ---"
docker logs --tail=10 codelupe-trainer 2>&1

Write-Host "`n--- PROCESSOR ---"
docker logs --tail=10 codelupe-processor 2>&1

Write-Host "`n--- DOWNLOADER ---"
docker logs --tail=10 codelupe-downloader 2>&1

Write-Host "`n=== CHECKING FOR DUPLICATE CONTAINERS ==="
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"