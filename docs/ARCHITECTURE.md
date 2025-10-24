# CodeLupe Architecture with Qwen2.5-Coder-14B

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CODELUPE PIPELINE                           │
│                    RTX 5090 (32GB VRAM) Optimized                   │
└─────────────────────────────────────────────────────────────────────┘

┌───────────────┐       ┌────────────────┐       ┌─────────────────┐
│   GitHub      │──────▶│  Elasticsearch │──────▶│   PostgreSQL    │
│   Crawler     │       │  Search Index  │       │   Repository    │
│   (Go)        │       │                │       │   Metadata      │
└───────────────┘       └────────────────┘       └─────────────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     REPOSITORY DOWNLOADER (Go)                      │
│  • Quality filtering (min stars/forks)                             │
│  • Target languages: Rust, Go, Python, TypeScript, Dart            │
│  • Concurrent downloads                                             │
│  • Metadata collection                                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │   Local Storage      │
                    │   /app/repos/        │
                    └──────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CODE PROCESSOR (Go - 14 cores)                    │
│  • File parsing & tokenization                                      │
│  • Language detection                                               │
│  • Quality analysis                                                 │
│  • Store in PostgreSQL (processed_files)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │   PostgreSQL         │
                    │   processed_files    │
                    │   quality_score ≥ 70 │
                    └──────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              QWEN2.5-CODER-14B TRAINER (Python)                     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────┐         │
│  │  Check for new files (every 5 min)                    │         │
│  │  If count >= 1000:                                    │         │
│  │    1. Fetch quality samples                           │         │
│  │    2. Format instruction-completion pairs             │         │
│  │    3. Split train (95%) / validation (5%)             │         │
│  │    4. Train with early stopping                       │         │
│  │    5. Save best model                                 │         │
│  └───────────────────────────────────────────────────────┘         │
│                                                                     │
│  Model: Qwen/Qwen2.5-Coder-14B-Instruct (4-bit + LoRA-256)         │
│  VRAM: 27GB / 32GB                                                  │
│  Speed: 2,500-3,000 tokens/sec                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │   Trained Model      │
                    │   /app/models/       │
                    │   qwen-codelupe/     │
                    └──────────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          DATA PIPELINE                              │
└─────────────────────────────────────────────────────────────────────┘

Step 1: COLLECTION
───────────────────
    GitHub Search Results
           │
           ├──▶ 275+ search terms
           ├──▶ Languages: Rust, Go, Python, TypeScript, JavaScript, Dart
           ├──▶ Frameworks: FastAPI, Angular, PyTorch, Tokio, etc.
           └──▶ 5 pages per term

           ▼

    Elasticsearch Index
    ┌─────────────────────┐
    │ github-coding-repos │
    │ • full_name         │
    │ • stars, forks      │
    │ • language          │
    │ • topics            │
    └─────────────────────┘


Step 2: DOWNLOAD
─────────────────
    Quality Filter
           │
           ├──▶ Min 10 stars, 3 forks
           ├──▶ Target languages only
           ├──▶ Exclude: tutorials, demos, forks
           └──▶ Score >= 50

           ▼

    Git Clone (depth=1)
           │
           └──▶ /app/repos/{owner}/{repo}

           ▼

    PostgreSQL: repositories table
    ┌────────────────────────────┐
    │ id, full_name, stars       │
    │ quality_score, local_path  │
    │ code_lines, file_count     │
    └────────────────────────────┘


Step 3: PROCESSING
───────────────────
    Walk Repository Files
           │
           ├──▶ Parse code files
           ├──▶ Tokenize content
           ├──▶ Analyze quality
           └──▶ Calculate score

           ▼

    Quality Filtering
    ┌──────────────────────────────────┐
    │ ✅ Code structure                │
    │ ✅ Documentation                 │
    │ ✅ Complexity                    │
    │ ✅ Naming conventions            │
    │ ✅ Security patterns             │
    │ ❌ Generated code                │
    │ ❌ Test fixtures                 │
    │ ❌ Config files                  │
    └──────────────────────────────────┘

           ▼

    PostgreSQL: processed_files table
    ┌────────────────────────────┐
    │ id, file_path, content     │
    │ language, quality_score    │
    │ created_at                 │
    └────────────────────────────┘


