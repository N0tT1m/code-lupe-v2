Write-Host "📊 CODELUPE TRAINING MONITOR" -ForegroundColor Cyan
Write-Host "============================"
Write-Host ""

# Check if services are running
Write-Host "🔍 Service Status:" -ForegroundColor Yellow
docker-compose ps | Select-String -Pattern "(trainer|processor|postgres)"
Write-Host ""

# Check GPU utilization
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    Write-Host "🎯 GPU Status:" -ForegroundColor Green
    nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits
    Write-Host ""
} else {
    Write-Host "❌ nvidia-smi not found. Install NVIDIA drivers." -ForegroundColor Red
    Write-Host ""
}

# Get training metrics
Write-Host "🤖 Training Metrics:" -ForegroundColor Magenta
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8090/metrics" -TimeoutSec 5
    Write-Host "✅ Trainer service is running" -ForegroundColor Green
    
    $metrics = $response.metrics
    Write-Host "📈 Model Version: $($metrics.model_version)"
    Write-Host "📁 Total Files Trained: $($metrics.total_files_trained)"
    Write-Host "🕐 Last Training: $($metrics.last_training_time -replace 'null', 'Never')"
    Write-Host "🔄 Training Active: $($response.training_in_progress)"
    Write-Host "💾 GPU Memory: $([math]::Round($response.gpu_memory_used, 1))GB / $([math]::Round($response.gpu_memory_total, 1))GB"
    
} catch {
    Write-Host "❌ Trainer service not accessible" -ForegroundColor Red
    Write-Host "   Check: http://localhost:8090/metrics"
}
Write-Host ""

# Get processing metrics  
Write-Host "⚙️ Processing Metrics:" -ForegroundColor Blue
try {
    $null = Invoke-RestMethod -Uri "http://localhost:9091/metrics" -TimeoutSec 5
    Write-Host "✅ Processor service is running" -ForegroundColor Green
    Write-Host "📊 Processing metrics: http://localhost:9091/metrics"
} catch {
    Write-Host "❌ Processor service not accessible" -ForegroundColor Red
}
Write-Host ""

# Show recent logs
Write-Host "📋 Recent Training Logs (last 10 lines):" -ForegroundColor Yellow
try {
    docker-compose logs --tail=10 trainer 2>$null
} catch {
    Write-Host "❌ No trainer logs available" -ForegroundColor Red
}
Write-Host ""

Write-Host "💡 Live monitoring commands:" -ForegroundColor Cyan
Write-Host "  • Training logs:     docker-compose logs -f trainer"
Write-Host "  • Processing logs:   docker-compose logs -f processor"
Write-Host "  • GPU monitoring:    nvidia-smi -l 1"
Write-Host "  • Training web UI:   http://localhost:8090/metrics"
Write-Host "  • Refresh monitor:   .\monitor_training.ps1"
Write-Host ""