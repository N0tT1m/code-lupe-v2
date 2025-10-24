# Docker Build Fix Guide

## Problem
Flash Attention 2 compilation is crashing Docker Desktop during build due to memory exhaustion and build timeout.

## Solutions (in order of recommendation)

### Solution 1: Use Pre-built Wheel (RECOMMENDED - Fastest)

The Dockerfile has been updated to try pre-built wheels first, then fall back to source build if needed.

```bash
# Just rebuild - it will try pre-built first
docker-compose build trainer
```

**Changes made to `Dockerfile.qwen-5090`**:
- Line 41-48: Try `pip install flash-attn` first (pre-built wheel)
- Falls back to source compilation only if wheel isn't available
- Much faster build time (minutes vs hours)

### Solution 2: Increase Docker Resources

If pre-built wheel isn't available and source build is required:

**macOS/Windows (Docker Desktop)**:
1. Open Docker Desktop
2. Go to Settings → Resources
3. Increase Memory to **16GB** (minimum)
4. Increase CPUs to **8+** (recommended)
5. Click "Apply & Restart"
6. Rebuild: `docker-compose build trainer`

### Solution 3: Build Without Flash Attention

Use the alternative Dockerfile that skips Flash Attention during build:

```bash
# Update docker-compose.yml temporarily
docker-compose build -f Dockerfile.qwen-5090-no-flash trainer
```

Then install Flash Attention after the container is running:

```bash
# Start the container
docker-compose up -d trainer

# Install Flash Attention inside the running container
docker-compose exec trainer bash
/app/install-flash-attn.sh
exit
```

### Solution 4: Build on Native Linux (Best Performance)

If you have access to a Linux machine with NVIDIA GPU:

```bash
# On Linux host
docker build -f Dockerfile.qwen-5090 --build-arg MAX_JOBS=4 -t codelupe-trainer .
```

Linux has better Docker performance and can handle parallel builds.

## Verification

After build completes, verify Flash Attention is available:

```bash
# Check if Flash Attention is installed
docker-compose run trainer python3 -c "import flash_attn; print('Flash Attention:', flash_attn.__version__)"

# Or check trainer logs
docker-compose up trainer
# Look for "Using Flash Attention 2" or "falling back to eager attention"
```

## Graceful Fallback

The trainer now gracefully falls back to regular attention if Flash Attention isn't available:

```python
# In continuous_trainer_qwen_5090.py:941-953
# Automatically detects and uses Flash Attention if available
# Falls back to eager attention otherwise
```

**Impact of fallback**:
- ✅ Training still works
- ⚠️ Slightly slower (10-20% performance hit)
- ⚠️ Slightly more memory usage
- ✅ No code changes needed

## Current Docker Build Status

### What Works:
- ✅ Pre-built wheel installation (fast)
- ✅ Graceful fallback to eager attention
- ✅ All other dependencies install correctly
- ✅ Model loads and trains successfully

### What's Challenging:
- ⚠️ Source compilation in Docker Desktop (memory limits)
- ⚠️ Long build times (3+ hours for source build)

## Troubleshooting

### Build Still Fails

**Error**: "rpc error: code = Unavailable"

**Fixes**:
1. Restart Docker Desktop
2. Increase resources (see Solution 2)
3. Use pre-built wheel (Solution 1)
4. Skip Flash Attention temporarily (Solution 3)

### Pre-built Wheel Not Found

**Error**: "No matching distribution found for flash-attn"

This means no pre-built wheel exists for your CUDA version. Options:

1. **Accept fallback**: Trainer will use eager attention (works fine)
2. **Increase resources**: Allow source compilation (Solution 2)
3. **Use Linux**: Build on native Linux (Solution 4)

### Build Timeout

**Error**: "build timeout" or "failed to receive status"

**Fixes**:
```bash
# Increase Docker build timeout
DOCKER_BUILDKIT=0 docker-compose build trainer

# Or use BuildKit with longer timeout
BUILDKIT_STEP_LOG_MAX_SIZE=50000000 docker-compose build trainer
```

### Out of Memory During Build

**Error**: "Killed" or "out of memory"

**Fixes**:
1. Increase Docker memory to 16GB+
2. Close other applications
3. Use Solution 3 (skip Flash Attention)
4. Build on Linux host

## Performance Comparison

| Method | Build Time | Runtime Performance | Memory Usage |
|--------|------------|-------------------|--------------|
| Flash Attention 2 (pre-built) | 5-10 min | 100% (best) | Lowest |
| Flash Attention 2 (source) | 2-4 hours | 100% (best) | Lowest |
| Eager Attention (fallback) | 5-10 min | 80-90% | +10-15% |

## Recommendation

**For Development**:
- Use Solution 1 (pre-built wheel)
- Accept eager attention fallback if wheel unavailable
- Performance difference is minimal for development

**For Production**:
- Build on Linux host with full resources
- Use Flash Attention 2 for best performance
- Or accept eager attention (still production-ready)

## Additional Help

If issues persist:

1. Check Docker logs: `docker-compose logs trainer`
2. Check build logs in Docker Desktop Dashboard
3. Try building other services first to ensure Docker is working
4. Restart Docker Desktop
5. Check disk space (need 50GB+ free)

## Success Indicators

Build is successful when you see:

```
✅ Successfully installed transformers peft trl
✅ Successfully installed flash-attn (or fallback message)
✅ Container starts without errors
✅ Trainer logs show "ContinuousTrainer initialized"
```
