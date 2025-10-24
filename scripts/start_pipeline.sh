#!/bin/bash

echo "🚀 CODELUPE CONTINUOUS TRAINING PIPELINE"
echo "🔥 LINUX OPTIMIZED + RTX 4090 + RYZEN 9 3900X"
echo "=============================================="
echo ""

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Check NVIDIA Docker runtime
if ! docker info | grep -q nvidia; then
    echo "⚠️  NVIDIA Docker runtime not detected. GPU training may not work."
    echo "   Install nvidia-docker2 for GPU support."
fi

# Create required directories
echo "📁 Creating directories..."
mkdir -p models checkpoints logs datasets

# Check if G:/repos exists (Windows path)
if [ ! -d "/mnt/g/repos" ] && [ ! -d "/g/repos" ] && [ ! -d "G:/repos" ]; then
    echo "⚠️  G:/repos not found. Make sure your repos are at G:/repos"
    echo "   Or update the volume mapping in docker-compose.yml"
fi

echo ""
echo "🔄 Starting services..."
echo "  • PostgreSQL Database"
echo "  • Elasticsearch & Kibana"  
echo "  • MongoDB & Admin"
echo "  • Redis Cache"
echo "  • Prometheus & Grafana"
echo "  • Repository Processor"
echo "  • Metrics Exporter"
echo "  • 🤖 CONTINUOUS TRAINER (RTX 4090)"
echo ""

# Start all services
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 30

# Show status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "🌐 Access Points:"
echo "  • Grafana Dashboard:    http://localhost:3000 (admin/admin123)"
echo "  • Prometheus:           http://localhost:9090"
echo "  • Kibana:               http://localhost:5601"
echo "  • MongoDB Admin:        http://localhost:8081"
echo "  • PostgreSQL Admin:     http://localhost:8080"
echo "  • Processing Metrics:   http://localhost:9091/metrics"
echo "  • 🤖 Training Metrics:  http://localhost:8090/metrics"
echo ""
echo "📈 Monitor Training:"
echo "  • Training logs:        docker-compose logs -f trainer"
echo "  • Processing logs:      docker-compose logs -f processor"
echo "  • GPU utilization:      nvidia-smi"
echo ""
echo "🎯 Training Pipeline Active!"
echo "   New repositories processed → Automatic model improvement"
echo "   Codestral-22B LoRA fine-tuning running continuously"
echo ""