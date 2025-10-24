# Codelupe Docker Daemon Crash Troubleshooting

## The Problem
Docker Desktop daemon crashes (CPU/RAM shows 0%) when building or running Codelupe, especially when:
- Running concurrent builds with other projects (like nexus-v2)
- Starting multiple heavy services simultaneously
- Trainer attempts to load large models
- Elasticsearch starts up with high memory allocation

## Root Causes
1. **Extreme resource requirements** - Codelupe needs 50GB+ RAM for full pipeline
2. **Concurrent builds** - Building with other Docker projects running
3. **Elasticsearch memory** - Java heap allocation can spike during startup
4. **Large build contexts** - Model files, datasets, and repo clones sent to daemon
5. **GPU + CPU competition** - Trainer using both GPU and excessive CPU threads

## Fixes Applied

### 1. Resource Limits Added
Created `docker-compose.resource-limited.yml` with strict memory/CPU caps.

### 2. Build Context Optimization
Created `.dockerignore` to exclude:
- Model files (*.bin, *.safetensors, *.pt)
- Datasets (*.jsonl, *.parquet)
- Repository clones (repos/ directory)
- Cache directories

## Resource Requirements

### Full Pipeline (All Services)
```
Elasticsearch:    2GB
PostgreSQL:       1GB
MongoDB:          512MB
Redis:            256MB
Trainer:          12GB (+ GPU VRAM)
Processor:        4GB
Downloader:       2GB
Crawler:          2GB
Monitoring:       3GB (Grafana, Prometheus, Kibana)
---
TOTAL:           ~27GB RAM minimum
```

**Required Docker Desktop Settings:**
- Memory: **32GB minimum** (64GB recommended)
- CPUs: **12-16 cores**
- Disk: **200GB minimum**

### Monitoring Only (No Training)
```
Elasticsearch:    2GB
PostgreSQL:       1GB
MongoDB:          512MB
Redis:            256MB
Monitoring:       3GB
---
TOTAL:           ~7GB RAM
```

**Required Docker Desktop Settings:**
- Memory: **12GB minimum**
- CPUs: **4-6 cores**
- Disk: **50GB**

## How to Use

### Option 1: Resource-Limited Full Pipeline (Recommended)
```bash
# Use resource-limited configuration
docker-compose -f docker-compose.yml -f docker-compose.resource-limited.yml up --build
```

### Option 2: Monitoring Only (No Training/Processing)
```bash
# Start only monitoring and databases
docker-compose -f docker-compose.yml -f docker-compose.resource-limited.yml up \
  --scale trainer=0 \
  --scale processor=0 \
  --scale downloader=0 \
  --scale crawler=0
```

### Option 3: Sequential Build (Safest for Windows)
```bash
# Stop everything
docker-compose down

# Build services one at a time
docker-compose build postgres
docker-compose build redis
docker-compose build mongodb
docker-compose build elasticsearch
# Wait for Elasticsearch build to complete before continuing
docker-compose build crawler
docker-compose build downloader
docker-compose build processor
docker-compose build trainer

# Start with resource limits
docker-compose -f docker-compose.yml -f docker-compose.resource-limited.yml up
```

### Option 4: Minimal Services for Development
```bash
# Start only essential services for development
docker-compose up postgres redis mongodb
```

## Critical Best Practices

### 1. NEVER Run Concurrent Builds
This is the #1 cause of daemon crashes.

```bash
# ❌ FATAL ERROR - Will crash daemon
cd ~/workspace/ai-apps/nexus-v2 && docker-compose build &
cd ~/workspace/ai-apps/codelupe && docker-compose build &

# ✅ CORRECT - Build sequentially, wait for completion
cd ~/workspace/ai-apps/nexus-v2
docker-compose build
# Wait until done
cd ~/workspace/ai-apps/codelupe
docker-compose build
```

### 2. Stop Other Projects First
```bash
# Before building codelupe, stop nexus-v2
cd ~/workspace/ai-apps/nexus-v2
docker-compose down

# Now safe to build codelupe
cd ~/workspace/ai-apps/codelupe
docker-compose build
```

### 3. Use Profiles for Targeted Deployments
```bash
# Start only crawler pipeline (no training)
docker-compose --profile crawler up

# Start only trainer (assumes data already exists)
docker-compose --profile trainer up
```

### 4. Monitor Resource Usage Continuously
```bash
# Watch resource usage in real-time
docker stats

# If any container approaches limit, stop and increase resources
```

### 5. Clean Docker Regularly
```bash
# Remove unused images and containers (frees space)
docker system prune -a

# Remove unused volumes (WARNING: deletes data!)
docker volume prune

# Remove everything (DANGEROUS: complete reset)
docker system prune -a --volumes
```

## Startup Order to Prevent Crashes

**Start services in this order to avoid resource spikes:**

