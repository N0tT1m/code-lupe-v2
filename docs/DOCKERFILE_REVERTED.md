# Dockerfile Reverted to Working Configuration

## What Changed

Reverted `Dockerfile.qwen-5090` to match the working configuration from your "Initial Commit" that was building successfully.

## Key Changes Made

### 1. CUDA Version
- **Before**: CUDA 12.4.0
- **After**: CUDA 12.6.1 ✅
- **Reason**: Matches your working setup and has better compatibility with Flash Attention

### 2. PyTorch Version
- **Before**: PyTorch 2.2+ with CUDA 12.4
- **After**: PyTorch 2.5.1 with CUDA 12.6 ✅
- **Reason**: Version alignment with CUDA base image

### 3. Flash Attention Version
- **Before**: v2.7.2.post1 (newer, unstable)
- **After**: v2.5.8 ✅
- **Reason**: Stable version that was working in your previous build

### 4. Triton Version
- **Before**: triton 2.3.1
- **After**: triton 3.0.0 ✅
- **Reason**: Compatible with newer PyTorch

### 5. Build Configuration
- **Before**: MAX_JOBS=1 (too conservative)
- **After**: MAX_JOBS=2 ✅
- **Reason**: Balanced between speed and stability (matches your working config)

### 6. Python Version
- **Before**: Python 3.11 (had to set as default manually)
- **After**: Python 3 (Ubuntu default) ✅
- **Reason**: Simpler, matches working config

## Build Order (Unchanged - This Was Working)

1. System dependencies
2. Build tools (pip, ninja, setuptools, wheel)
3. CUDA environment variables
4. PyTorch with matching CUDA version
5. Triton
6. Flash Attention from source
7. Other dependencies
8. Copy application code

## What Should Work Now

```bash
# This should now build successfully like it did before
docker-compose build trainer
```

## Build Time Expectations

- **Total build time**: 20-40 minutes
- **Flash Attention compilation**: 15-30 minutes (with MAX_JOBS=2)
- **Other dependencies**: 5-10 minutes

## Why It Was Failing Before

The newer versions had compatibility issues:
- ❌ CUDA 12.4 + Flash Attention v2.7.2 = compatibility issues
- ❌ Mismatched PyTorch and CUDA versions
- ❌ MAX_JOBS=1 was too slow, MAX_JOBS=4 caused OOM
- ✅ CUDA 12.6 + Flash Attention v2.5.8 = proven stable combination

## Verification

After build completes:

```bash
# Check Flash Attention
docker-compose run trainer python3 -c "import flash_attn; print('Flash Attention:', flash_attn.__version__)"

# Should output: Flash Attention: 2.5.8

# Check CUDA
docker-compose run trainer python3 -c "import torch; print('CUDA:', torch.version.cuda)"

# Should output: CUDA: 12.6
```

## Configuration Summary

| Component | Version | Status |
|-----------|---------|--------|
| Base Image | nvidia/cuda:12.6.1-devel-ubuntu22.04 | ✅ Stable |
| Python | 3 (Ubuntu default) | ✅ Simple |
| PyTorch | 2.5.1+cu126 | ✅ Matching CUDA |
| Flash Attention | 2.5.8 | ✅ Proven stable |
| Triton | 3.0.0 | ✅ Compatible |
| MAX_JOBS | 2 | ✅ Balanced |

## What to Do if Build Still Fails

1. **Restart Docker Desktop completely**
   ```bash
   # Close Docker Desktop
   # Wait 10 seconds
   # Open Docker Desktop
   # Wait for it to fully start
   ```

2. **Clear Docker build cache**
   ```bash
   docker system prune -a
   docker-compose build --no-cache trainer
   ```

3. **Check Docker resources**
   - Memory: At least 8GB (16GB recommended)
   - Disk: At least 50GB free
   - CPU: 4+ cores

4. **Monitor the build**
   ```bash
   docker-compose build trainer 2>&1 | tee build.log
   ```

This will save output to `build.log` for debugging.

## Success Indicators

✅ You'll know it worked when you see:

```
Successfully installed flash-attn-2.5.8
Successfully installed transformers-4.41.0 peft-0.11.0 ...
Successfully tagged codelupe-trainer:latest
```

## Next Steps After Successful Build

```bash
# Start the trainer
docker-compose up -d trainer

# Check logs
docker-compose logs -f trainer

# Check health
curl http://localhost:8090/health
```
