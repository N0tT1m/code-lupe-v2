# Quick Start Guide

## Project Structure

```
codelupe/
├── src/
│   ├── python/
│   │   ├── trainers/          # AI model training scripts
│   │   ├── crawlers/          # GitHub repository crawlers
│   │   ├── processors/        # Data processing pipeline
│   │   └── utils/             # Shared utilities
│   └── go/
│       ├── crawler/           # Main crawler service
│       ├── downloader/        # Repository downloader
│       └── processor/         # High-performance processor
├── docs/                       # Documentation
├── tests/                      # Test suites
├── config/                     # Configuration files
└── scripts/                    # Helper scripts
```

## Quick Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- Go 1.21+ (for local development)

### 1. Clone & Configure
```bash
git clone <repository-url>
cd codelupe
cp .env.example .env
# Edit .env with your settings
```

### 2. Start Services
```bash
# Start all infrastructure services
docker-compose up -d

# View logs
docker-compose logs -f trainer
```

### 3. Development Setup (Optional)
```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/python/ -v
```

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main service orchestration |
| `pyproject.toml` | Python dependencies & config |
| `.pre-commit-config.yaml` | Code quality hooks |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `Dockerfile.qwen-5090` | Trainer container |

## Common Tasks

### Build Trainer
```bash
docker-compose build trainer
```

### View Trainer Logs
```bash
docker-compose logs -f trainer
```

### Run Tests
```bash
# Python tests
pytest tests/python/ -v --cov

# Go tests
go test -v ./...
```

### Code Quality
```bash
# Format code
black src/python/

# Lint code
ruff check src/python/

# Type check
mypy src/python/
```

### Access Services
- Kibana: http://localhost:5601
- Grafana: http://localhost:3000
- PostgreSQL Admin: http://localhost:8080
- Prometheus: http://localhost:9090
- Trainer Metrics: http://localhost:8090/metrics
- Trainer Health: http://localhost:8090/health

## Troubleshooting

### Docker Build Fails
```bash
# Increase Docker memory to 16GB+
# Docker Desktop → Settings → Resources → Memory

# Or build with single job
docker-compose build --build-arg MAX_JOBS=1 trainer
```

### Import Errors
```bash
# Reinstall in development mode
pip install -e .
```

### Pre-commit Hook Fails
```bash
# Auto-fix issues
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## Documentation

- **Architecture**: [docs/ARCHITECTURE.md](./ARCHITECTURE.md)
- **Improvements**: [docs/PROJECT_IMPROVEMENTS.md](./PROJECT_IMPROVEMENTS.md)
- **Deployment**: [docs/deployment/](./deployment/)
- **Models**: [docs/models/](./models/)

## Support

For issues:
1. Check logs: `docker-compose logs <service>`
2. Check health: `curl http://localhost:8090/health`
3. Review documentation in `docs/`
4. Open GitHub issue
