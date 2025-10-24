#!/bin/bash

# Stop Ultra-Optimized Training Script
set -e

echo "🛑 Stopping Ultra-Optimized Training..."

# Stop the ultra trainer gracefully
echo "📱 Stopping ultra-trainer container..."
docker-compose -f docker-compose.ultra.yml stop ultra-trainer

# Save any running checkpoints
echo "💾 Allowing time for checkpoint saves..."
sleep 10

# Stop all services
echo "🐳 Stopping all services..."
docker-compose -f docker-compose.ultra.yml down

# Optional: Clean up resources
read -p "🧹 Clean up Docker resources? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 Cleaning up Docker resources..."
    docker system prune -f
    docker volume prune -f
fi

echo "✅ Ultra-training stopped successfully!"
echo ""
echo "📊 Training artifacts preserved in:"
echo "   Models: ./models/"
echo "   Checkpoints: ./checkpoints/"
echo "   Logs: ./logs/"