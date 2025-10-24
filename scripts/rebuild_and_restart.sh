#!/bin/bash

echo "🛑 COMPLETE REBUILD AND RESTART SCRIPT"
echo "======================================="

# Stop all running containers
echo "🔄 Stopping all containers..."
docker-compose down

# Remove all containers (including stopped ones)
echo "🗑️  Removing all containers..."
docker-compose rm -f

# Remove all images to force rebuild
echo "🧹 Removing old images..."
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}" | grep codelupe | awk '{print $2}' | xargs -r docker rmi -f

# Remove dangling images and build cache
echo "🧽 Cleaning up dangling images and build cache..."
docker image prune -f
docker builder prune -f

# Remove volumes (CAREFUL - this removes data!)
echo "⚠️  WARNING: About to remove volumes (this will delete data!)"
read -p "Do you want to remove volumes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing volumes..."
    docker-compose down -v
    docker volume prune -f
else
    echo "ℹ️  Keeping volumes..."
fi

# Rebuild all images
echo "🔨 Rebuilding all images..."
docker-compose build --no-cache --parallel

# Start the infrastructure services first
echo "🚀 Starting infrastructure services..."
docker-compose up -d postgres elasticsearch redis mongodb

# Wait for services to be healthy
echo "⏳ Waiting for infrastructure to be ready..."
timeout=300
counter=0
while [ $counter -lt $timeout ]; do
    if docker-compose ps postgres | grep -q "healthy"; then
        if docker-compose ps elasticsearch | grep -q "healthy"; then
            echo "✅ Infrastructure is ready!"
            break
        fi
    fi
    echo "Waiting... ($counter/$timeout seconds)"
    sleep 5
    counter=$((counter + 5))
done

if [ $counter -ge $timeout ]; then
    echo "❌ Infrastructure failed to start within $timeout seconds"
    exit 1
fi

# Start the processing services
echo "🔄 Starting processing services..."
docker-compose up -d downloader processor

# Wait a bit then start trainer
echo "⏳ Waiting before starting trainer..."
sleep 30

echo "🤖 Starting trainer..."
docker-compose up -d trainer

# Start monitoring services
echo "📊 Starting monitoring services..."
docker-compose up -d grafana prometheus kibana adminer mongo-express metrics-exporter

echo "✅ All services started!"
echo ""
echo "📋 Service Status:"
docker-compose ps

echo ""
echo "🔗 Service URLs:"
echo "  - Grafana: http://localhost:3000 (admin/admin123)"
echo "  - Prometheus: http://localhost:9090"
echo "  - Kibana: http://localhost:5601"
echo "  - Adminer: http://localhost:8080"
echo "  - Mongo Express: http://localhost:8081"
echo "  - Trainer Metrics: http://localhost:8090/metrics"
echo "  - Pipeline Metrics: http://localhost:9091/metrics"

echo ""
echo "🏆 Rebuild complete! Monitor logs with:"
echo "  docker-compose logs -f"