Step 4: TRAINING
─────────────────
    Query New Samples
    SELECT * FROM processed_files
    WHERE id > last_trained_id
      AND quality_score >= 70
      AND LENGTH(content) BETWEEN 50 AND 8000
    ORDER BY quality_score DESC
    LIMIT 100000

           ▼

    Format Training Data
    ┌──────────────────────────────────────┐
    │ <|im_start|>system                   │
    │ You are Qwen, an AI coding assistant │
    │ <|im_end|>                           │
    │ <|im_start|>user                     │
    │ {instruction}                        │
    │ {context_code}                       │
    │ <|im_end|>                           │
    │ <|im_start|>assistant                │
    │ {completion_code}                    │
    │ <|im_end|>                           │
    └──────────────────────────────────────┘

           ▼

    Split Dataset
           │
           ├──▶ 95% Training
           └──▶ 5% Validation

           ▼

    Train Qwen2.5-Coder-14B
    ┌──────────────────────────────┐
    │ • 4-bit NF4 quantization     │
    │ • LoRA rank 256, alpha 512   │
    │ • BFloat16 training          │
    │ • Flash Attention 2          │
    │ • Early stopping             │
    └──────────────────────────────┘

           ▼

    Save Best Model
    /app/models/qwen-codelupe/
    ┌────────────────────────────┐
    │ adapter_model.safetensors  │
    │ adapter_config.json        │
    │ tokenizer files            │
    └────────────────────────────┘
```

---

## Training Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS TRAINING LOOP                         │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   START      │
    └──────┬───────┘
           │
           ▼
    ┌─────────────────────────┐
    │ Load State File         │
    │ last_trained_id: 12345  │
    └────────┬────────────────┘
             │
             ▼
    ┌─────────────────────────┐
    │ Wait 5 minutes          │
    └────────┬────────────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │ Count New Files                 │
    │ WHERE id > last_trained_id      │
    │   AND quality_score >= 70       │
    └────────┬────────────────────────┘
             │
             ├──▶ Count < 1000 ────────┐
             │                          │
             ▼                          │
    ┌──────────────────┐                │
    │ Count >= 1000    │                │
    └────────┬─────────┘                │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Fetch Training Samples   │        │
    │ LIMIT 100,000            │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Format Instruction-      │        │
    │ Completion Pairs         │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Split Train/Val (95/5)   │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Initialize Trainer       │        │
    │ • Model: Qwen2.5-14B     │        │
    │ • LoRA: rank 256         │        │
    │ • Batch: 4 × 4 = 16      │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Train for 1 Epoch        │        │
    │ • Evaluate every 100     │        │
    │ • Save checkpoints       │        │
    │ • Early stopping         │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Evaluate on Validation   │        │
    │ Calculate: eval_loss     │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Save Best Model          │        │
    │ /app/models/qwen/        │        │
    └────────┬─────────────────┘        │
             │                          │
             ▼                          │
    ┌──────────────────────────┐        │
    │ Update State File        │        │
    │ last_trained_id: 15789   │        │
    │ total_runs: 5            │        │
    └────────┬─────────────────┘        │
             │                          │
             └──────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Loop Forever    │
                  │ (until shutdown)│
                  └─────────────────┘
```

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DOCKER COMPOSE STACK                           │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Elasticsearch   │  │   PostgreSQL     │  │    MongoDB       │
│  Port: 9200      │  │   Port: 5433     │  │    Port: 27017   │
│  • Search index  │  │   • Metadata     │  │    • Alternative │
│  • Fast queries  │  │   • Quality data │  │    • Optional    │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                     │                      │
         └─────────────────────┴──────────────────────┘
                               │
         ┌─────────────────────┴──────────────────────┐
         │           codelupe-network                 │
         │           (Docker bridge)                  │
         └─────────────────────┬──────────────────────┘
                               │
         ┌─────────────────────┴──────────────────────┐
         │                                             │
         ▼                                             ▼
┌──────────────────┐                         ┌──────────────────┐
│   Crawler        │                         │   Downloader     │
│   (Go)           │                         │   (Go)           │
│   Port: N/A      │                         │   Port: N/A      │
│   • Scrapes      │                         │   • Clones repos │
│   • Rate limits  │                         │   • Filters      │
└──────────────────┘                         └──────────────────┘
         │                                             │
         ▼                                             ▼
