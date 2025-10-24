#!/bin/bash

echo "🚀 CodeLupe Monitoring Setup"
echo "================================"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command_exists docker; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Check if G:\repos exists (Windows path)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    if [ ! -d "/g/repos" ] && [ ! -d "G:/repos" ]; then
        echo "⚠️  Warning: G:/repos directory not found. Creating directory..."
        mkdir -p "/g/repos" 2>/dev/null || echo "❌ Could not create G:/repos directory"
    fi
fi

# Build all services
echo "🏗️  Building Docker images..."
docker-compose build

# Start infrastructure services first
echo "🚀 Starting infrastructure services..."
docker-compose up -d postgres redis elasticsearch mongodb

# Wait for services to be healthy
echo "⏳ Waiting for infrastructure services to be ready..."
sleep 30

# Check if services are healthy
check_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    echo "🔍 Checking $service..."
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps $service | grep -q "healthy\|Up"; then
            echo "✅ $service is ready"
            return 0
        fi
        echo "⏳ Waiting for $service (attempt $attempt/$max_attempts)..."
        sleep 10
        ((attempt++))
    done
    
    echo "❌ $service failed to start properly"
    return 1
}

# Check core services
check_service postgres
check_service elasticsearch
check_service redis

# Start monitoring services
echo "📊 Starting monitoring services..."
docker-compose up -d prometheus grafana metrics-exporter

# Wait for monitoring services
sleep 20
check_service prometheus
check_service grafana
check_service metrics-exporter

# Start processing services
echo "🔄 Starting processing services..."
docker-compose up -d crawler downloader processor

# Wait for processing services
sleep 15
check_service processor

# Display access information
echo ""
echo "🎉 CodeLupe Monitoring Setup Complete!"
echo "======================================"
echo ""
echo "📊 Access Points:"
echo "  • Grafana Dashboard:    http://localhost:3000 (admin/admin123)"
echo "  • Prometheus:           http://localhost:9090"
echo "  • Metrics Exporter:     http://localhost:9091/metrics"
echo "  • Elasticsearch:        http://localhost:9200"
echo "  • Kibana:              http://localhost:5601"
echo "  • PostgreSQL:           localhost:5432 (coding_user/coding_pass)"
echo "  • Redis:               localhost:6379"
echo "  • MongoDB:             localhost:27017"
echo "  • Adminer (DB GUI):    http://localhost:8080"
echo "  • Mongo Express:       http://localhost:8081"
echo ""
echo "📈 Monitoring Features:"
echo "  • Real-time processing metrics"
echo "  • Repository analysis dashboard"
echo "  • Worker performance tracking"
echo "  • System resource monitoring"
echo "  • Database performance metrics"
echo "  • Automatic alerting"
echo "  • Resume capability tracking"
echo ""
echo "🔄 Processing Pipeline:"
echo "  • Crawler: Discovers repositories"
echo "  • Downloader: Downloads to G:/repos"
echo "  • Processor: Processes files with full resume capability"
echo "  • All progress tracked in PostgreSQL"
echo ""

# Import Grafana dashboard
echo "📊 Setting up Grafana dashboard..."
sleep 10

# Wait for Grafana to be fully ready
echo "⏳ Waiting for Grafana to be ready..."
max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s -f http://localhost:3000/api/health >/dev/null 2>&1; then
        echo "✅ Grafana is ready"
        break
    fi
    echo "⏳ Waiting for Grafana (attempt $attempt/$max_attempts)..."
    sleep 5
    ((attempt++))
done

# Configure Prometheus datasource in Grafana
echo "🔗 Configuring Prometheus datasource..."
curl -X POST \
  http://admin:admin123@localhost:3000/api/datasources \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://prometheus:9090",
    "access": "proxy",
    "isDefault": true
  }' >/dev/null 2>&1

# Import dashboard (you'll need to do this manually via Grafana UI)
echo "📈 Dashboard JSON available at: ./grafana_dashboard.json"
echo "   Import this manually in Grafana > Dashboards > Import"

# Show running services
echo ""
echo "🐳 Running Services:"
docker-compose ps

# Show logs for any failed services
echo ""
echo "📋 Checking for any service issues..."
failed_services=$(docker-compose ps --services --filter "status=exited")
if [ -n "$failed_services" ]; then
    echo "❌ Some services failed to start:"
    echo "$failed_services"
    echo ""
    echo "📋 Use 'docker-compose logs <service_name>' to check logs"
else
    echo "✅ All services are running successfully"
fi

echo ""
echo "🎯 Next Steps:"
echo "1. Open Grafana at http://localhost:3000"
echo "2. Import the dashboard from grafana_dashboard.json"
echo "3. Monitor processing progress in real-time"
echo "4. Check G:/repos for downloaded repositories"
echo "5. Use 'docker-compose logs processor' to see processing logs"
echo ""
echo "🛠️  Troubleshooting:"
echo "• Stop all: docker-compose down"
echo "• View logs: docker-compose logs <service>"
echo "• Restart service: docker-compose restart <service>"
echo "• Check status: docker-compose ps"
echo ""
echo "🚀 Happy monitoring! Your Ryzen 9 3900X is ready to process at full speed!"