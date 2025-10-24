# Qwen2.5-Coder-14B Deployment Checklist

## Pre-Deployment

### ✅ Hardware Verification
- [ ] RTX 5090 with 32GB VRAM confirmed
- [ ] CUDA 12.4+ drivers installed
- [ ] `nvidia-smi` shows GPU correctly
- [ ] Docker with NVIDIA runtime configured
- [ ] Sufficient disk space (>500GB recommended for models + cache)

### ✅ Environment Setup
- [ ] `.env` file created with all required variables
- [ ] Hugging Face token obtained (for model download)
- [ ] Weights & Biases account (optional but recommended)
- [ ] PostgreSQL running with processed_files table
- [ ] Network access to Hugging Face Hub

### ✅ Code Verification
- [ ] `continuous_trainer_qwen_5090.py` in place
- [ ] `Dockerfile.qwen-5090` in place
- [ ] Docker Compose updated (see README)
- [ ] Logs directory exists: `mkdir -p logs`
- [ ] Models directory exists: `mkdir -p models`
- [ ] Checkpoints directory exists: `mkdir -p checkpoints`

---

## Deployment Steps

### Step 1: Environment Configuration (5 min)

Create `.env` file:
```bash
cat > .env << 'EOF'
# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=coding_db
POSTGRES_USER=coding_user
POSTGRES_PASSWORD=coding_pass

# Hugging Face
HF_TOKEN=hf_your_token_here

# Weights & Biases (optional)
WANDB_API_KEY=your_wandb_key_here

# Training Configuration
MIN_NEW_FILES=1000
MAX_DATASET_SIZE=100000
CHECK_INTERVAL=300
TRAINING_EPOCHS=1
BATCH_SIZE=4
GRADIENT_ACCUMULATION_STEPS=4
LEARNING_RATE=2e-5
EOF
```

**Checklist:**
- [ ] HF_TOKEN is valid (test: `huggingface-cli whoami`)
- [ ] Database credentials match docker-compose.yml
- [ ] File saved with correct permissions

---

### Step 2: Build Docker Image (10-15 min)

```bash
# Build image
docker build -f Dockerfile.qwen-5090 -t codelupe-qwen-5090:latest .

# Verify build
docker images | grep codelupe-qwen-5090
```

**Checklist:**
- [ ] Build completed without errors
- [ ] Image size reasonable (~15-20GB)
- [ ] PyTorch with CUDA support confirmed in logs

**Expected output:**
```
Successfully built abc123def456
Successfully tagged codelupe-qwen-5090:latest
```

---

### Step 3: Test Database Connection (2 min)

```bash
# Test connection from container
docker run --rm --network codelupe-network \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=coding_db \
  -e POSTGRES_USER=coding_user \
  -e POSTGRES_PASSWORD=coding_pass \
  codelupe-qwen-5090:latest \
  python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='postgres',
    port=5432,
    database='coding_db',
    user='coding_user',
    password='coding_pass'
)
print('✅ Database connection successful')
conn.close()
"
```

**Checklist:**
- [ ] Connection successful
- [ ] No timeout errors
- [ ] Credentials valid

---

### Step 4: Verify GPU Access (2 min)

```bash
# Test GPU visibility
docker run --rm --runtime=nvidia --gpus all \
  codelupe-qwen-5090:latest \
  python3 -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB')
"
```

**Expected output:**
```
CUDA available: True
CUDA version: 12.4
GPU: NVIDIA GeForce RTX 5090
VRAM: 32.00 GB
```

**Checklist:**
- [ ] CUDA available = True
- [ ] GPU name shows RTX 5090
- [ ] VRAM shows 32GB

---

### Step 5: Download Model (First Run, 30-60 min)

The model will auto-download on first run, but you can pre-download:

```bash
# Pre-download model (optional but recommended)
docker run --rm -v ./cache:/app/cache \
  -e HF_TOKEN=your_token_here \
  codelupe-qwen-5090:latest \
  python3 -c "
from transformers import AutoModelForCausalLM, AutoTokenizer

print('Downloading Qwen2.5-Coder-14B-Instruct...')
tokenizer = AutoTokenizer.from_pretrained(
    'Qwen/Qwen2.5-Coder-14B-Instruct',
    trust_remote_code=True,
    cache_dir='/app/cache'
)
print('✅ Tokenizer downloaded')

model = AutoModelForCausalLM.from_pretrained(
    'Qwen/Qwen2.5-Coder-14B-Instruct',
    trust_remote_code=True,
    cache_dir='/app/cache',
    torch_dtype='auto',
    device_map='cpu'
)
print('✅ Model downloaded')
print(f'Model size: {sum(p.numel() for p in model.parameters())/1e9:.2f}B parameters')
"
```

**Checklist:**
- [ ] Download completed (~28GB)
- [ ] No authentication errors
- [ ] Model files in cache directory
- [ ] 14B parameters confirmed

---

### Step 6: Start Training Service (2 min)

```bash
# Start the trainer
docker-compose up -d qwen-5090-trainer

# Follow logs
docker-compose logs -f qwen-5090-trainer
```

