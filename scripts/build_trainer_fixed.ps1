# Build trainer with fixed python3 command

Write-Host "Building trainer with corrected python3 command..."

# Clean up
docker-compose stop trainer 2>$null
docker container rm -f codelupe-trainer 2>$null
docker image rm -f codelupe-trainer 2>$null

Write-Host "Starting build (this will take 10-15 minutes for flash-attention compilation)..."
$startTime = Get-Date

# Build with progress
docker-compose build --no-cache trainer

if ($LASTEXITCODE -eq 0) {
    $totalTime = (Get-Date) - $startTime
    Write-Host "✅ Build completed in $($totalTime.ToString('mm\:ss'))" -ForegroundColor Green
    
    Write-Host "Testing flash-attention..."
    $testResult = docker run --rm codelupe-trainer python3 -c "import flash_attn; print('✅ Flash Attention version:', flash_attn.__version__)"
    Write-Host $testResult
    
    Write-Host "Starting trainer..."
    docker-compose up -d trainer
    
    Start-Sleep 15
    Write-Host "Trainer status:"
    docker logs codelupe-trainer --tail=15
} else {
    Write-Host "❌ Build failed - trying fallback without flash-attention" -ForegroundColor Red
    Write-Host "Run: .\fallback_trainer.ps1"
}