Write-Host "🔧 REBUILDING SERVICES" -ForegroundColor Yellow
Write-Host "======================"
Write-Host ""

Write-Host "🛠️ Rebuilding metrics-exporter with Go 1.22..." -ForegroundColor Cyan
docker-compose build metrics-exporter

Write-Host ""
Write-Host "🛠️ Rebuilding trainer with latest changes..." -ForegroundColor Cyan  
docker-compose build trainer

Write-Host ""
Write-Host "🔄 Restarting affected services..." -ForegroundColor Green
docker-compose up -d metrics-exporter trainer

Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "✅ Services rebuilt successfully!" -ForegroundColor Green
Write-Host ""