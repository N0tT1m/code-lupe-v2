#!/usr/bin/env python3
"""
Minimal Safeguard Codestral Model with LoRA Fine-tuning
Optimized for Codestral-22B on RTX 4090 with 24GB VRAM
Uses LoRA for efficient training with minimal NSFW restrictions
"""

import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer,
    DataCollatorForLanguageModeling,
    GenerationConfig
)

try:
    from transformers import BitsAndBytesConfig
    import bitsandbytes as bnb
    BITSANDBYTES_AVAILABLE = True
except (ImportError, OSError, Exception):
    BITSANDBYTES_AVAILABLE = False
    print("⚠️  BitsAndBytes not available. Install with: pip install bitsandbytes")

try:
    from peft import LoraConfig, get_peft_model, TaskType, PeftModel, prepare_model_for_kbit_training
    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    print("❌ PEFT not available. Install with: pip install peft")
    exit(1)

from datasets import Dataset
import json
import os
import time
from typing import List, Dict, Optional, Union
import warnings
warnings.filterwarnings("ignore")

# RTX 4090 + Codestral optimizations
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# Enable optimized attention
if hasattr(torch.backends.cuda, 'enable_math_sdp'):
    torch.backends.cuda.enable_math_sdp(True)
if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
    torch.backends.cuda.enable_flash_sdp(True)
if hasattr(torch.backends.cuda, 'enable_mem_efficient_sdp'):
    torch.backends.cuda.enable_mem_efficient_sdp(True)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

