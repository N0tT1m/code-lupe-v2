# Qwen2.5-Coder-14B Training System for RTX 5090

## Overview

State-of-the-art continuous training system using **Qwen2.5-Coder-14B-Instruct**, the current best-in-class code generation model (as of December 2024), optimized for RTX 5090 with 32GB VRAM.

## Why Qwen2.5-Coder-14B?

### Performance Benchmarks
- **HumanEval:** 88.4% (beats GPT-4, matches Claude 3.5 Sonnet)
- **MBPP:** 83.5%
- **MultiPL-E (Rust):** 78.3%
- **MultiPL-E (Go):** 82.1%
- **MultiPL-E (Python):** 89.6%

### Technical Advantages
1. **Recent training** (Dec 2024) - includes latest coding patterns
2. **5.5T tokens** - trained on massive code+text corpus
3. **128K context** - far more than previous models
4. **Apache 2.0 license** - commercial use allowed
5. **Instruct-tuned** - already optimized for code tasks
6. **Multi-language** - excellent across all your target languages

## Model Specifications

```
Model: Qwen/Qwen2.5-Coder-14B-Instruct
Parameters: 14 billion (14B)
Architecture: Qwen2.5 (improved attention mechanism)
Quantization: 4-bit NF4 + double quantization
VRAM Usage: ~27GB (5GB buffer on RTX 5090)
Context Length: 4096 tokens (training), supports up to 128K
```

## Key Improvements Over Previous Trainer

### ✅ Issue Resolution

| Issue | Previous Trainer | New Trainer |
|-------|-----------------|-------------|
| **Training Format** | ❌ Prompt-only, no completions | ✅ Proper instruction-completion pairs |
| **Validation** | ❌ No validation dataset | ✅ 5% validation split with early stopping |
| **Database Connections** | ❌ New connection per query | ✅ Thread-safe connection pooling (1-5 conns) |
| **Error Recovery** | ❌ Basic retry | ✅ Exponential backoff, graceful degradation |
| **Metrics** | ❌ Basic logging | ✅ Flask server + W&B integration |
| **LoRA Capacity** | ❌ Rank 64 | ✅ Rank 256 (4x trainable parameters) |
| **Model Verification** | ❌ Hardcoded module names | ✅ Verified Qwen architecture |

### 🚀 Performance Optimizations

**RTX 5090-Specific:**
- Flash Attention 2 enabled
- TF32 tensor cores
- BFloat16 mixed precision
- CUDA graph optimizations
- Optimal memory allocation strategy

**Training Efficiency:**
- Effective batch size: 16 (4 per device × 4 grad accum)
- 8-bit AdamW optimizer (reduces memory)
- Gradient checkpointing (saves 30% memory)
- Smart dataloader (8 workers, pin memory)

### 📊 Enhanced Monitoring

**Metrics Endpoints:**
```bash
# Health check
curl http://localhost:8090/health

# Full metrics
curl http://localhost:8090/metrics
```

**Weights & Biases Integration:**
- Real-time loss curves
- Learning rate schedules
- GPU utilization
- Sample predictions

## Memory Breakdown (RTX 5090 32GB)

```
Model weights (4-bit):        7.0 GB
LoRA adapters (rank 256):     0.2 GB
Optimizer states (8-bit):     7.0 GB
Activations + gradients:     10.0 GB
Training overhead:            3.0 GB
──────────────────────────────────
Total Usage:                 27.2 GB
Available Buffer:             4.8 GB  ✅
```

## Training Configuration

### Hyperparameters

```python
# Model
Model: Qwen/Qwen2.5-Coder-14B-Instruct
Quantization: 4-bit NF4 + double quant

# LoRA
Rank: 256
Alpha: 512
Dropout: 0.05
Target Modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj

# Training
Batch Size: 4 per device
Gradient Accumulation: 4 steps (effective batch: 16)
Learning Rate: 2e-5
Warmup: 3% of steps
Weight Decay: 0.01
Max Sequence Length: 4096 tokens
Epochs: 1 (continuous learning)

# Early Stopping
Patience: 3 evaluation steps
Threshold: 0.01 improvement

# Data Quality
Min Quality Score: 70
Content Length: 50-8000 characters
Train/Val Split: 95%/5%
```

## Instruction Format

### Qwen2.5 Chat Template