┌──────────────────┐                         ┌──────────────────┐
│   Processor      │                         │   Metrics        │
│   (Go)           │                         │   Exporter       │
│   • 14 cores     │                         │   Port: 9091     │
│   • 16GB RAM     │                         │   • Prometheus   │
│   • File parsing │                         │   • Stats        │
└──────────────────┘                         └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 QWEN2.5-CODER TRAINER                           │
│                 (Python + PyTorch)                              │
│                                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │  Connection    │  │  Data Prep     │  │  Training      │   │
│  │  Pool          │  │  • Format      │  │  • LoRA        │   │
│  │  • 1-5 conns   │  │  • Split       │  │  • Flash Attn  │   │
│  │  • Retry       │  │  • Tokenize    │  │  • Early stop  │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                 │
│  Port: 8090 (metrics)                                           │
│  VRAM: 27GB / 32GB                                              │
│  GPU: RTX 5090                                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│  Trained Model   │
│  • LoRA adapter  │
│  • Tokenizer     │
│  • Config        │
└──────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                   MONITORING STACK                               │
├──────────────────────────────────────────────────────────────────┤
│  Prometheus (9090)  →  Grafana (3000)  →  Dashboards            │
│  Kibana (5601)      →  Elasticsearch   →  Log Analysis          │
│  W&B (external)     →  Training Runs   →  Experiment Tracking   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Memory Layout (RTX 5090 32GB)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RTX 5090 VRAM (32GB)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Model Weights (4-bit NF4 Quantization)            7.0 GB     │  │
│  │ • 14B parameters × 0.5 bytes = 7GB                           │  │
│  │ • Double quantization saves ~15%                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ LoRA Adapters (Rank 256)                          0.2 GB     │  │
│  │ • q_proj, k_proj, v_proj, o_proj                             │  │
│  │ • gate_proj, up_proj, down_proj                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Optimizer States (8-bit AdamW)                    7.0 GB     │  │
│  │ • Momentum                                                    │  │
│  │ • Variance                                                    │  │
│  │ • 8-bit quantization saves 4x memory                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Activations & Gradients                          10.0 GB     │  │
│  │ • Batch size 4 × sequence length 4096                        │  │
│  │ • Gradient checkpointing saves 30%                           │  │
│  │ • BFloat16 precision                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ PyTorch CUDA Overhead                             3.0 GB     │  │
│  │ • Kernel cache                                               │  │
│  │ • CUDA graphs                                                │  │
│  │ • Memory pools                                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Buffer / Available                                4.8 GB     │  │
│  │ • Safety margin for peak usage                               │  │
│  │ • Temporary allocations                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Total: 27.2 GB / 32 GB (85% utilization) ✅                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Training Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE STAGES                         │
└─────────────────────────────────────────────────────────────────────┘

Stage 1: DATA FETCHING
───────────────────────
    PostgreSQL Query (with connection pooling)
           │
           ├──▶ Fetch rows where id > last_trained_id
           ├──▶ Filter quality_score >= 70
           ├──▶ Filter content length 50-8000
           └──▶ Order by quality_score DESC

           ▼

    Sample List: 1,000 - 100,000 samples


Stage 2: DATA FORMATTING
─────────────────────────
    For each sample:
           │
           ├──▶ Split code (35% context / 65% completion)
           ├──▶ Choose random instruction template
           ├──▶ Format as Qwen chat template
           └──▶ Tokenize (max 4096 tokens)

           ▼

    Formatted Dataset: List[str]


Stage 3: DATASET SPLITTING
───────────────────────────
    Shuffle with seed=42
           │
           ├──▶ 95% → Training set
           └──▶ 5% → Validation set

           ▼

    HuggingFace Dataset objects


Stage 4: MODEL INITIALIZATION
──────────────────────────────
    Load Base Model
           │
           ├──▶ Qwen2.5-Coder-14B-Instruct
           ├──▶ 4-bit quantization
           ├──▶ Flash Attention 2
           └──▶ BFloat16

           ▼

    Prepare for Training
           │
           ├──▶ prepare_model_for_kbit_training
           ├──▶ Apply LoRA (rank 256)
           └──▶ Enable gradient checkpointing

           ▼

    Ready Model (1.68% trainable params)


Stage 5: TRAINING LOOP
──────────────────────
    Epoch Loop (1 epoch)
           │
           ├──▶ Batch Loop
           │    │
           │    ├──▶ Forward pass
           │    ├──▶ Compute loss
           │    ├──▶ Backward pass
           │    ├──▶ Gradient accumulation (4 steps)
           │    └──▶ Optimizer step
           │
           ├──▶ Evaluation (every 100 steps)
           │    │
           │    ├──▶ Compute validation loss
           │    └──▶ Check early stopping
           │
           └──▶ Checkpointing (every 100 steps)
                │
                └──▶ Save if best model

           ▼

    Training Complete


Stage 6: MODEL SAVING
─────────────────────
    Save LoRA Adapter
           │
           ├──▶ adapter_model.safetensors
           ├──▶ adapter_config.json
           └──▶ tokenizer files

           ▼

    /app/models/qwen-codelupe/


