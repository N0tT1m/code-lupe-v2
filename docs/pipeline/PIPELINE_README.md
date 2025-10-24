# 🚀 CodeLupe Continuous Training Pipeline

**Linux-optimized continuous training for Codestral-22B with RTX 4090 + Ryzen 9 3900X**

## 🎯 Quick Start

### Windows PowerShell:
```powershell
# Start entire pipeline
.\start_pipeline.ps1

# Monitor training
.\monitor_training.ps1

# Stop pipeline
.\stop_pipeline.ps1
```

### Linux/Mac:
```bash
# Start entire pipeline
./start_pipeline.sh

# Monitor training  
./monitor_training.sh

# Stop pipeline
./stop_pipeline.sh
```

## 🏗️ Architecture

### Services:
- **🤖 Trainer**: Continuous Codestral-22B LoRA fine-tuning
- **⚙️ Processor**: Multi-threaded repository processing
- **📊 Monitoring**: Prometheus + Grafana dashboards
- **💾 Databases**: PostgreSQL + MongoDB + Redis + Elasticsearch

### Continuous Learning Flow:
1. **Process** repositories in \\\\192.168.1.66\plex3\codelupe\repos 
2. **Analyze** code quality and extract features
3. **Trigger** training when sufficient new data available
4. **Train** Codestral-22B with LoRA (removes NSFW restrictions)
5. **Monitor** GPU utilization and training metrics
6. **Repeat** automatically

## 🎮 Configuration

### Training Parameters:
- **MIN_NEW_FILES**: 1000 (trigger training threshold)
- **MAX_DATASET_SIZE**: 100000 (max files per training cycle)
- **CHECK_INTERVAL**: 300 seconds (check for new data)
- **TRAINING_EPOCHS**: 1 (continuous learning)

### Hardware Optimization:
- **CPU**: 24 cores (Ryzen 9 3900X)
- **GPU**: RTX 4090 with 4-bit quantization
- **Memory**: 32GB container limit
- **Storage**: \\\\192.168.1.66\plex3\codelupe\repos for repository data

## 📊 Monitoring

### Web Interfaces:
- **Training Metrics**: http://localhost:8090/metrics
- **Processing Metrics**: http://localhost:9091/metrics  
- **Grafana Dashboard**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090

### Command Line:
```powershell
# Live training logs
docker-compose logs -f trainer

# GPU utilization
nvidia-smi -l 1

# Service status
docker-compose ps
```

## 🔧 Troubleshooting

### GPU Issues:
```powershell
# Check NVIDIA Docker
docker info | findstr nvidia

# Test GPU in container
docker run --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
```

### Service Issues:
```powershell
# Restart specific service
docker-compose restart trainer

# View service logs
docker-compose logs trainer

# Check health
docker-compose ps
```

### Storage Issues:
- Ensure \\\\192.168.1.66\plex3\codelupe\repos exists and contains repositories
- Check Docker volume permissions
- Verify available disk space for models/checkpoints

## 🎨 Model Output

The fine-tuned model will be saved to:
- **Active Model**: `./models/current_model/`
- **Checkpoints**: `./checkpoints/training_vX/`
- **Logs**: `./logs/continuous_training.log`

## 🔥 Performance Tips

1. **Pre-download** Codestral-22B model to avoid cold start delays
2. **Monitor** GPU temperature during training
3. **Use SSD** storage for faster model loading
4. **Close** unnecessary applications to free RAM
5. **Check** Windows power settings (High Performance mode)

## 🎯 Success Indicators

✅ **Training Active**: GPU utilization > 80%  
✅ **Data Processing**: New files being added to database  
✅ **Model Improving**: Version number incrementing  
✅ **Metrics Available**: All web endpoints responding  

---

**🤖 Enjoy your unrestricted coding model!**