```bash
# 1. Databases first (lightweight)
docker-compose up -d postgres redis mongodb

# 2. Wait 30 seconds, then Elasticsearch (heavy)
sleep 30
docker-compose up -d elasticsearch

# 3. Wait for Elasticsearch health check
docker-compose ps elasticsearch

# 4. Start monitoring
docker-compose up -d prometheus grafana kibana

# 5. Start pipeline services one at a time
docker-compose up -d crawler
sleep 10
docker-compose up -d downloader
sleep 10
docker-compose up -d processor

# 6. Finally, trainer (requires GPU)
docker-compose up -d trainer
```

## Recovery from Daemon Crash

If Docker Desktop daemon freezes or crashes:

1. **Stop ALL builds immediately**
   ```bash
   # Ctrl+C any running docker-compose commands
   ```

2. **Restart Docker Desktop**
   - Right-click Docker Desktop icon
   - Select "Restart Docker Desktop"
   - Wait 3-5 minutes for full restart

3. **Verify daemon is running**
   ```bash
   docker ps
   # Should return empty list or running containers
   ```

4. **Clear build cache (if needed)**
   ```bash
   docker builder prune -a
   ```

5. **Use resource-limited mode when restarting**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.resource-limited.yml up
   ```

## Common Error Patterns

### Error: "Cannot connect to the Docker daemon"
**Cause:** Daemon crashed or not started
**Solution:** Restart Docker Desktop, wait 5 minutes

### Error: "No space left on device"
**Cause:** Docker disk image full
**Solution:**
```bash
docker system prune -a --volumes
# Then increase disk size in Docker Desktop settings
```

### Error: Services keep restarting/crashing
**Cause:** Insufficient memory allocation
**Solution:**
- Check `docker stats` for memory usage
- Increase Docker Desktop memory allocation
- Use `docker-compose.resource-limited.yml`

### Error: Build hangs at "Sending build context"
**Cause:** Sending large files (models, datasets, repos) to daemon
**Solution:**
- Verify `.dockerignore` is in place
- Check for large files in build context:
  ```bash
  du -sh .
  ```

## Monitoring Checklist

Before starting Codelupe:
- [ ] No other Docker builds running
- [ ] nexus-v2 or other projects are stopped
- [ ] Docker Desktop has 32GB+ RAM allocated
- [ ] Using `docker-compose.resource-limited.yml`
- [ ] `.dockerignore` file exists and excludes large files
- [ ] At least 100GB free disk space
- [ ] GPU drivers updated (for trainer)

## Troubleshooting Specific Services

### Elasticsearch
**Most common crash cause due to high memory usage**

```bash
# Check Elasticsearch logs
docker logs codelupe-elasticsearch

# If crashing, reduce memory further
# Edit docker-compose.resource-limited.yml:
- "ES_JAVA_OPTS=-Xms256m -Xmx512m"  # Ultra-low for stability
```

### Trainer
**GPU service with high CPU/memory requirements**

```bash
# Check if GPU is accessible
docker exec codelupe-trainer nvidia-smi

# Reduce CPU threads in docker-compose.resource-limited.yml:
- OMP_NUM_THREADS=2
- MKL_NUM_THREADS=2

# Check CUDA memory
docker exec codelupe-trainer python -c "import torch; print(torch.cuda.memory_summary())"
```

### Processor
**CPU-intensive Go service**

```bash
# Check processor logs
docker logs codelupe-processor

# Reduce GOMAXPROCS in docker-compose.resource-limited.yml:
- GOMAXPROCS=2  # Use fewer CPU cores
```

## Alternative: Selective Service Deployment

If you can't run the full pipeline, run services separately:

### Development Setup (Minimal)
```bash
docker-compose up postgres redis mongodb adminer mongo-express
```

### Crawler Only
```bash
docker-compose up postgres redis mongodb elasticsearch crawler
```

### Training Only (Assumes data exists)
```bash
docker-compose up postgres redis trainer
```

## Windows-Specific Issues

### WSL 2 Backend
Ensure Docker Desktop is using WSL 2:
- Docker Desktop → Settings → General → "Use WSL 2 based engine" ✓

### Memory Allocation in WSL 2
Create/edit `%USERPROFILE%\.wslconfig`:
```ini
[wsl2]
memory=32GB
processors=12
swap=8GB
```

Restart WSL:
```powershell
wsl --shutdown
```

## Need Help?

If daemon crashes persist:
1. **Export logs:**
   ```bash
   docker-compose logs > codelupe-logs.txt
   ```

2. **Check Docker Desktop logs:**
   - Docker Desktop → Troubleshoot → Get support

3. **Consider cloud alternatives:**
   - **AWS EC2** with GPU (p3.2xlarge or better)
   - **Google Colab** for training experiments
   - **Paperspace Gradient** for full pipeline
   - **Lambda Labs** for GPU training

## Summary

**Key takeaways:**
- Codelupe requires **32GB+ RAM** for full pipeline
- **NEVER** run concurrent Docker builds
- Use `docker-compose.resource-limited.yml` always
- Start services sequentially, not all at once
- Monitor with `docker stats` continuously
- Clean Docker regularly to free space
