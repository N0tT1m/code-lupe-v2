Write-Host "🚀 CODELUPE CONTINUOUS TRAINING PIPELINE" -ForegroundColor Green
Write-Host "🔥 WINDOWS + RTX 4090 + RYZEN 9 3900X" -ForegroundColor Yellow
Write-Host "==========================================" 
Write-Host ""

# Check Docker Compose
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ docker-compose not found. Please install Docker Compose." -ForegroundColor Red
    exit 1
}

# Check NVIDIA Docker runtime
$dockerInfo = docker info 2>$null | Select-String "nvidia"
if (-not $dockerInfo) {
    Write-Host "⚠️  NVIDIA Docker runtime not detected. GPU training may not work." -ForegroundColor Yellow
    Write-Host "   Install nvidia-docker2 for GPU support."
}

# Create required directories
Write-Host "📁 Creating directories..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "models", "checkpoints", "logs", "datasets" | Out-Null

# Check if G:/repos exists
if (-not (Test-Path "\\\\192.168.1.66\plex3\codelupe\repos")) {
    Write-Host "⚠️  \\\\192.168.1.66\plex3\codelupe\repos not found. Make sure your repositories are at \\\\192.168.1.66\plex3\codelupe\repos" -ForegroundColor Yellow
    Write-Host "   Or update the volume mapping in docker-compose.yml"
}

Write-Host ""
Write-Host "🔄 Starting services..." -ForegroundColor Cyan
Write-Host "  • PostgreSQL Database"
Write-Host "  • Elasticsearch & Kibana"  
Write-Host "  • MongoDB & Admin"
Write-Host "  • Redis Cache"
Write-Host "  • Prometheus & Grafana"
Write-Host "  • Repository Processor"
Write-Host "  • Metrics Exporter"
Write-Host "  • 🤖 CONTINUOUS TRAINER (RTX 4090)" -ForegroundColor Magenta
Write-Host ""

# Start all services
docker-compose up -d

Write-Host ""
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Show status
Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "Access Points:" -ForegroundColor Green
Write-Host "  * Grafana Dashboard:    http://localhost:3000 (admin/admin123)"
Write-Host "  * Prometheus:           http://localhost:9090"
Write-Host "  * Kibana:               http://localhost:5601"
Write-Host "  * MongoDB Admin:        http://localhost:8081"
Write-Host "  * PostgreSQL Admin:     http://localhost:8080"
Write-Host "  * Processing Metrics:   http://localhost:9091/metrics"
Write-Host "  * Training Metrics:     http://localhost:8090/metrics" -ForegroundColor Magenta
Write-Host ""
Write-Host "Monitor Training:" -ForegroundColor Yellow
Write-Host "  * Training logs:        docker-compose logs -f trainer"
Write-Host "  * Processing logs:      docker-compose logs -f processor"
Write-Host "  * GPU utilization:      nvidia-smi"
Write-Host "  * Monitor script:       .\monitor_training.ps1"
Write-Host ""
Write-Host "🎯 Training Pipeline Active!" -ForegroundColor Green
Write-Host "   New repositories processed → Automatic model improvement"
Write-Host "   Codestral-22B LoRA fine-tuning running continuously"
Write-Host ""