# CodeLupe 🔍

**Version:** 2.0
**Optimized For:** RTX 5090 (32GB VRAM) + Ryzen 9 3900X

A sophisticated GitHub repository indexing, downloading, and AI training system focused on high-quality code. Continuously trains Qwen2.5-Coder-14B on curated repositories across Rust, Go, Python, TypeScript, and more.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Components](#components)
7. [Development](#development)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)

---

## Quick Start

### Prerequisites

- **Hardware**: Multi-core CPU (12+ cores), 64GB RAM, RTX 5090 or similar GPU, 1TB+ SSD
- **Software**: Docker & Docker Compose 24+, CUDA 12.4+ (for GPU training)

### 5-Minute Setup

```bash
# 1. Clone repository
git clone https://github.com/n0tt1m/codelupe.git
cd codelupe

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start all services
docker-compose up -d

# 4. View logs
docker-compose logs -f trainer

# 5. Access services
# - Kibana: http://localhost:5601
# - Grafana: http://localhost:3000
# - Trainer Health: http://localhost:8090/health
```

---

## Features

- **275+ Search Terms**: Comprehensive coverage of Rust, Go, Python, TypeScript, AI/ML, databases, frameworks, and DevOps tools
- **Quality Filtering**: Intelligent filtering to exclude tutorials, demos, and low-quality repositories
- **Multi-Database**: Elasticsearch (search), PostgreSQL (metadata), MongoDB, Redis
- **High-Performance Processing**: Optimized for Ryzen 9 3900X (24 threads) - configurable worker count
- **GPU Training**: Continuous Qwen2.5-Coder-14B training on RTX 5090 with 4-bit quantization + LoRA
- **Resumable Pipeline**: Checkpoint-based processing with automatic resume
- **Real-time Monitoring**: Prometheus, Grafana, Weights & Biases integration
- **Docker Deployment**: Complete containerized stack with GPU support

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CODELUPE PIPELINE                           │
└─────────────────────────────────────────────────────────────────────┘

GitHub Crawler → Elasticsearch → PostgreSQL → Downloader → Processor → Trainer
     ↓              ↓              ↓            ↓           ↓           ↓
  275+ terms    Index repos    Metadata    Git clone    Parse      Qwen 14B
  5 pages ea.   Fast search    Quality     Filter      Files      4-bit LoRA
```

### Data Flow

1. **Crawler** (`main.go`): Scrapes GitHub for 275+ terms → Elasticsearch
2. **Downloader** (`downloader.go`): Quality filters → Git clone repositories
3. **Processor** (`resumable_processor.go`): Parse files → PostgreSQL (processed_files)
4. **Trainer** (`continuous_training_qwen.py`): Train Qwen2.5-Coder-14B → Save LoRA adapter

### Key Components

| Component | Language | Purpose | Port |
|-----------|----------|---------|------|
| Crawler | Go | GitHub search & indexing | - |
| Downloader | Go | Repository downloads | - |
| Processor | Go | **File processing (48 workers)** | - |
| Trainer | Python | AI model training | 8090 |
| Elasticsearch | - | Search index | 9200 |
| PostgreSQL | - | Metadata storage | 5433 |
| Prometheus | - | Metrics | 9090 |
| Grafana | - | Dashboards | 3000 |

---

## Installation

### System Requirements

**Minimum**: 8 cores, 32GB RAM, RTX 3090 (24GB), 500GB SSD
**Recommended**: 12+ cores, 64GB RAM, RTX 5090 (32GB), 1TB NVMe

### Step-by-Step

#### 1. Install Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Install NVIDIA Container Toolkit (for GPU)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### 2. Clone & Configure

```bash
git clone https://github.com/yourusername/codelupe.git
cd codelupe
cp .env.example .env
nano .env  # Edit configuration
```

#### 3. Start Services

```bash
docker-compose up -d
docker-compose ps  # Verify all services running
```

#### 4. Verify Installation

```bash
curl http://localhost:9200  # Elasticsearch
curl http://localhost:8090/health  # Trainer
docker-compose exec postgres psql -U coding_user -d coding_db -c "SELECT version();"
```

---

## Configuration

### Main Configuration Files

#### 1. `config.json` - Main Settings

```json
{
  "github_tokens": ["your_token_here"],
  "storage": {
    "primary_path": "/app/repos",
    "max_primary_gb": 14000
  },
  "performance": {
    "workers_per_token": 4,
    "concurrent_clones": 8
  },
  "quality_filters": {
    "min_stars": 10,
    "min_quality_score": 30,
    "max_repo_size_kb": 100000
  },
  "target_languages": [
    "Python", "Go", "Dart", "TypeScript", "JavaScript", "C#", "Rust", "SQL"
  ]
}
```

#### 2. Worker Configuration - `resumable_processor.go:105`

**Current Setting** (48 workers on 24-thread CPU):
```go
workerCount := runtime.GOMAXPROCS(0) * 2  // 48 workers
```

**To Change Worker Count**:

| Setting | Workers | Use Case |
|---------|---------|----------|
| `runtime.GOMAXPROCS(0) * 1` | 24 | Low CPU usage |
| `runtime.GOMAXPROCS(0) * 2` | 48 | **Balanced (default)** |
| `runtime.GOMAXPROCS(0) * 4` | 96 | Maximum throughput |
| `4` (fixed) | 4 | **Fixed 4 workers** |

**Example - Set to 4 workers**:
```go
workerCount := 4  // Fixed 4 workers regardless of CPU count
```

#### 3. Environment Variables (`.env`)

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=coding_db
POSTGRES_USER=coding_user
POSTGRES_PASSWORD=coding_pass

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# GitHub
GITHUB_TOKEN=your_token_here

# Paths
DOWNLOAD_DIR=/app/repos
REPOS_DIR=/app/repos

# Training
WANDB_API_KEY=your_wandb_key  # Optional
```

---

## Components

### 1. GitHub Crawler (`main.go`)

**Purpose**: Scrapes GitHub search results and indexes repositories

**Features**:
- 275+ curated search terms (languages, frameworks, AI/ML, databases, DevOps)
- Rate limiting with exponential backoff
- Elasticsearch indexing
- Metadata extraction (stars, forks, topics, language)

**Usage**:
```bash
go run main.go
# Or: docker-compose up -d crawler
```

### 2. Repository Downloader (`downloader.go`)

**Purpose**: Downloads repositories from Elasticsearch index with quality filtering

**Features**:
- Quality filters (min stars, forks, languages)
- Concurrent downloads (configurable)
- PostgreSQL metadata tracking
- Retry logic for failures

**Usage**:
```bash
go run downloader.go download ./repos 3  # 3 concurrent downloads
go run downloader.go retry ./repos 3     # Retry failed
```

### 3. Resumable Processor (`resumable_processor.go`) ⚙️

**Purpose**: Processes downloaded repositories and extracts code files

**Worker Configuration** (Line 105):
```go
workerCount := runtime.GOMAXPROCS(0) * 2  // Currently: 48 workers
```

**To set to 4 workers**:
```go
workerCount := 4  // Fixed 4 workers
```

**Features**:
- Resumable processing with PostgreSQL checkpoints
- Parallel file processing (configurable workers)
- Quality scoring (0-100)
- MD5 deduplication
- Language detection
- Batch inserts for performance

**Database Tables**:
- `processing_jobs`: Job status tracking
- `processed_files`: Extracted code files
- `processing_checkpoints`: Resume points

**Usage**:
```bash
export DATABASE_URL="postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"
export REPOS_DIR="/app/repos"
go run resumable_processor.go
```

### 4. Qwen Trainer (`continuous_training_qwen.py`)

**Purpose**: Continuously trains Qwen2.5-Coder-14B on processed code

**Training Loop**:
1. Check for new files every 5 minutes
2. If ≥1000 new quality files (score ≥70): start training
3. Format as instruction-completion pairs
4. Train for 1 epoch with early stopping
5. Save best LoRA adapter

**Memory Usage** (RTX 5090 32GB):
- Model weights (4-bit): 7.0 GB
- LoRA adapters (rank 256): 0.2 GB
- Optimizer states (8-bit): 7.0 GB
- Activations/gradients: 10.0 GB
- CUDA overhead: 3.0 GB
- **Total**: 27.2 GB / 32 GB (85%)

**Configuration**:
```python
batch_size = 4
gradient_accumulation_steps = 4
lora_rank = 256
lora_alpha = 512
max_seq_length = 4096
```

**Usage**:
```bash
docker-compose up -d trainer
docker-compose logs -f trainer
curl http://localhost:8090/health
```

---

## Development

### Setup Development Environment

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Install Go tools
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

### Running Tests

```bash
# Python tests
pytest tests/python/ -v --cov

# Go tests
go test -v ./...

# Integration tests
pytest -m integration
```

### Code Quality

```bash
# Format Python
black src/python/

# Lint Python
ruff check src/python/

# Type check
mypy src/python/

# Format Go
gofmt -w .

# Lint Go
golangci-lint run
```

### Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(crawler): add exponential backoff
fix(trainer): resolve CUDA OOM
docs: update README
```

**Types**: feat, fix, docs, style, refactor, perf, test, build, ci, chore

---

## API Reference

### Trainer Health

**GET** `http://localhost:8090/health`

```json
{
  "status": "healthy",
  "model_loaded": true,
  "last_trained_id": 15789
}
```

### Trainer Metrics

**GET** `http://localhost:8090/metrics`

```json
{
  "state": {
    "last_trained_id": 15789,
    "total_training_runs": 5
  },
  "train_metrics": {
    "loss": 0.234,
    "eval_loss": 0.198
  }
}
```

### Database Queries

```sql
-- Download statistics
SELECT * FROM get_download_stats();

-- Top repos by language
SELECT * FROM get_repos_by_language('Rust');

-- All processed files
SELECT language, COUNT(*), AVG(quality_score)
FROM processed_files
GROUP BY language;
```

### Elasticsearch

```bash
curl -X GET "localhost:9200/github-coding-repos/_search" \
  -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        {"match": {"language": "Rust"}},
        {"range": {"stars": {"gte": 100}}}
      ]
    }
  }
}'
```

---

## Troubleshooting

### Docker Build Fails (OOM)

```bash
# Increase Docker memory to 16GB+ in Docker Desktop settings
# Or build with fewer jobs:
docker-compose build --build-arg MAX_JOBS=1 trainer
```

### CUDA Out of Memory

Reduce memory usage in training config:
```python
batch_size = 2          # Reduce from 4
lora_rank = 128         # Reduce from 256
max_seq_length = 2048   # Reduce from 4096
```

### PostgreSQL Connection Issues

```bash
docker-compose ps postgres          # Check status
docker-compose logs postgres        # View logs
docker-compose restart postgres     # Restart
docker-compose exec postgres psql -U coding_user -d coding_db  # Test
```

### Import Errors (Python)

```bash
pip install -e .        # Reinstall in dev mode
pip install -e ".[dev]" # With dev dependencies
```

---

## Contributing

### Pull Request Process

1. **Fork and clone**: `git clone https://github.com/yourusername/codelupe.git`
2. **Create branch**: `git checkout -b feat/your-feature`
3. **Make changes**: Edit code, add tests
4. **Run tests**: `pytest -v && go test -v ./...`
5. **Commit**: `git commit -m "feat(component): description"`
6. **Push**: `git push origin feat/your-feature`
7. **Create PR**: On GitHub

### Code Style

**Python**: PEP 8, type hints, max 100 chars, format with `black`
**Go**: Effective Go, format with `gofmt`, lint with `golangci-lint`

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Monitoring

### Dashboards

- **Grafana**: http://localhost:3000 (system metrics, training metrics)
- **Kibana**: http://localhost:5601 (logs, search analytics)
- **Prometheus**: http://localhost:9090 (raw metrics)
- **W&B**: https://wandb.ai (experiment tracking)

### Logs

```bash
docker-compose logs -f              # All logs
docker-compose logs -f trainer      # Trainer only
docker-compose logs -f --tail=100   # Last 100 lines
```

---

## Performance Tuning

### Processor Workers

**File**: `resumable_processor.go:105`

| Configuration | Workers (24-thread CPU) | Use Case |
|---------------|-------------------------|----------|
| `runtime.GOMAXPROCS(0) * 1` | 24 | Low CPU load |
| `runtime.GOMAXPROCS(0) * 2` | 48 | **Balanced** |
| `runtime.GOMAXPROCS(0) * 4` | 96 | Max throughput |
| `4` (fixed) | 4 | **Fixed count** |

### Training Settings

**RTX 5090 (32GB)**:
- Batch size: 4-8
- Seq length: 4096
- LoRA rank: 256
- 4-bit quantization

**RTX 3090 (24GB)**:
- Batch size: 2-4
- Seq length: 2048
- LoRA rank: 128
- 4-bit quantization

---

## Project Structure

```
codelupe/
├── main.go                      # GitHub crawler
├── downloader.go                # Repository downloader
├── resumable_processor.go       # Code processor (WORKER CONFIG: Line 105)
├── metrics_exporter.go          # Prometheus metrics
├── config.json                  # Main configuration
├── docker-compose.yml           # Service orchestration
├── README.md                    # This file
├── CONTRIBUTING.md              # Contribution guidelines
├── docs/
│   ├── ARCHITECTURE.md          # Detailed architecture
│   ├── QUICK_START.md           # Quick start guide
│   └── DVC_SETUP.md             # Data versioning
├── src/
│   ├── python/trainers/         # Training scripts
│   └── go/processor/            # Go processors
└── tests/
    ├── python/                  # Python tests
    └── go/                      # Go tests
```

---

## Useful Commands

```bash
# Start/Stop
docker-compose up -d             # Start all
docker-compose down              # Stop all
docker-compose restart trainer   # Restart service

# Build
docker-compose build trainer     # Rebuild trainer

# Logs
docker-compose logs -f trainer   # Follow logs

# Database
docker-compose exec postgres psql -U coding_user -d coding_db

# Backup/Restore
docker-compose exec postgres pg_dump -U coding_user coding_db > backup.sql
cat backup.sql | docker-compose exec -T postgres psql -U coding_user coding_db

# Clean up
docker system prune -a           # Remove unused containers/images
```

---

## License

MIT License - see LICENSE file for details

## Support

For issues:
1. Check logs: `docker-compose logs <service>`
2. Check health: `curl http://localhost:8090/health`
3. Review [docs/](docs/) directory
4. Open GitHub issue

---

**End of README**

For detailed architecture diagrams and deep dives, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)