Stage 7: STATE UPDATE
─────────────────────
    Update State File
           │
           ├──▶ last_trained_id = max(sample_ids)
           ├──▶ total_training_runs += 1
           ├──▶ total_samples_trained += len(samples)
           └──▶ last_training_time = now()

           ▼

    trainer_state_qwen.json
```

---

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MONITORING & OBSERVABILITY                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        TRAINER METRICS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Flask Server (Port 8090)                                           │
│  ┌────────────────────┬────────────────────┐                       │
│  │  /health           │  /metrics          │                       │
│  │  • status          │  • state           │                       │
│  │  • model_loaded    │  • train_metrics   │                       │
│  │  • last_trained_id │  • config          │                       │
│  └────────────────────┴────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ├──────────────────────┐
                               │                      │
                               ▼                      ▼
┌──────────────────────────────────┐   ┌──────────────────────────────┐
│  Weights & Biases (W&B)          │   │  Prometheus                  │
│  • Loss curves                   │   │  • Time-series metrics       │
│  • Learning rate                 │   │  • Scrape interval: 15s      │
│  • GPU utilization               │   │  • Retention: 30d            │
│  • Sample predictions            │   │                              │
│  • Hyperparameters               │   │  Grafana Dashboards          │
│  • Experiment comparison         │   │  • Real-time plots           │
└──────────────────────────────────┘   │  • Alerts                    │
                                        │  • Historical trends         │
                                        └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          LOG AGGREGATION                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  /app/logs/continuous_training_qwen.log                             │
│  ┌───────────────────────────────────────┐                         │
│  │ • Training events                     │                         │
│  │ • Error messages                      │                         │
│  │ • Performance metrics                 │                         │
│  │ • State changes                       │                         │
│  └───────────────────────────────────────┘                         │
│                    │                                                │
│                    ▼                                                │
│         ┌─────────────────────┐                                    │
│         │  Kibana (5601)      │                                    │
│         │  • Log search       │                                    │
│         │  • Visualizations   │                                    │
│         │  • Alerts           │                                    │
│         └─────────────────────┘                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         GPU MONITORING                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  nvidia-smi (every 1s)                                              │
│  ┌───────────────────────────────────────┐                         │
│  │ GPU Utilization:  85-95%              │                         │
│  │ Memory Used:      27.2 / 32.0 GB      │                         │
│  │ Temperature:      65-75°C             │                         │
│  │ Power:            320-400W            │                         │
│  │ Clock:            2.5 GHz             │                         │
│  └───────────────────────────────────────┘                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PHYSICAL DEPLOYMENT                             │
└─────────────────────────────────────────────────────────────────────┘

                        ┌──────────────────┐
                        │  Host Machine    │
                        │  • Ubuntu 22.04  │
                        │  • Docker 24+    │
                        │  • CUDA 12.4     │
                        └────────┬─────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
                 ▼                               ▼
        ┌────────────────┐            ┌─────────────────┐
        │  RTX 5090      │            │  Ryzen 9 3900X  │
        │  32GB VRAM     │            │  12c/24t CPU    │
        │  Boost: 2.5GHz │            │  64GB DDR4      │
        └────────────────┘            └─────────────────┘
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                         ┌───────┴────────┐
                         │  Docker Engine │
                         └───────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Data Services  │   │ Processing       │   │ Training         │
│ • Elasticsearch│   │ • Crawler        │   │ • Qwen Trainer   │
│ • PostgreSQL   │   │ • Downloader     │   │ • GPU Access     │
│ • MongoDB      │   │ • Processor      │   │ • 27GB VRAM      │
│ • Redis        │   │ • Metrics        │   │                  │
└────────────────┘   └──────────────────┘   └──────────────────┘

Storage Volumes:
├─ /app/repos/         (500GB+ - Downloaded repositories)
├─ /app/models/        (50GB - Trained models)
├─ /app/checkpoints/   (10GB - Training checkpoints)
├─ /app/cache/         (100GB - HuggingFace cache)
├─ /app/logs/          (5GB - Log files)
└─ postgres_data       (50GB - Database)
```

---

This architecture provides:

1. **Scalability** - Each component can scale independently
2. **Reliability** - Connection pooling, retry logic, state persistence
3. **Observability** - Comprehensive metrics and logging
4. **Performance** - Optimized for RTX 5090, Flash Attention, TF32
5. **Quality** - Multi-stage filtering, validation sets, early stopping
6. **Maintainability** - Clear separation of concerns, well-documented

The system continuously improves as new high-quality code is added to the database.