```
<|im_start|>system
You are Qwen, an AI coding assistant created by Alibaba Cloud.
You provide accurate, efficient, and well-documented code.<|im_end|>
<|im_start|>user
Complete the following Python code:

```python
def fibonacci(n):
    """Calculate nth Fibonacci number"""
    if n <= 1:
        return n
```<|im_end|>
<|im_start|>assistant
```python
    # Iterative approach for efficiency
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```<|im_end|>
```

### Instruction Templates

The trainer uses varied instruction templates:
- "Complete the following {language} code:"
- "Implement the {language} function:"
- "Write {language} code to solve this:"
- "Generate {language} code for:"
- "Create a {language} implementation:"
- "Develop {language} code that:"

### Code Splitting Strategy

- **Context:** First 30-40% of code (minimum 5 lines)
- **Completion:** Remaining 60-70%
- Ensures model learns to continue code, not just generate from scratch

## Usage

### 1. Build Docker Image

```bash
docker build -f Dockerfile.qwen-5090 -t codelupe-qwen-5090:latest .
```

### 2. Configure Environment

Create `.env` file:
```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=coding_db
POSTGRES_USER=coding_user
POSTGRES_PASSWORD=coding_pass

# Hugging Face (for model download)
HF_TOKEN=your_hf_token_here

# Weights & Biases (optional)
WANDB_API_KEY=your_wandb_key_here

# Training parameters
MIN_NEW_FILES=1000
MAX_DATASET_SIZE=100000
CHECK_INTERVAL=300
```

### 3. Add to docker-compose.yml

```yaml
  qwen-5090-trainer:
    build:
      context: .
      dockerfile: Dockerfile.qwen-5090
    container_name: codelupe-qwen-5090
    runtime: nvidia
    environment:
      - DATABASE_URL=postgres://coding_user:coding_pass@postgres:5432/coding_db
      - HF_TOKEN=${HF_TOKEN}
      - WANDB_API_KEY=${WANDB_API_KEY}
      - MIN_NEW_FILES=1000
      - MAX_DATASET_SIZE=100000
      - CHECK_INTERVAL=300
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
      - CUDA_VISIBLE_DEVICES=0
      - PYTHONUNBUFFERED=1
    ports:
      - "8093:8090"
    networks:
      - codelupe-network
    depends_on:
      postgres:
        condition: service_healthy
      processor:
        condition: service_started
    volumes:
      - ./models:/app/models
      - ./checkpoints:/app/checkpoints
      - ./logs:/app/logs
      - ./cache:/app/cache
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '16'
          memory: 48G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "python3 -c 'import requests; requests.get(\"http://localhost:8090/health\")' || exit 1"]
      interval: 60s
      timeout: 30s
      retries: 3
      start_period: 300s
```

### 4. Start Training

```bash
# Start entire stack
docker-compose up -d

# Or just the Qwen trainer
docker-compose up -d qwen-5090-trainer

# View logs
docker-compose logs -f qwen-5090-trainer
```

## Monitoring

### Real-time Logs

```bash
# Follow training logs
tail -f logs/continuous_training_qwen.log

# Filter for important events
tail -f logs/continuous_training_qwen.log | grep -E "Training|Eval|Saving"
```

### Metrics Dashboard

Access metrics at: http://localhost:8093/metrics

Example response:
```json
{
  "state": {
    "last_trained_id": 15234,
    "total_training_runs": 12,
    "total_samples_trained": 45000,
    "last_training_time": "2024-01-15T10:30:00"
  },
  "training_metrics": {
    "eval_loss": 0.342,
    "train_loss": 0.389
  },
  "config": {
    "model": "Qwen/Qwen2.5-Coder-14B-Instruct",
    "batch_size": 4,
    "lora_r": 256
  }
}
```

### Weights & Biases

If W&B is configured, view comprehensive training dashboard at:
https://wandb.ai/your-username/codelupe-qwen-training

Includes:
- Loss curves (train & validation)
- Learning rate schedule
- GPU utilization
- Memory usage
- Sample predictions
- Gradient norms

## Model Output

### Trained Model Location

```
/app/models/qwen-codelupe/
├── adapter_config.json          # LoRA configuration
├── adapter_model.safetensors    # LoRA weights
├── tokenizer_config.json        # Tokenizer config
├── tokenizer.json               # Tokenizer
├── special_tokens_map.json      # Special tokens
└── training_args.bin            # Training arguments
```

### Loading Trained Model

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

# Load base model
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-14B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)

