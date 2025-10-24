# W&B Metrics Quick Reference

This is a condensed reference of all metrics logged to Weights & Biases.

## 📊 Metric Categories

### 1. Training Metrics (`train/*`, `eval/*`, `batch/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `train/loss` | Training loss | Every logging step |
| `train/perplexity` | exp(train_loss) | Every logging step |
| `train/learning_rate` | Current learning rate | Every logging step |
| `train/epoch` | Current epoch | Every logging step |
| `eval/loss` | Evaluation loss | Every eval step |
| `eval/perplexity` | exp(eval_loss) | Every eval step |
| `batch/loss` | Per-batch loss | Every batch |
| `batch/perplexity` | Per-batch perplexity | Every batch |
| `batch/size` | Batch size | Every batch |
| `batch/grad_norm` | Gradient norm | Every batch |

### 2. System Metrics (`system/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `system/cpu_percent` | CPU utilization % | Every 10 steps |
| `system/cpu_count` | Number of CPU cores | Every 10 steps |
| `system/memory_used_gb` | RAM used (GB) | Every 10 steps |
| `system/memory_available_gb` | RAM available (GB) | Every 10 steps |
| `system/memory_percent` | RAM utilization % | Every 10 steps |
| `system/disk_used_gb` | Disk used (GB) | Every 10 steps |
| `system/disk_free_gb` | Disk free (GB) | Every 10 steps |
| `system/disk_percent` | Disk utilization % | Every 10 steps |
| `system/gpu_0_memory_allocated_gb` | GPU memory allocated (GB) | Every 10 steps |
| `system/gpu_0_memory_reserved_gb` | GPU memory reserved (GB) | Every 10 steps |
| `system/gpu_0_utilization` | GPU compute % | Every 10 steps |
| `system/gpu_0_memory_utilization` | GPU memory % | Every 10 steps |

### 3. Data Quality Metrics (`data/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `data/total_samples` | Total samples processed | Per run |
| `data/avg_quality_score` | Average quality score | Per run |
| `data/avg_code_length` | Average code length | Per run |
| `data/language_{lang}` | Count per language | Per run |
| `data/language_{lang}_percent` | Percentage per language | Per run |
| `data/blocked_malicious` | Malicious code blocked | Per run |
| `data/blocked_secrets` | Secrets blocked | Per run |
| `data/blocked_license` | License violations blocked | Per run |
| `data/blocked_total` | Total blocked | Per run |
| `data/pass_rate` | Pass rate % | Per run |

### 4. Dataset Statistics (`dataset/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `dataset/train_size` | Training set size | Per run |
| `dataset/eval_size` | Validation set size | Per run |
| `dataset/total_size` | Total dataset size | Per run |
| `dataset/train_eval_ratio` | Train/eval ratio | Per run |
| `dataset/avg_tokens_per_sample` | Avg tokens per sample | Per run |
| `dataset/max_tokens` | Max tokens in dataset | Per run |
| `dataset/min_tokens` | Min tokens in dataset | Per run |

### 5. Performance Metrics (`performance/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `performance/samples_per_second` | Training throughput | Per run |
| `performance/tokens_per_second` | Token processing rate | Per run |
| `performance/batch_time_ms` | Avg batch time (ms) | Per run |

### 6. Model Metrics (`gradients/*`, `weights/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `gradients/global_norm` | Global gradient norm | Optional |
| `gradients/mean_norm` | Mean gradient norm | Optional |
| `gradients/max_norm` | Max gradient norm | Optional |
| `gradients/min_norm` | Min gradient norm | Optional |
| `weights/global_mean` | Global weight mean | Optional |
| `weights/global_std` | Global weight std | Optional |

### 7. Continuous Training State (`continuous/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `continuous/run_number` | Current run number | Per run |
| `continuous/total_runs` | Total runs completed | Per run |
| `continuous/last_trained_id` | Last processed DB ID | Per run |
| `continuous/total_samples_trained` | Total samples trained | Per run |
| `continuous/uptime_hours` | System uptime (hours) | Per run |

