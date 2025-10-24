# Build trainer with flash-attention (takes 10-15 minutes)

Write-Host "Building trainer with flash-attention from source..."
Write-Host "This will take 10-15 minutes - flash-attention needs to compile CUDA kernels"
Write-Host ""

# Stop and remove trainer
docker-compose stop trainer
docker container rm -f codelupe-trainer 2>$null
docker image rm -f codelupe-trainer 2>$null

# Build trainer with verbose output
Write-Host "Starting build..."
$startTime = Get-Date

# Build with progress
$buildJob = Start-Job -ScriptBlock {
    docker-compose build --no-cache trainer
}

# Monitor progress
while ($buildJob.State -eq "Running") {
    $elapsed = (Get-Date) - $using:startTime
    Write-Host "Building... elapsed: $($elapsed.ToString('mm\:ss'))" -ForegroundColor Yellow
    Start-Sleep 30
}

# Get result
$result = Receive-Job $buildJob
Remove-Job $buildJob

if ($LASTEXITCODE -eq 0) {
    $totalTime = (Get-Date) - $startTime
    Write-Host "✅ Build completed in $($totalTime.ToString('mm\:ss'))" -ForegroundColor Green
    
    Write-Host "Starting trainer..."
    docker-compose up -d trainer
    
    Write-Host "Waiting for trainer to initialize..."
    Start-Sleep 10
    
    Write-Host "Checking trainer logs:"
    docker logs codelupe-trainer --tail=20
} else {
    Write-Host "❌ Build failed" -ForegroundColor Red
    Write-Host $result
}