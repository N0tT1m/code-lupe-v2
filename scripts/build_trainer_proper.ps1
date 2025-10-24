# Build trainer with proper flash-attention from source

Write-Host "Building trainer with flash-attention from source (proper method)..."
Write-Host "This builds flash-attention v2.5.8 which is more stable"
Write-Host ""

# Clean up any existing trainer
docker-compose stop trainer 2>$null
docker container rm -f codelupe-trainer 2>$null
docker image rm -f codelupe-trainer 2>$null

Write-Host "Starting build with better source compilation..."
$startTime = Get-Date

# Build with real-time output
docker-compose build --no-cache --progress=plain trainer

if ($LASTEXITCODE -eq 0) {
    $totalTime = (Get-Date) - $startTime
    Write-Host "✅ Build completed in $($totalTime.ToString('mm\:ss'))" -ForegroundColor Green
    
    Write-Host "Testing flash-attention import..."
    $testResult = docker run --rm codelupe-trainer python3 -c "import flash_attn; print('Flash Attention version:', flash_attn.__version__)"
    
    if ($testResult -match "Flash Attention version") {
        Write-Host "✅ Flash Attention working: $testResult" -ForegroundColor Green
        
        Write-Host "Starting trainer..."
        docker-compose up -d trainer
        
        Start-Sleep 10
        Write-Host "Trainer logs:"
        docker logs codelupe-trainer --tail=10
    } else {
        Write-Host "⚠️ Flash Attention import test failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Build failed" -ForegroundColor Red
}