**Checklist:**
- [ ] Container started successfully
- [ ] No immediate crashes
- [ ] Logs show initialization progress

**Expected log sequence:**
```
Starting continuous training system
Model: Qwen/Qwen2.5-Coder-14B-Instruct
Check interval: 300s
Loading model: Qwen/Qwen2.5-Coder-14B-Instruct
Successfully connected to PostgreSQL
Trainable params: 234,881,024 (1.68%)
Metrics server started on port 8090
Training check #1
New files available: 542
Waiting for more files (542/1000)
```

---

### Step 7: Verify Metrics Endpoint (1 min)

```bash
# Check health
curl http://localhost:8093/health

# Check full metrics
curl http://localhost:8093/metrics | jq
```

**Expected response:**
```json
{
  "status": "healthy",
  "last_trained_id": 0,
  "total_training_runs": 0,
  "model_loaded": true
}
```

**Checklist:**
- [ ] Health endpoint responds
- [ ] Status is "healthy"
- [ ] model_loaded is true

---

### Step 8: Verify Training State File (1 min)

```bash
# Check state file exists
ls -lh checkpoints/trainer_state_qwen.json

# View state
cat checkpoints/trainer_state_qwen.json | jq
```

**Expected:**
```json
{
  "last_trained_id": 0,
  "total_training_runs": 0,
  "total_samples_trained": 0,
  "last_training_time": null
}
```

**Checklist:**
- [ ] State file created
- [ ] JSON is valid
- [ ] Permissions allow read/write

---

## First Training Run

### Step 9: Wait for Training Trigger

The trainer will automatically start when:
- New files >= MIN_NEW_FILES (default: 1000)
- Quality score >= 70
- Content length: 50-8000 characters

**Monitor logs:**
```bash
tail -f logs/continuous_training_qwen.log | grep -E "Training|Eval|Saving"
```

**Checklist:**
- [ ] Training triggered automatically
- [ ] Dataset preparation successful
- [ ] Model loading successful
- [ ] Training started without OOM

---

### Step 10: Monitor First Epoch (varies, ~1-2 hours)

**Key metrics to watch:**

```bash
# GPU utilization (should be >90%)
watch -n 1 nvidia-smi

# Training logs
tail -f logs/continuous_training_qwen.log

# Metrics endpoint
watch -n 10 'curl -s http://localhost:8093/metrics | jq .training_metrics'
```

**Healthy signs:**
- GPU utilization: 85-95%
- Memory usage: ~27-28GB / 32GB
- Loss decreasing
- No OOM errors
- Regular checkpoint saves

**Warning signs:**
- GPU utilization < 50% (dataloader bottleneck?)
- Memory at 31.9GB (may OOM soon)
- Loss increasing (learning rate too high?)
- Frequent restarts (OOM errors)

**Checklist:**
- [ ] Training progressing smoothly
- [ ] GPU well-utilized
- [ ] No memory issues
- [ ] Loss trending downward
- [ ] Checkpoints saving

---

### Step 11: Verify Model Saving (end of epoch)

```bash
# Check output directory
ls -lh models/qwen-codelupe/

# Verify adapter files
ls -lh models/qwen-codelupe/adapter_*
```

**Expected files:**
```
adapter_config.json
adapter_model.safetensors
tokenizer.json
tokenizer_config.json
special_tokens_map.json
training_args.bin
```

**Checklist:**
- [ ] All files present
- [ ] adapter_model.safetensors > 100MB
- [ ] No corrupted files
- [ ] Permissions allow reading

---

## Post-Deployment Verification

### Step 12: Test Trained Model (5 min)

```bash
# Test inference
docker run --rm --runtime=nvidia --gpus all \
  -v ./models:/app/models \
  -v ./cache:/app/cache \
  codelupe-qwen-5090:latest \
  python3 << 'EOF'
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

print("Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-14B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
    cache_dir="/app/cache"
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(
    base_model,
    "/app/models/qwen-codelupe"
)

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    "/app/models/qwen-codelupe",
    trust_remote_code=True
)

print("\nGenerating test code...\n")
prompt = """<|im_start|>system
You are Qwen, an AI coding assistant.
<|im_end|>
<|im_start|>user
Write a Python function to reverse a string:

```python
def reverse_string(s: str) -> str:
    """
```<|im_end|>
<|im_start|>assistant
"""

inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
outputs = model.generate(
    **inputs,
    max_new_tokens=200,
    temperature=0.2,
    top_p=0.95,
    do_sample=True
)

result = tokenizer.decode(outputs[0], skip_special_tokens=False)
print(result)
EOF
```

**Checklist:**
- [ ] Model loads without errors
- [ ] Generation completes
- [ ] Output is coherent code
- [ ] No CUDA errors

---

### Step 13: Check Weights & Biases (if enabled)

Visit: https://wandb.ai/your-username/codelupe-qwen-training

**Checklist:**
- [ ] Run appears in dashboard
- [ ] Loss curves visible
- [ ] GPU metrics logged
- [ ] Hyperparameters recorded

---

### Step 14: Review Logs for Issues

```bash
# Search for errors
grep -i "error" logs/continuous_training_qwen.log

# Search for warnings
grep -i "warning" logs/continuous_training_qwen.log

