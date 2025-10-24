# Simple Kubernetes deployment script
Write-Host "Starting CodeLupe Kubernetes Pipeline..." -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green

# Check if kubectl is available
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: kubectl not found. Please install kubectl." -ForegroundColor Red
    exit 1
}

# Check if Docker Desktop is running (for local k8s)
$dockerStatus = docker info 2>$null
if (-not $dockerStatus) {
    Write-Host "ERROR: Docker not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Build images
Write-Host "Building Docker images..." -ForegroundColor Yellow
docker build -f Dockerfile.trainer -t codelupe-trainer:latest .
docker build -f Dockerfile.processor -t codelupe-processor:latest .

# Create namespace
Write-Host "Creating namespace..." -ForegroundColor Cyan
kubectl apply -f kubernetes/namespace.yaml

# Deploy storage
Write-Host "Deploying storage..." -ForegroundColor Cyan
kubectl apply -f kubernetes/storage.yaml

# Deploy services
Write-Host "Deploying PostgreSQL..." -ForegroundColor Cyan
kubectl apply -f kubernetes/postgres.yaml

Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=available --timeout=300s deployment/postgres -n codelupe

Write-Host "Deploying Processor..." -ForegroundColor Cyan
kubectl apply -f kubernetes/processor.yaml

Write-Host "Deploying Trainer..." -ForegroundColor Cyan
kubectl apply -f kubernetes/trainer.yaml

Write-Host "Deploying Monitoring..." -ForegroundColor Cyan
kubectl apply -f kubernetes/monitoring.yaml

# Wait for deployments with longer timeout for trainer
Write-Host "Waiting for deployments to be ready..." -ForegroundColor Yellow
Write-Host "(Trainer may take 10-15 minutes on first run)" -ForegroundColor Yellow

kubectl wait --for=condition=available --timeout=300s deployment/processor -n codelupe
kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n codelupe
kubectl wait --for=condition=available --timeout=300s deployment/grafana -n codelupe

Write-Host "Waiting for trainer (this takes longer)..." -ForegroundColor Yellow
kubectl wait --for=condition=available --timeout=1200s deployment/trainer -n codelupe

# Show status
Write-Host ""
Write-Host "Deployment Status:" -ForegroundColor Green
kubectl get pods -n codelupe

Write-Host ""
Write-Host "Access Points:" -ForegroundColor Green
Write-Host "* Training Metrics:  http://localhost:30090/metrics"
Write-Host "* Prometheus:        http://localhost:30900"  
Write-Host "* Grafana:           http://localhost:30300 (admin/admin123)"

Write-Host ""
Write-Host "Monitor Commands:" -ForegroundColor Yellow
Write-Host "* kubectl logs -f deployment/trainer -n codelupe"
Write-Host "* kubectl logs -f deployment/processor -n codelupe"
Write-Host "* kubectl get pods -n codelupe"

Write-Host ""
Write-Host "Training Pipeline Active!" -ForegroundColor Green
Write-Host "RTX 4090 + Ryzen 9 3900X ready for Codestral-22B training!"