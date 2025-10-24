# Build trainer without flash-attention as fallback

Write-Host "Building trainer WITHOUT flash-attention (fallback mode)..."
Write-Host "This will work but training will be slower"

# Create temporary Dockerfile without flash-attention
$fallbackDockerfile = @"
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements_codestral.txt .
RUN pip3 install --no-cache-dir --upgrade pip

# Install build dependencies first
RUN pip3 install --no-cache-dir \
    packaging \
    ninja \
    wheel \
    setuptools

# Install PyTorch with CUDA 12.1
RUN pip3 install --no-cache-dir torch==2.4.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install transformers and other requirements
RUN pip3 install --no-cache-dir -r requirements_codestral.txt

# Install triton
RUN pip3 install --no-cache-dir triton==2.3.1

# Copy training scripts
COPY continuous_trainer.py .
COPY minimal_codestral_model.py .

# Create directories
RUN mkdir -p /app/models /app/checkpoints /app/logs /app/datasets

# Environment variables for optimization
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
ENV CUDA_LAUNCH_BLOCKING=0
ENV TORCH_CUDNN_V8_API_ENABLED=1
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import torch; print('GPU Available:', torch.cuda.is_available())" || exit 1

# Expose metrics port
EXPOSE 8090

CMD ["python3", "continuous_trainer.py"]
"@

# Write fallback dockerfile
$fallbackDockerfile | Out-File -FilePath "Dockerfile.trainer.fallback" -Encoding UTF8

# Update trainer code to not require flash attention
$fallbackTrainer = Get-Content "continuous_trainer.py" -Raw
$fallbackTrainer = $fallbackTrainer -replace 'attn_implementation="flash_attention_2",', ''
$fallbackTrainer | Out-File -FilePath "continuous_trainer_fallback.py" -Encoding UTF8

# Build using fallback
docker build -f Dockerfile.trainer.fallback -t codelupe-trainer .

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Fallback trainer built successfully" -ForegroundColor Green
    
    # Update docker-compose to use fallback trainer
    Write-Host "Starting fallback trainer..."
    docker-compose up -d trainer
    
    Start-Sleep 10
    Write-Host "Trainer logs:"
    docker logs codelupe-trainer --tail=10
} else {
    Write-Host "❌ Even fallback build failed" -ForegroundColor Red
}

# Cleanup
Remove-Item "Dockerfile.trainer.fallback" -ErrorAction SilentlyContinue
Remove-Item "continuous_trainer_fallback.py" -ErrorAction SilentlyContinue