### 8. Progress Metrics (`progress/*`)

| Metric | Description | Frequency |
|--------|-------------|-----------|
| `progress/step` | Current training step | Per logging step |
| `progress/step_percent` | Step completion % | Per logging step |
| `progress/epoch` | Current epoch | Per logging step |
| `progress/epoch_percent` | Epoch completion % | Per logging step |
| `progress/eta_minutes` | ETA (minutes) | Per logging step |
| `progress/eta_hours` | ETA (hours) | Per logging step |

---

## 📈 W&B Dashboard Recommended Charts

### Overview Dashboard

1. **Loss Tracking**
   - Line chart: `train/loss` and `eval/loss` over steps
   - Line chart: `train/perplexity` and `eval/perplexity` over steps

2. **System Health**
   - Line chart: `system/gpu_0_utilization` and `system/gpu_0_memory_utilization`
   - Line chart: `system/memory_percent` and `system/cpu_percent`

3. **Training Progress**
   - Line chart: `progress/step_percent` and `progress/epoch_percent`
   - Number panel: `continuous/total_samples_trained`

4. **Performance**
   - Line chart: `performance/samples_per_second`
   - Line chart: `performance/tokens_per_second`

### Data Quality Dashboard

1. **Quality Metrics**
   - Number panel: `data/avg_quality_score`
   - Bar chart: `data/language_{lang}` distribution

2. **Security Filtering**
   - Number panel: `data/blocked_total`
   - Pie chart: `data/blocked_malicious`, `data/blocked_secrets`, `data/blocked_license`
   - Line chart: `data/pass_rate`

3. **Dataset Stats**
   - Number panel: `dataset/train_size`, `dataset/eval_size`
   - Number panel: `dataset/avg_tokens_per_sample`

### Performance Dashboard

1. **Throughput**
   - Line chart: `performance/samples_per_second` over time
   - Line chart: `performance/tokens_per_second` over time

2. **Resource Utilization**
   - Heatmap: GPU memory over time
   - Line chart: `system/gpu_0_utilization` with `performance/samples_per_second` overlay

3. **Batch Timing**
   - Histogram: `performance/batch_time_ms` distribution

---

## 🔧 Common Queries

### Find best training run
```
Sort runs by: eval/loss (ascending)
```

### Compare learning rates
```
Group runs by: hyperparams/learning_rate
Chart: train/loss over steps
```

### Identify bottlenecks
```
Chart: system/gpu_0_utilization
If < 80%: Check data loading or CPU bottleneck
```

### Monitor data quality over time
```
X-axis: continuous/run_number
Y-axis: data/avg_quality_score
```

---

## 💡 Best Practices

1. **Tag your runs** - Use descriptive names for experiments
2. **Group related runs** - Use W&B groups for hyperparameter sweeps
3. **Compare runs** - Use W&B parallel coordinates plot for multi-metric comparison
4. **Set alerts** - Configure W&B alerts for eval_loss spikes or GPU utilization drops
5. **Export data** - Download metrics as CSV for offline analysis

---

## 🚨 Monitoring Alerts (Recommended)

Set up W&B alerts for:

1. **Training Health**
   - Alert if `eval/loss` increases by > 10% over 100 steps
   - Alert if `train/loss` is NaN or Inf

2. **System Health**
   - Alert if `system/gpu_0_utilization` < 50% for > 5 minutes
   - Alert if `system/memory_percent` > 95%

3. **Data Quality**
   - Alert if `data/avg_quality_score` < 0.6
   - Alert if `data/blocked_total` > 20% of samples

4. **Performance**
   - Alert if `performance/samples_per_second` drops by > 30%

---

## 📝 Notes

- All metrics are logged asynchronously (non-blocking)
- System metrics are sampled every 10 steps to reduce overhead
- Gradient/weight metrics are optional (disabled by default for performance)
- No data or model artifacts are stored on W&B (metrics only)

For full implementation details, see `WANDB_INTEGRATION.md`.
