#!/bin/bash

# Ultra-Optimized Training Startup Script for RTX 4090
set -e

echo "🚀 Starting Ultra-Optimized Codestral-22B Training"
echo "=================================================="

# Check for NVIDIA Docker runtime
if ! docker info | grep -q nvidia; then
    echo "❌ NVIDIA Docker runtime not detected!"
    echo "Install nvidia-container-toolkit and restart Docker"
    exit 1
fi

# Check GPU availability
if ! nvidia-smi > /dev/null 2>&1; then
    echo "❌ NVIDIA GPU not detected!"
    exit 1
fi

GPU_COUNT=$(nvidia-smi -L | wc -l)
GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)

echo "✅ Found $GPU_COUNT GPU(s)"
echo "✅ GPU Memory: ${GPU_MEMORY}MB"

if [ "$GPU_MEMORY" -lt 20000 ]; then
    echo "⚠️  Warning: Less than 20GB VRAM detected. Training may be slower."
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p datasets ultra_datasets models checkpoints logs cache
mkdir -p monitoring/prometheus monitoring/grafana/dashboards monitoring/grafana/datasources

# Create basic Prometheus config if it doesn't exist
if [ ! -f "monitoring/prometheus.yml" ]; then
    echo "📝 Creating Prometheus configuration..."
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ultra-trainer'
    static_configs:
      - targets: ['localhost:8091']
    scrape_interval: 5s
    metrics_path: /metrics
EOF
fi

# Create Grafana datasource config
if [ ! -f "monitoring/grafana/datasources/prometheus.yml" ]; then
    echo "📝 Creating Grafana datasource configuration..."
    mkdir -p monitoring/grafana/datasources
    cat > monitoring/grafana/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
EOF
fi

# Check for dataset files
DATASET_COUNT=$(find datasets ultra_datasets -name "*.json" 2>/dev/null | wc -l)
echo "📊 Found $DATASET_COUNT dataset files"

if [ "$DATASET_COUNT" -eq 0 ]; then
    echo "⚠️  No dataset files found in datasets/ or ultra_datasets/"
    echo "   Add your JSON dataset files to these directories"
fi

# Start services
echo "🐳 Starting Docker Compose services..."
docker-compose -f docker-compose.ultra.yml up -d postgres redis prometheus grafana

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
docker-compose -f docker-compose.ultra.yml ps

# Start ultra-trainer
echo "🔥 Starting Ultra-Optimized Trainer..."
docker-compose -f docker-compose.ultra.yml up ultra-trainer

echo "✅ Training setup complete!"
echo ""
echo "🌐 Access points:"
echo "   Grafana Dashboard: http://localhost:3000 (admin/admin123)"
echo "   Prometheus: http://localhost:9090"
echo "   Training Logs: docker-compose -f docker-compose.ultra.yml logs -f ultra-trainer"
echo ""
echo "🛑 To stop: docker-compose -f docker-compose.ultra.yml down"