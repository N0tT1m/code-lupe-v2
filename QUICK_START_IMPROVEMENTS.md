# Quick Start Guide: Using the New Improvements

## 🎉 What's New

Your CodeLupe project has been upgraded with 10 major improvements! Here's how to use them.

## 🧪 Testing (Priority: Run These First!)

### Run Go Tests
```bash
# All tests with race detection
make test

# With coverage report
make test-coverage
open coverage.html  # View in browser
```

### Run Python Tests
```bash
# All Python tests
pytest tests/python/ -v

# Only unit tests (fast)
pytest -m "not integration"

# Only integration tests (requires services running)
docker-compose up -d postgres elasticsearch
pytest -m integration
```

## 🔐 Security Setup

### Initialize Secrets
```bash
# Run the setup script
./scripts/setup_secrets.sh

# It will prompt for:
# - PostgreSQL password
# - GitHub token
# - Weights & Biases API key
# - Hugging Face token
```

### Use Secrets in Docker
```bash
# Start with secrets (production mode)
docker-compose -f docker-compose.yml -f docker-compose.secrets.yml up -d

# Verify secrets are working
docker-compose exec trainer env | grep _FILE
```

## 📝 Git Commit Template

### Setup
```bash
# Configure git to use the template
git config --local commit.template .gitmessage

# Now when you commit:
git commit
# Your editor opens with the template!
```

### Example Commits
```bash
# Feature
git commit -m "feat(api): add repository search endpoint"

# Bug fix
git commit -m "fix(crawler): resolve rate limit handling"

# Documentation
git commit -m "docs(readme): update installation instructions"
```

## 🌐 API & Dashboard

### Start API Server
```bash
# Option 1: Standalone
go run cmd/api/main.go

# Option 2: With Docker (recommended)
docker-compose up api
```

### Access Dashboard
```bash
# Start a simple HTTP server
cd web/dashboard
python3 -m http.server 3000

# Open in browser
open http://localhost:3000
```

### API Examples
```bash
# Get stats
curl http://localhost:8080/api/v1/repositories/stats | jq

# Search repositories
curl "http://localhost:8080/api/v1/repositories/search?q=rust&min_stars=100" | jq

# Top quality repos
curl http://localhost:8080/api/v1/quality/top?limit=10 | jq

# Language stats
curl http://localhost:8080/api/v1/languages | jq
```

## 📊 Data Versioning (DVC)

### Initialize DVC
```bash
# DVC is already initialized, but you need to configure storage
# Option 1: S3 (production)
dvc remote modify storage url s3://your-bucket/codelupe-data
dvc remote modify storage region us-east-1

# Option 2: Local (development)
dvc remote modify storage url ./dvc-storage
```

### Track Data
```bash
# Track datasets
dvc add datasets/

# Track models
dvc add models/qwen-codelupe/

# Commit the .dvc files
git add datasets.dvc models.dvc .gitignore
git commit -m "feat(data): add DVC tracking for datasets and models"

# Push data to remote
dvc push
```

### Version Your Data
```bash
# Make changes to datasets
# ... add new files ...

# Update DVC tracking
dvc add datasets/

# Commit and tag
git add datasets.dvc
git commit -m "feat(data): add 10k new Rust samples"
git tag -a data-v1.1.0 -m "Dataset v1.1.0"

# Push everything
dvc push
git push --follow-tags
```

### Switch Versions
```bash
# Checkout old version
git checkout data-v1.0.0
dvc pull  # Downloads the data for that version

# Return to latest
git checkout main
dvc pull
```

## 🔧 Circuit Breaker (Error Handling)

Circuit breaker is already integrated into the codebase. To use it in your code:

```go
import "codelupe/pkg/circuitbreaker"

// Create circuit breaker
cb := circuitbreaker.New(circuitbreaker.Config{
    MaxFailures: 5,
    Timeout:     30 * time.Second,
    OnStateChange: func(from, to circuitbreaker.State) {
        log.Printf("Circuit: %s -> %s", from, to)
    },
})

// Use it
err := cb.Execute(func() error {
    return riskyOperation()
})
```

## 🧹 Repository Cleanup