# Search for OOM
grep -i "out of memory" logs/continuous_training_qwen.log
```

**Checklist:**
- [ ] No critical errors
- [ ] Warnings are benign
- [ ] No OOM events

---

## Ongoing Monitoring

### Daily Checks

```bash
# Check service status
docker-compose ps | grep qwen-5090

# Check training count
curl -s http://localhost:8093/metrics | jq .state.total_training_runs

# Check last training time
curl -s http://localhost:8093/metrics | jq .state.last_training_time

# Check recent logs
tail -n 100 logs/continuous_training_qwen.log
```

**Checklist:**
- [ ] Service running
- [ ] Training count increasing
- [ ] Last training recent (< 24h)
- [ ] No repeated errors

---

### Weekly Checks

```bash
# Check disk usage
df -h | grep -E "models|checkpoints|cache"

# Check model quality
# (Run evaluation benchmark)

# Review training metrics trend
curl -s http://localhost:8093/metrics | jq .training_metrics

# Check GPU health
nvidia-smi -q | grep -E "Temperature|Power|Memory"
```

**Checklist:**
- [ ] Sufficient disk space (>100GB free)
- [ ] Model quality maintaining/improving
- [ ] Loss trends healthy
- [ ] GPU temperature < 80°C

---

## Troubleshooting

### Issue: Container Won't Start

**Symptoms:**
```bash
$ docker-compose up -d qwen-5090-trainer
Error: ...
```

**Debug:**
```bash
# Check logs
docker-compose logs qwen-5090-trainer

# Try manual start
docker run --rm -it --runtime=nvidia --gpus all \
  codelupe-qwen-5090:latest /bin/bash

# Inside container, run:
python3 /app/continuous_trainer_qwen_5090.py
```

**Common causes:**
- Missing .env file
- Invalid database credentials
- GPU not accessible
- CUDA driver mismatch

---

### Issue: Out of Memory (OOM)

**Symptoms:**
```
torch.cuda.OutOfMemoryError: CUDA out of memory
```

**Solutions:**

1. Reduce batch size:
```python
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 8
```

2. Reduce sequence length:
```python
MAX_LENGTH = 2048
```

3. Reduce LoRA rank:
```python
LORA_R = 128
LORA_ALPHA = 256
```

4. Disable Flash Attention:
```python
USE_FLASH_ATTENTION = False
```

---

### Issue: Slow Training

**Symptoms:**
- Tokens/sec < 1000
- GPU utilization < 70%

**Debug:**
```bash
# Check dataloader
# If CPU at 100%, increase workers
DATALOADER_NUM_WORKERS = 12

# Check Flash Attention
grep "flash_attention" logs/continuous_training_qwen.log

# Check TF32
grep "TF32" logs/continuous_training_qwen.log
```

---

### Issue: Poor Model Quality

**Debug:**
```bash
# Check training samples
# Are they high quality?

# Check validation loss
curl -s http://localhost:8093/metrics | jq .training_metrics.eval_loss

# Increase quality threshold
QUALITY_THRESHOLD = 80
```

---

## Success Criteria

### Deployment Successful When:
- ✅ Container running continuously for > 24 hours
- ✅ At least 1 training run completed
- ✅ Model saved successfully
- ✅ No OOM errors
- ✅ GPU utilization > 80%
- ✅ Validation loss decreasing
- ✅ Metrics endpoint responding
- ✅ State file updating

### Production Ready When:
- ✅ Multiple training runs successful (>5)
- ✅ Model quality validated
- ✅ Monitoring dashboards working
- ✅ Alerting configured
- ✅ Backup strategy in place
- ✅ Documentation complete
- ✅ Team trained on operations

---

## Rollback Plan

If deployment fails:

1. Stop container:
```bash
docker-compose stop qwen-5090-trainer
```

2. Revert to previous trainer:
```bash
docker-compose up -d trainer  # Original Mamba trainer
```

3. Investigate issues
4. Fix configuration
5. Retry deployment

---

## Next Steps After Successful Deployment

1. **Monitor for 1 week**
   - Daily health checks
   - Review training metrics
   - Check model quality

2. **Benchmark model quality**
   - Run HumanEval subset
   - Test on real use cases
   - Compare to baseline

3. **Optimize hyperparameters**
   - Tune learning rate
   - Adjust LoRA rank
   - Experiment with batch sizes

4. **Scale up training**
   - Increase dataset size
   - Add more data sources
   - Implement curriculum learning

5. **Deploy to production**
   - Serve model via API
   - Integrate with applications
   - Monitor inference performance

---

## Support Resources

- **Documentation:** README_QWEN_5090.md
- **Model comparison:** MODEL_COMPARISON.md
- **Logs:** /app/logs/continuous_training_qwen.log
- **Metrics:** http://localhost:8093/metrics
- **W&B Dashboard:** https://wandb.ai (if configured)
- **Qwen Docs:** https://qwenlm.github.io/

---

## Sign-Off

Deployment completed by: _______________
Date: _______________
Training runs completed: _______________
Model quality verified: [ ] Yes [ ] No
Issues encountered: _______________
Notes: _______________
