#!/bin/bash

echo "🛑 STOPPING CODELUPE CONTINUOUS TRAINING PIPELINE"
echo "================================================="
echo ""

echo "💾 Gracefully stopping services..."
echo "  • Saving trainer state and model checkpoints"
echo "  • Stopping continuous training"
echo "  • Shutting down processing pipeline"
echo "  • Stopping monitoring services"
echo ""

# Stop all services gracefully
docker-compose down

echo ""
echo "📊 Final Status:"
docker-compose ps

echo ""
echo "✅ Pipeline stopped successfully!"
echo ""
echo "💡 To restart: ./start_pipeline.sh"
echo "💡 To remove volumes: docker-compose down -v"
echo "💡 To rebuild: docker-compose build"
echo ""