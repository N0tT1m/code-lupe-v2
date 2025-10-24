# Codelupe Windows Pipeline

Complete automated pipeline from GitHub repository collection to Codestral-22B training on Windows with RTX 4090.

## Quick Start

```batch
# 1. Start the complete pipeline
start-windows-pipeline.bat

# 2. Monitor progress
http://localhost:3000  (Grafana - admin/admin123)

# 3. Stop pipeline  
stop-windows-pipeline.bat
```

## Pipeline Flow

```
GitHub → Crawler → Downloader → Processor → Dataset → Ultra-Trainer → Model
```

### 1. **Crawler** 
- Searches GitHub for repositories
- Filters by language, stars, activity
- Stores metadata in PostgreSQL/Elasticsearch

### 2. **Downloader**
- Downloads repositories from GitHub
- Manages rate limiting and API tokens
- Stores in `\\\\192.168.1.66\plex3\codelupe\repos` directory

### 3. **Processor** 
- Extracts code files from repositories
- Filters by language and quality
- Creates training datasets in `\\\\192.168.1.66\plex3\codelupe\datasets`

### 4. **Ultra-Trainer**
- Trains Codestral-22B with LoRA
- Ultra-optimized for RTX 4090
- Saves models to `\\\\192.168.1.66\plex3\codelupe\models`

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3000 | Dashboards & Monitoring |
| Prometheus | 9090 | Metrics Collection |
| PostgreSQL | 5432 | Metadata Storage |
| Redis | 6379 | Caching & Queues |
| Elasticsearch | 9200 | Search & Indexing |
| Adminer | 8080 | Database Admin |
| Ultra-Trainer | 8090 | Training API |

## Grafana Dashboards

Access at http://localhost:3000 (admin/admin123):

1. **Codelupe Pipeline Overview** - High-level pipeline status
2. **Training Dashboard** - RTX 4090 training metrics, GPU usage, loss
3. **Data Pipeline** - Repository processing, file stats, errors  
4. **System Resources** - Container metrics, CPU, memory, disk

## Directory Structure

```
codelupe/
├── repos/              # Downloaded repositories
├── datasets/           # Generated training datasets  
├── models/             # Trained models
├── checkpoints/        # Training checkpoints
├── logs/              # Service logs
├── monitoring/        # Grafana/Prometheus configs
└── *_cache/          # Various caches
```

## Configuration

### Environment Variables

Set these in Windows before starting:

```batch
set GITHUB_TOKEN=your_github_token_here
set WANDB_API_KEY=your_wandb_key_here  
```

### Training Parameters

Edit in `docker-compose.windows.yml`:

```yaml
environment:
  - LORA_R=128              # LoRA rank
  - LORA_ALPHA=32           # LoRA alpha  
  - BATCH_SIZE=1            # Micro batch size
  - GRADIENT_ACCUMULATION_STEPS=32
  - LEARNING_RATE=1e-4
  - MAX_DATASET_SIZE=1000000
```

## Monitoring

### Real-time Monitoring
- **Grafana**: Complete dashboards with alerts
- **Logs**: `docker-compose -f docker-compose.windows.yml logs -f`
- **GPU**: `nvidia-smi -l 1`

### Key Metrics
- Repository collection rate
- File processing speed  
- Training loss and GPU utilization
- Memory usage and temperatures
- Pipeline errors and bottlenecks

## Windows-Specific Features

### File Paths
- Uses Windows-style paths (`\\\\192.168.1.66\plex3\codelupe\repos`)
- Compatible with Windows Docker Desktop
- Handles Windows file permissions

### GPU Support
- NVIDIA Container Toolkit integration
- RTX 4090 optimized settings
- Windows CUDA support

### Batch Scripts
- `start-windows-pipeline.bat` - One-click startup
- `stop-windows-pipeline.bat` - Graceful shutdown
- Automatic dependency checking

## Hardware Requirements

### Minimum
- Windows 10/11 with WSL2
- 16GB RAM
- 100GB free disk space
- NVIDIA GPU with 8GB+ VRAM

### Recommended (for RTX 4090)
- Windows 11
- 32GB+ RAM  
- 500GB+ NVMe SSD
- RTX 4090 (24GB VRAM)
- Fast internet connection

## Troubleshooting

### Docker Issues
```batch
# Restart Docker Desktop
# Enable WSL2 integration
# Install nvidia-container-toolkit
```

### GPU Issues  
```batch
# Update NVIDIA drivers
# Install CUDA Toolkit
# Verify: nvidia-smi
```

### Memory Issues
```batch
# Reduce LORA_R in docker-compose.windows.yml
# Lower BATCH_SIZE
# Increase Windows virtual memory
```

### Permission Issues
```batch
# Run as Administrator
# Check Docker Desktop settings
# Verify WSL2 file permissions
```

## Performance Tips

1. **Use SSD storage** for all directories
2. **Set GitHub token** for higher API limits  
3. **Monitor GPU temperature** during training
4. **Close unnecessary applications**
5. **Use Windows Game Mode** for better performance

## Pipeline Control

### Start Individual Services
```batch
# Just database services
docker-compose -f docker-compose.windows.yml up -d postgres redis elasticsearch

# Just training (requires datasets)
docker-compose -f docker-compose.windows.yml up -d ultra-trainer
```

### Scale Services
```batch
# Multiple processors
docker-compose -f docker-compose.windows.yml up -d --scale processor=3
```

### View Specific Logs
```batch
# Training logs only
docker-compose -f docker-compose.windows.yml logs -f ultra-trainer

# All errors
docker-compose -f docker-compose.windows.yml logs | findstr ERROR
```

## Output

### Trained Models
Models saved to `\\\\192.168.1.66\plex3\codelupe\models` with:
- LoRA adapters
- Tokenizer configuration
- Training metadata
- Performance metrics

### Datasets  
Generated datasets in `\\\\192.168.1.66\plex3\codelupe\datasets`:
- JSON format for training
- Language-separated files
- Quality filtered code

### Metrics
Comprehensive metrics in Grafana:
- Training progress and performance
- System resource utilization  
- Pipeline throughput and errors
- GPU utilization and temperatures

## Next Steps

After training completes:
1. **Evaluate model** using validation scripts
2. **Deploy model** to your applications
3. **Fine-tune further** with specific datasets
4. **Monitor performance** in production