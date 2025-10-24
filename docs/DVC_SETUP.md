# Data Version Control (DVC) Setup

This document explains how to use DVC for versioning datasets and models in CodeLupe.

## Overview

DVC (Data Version Control) tracks large files and datasets that shouldn't be stored in Git. It works alongside Git to version control:

- Training datasets
- Processed code samples
- Trained model checkpoints
- Experiment results

## Installation

```bash
# Install DVC
pip install dvc[s3]  # With S3 support
# OR
pip install dvc      # Basic installation

# Initialize DVC (already done)
dvc init
```

## Configuration

DVC is configured to use S3 for remote storage. Configuration is in `.dvc/config`.

### Setting up S3 Remote Storage

```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Or use AWS CLI
aws configure

# Test connection
dvc remote list
```

### Using Local Storage (Development)

```bash
# Switch to local storage for development
dvc remote add -d local ./dvc-storage

# Or modify .dvc/config to use local remote
```

## Tracking Files with DVC

### Track a Directory

```bash
# Track the datasets directory
dvc add datasets/

# This creates datasets.dvc file
# Commit both the .dvc file and .gitignore changes
git add datasets.dvc datasets/.gitignore
git commit -m "feat(data): track datasets with DVC"
```

### Track Models

```bash
# Track trained models
dvc add models/qwen-codelupe/

git add models/qwen-codelupe.dvc models/.gitignore
git commit -m "feat(models): add trained Qwen model v1.0"
```

### Track Processed Files

```bash
# Track processed code database
dvc add processed_files_export.parquet

git add processed_files_export.parquet.dvc
git commit -m "feat(data): add processed files snapshot"
```

## Pushing and Pulling Data

### Push Data to Remote

```bash
# Push all tracked files
dvc push

# Push specific file
dvc push datasets.dvc
```

### Pull Data from Remote

```bash
# Pull all tracked files
dvc pull

# Pull specific file
dvc pull datasets.dvc
```

## Versioning Datasets

### Create a New Version

```bash
# 1. Update the dataset
# ... add new files to datasets/ ...

# 2. Update DVC tracking
dvc add datasets/

# 3. Commit the change
git add datasets.dvc
git commit -m "feat(data): add 10k new code samples"

# 4. Create a git tag
git tag -a v1.1.0 -m "Dataset version 1.1.0 - 10k new samples"

# 5. Push data and code
dvc push
git push --follow-tags
```

### Switch Between Versions

```bash
# Checkout a specific version
git checkout v1.0.0

# Pull the corresponding data
dvc pull

# Return to latest
git checkout main
dvc pull
```

## Experiment Tracking

### Track an Experiment

```bash
# Start experiment
dvc exp run --name experiment_1

# Save results
dvc exp save experiment_1

# View experiments
dvc exp show
```

### Compare Experiments

```bash
# List all experiments
dvc exp list

# Show experiment metrics
dvc metrics show

# Compare two experiments
dvc metrics diff experiment_1 experiment_2
```

## Pipeline Definition

Create a DVC pipeline for reproducible data processing:

```yaml
# dvc.yaml
stages:
  download:
    cmd: go run downloader.go download ./repos 5
    deps:
      - downloader.go
    outs:
      - repos/

  process:
    cmd: go run resumable_processor.go
    deps:
      - resumable_processor.go
      - repos/
    outs:
      - processed_files.db

  export:
    cmd: python src/python/processors/export_dataset.py
    deps:
      - src/python/processors/export_dataset.py
      - processed_files.db
    outs:
      - datasets/training_data.parquet
    metrics:
      - datasets/stats.json

  train:
    cmd: python src/python/trainers/continuous_trainer_qwen_5090.py
    deps:
      - src/python/trainers/continuous_trainer_qwen_5090.py
      - datasets/training_data.parquet
    params:
      - train.batch_size
      - train.learning_rate
    outs:
      - models/qwen-codelupe/
    metrics:
      - models/metrics.json
```

Run the pipeline:

```bash
# Run entire pipeline
dvc repro

# Run specific stage
dvc repro train
```

## Best Practices

### 1. Use .dvcignore

Add patterns to `.dvcignore` to avoid tracking unnecessary files:

```
*.log
*.tmp
__pycache__/
.pytest_cache/
```

### 2. Tag Important Versions

```bash
# Tag major dataset versions
git tag -a data-v1.0.0 -m "Initial production dataset"
git tag -a model-v1.0.0 -m "First production model"

# Push tags
git push --tags
```

### 3. Document Changes

Use meaningful commit messages:

```bash
git commit -m "feat(data): add 50k Rust repositories
- Increased quality threshold to 75
- Added advanced error handling patterns
- Total samples: 250k -> 300k"
```

### 4. Regular Backups

```bash
# Push data regularly
dvc push

# Verify remote storage
dvc status -c
```

### 5. Clean Up Cache

```bash
# Remove unused cache files
dvc gc

# Clean up workspace
dvc gc --workspace

# Remove specific version
dvc gc --revisions main
```

## Troubleshooting

### Issue: DVC push fails

```bash
# Check remote configuration
dvc remote list

# Verify credentials
aws s3 ls s3://codelupe-data/

# Check DVC status
dvc status -c
```

### Issue: Large transfer times

```bash
# Use --jobs for parallel transfers
dvc push --jobs 4

# Check file sizes
dvc list . --dvc-only --size
```

### Issue: Corrupted cache

```bash
# Verify cache integrity
dvc cache verify

# Rebuild cache
dvc cache rebuild
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: DVC Pipeline

on:
  push:
    branches: [main]

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup DVC
        uses: iterative/setup-dvc@v1

      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Pull data
        run: dvc pull

      - name: Run pipeline
        run: dvc repro

      - name: Push results
        run: dvc push
```

## Useful Commands

```bash
# Show DVC status
dvc status

# List tracked files
dvc list . --dvc-only

# Get file info
dvc get . datasets/training_data.parquet --show-url

# Import data from another DVC project
dvc import https://github.com/user/repo path/to/data

# Diff between versions
dvc diff HEAD~1 HEAD

# Show dependency graph
dvc dag

# Check cache size
du -sh .dvc/cache
```

## Resources

- [DVC Documentation](https://dvc.org/doc)
- [DVC Tutorial](https://dvc.org/doc/start)
- [DVC with S3](https://dvc.org/doc/user-guide/data-management/remote-storage/amazon-s3)
- [DVC Pipeline](https://dvc.org/doc/start/data-pipelines)
