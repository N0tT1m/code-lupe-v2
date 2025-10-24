#!/bin/bash

echo "🚀 Codestral-22B LoRA Setup for RTX 4090"
echo "========================================"

# Check if CUDA is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ NVIDIA GPU not detected or drivers not installed"
    exit 1
fi

echo "🔍 Checking GPU..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "🐍 Python version: $python_version"

if ! python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Python 3.8+ required"
    exit 1
fi

# Install requirements
echo "📦 Installing Codestral requirements..."
pip install --upgrade pip

# Install PyTorch with CUDA support first
echo "⚡ Installing PyTorch with CUDA..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install other requirements
echo "📦 Installing remaining packages..."
pip install -r requirements_codestral.txt

# Verify installation
echo "✅ Verifying installation..."
python -c "
import torch
import transformers
import peft
import bitsandbytes

print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name()}')
    print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB')
print(f'Transformers: {transformers.__version__}')
print(f'PEFT: {peft.__version__}')
print('✅ All packages installed successfully!')
"

echo ""
echo "🎯 Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Make sure you have access to Codestral-22B model"
echo "2. Prepare your dataset JSON file"
echo "3. Run: python minimal_codestral_model.py"
echo "4. Uncomment training section and update dataset path"
echo "5. Start LoRA fine-tuning!"
echo ""
echo "💡 Tips:"
echo "• LoRA training is much faster than full fine-tuning"
echo "• Your RTX 4090 can handle Codestral-22B with 4-bit quantization"
echo "• Training should take 2-4 hours with your dataset"
echo "• Results will be saved to ./codestral_unrestricted/"