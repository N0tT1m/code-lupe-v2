# Ultra-Optimized RTX 4090 Training with Docker Compose

This setup provides a localhost-based Docker Compose configuration for ultra-optimized Codestral-22B training on RTX 4090.

## Quick Start

```bash
# 1. Start ultra-optimized training
./scripts/start-ultra-training.sh

# 2. Monitor training (optional)
docker-compose -f docker-compose.ultra.yml logs -f ultra-trainer

# 3. Stop training
./scripts/stop-ultra-training.sh
```

## Features

### 🚀 Ultra-Optimizations for RTX 4090
- **4-bit quantization** with NF4 + double quantization
- **Flash Attention 2** for memory efficiency  
- **BF16 mixed precision** training
- **8-bit AdamW optimizer**
- **Aggressive LoRA** (r=128, alpha=32)
- **Streaming datasets** for massive files
- **Memory-mapped file loading**
- **Model compilation** with PyTorch 2.0

### 🐳 Docker Setup
- **Host networking** for maximum performance
- **NVIDIA runtime** with GPU passthrough
- **Localhost connections** to all services
- **Auto-detection** of dataset files
- **Volume mounting** for persistent storage

### 📊 Monitoring
- **Grafana** dashboard at http://localhost:3000
- **Prometheus** metrics at http://localhost:9090
- **Real-time training logs**
- **GPU memory monitoring**

## Directory Structure

```
├── datasets/           # Your training datasets (JSON files)
├── ultra_datasets/     # Additional massive datasets  
├── models/            # Output trained models
├── checkpoints/       # Training checkpoints
├── logs/             # Training logs
├── cache/            # Caching directory
└── monitoring/       # Grafana/Prometheus configs
```

## Configuration

### Environment Variables

The ultra-trainer accepts these environment variables:

```bash
# Database
DATABASE_URL=postgres://coding_user:coding_pass@host.docker.internal:5432/coding_db

# Datasets (comma-separated paths)
DATASET_PATHS=/app/ultra_datasets/dataset1.json,/app/ultra_datasets/dataset2.json

# Training parameters
CUDA_MEMORY_FRACTION=0.98
OMP_NUM_THREADS=12
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# Output
OUTPUT_DIR=/app/models/codestral_ultra_optimized
WANDB_PROJECT=codelupe-ultra-training
```

### Dataset Format

Place JSON files in `datasets/` or `ultra_datasets/` directories:

```json
[
  {"text": "your training code/text here"},
  {"text": "more training data..."},
  ...
]
```

## Training Configuration

The ultra-optimized trainer uses these settings:

- **Base Model**: `mistralai/Codestral-22B-v0.1`
- **LoRA Rank**: 128 (high performance)
- **LoRA Alpha**: 32 (stable training)
- **Batch Size**: 1 (micro-batch)
- **Gradient Accumulation**: 32 steps
- **Effective Batch Size**: 32
- **Learning Rate**: 1e-4
- **Quantization**: 4-bit NF4
- **Attention**: Flash Attention 2

## Memory Usage

Expected VRAM usage on RTX 4090:
- **Base Model (4-bit)**: ~12GB
- **LoRA Adapters**: ~2GB  
- **Training Overhead**: ~6GB
- **Total**: ~20GB (fits in 24GB)

## Commands

### Start Training
```bash
./scripts/start-ultra-training.sh
```

### Monitor Training  
```bash
# Follow logs
docker-compose -f docker-compose.ultra.yml logs -f ultra-trainer

# Check GPU usage
nvidia-smi

# View container stats
docker stats codelupe-ultra-trainer
```

### Stop Training
```bash
./scripts/stop-ultra-training.sh
```

### Manual Controls
```bash
# Start specific services
docker-compose -f docker-compose.ultra.yml up -d postgres redis

# Start only trainer
docker-compose -f docker-compose.ultra.yml up ultra-trainer

# Scale down
docker-compose -f docker-compose.ultra.yml down
```

## Troubleshooting

### NVIDIA Runtime Issues
```bash
# Install nvidia-container-toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Memory Issues
```bash
# Reduce memory usage
export CUDA_MEMORY_FRACTION=0.90
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:64

# Check GPU memory
nvidia-smi -l 1
```

### Dataset Issues
```bash
# Check dataset files
find datasets ultra_datasets -name "*.json" -exec wc -l {} \;

# Validate JSON format
python -m json.tool datasets/your_dataset.json > /dev/null
```

## Performance Tips

1. **Use SSD storage** for datasets and models
2. **Close other GPU applications** (browsers, etc.)
3. **Monitor GPU temperature** during training
4. **Use smaller datasets** for testing first
5. **Enable swap** if you have limited RAM

## Output

Trained models are saved to:
- **Final Model**: `./models/codestral_ultra_optimized/`
- **Checkpoints**: `./checkpoints/checkpoint-{step}/`
- **Logs**: `./logs/`

The model includes:
- LoRA adapters
- Tokenizer configuration  
- Training configuration
- Metadata about optimizations used