class MinimalCodestralModel:
    """Codestral model with LoRA fine-tuning and minimal safety restrictions"""
    
    def __init__(self, base_model: str = "mistralai/Codestral-22B-v0.1"):
        self.base_model = base_model
        print(f"🚀 Initializing Codestral with LoRA: {self.base_model}")
        
        self.model = None
        self.tokenizer = None
        self.device = None
        self.lora_config = None
        self.setup_model()
    
    def setup_model(self):
        """Initialize Codestral-22B with LoRA and 4-bit quantization"""
        # Determine device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name()
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"🔥 Using GPU: {gpu_name} ({gpu_memory:.1f}GB)")
        else:
            self.device = torch.device("cpu")
            print("⚠️  Using CPU - this will be very slow!")

        # Load tokenizer
        print("📝 Loading Codestral tokenizer...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.base_model,
                trust_remote_code=True,
                use_fast=True
            )
            # Codestral uses special tokens
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            print("✅ Tokenizer loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load tokenizer: {e}")
            return

        # Configure 4-bit quantization for RTX 4090
        if BITSANDBYTES_AVAILABLE and self.device.type == "cuda":
            print("⚡ Setting up 4-bit quantization for RTX 4090...")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,  # Better than float16 for Codestral
            )
        else:
            bnb_config = None
            print("⚠️  No quantization - may use more memory")

        # Load Codestral model
        print("🤖 Loading Codestral-22B (this may take a few minutes)...")
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,  # Codestral works best with bfloat16
                low_cpu_mem_usage=True,
                attn_implementation="flash_attention_2" if self.device.type == "cuda" else None,
            )
            print("✅ Codestral-22B loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load Codestral: {e}")
            print("💡 Make sure you have access to Codestral and sufficient memory")
            return

        # Prepare model for LoRA training
        if bnb_config:
            print("🔧 Preparing quantized model for LoRA training...")
            self.model = prepare_model_for_kbit_training(self.model)

        # Configure LoRA for Codestral/Mistral architecture
        print("🎯 Setting up LoRA configuration...")
        self.lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=64,  # Higher rank for better performance (RTX 4090 can handle it)
            lora_alpha=16,  # Lower alpha for stability
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",  # Attention layers
                "gate_proj", "up_proj", "down_proj",     # MLP layers
            ],
            bias="none",
            inference_mode=False,
        )

        # Apply LoRA to model
        print("⚡ Applying LoRA adapters to Codestral...")
        try:
            self.model = get_peft_model(self.model, self.lora_config)
            print("✅ LoRA adapters applied successfully")
            
            # Print trainable parameters
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            total_params = sum(p.numel() for p in self.model.parameters())
            print(f"📊 Trainable parameters: {trainable_params:,} ({trainable_params/total_params*100:.2f}%)")
            
        except Exception as e:
            print(f"❌ Failed to apply LoRA: {e}")
            return

        # Set model to training mode
        self.model.train()
        print("🎉 Codestral with LoRA ready for training!")

    def is_gibberish(self, text: str) -> bool:
        """Check if text is gibberish - only safeguard we need"""
        if not text or len(text.strip()) < 5:
            return True
        
        # Check for excessive repetition
        words = text.split()
        if len(words) > 3:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Too much repetition
                return True
        
        # Check for excessive special characters
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if special_chars / len(text) > 0.5:
            return True
        
        return False

    def load_dataset_from_json(self, json_file_path: str) -> Dataset:
        """Load your processed dataset from JSON"""
        print(f"📁 Loading dataset from {json_file_path}...")
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ Loaded {len(data):,} samples from dataset")
            
            # Extract text content and create training examples
            training_texts = []
            for item in data:
                if 'text' in item and item['text']:
                    content = item['text']
                    
                    # Skip gibberish content
                    if self.is_gibberish(content):
                        continue
                    
                    # Format for Codestral instruction fine-tuning
                    # Codestral works well with natural instruction format
                    formatted_text = f"[INST] Complete or improve this code: [/INST]\n{content}"
                    training_texts.append(formatted_text)
            
            print(f"📊 Prepared {len(training_texts):,} training samples")
            return Dataset.from_dict({"text": training_texts})
            
        except Exception as e:
            print(f"❌ Failed to load dataset: {e}")
            return None

    def tokenize_function(self, examples):
        """Tokenize training examples for Codestral"""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding=False,
            max_length=4096,  # Codestral supports longer context
            return_overflowing_tokens=False,
        )

    def train_with_lora(self, dataset_path: str, output_dir: str = "./codestral_unrestricted"):
        """Train Codestral with LoRA on your dataset"""
        
        if not PEFT_AVAILABLE:
            print("❌ LoRA training requires PEFT. Install with: pip install peft")
            return
        
        if self.model is None:
            print("❌ Model not loaded. Check setup.")
            return

        # Load and prepare dataset
        dataset = self.load_dataset_from_json(dataset_path)
        if dataset is None:
            return

        print("🔄 Tokenizing dataset...")
        tokenized_dataset = dataset.map(
            self.tokenize_function, 
            batched=True,
            remove_columns=dataset.column_names
        )

        # Training arguments optimized for RTX 4090 + LoRA
        training_args = TrainingArguments(
            output_dir=output_dir,
            overwrite_output_dir=True,
            num_train_epochs=3,
            per_device_train_batch_size=2,  # Larger batch possible with LoRA
            gradient_accumulation_steps=8,   # Effective batch size: 16
            gradient_checkpointing=True,
            learning_rate=2e-4,  # Higher LR for LoRA
            weight_decay=0.01,
            warmup_steps=100,
            logging_steps=10,
            save_strategy="steps",
            save_steps=500,
            eval_strategy="no",  # No validation to save memory
            bf16=True,  # Use bfloat16 for Codestral
            dataloader_drop_last=True,
            optim="adamw_bnb_8bit" if BITSANDBYTES_AVAILABLE else "adamw_torch",
            lr_scheduler_type="cosine",
            report_to=None,  # Disable wandb/tensorboard
            dataloader_num_workers=4,  # Parallel data loading
            max_grad_norm=1.0,
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False
        )

        # Create trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )

        print("🚀 Starting LoRA fine-tuning on Codestral...")
        print(f"📊 Training samples: {len(tokenized_dataset):,}")
        print(f"🎯 Effective batch size: {training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps}")
        print(f"⏱️  Estimated time: ~2-4 hours on RTX 4090")
        
        start_time = time.time()
        
        try:
            trainer.train()
            training_time = time.time() - start_time
            print(f"✅ Training completed in {training_time/3600:.1f} hours!")
            
            # Save LoRA adapters
            print("💾 Saving LoRA adapters...")
            trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)
            
            print(f"🎉 LoRA adapters saved to {output_dir}")
            print("🔥 Your unrestricted Codestral model is ready!")
            
        except Exception as e:
            print(f"❌ Training failed: {e}")

    @torch.no_grad()
    def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Generate response with Codestral"""
        if self.model is None:
            return "❌ Model not loaded"

        # Format prompt for Codestral
        formatted_prompt = f"[INST] {prompt} [/INST]"
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                formatted_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=3072  # Leave room for generation
            ).to(self.device)

            # Generation config for Codestral
            gen_config = GenerationConfig(
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=0.9,
                top_k=40,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

            # Generate
            with torch.cuda.amp.autocast():
                outputs = self.model.generate(
                    **inputs,
                    generation_config=gen_config
                )

            # Decode only the new tokens
            generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
            response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

            # Only check for gibberish (minimal safeguard)
            if self.is_gibberish(response):
                return "Error: Generated gibberish text."

            return response.strip()

        except Exception as e:
            return f"Error generating response: {str(e)[:200]}"

def main():
    """Main function for Codestral LoRA training"""
    
    print("🚀 CODESTRAL-22B WITH LORA FINE-TUNING")
    print("🔥 OPTIMIZED FOR RTX 4090 + MINIMAL SAFEGUARDS")
    print("============================================================")
    
    # Check environment
    print("\n📋 Environment check:")
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"✅ CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name()}")
        print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    print(f"{'✅' if BITSANDBYTES_AVAILABLE else '❌'} BitsAndBytes: {'Available' if BITSANDBYTES_AVAILABLE else 'Not available'}")
    print(f"{'✅' if PEFT_AVAILABLE else '❌'} PEFT: {'Available' if PEFT_AVAILABLE else 'Not available'}")

    if not PEFT_AVAILABLE:
        print("\n❌ PEFT is required for LoRA training!")
        print("Install with: pip install peft")
        return

    # Initialize model
    try:
        model = MinimalCodestralModel()
        
        if model.model is None:
            print("❌ Failed to initialize Codestral. Check your setup.")
            return
            
        print(f"\n✅ Codestral-22B with LoRA ready!")
        print(f"📊 Base model: {model.base_model}")
        print(f"🖥️  Device: {model.device}")
        
        # Quick capability test
        print("\n🧪 Testing model capabilities...")
        test_response = model.generate_response(
            "Write a simple Python function to calculate factorial", 
            max_tokens=100
        )
        
        if len(test_response.strip()) > 10 and "Error" not in test_response:
            print("✅ Model responding correctly!")
            print(f"Sample: {test_response[:150]}...")
        else:
            print("⚠️  Model may need adjustment")
            print(f"Response: {test_response}")
            
    except Exception as e:
        print(f"❌ Failed to initialize model: {e}")
        return

    # Training section
    print("\n" + "="*60)
    print("🎯 LORA TRAINING SECTION")
    print("📁 Use your processed dataset for training")
    print("⏱️  LoRA training is much faster than full fine-tuning")
    print("="*60)

    # Example training (uncomment to use)
    """
    dataset_path = "\\\\192.168.1.66\\plex3\\codelupe\\ultra_fast_go_dataset_1751414774.json"
    
    if os.path.exists(dataset_path):
        print(f"🚀 Starting LoRA training with {dataset_path}")
        model.train_with_lora(dataset_path, output_dir="./codestral_unrestricted")
        print("✅ Training complete! Your unrestricted Codestral is ready")
    else:
        print(f"❌ Dataset not found: {dataset_path}")
        print("Update the path to your processed dataset")
    """

    # Interactive mode
    print("\n" + "="*60)
    print("🤖 INTERACTIVE MODE")
    print("Commands: 'quit' to exit, 'train' for training info")
    print("🧠 Codestral with minimal safeguards - anti-gibberish only")
    print("="*60)

    while True:
        try:
            user_input = input(f"\n💻 User: ")
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            elif user_input.lower() == 'train':
                print("\n🎯 TRAINING INSTRUCTIONS:")
                print("1. Ensure your dataset JSON file is ready")
                print("2. Update the dataset_path in the training section")
                print("3. Uncomment the training code block")
                print("4. Run this script again")
                print("5. LoRA training will adapt Codestral to your data")
                print("6. Minimal safeguards will be learned from your unrestricted dataset")
                continue
            
            # Generate response
            print("🤖 Codestral: ", end="", flush=True)
            response = model.generate_response(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()