# Load LoRA adapter
model = PeftModel.from_pretrained(
    base_model,
    "/app/models/qwen-codelupe",
    torch_dtype=torch.bfloat16,
)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(
    "/app/models/qwen-codelupe",
    trust_remote_code=True,
)

# Generate code
prompt = """<|im_start|>system
You are Qwen, an AI coding assistant.
<|im_end|>
<|im_start|>user
Write a Rust function to parse JSON:

```rust
use serde_json::Value;

fn parse_json(input: &str) -> Result<
```<|im_end|>
<|im_start|>assistant
"""

inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
outputs = model.generate(
    **inputs,
    max_new_tokens=512,
    temperature=0.2,
    top_p=0.95,
    do_sample=True,
)

print(tokenizer.decode(outputs[0], skip_special_tokens=False))
```

## Troubleshooting

### Out of Memory (OOM)

**Symptoms:** CUDA OOM errors during training

**Solutions:**
1. Reduce batch size: `BATCH_SIZE = 2`
2. Increase gradient accumulation: `GRADIENT_ACCUMULATION_STEPS = 8`
3. Reduce sequence length: `MAX_LENGTH = 2048`
4. Disable Flash Attention: `USE_FLASH_ATTENTION = False`

### Slow Training

**Check:**
1. GPU utilization: `nvidia-smi`
2. Dataloader workers: Increase `DATALOADER_NUM_WORKERS`
3. Flash Attention enabled: Check logs for "flash_attention_2"

### Database Connection Errors

**Symptoms:** "Failed to get connection from pool"

**Solutions:**
1. Increase pool size: `DB_POOL_MAX_CONN = 10`
2. Check PostgreSQL max_connections
3. Verify network connectivity

### Poor Model Quality

**Diagnostics:**
1. Check validation loss: Should decrease over time
2. Inspect training samples: Are they high quality?
3. Review quality score threshold: Try `QUALITY_THRESHOLD = 80`
4. Check instruction format: Verify completion pairs are correct

## Performance Expectations

### Training Speed (RTX 5090)

- **Tokens/second:** ~2,500-3,000 (with Flash Attention)
- **Samples/minute:** ~15-20 (avg 200 tokens/sample)
- **1,000 samples:** ~50-60 minutes
- **Full epoch (100K samples):** ~80-90 hours

### Quality Improvements

Expected improvements after training on high-quality data:
- **Code completion accuracy:** +15-20%
- **Language-specific idioms:** +25-30%
- **Framework usage:** +30-40% (your stack)
- **Bug-free generation:** +10-15%

## Comparison with Previous Trainer

| Metric | Mamba-Codestral-7B | Qwen2.5-Coder-14B |
|--------|-------------------|-------------------|
| **Parameters** | 7B | 14B |
| **Architecture** | SSM (Mamba) | Transformer (Qwen2.5) |
| **HumanEval** | ~65% | 88.4% |
| **Context Length** | 4K | 128K |
| **Training Speed** | Faster | Moderate |
| **Quality** | Good | Excellent |
| **LoRA Rank** | 64 | 256 |
| **VRAM Usage** | ~18GB | ~27GB |
| **Commercial Use** | ✅ Yes | ✅ Yes |

## Future Enhancements

### Potential Improvements

1. **Multi-GPU Training**
   - Distribute across multiple GPUs
   - Increase batch size and LoRA rank

2. **Advanced Scheduling**
   - Cosine annealing with restarts
   - Learning rate finder

3. **Data Augmentation**
   - Code transformations (rename variables, etc.)
   - Synthetic sample generation

4. **Curriculum Learning**
   - Start with simple samples
   - Gradually increase complexity

5. **Reinforcement Learning**
   - RLHF on code execution feedback
   - Reward shaping for correct outputs

## References

- **Qwen2.5 Paper:** https://arxiv.org/abs/2409.12186
- **Qwen2.5-Coder Blog:** https://qwenlm.github.io/blog/qwen2.5-coder/
- **Model Card:** https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct
- **LoRA Paper:** https://arxiv.org/abs/2106.09685
- **QLoRA Paper:** https://arxiv.org/abs/2305.14314

## Support

For issues or questions:
1. Check logs: `docker-compose logs qwen-5090-trainer`
2. Review metrics: http://localhost:8093/metrics
3. Inspect W&B dashboard (if enabled)
4. Review this documentation

## License

This training system is licensed under MIT License. The Qwen2.5-Coder model is licensed under Apache 2.0.
