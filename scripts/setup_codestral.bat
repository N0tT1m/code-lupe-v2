@echo off
echo 🚀 Codestral-22B LoRA Setup for RTX 4090
echo ========================================

REM Check if NVIDIA GPU is available
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ NVIDIA GPU not detected or drivers not installed
    pause
    exit /b 1
)

echo 🔍 Checking GPU...
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits

REM Check Python version
python --version
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 3.8+ required
    pause
    exit /b 1
)

REM Install requirements
echo 📦 Installing Codestral requirements...
python -m pip install --upgrade pip

REM Install PyTorch with CUDA support first
echo ⚡ Installing PyTorch with CUDA...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

REM Install other requirements
echo 📦 Installing remaining packages...
pip install -r requirements_codestral.txt

REM Verify installation
echo ✅ Verifying installation...
python -c "import torch; import transformers; import peft; import bitsandbytes; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name() if torch.cuda.is_available() else \"None\"}'); print(f'Transformers: {transformers.__version__}'); print(f'PEFT: {peft.__version__}'); print('✅ All packages installed successfully!')"

echo.
echo 🎯 Setup Complete!
echo ==================
echo.
echo Next steps:
echo 1. Make sure you have access to Codestral-22B model
echo 2. Prepare your dataset JSON file
echo 3. Run: python minimal_codestral_model.py
echo 4. Uncomment training section and update dataset path
echo 5. Start LoRA fine-tuning!
echo.
echo 💡 Tips:
echo • LoRA training is much faster than full fine-tuning
echo • Your RTX 4090 can handle Codestral-22B with 4-bit quantization
echo • Training should take 2-4 hours with your dataset
echo • Results will be saved to ./codestral_unrestricted/
echo.
pause