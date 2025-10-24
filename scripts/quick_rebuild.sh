#!/bin/bash

echo "⚡ QUICK REBUILD (KEEPS VOLUMES)"
echo "==============================="

# Stop all running containers
echo "🔄 Stopping all containers..."
docker-compose down

# Remove containers but keep volumes
echo "🗑️  Removing containers (keeping data)..."
docker-compose rm -f

# Remove only the application images (not infrastructure)
echo "🧹 Removing application images..."
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}" | grep -E "codelupe.*(trainer|processor|downloader)" | awk '{print $2}' | xargs -r docker rmi -f

# Clean build cache
echo "🧽 Cleaning build cache..."
docker builder prune -f

# Rebuild only the fixed services
echo "🔨 Rebuilding fixed services..."
docker-compose build --no-cache trainer processor downloader

# Start everything
echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Quick rebuild complete!"
echo ""
echo "📋 Monitor the fixes:"
echo "  docker-compose logs -f trainer processor downloader"