# Check if the fixes are working

Write-Host "=== CONTAINER STATUS ==="
docker-compose ps

Write-Host "`n=== TRAINER STATUS ==="
$trainerLogs = docker logs codelupe-trainer --tail=10 2>&1
if ($trainerLogs -match "Flash Attention 2 not available|Falling back to standard attention") {
    Write-Host "✅ Trainer: Using fallback attention (no flash-attn errors)" -ForegroundColor Green
} elseif ($trainerLogs -match "Using Flash Attention 2") {
    Write-Host "✅ Trainer: Flash Attention working" -ForegroundColor Green
} elseif ($trainerLogs -match "Continuous Trainer initialized") {
    Write-Host "✅ Trainer: Running successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Trainer: Issues detected" -ForegroundColor Red
    Write-Host $trainerLogs
}

Write-Host "`n=== PROCESSOR STATUS ==="
$processorLogs = docker logs codelupe-processor --tail=10 2>&1
if ($processorLogs -match "Batch insert completed|Resumable Processor initialized") {
    Write-Host "✅ Processor: Running successfully" -ForegroundColor Green
} elseif ($processorLogs -match "transaction is aborted") {
    Write-Host "❌ Processor: Still has transaction errors" -ForegroundColor Red
} else {
    Write-Host "⚠️ Processor: Status unclear" -ForegroundColor Yellow
    Write-Host $processorLogs
}

Write-Host "`n=== DOWNLOADER STATUS ==="
$downloaderLogs = docker logs codelupe-downloader --tail=10 2>&1
if ($downloaderLogs -match "Starting repo downloader.*P:/codelupe/repos|/app/repos") {
    Write-Host "✅ Downloader: Using correct path" -ForegroundColor Green
} elseif ($downloaderLogs -match "Download process completed") {
    Write-Host "✅ Downloader: Completed successfully" -ForegroundColor Green
} else {
    Write-Host "⚠️ Downloader: Status unclear" -ForegroundColor Yellow
    Write-Host $downloaderLogs
}

Write-Host "`n=== NAS CHECK ==="
if (Test-Path "P:\codelupe\repos") {
    $items = Get-ChildItem "P:\codelupe\repos" -ErrorAction SilentlyContinue
    Write-Host "✅ P:\codelupe\repos exists with $($items.Count) items" -ForegroundColor Green
} else {
    Write-Host "❌ P:\codelupe\repos not accessible" -ForegroundColor Red
}