#!/bin/bash

echo "📊 CODELUPE TRAINING MONITOR"
echo "============================"
echo ""

# Check if services are running
echo "🔍 Service Status:"
docker-compose ps | grep -E "(trainer|processor|postgres)"
echo ""

# Check GPU utilization
if command -v nvidia-smi &> /dev/null; then
    echo "🎯 GPU Status:"
    nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits
    echo ""
fi

# Get training metrics
echo "🤖 Training Metrics:"
if curl -s http://localhost:8090/metrics > /dev/null 2>&1; then
    echo "✅ Trainer service is running"
    curl -s http://localhost:8090/metrics | jq -r '
        "📈 Model Version: " + (.metrics.model_version | tostring) + 
        "\n📁 Total Files Trained: " + (.metrics.total_files_trained | tostring) + 
        "\n🕐 Last Training: " + (.metrics.last_training_time // "Never") +
        "\n🔄 Training Active: " + (.training_in_progress | tostring) +
        "\n💾 GPU Memory: " + (.gpu_memory_used | tostring) + "GB / " + (.gpu_memory_total | tostring) + "GB"
    ' 2>/dev/null || echo "📊 Raw metrics available at http://localhost:8090/metrics"
else
    echo "❌ Trainer service not accessible"
fi
echo ""

# Get processing metrics  
echo "⚙️ Processing Metrics:"
if curl -s http://localhost:9091/metrics > /dev/null 2>&1; then
    echo "✅ Processor service is running"
    echo "📊 Processing metrics available at http://localhost:9091/metrics"
else
    echo "❌ Processor service not accessible"
fi
echo ""

# Show recent logs
echo "📋 Recent Training Logs (last 10 lines):"
docker-compose logs --tail=10 trainer 2>/dev/null || echo "❌ No trainer logs available"
echo ""

echo "💡 Live monitoring:"
echo "  • Training logs:     docker-compose logs -f trainer"
echo "  • Processing logs:   docker-compose logs -f processor"
echo "  • GPU monitoring:    watch nvidia-smi"
echo "  • Training web UI:   http://localhost:8090/metrics"
echo ""