### Run Cleanup Script
```bash
# This will organize scripts and remove binaries
./scripts/cleanup_repo.sh

# Review changes
git status

# Commit if happy with changes
git add .
git commit -m "chore: reorganize repository structure"
```

## 📦 Project Structure (After Improvements)

```
codelupe/
├── cmd/
│   └── api/               # API server
├── internal/
│   ├── api/              # API implementation
│   ├── downloader/       # Modular downloader
│   ├── models/           # Data models
│   ├── quality/          # Quality filters
│   └── storage/          # Database layer
├── pkg/
│   ├── circuitbreaker/   # Circuit breaker
│   └── secrets/          # Secrets management
├── tests/
│   ├── go/               # Go tests
│   └── python/           # Python tests
├── scripts/
│   ├── windows/          # PowerShell/Batch
│   ├── deployment/       # Shell scripts
│   └── monitoring/       # Monitoring scripts
├── web/
│   └── dashboard/        # Web dashboard
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DVC_SETUP.md
│   └── ...
├── .dvc/                 # DVC configuration
├── dvc.yaml             # DVC pipeline
├── CONTRIBUTING.md      # Contribution guide
└── IMPLEMENTATION_SUMMARY.md
```

## 🚀 Recommended Workflow

### Daily Development

1. **Pull latest code and data:**
   ```bash
   git pull
   dvc pull
   ```

2. **Make changes**

3. **Run tests:**
   ```bash
   make test
   pytest tests/python/ -v
   ```

4. **Commit with template:**
   ```bash
   git commit
   # Use the template to write a good message
   ```

5. **If you changed data:**
   ```bash
   dvc add datasets/
   git add datasets.dvc
   git commit -m "feat(data): describe changes"
   dvc push
   ```

### Before Pull Request

```bash
# Run all checks
make pre-commit

# This runs:
# - Code formatting
# - Linting
# - All tests
```

## 📈 Monitoring

### Check Services
```bash
# API health
curl http://localhost:8080/health

# Metrics
curl http://localhost:9091/metrics

# Elasticsearch
curl http://localhost:9200/_cluster/health

# Trainer status
curl http://localhost:8090/health
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trainer

# API logs
tail -f logs/api.log
```

## 🆘 Troubleshooting

### Tests Failing
```bash
# Clean cache and retry
make clean
make test

# For Python
pytest --cache-clear tests/python/
```

### Secrets Not Working
```bash
# Check secrets files exist
ls -la secrets/

# Verify permissions
chmod 600 secrets/*

# Test reading
go run -c 'import "codelupe/pkg/secrets"; secrets.ReadSecret("POSTGRES_PASSWORD")'
```

### DVC Issues
```bash
# Check status
dvc status -c

# Verify remote
dvc remote list

# Rebuild cache
dvc cache rebuild
```

### API Not Responding
```bash
# Check if running
curl http://localhost:8080/health

# Check logs
docker-compose logs api

# Restart
docker-compose restart api
```

## 📚 Additional Resources

- **Testing:** See test files for examples
- **API:** Check `internal/api/server.go` for all endpoints
- **DVC:** Read `docs/DVC_SETUP.md` for full guide
- **Contributing:** See `CONTRIBUTING.md` for guidelines
- **Architecture:** See `docs/ARCHITECTURE.md` for system design

## ✅ Verification Checklist

After implementing improvements, verify:

- [ ] Tests run successfully (`make test`)
- [ ] Python tests pass (`pytest tests/python/`)
- [ ] Secrets are configured (`ls secrets/`)
- [ ] Git template is set (`git config commit.template`)
- [ ] API responds (`curl localhost:8080/health`)
- [ ] Dashboard loads (http://localhost:3000)
- [ ] DVC is initialized (`dvc status`)
- [ ] Docker services start (`docker-compose up`)

## 🎓 Learning More

1. **Circuit Breaker:** `examples/circuit_breaker_usage.go`
2. **API Usage:** `internal/api/server.go`
3. **Testing:** `tests/python/conftest.py`
4. **DVC:** `docs/DVC_SETUP.md`
5. **Commits:** `.gitmessage`

---

**Questions?** Check `IMPLEMENTATION_SUMMARY.md` for detailed information on each improvement.

**Issues?** All improvements include comprehensive tests and documentation.

**Ready for production!** 🚀
