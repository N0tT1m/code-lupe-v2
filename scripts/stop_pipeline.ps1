Write-Host "🛑 STOPPING CODELUPE CONTINUOUS TRAINING PIPELINE" -ForegroundColor Red
Write-Host "================================================="
Write-Host ""

Write-Host "💾 Gracefully stopping services..." -ForegroundColor Yellow
Write-Host "  • Saving trainer state and model checkpoints"
Write-Host "  • Stopping continuous training"
Write-Host "  • Shutting down processing pipeline"
Write-Host "  • Stopping monitoring services"
Write-Host ""

# Stop all services gracefully
docker-compose down

Write-Host ""
Write-Host "📊 Final Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "✅ Pipeline stopped successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "💡 Commands:" -ForegroundColor Yellow
Write-Host "  • Restart:      .\start_pipeline.ps1"
Write-Host "  • Remove data:  docker-compose down -v"
Write-Host "  • Rebuild:      docker-compose build"
Write-Host ""