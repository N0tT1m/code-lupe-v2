#!/usr/bin/env python3
"""
Minimal Safeguard Coding Model with GitHub Training Pipeline
Fixed for proper model loading and generation
Optimized for RTX 4090 with 24GB VRAM
"""

import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM,
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

try:
    from peft import LoraConfig, get_peft_model, TaskType
    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    print("⚠️  PEFT not available. Install with: pip install peft")

from datasets import Dataset
import requests
import base64
import json
import os
import time
from typing import List, Dict, Optional, Union
import subprocess
import tempfile
import shutil
import warnings
warnings.filterwarnings("ignore")

# Modern instruct models that work well
RECOMMENDED_MODELS = {
    # Small models (< 3GB VRAM)
    "phi-2": "microsoft/phi-2",
    "stablelm": "stabilityai/stablelm-2-1_6b",
    "tinyllama": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    
    # Medium models (4-8GB VRAM)
    "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
    "zephyr": "HuggingFaceH4/zephyr-7b-beta",
    "openchat": "openchat/openchat-3.5-0106",
    
    # Large models (12-24GB VRAM) 
    "lmstudio-community": "lmstudio-community/Qwen2.5-Coder-7B-Instruct",
    "deepseek": "deepseek-ai/deepseek-coder-6.7b-instruct",
    "codellama": "codellama/CodeLlama-7b-Instruct-hf",
    
    # Fallback models that always work
    "gpt2": "gpt2",
    "distilgpt2": "distilgpt2",
}

class GitHubDataFetcher:
    """Fetch and process repositories from GitHub"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.headers = {}
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
        
        # File extensions to process
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.sh', '.sql', '.r', '.m', '.pl', '.lua', '.dart', '.vim',
            '.sol', '.asm', '.hack'
        }
    
    def clone_and_process_repo(self, repo_url: str, max_files: int = 1000) -> List[Dict]:
        """Clone repo locally and process files"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Clone repository
            subprocess.run(['git', 'clone', '--depth', '1', repo_url, temp_dir], 
                         check=True, capture_output=True)
            
            files_data = []
            for root, dirs, files in os.walk(temp_dir):
                # Skip .git directory
                if '.git' in root:
                    continue
                    
                for file in files[:max_files]:
                    if any(file.endswith(ext) for ext in self.code_extensions):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if content.strip():  # Skip empty files
                                    files_data.append({
                                        'path': os.path.relpath(file_path, temp_dir),
                                        'content': content,
                                        'repo': repo_url.split('/')[-1],
                                        'size': len(content)
                                    })
                        except Exception as e:
                            print(f"Error reading file {file_path}: {e}")
                            
            return files_data
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
            return []
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class MinimalCodingModel:
    """Coding model with minimal safety restrictions"""
    
    def __init__(self, base_model: str = None):
        # Select model based on available resources
        if base_model:
            self.base_model = base_model
        else:
            self.base_model = self.auto_select_model()
                
        print(f"Selected model: {self.base_model}")
        self.model = None
        self.tokenizer = None
        self.model_type = None
        self.device = None
        self.setup_model()
    
    def auto_select_model(self):
        """Auto-select model based on available resources"""
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU detected with {gpu_memory:.1f}GB memory")
            
            if gpu_memory >= 20:
                print("Selecting large model for high-end GPU")
                return RECOMMENDED_MODELS["codellama"]
            elif gpu_memory >= 8:
                print("Selecting medium model for mid-range GPU")
                return RECOMMENDED_MODELS["mistral"]
            else:
                print("Selecting small model for low-end GPU")
                return RECOMMENDED_MODELS["phi-2"]
        else:
            print("No GPU detected, using CPU-friendly model")
            return RECOMMENDED_MODELS["gpt2"]
    
    def determine_model_type(self, model_name: str):
        """Determine if model is encoder-decoder or decoder-only"""
        encoder_decoder_models = ['t5', 'bart', 'mbart', 'pegasus', 'marian', 'blenderbot']
        
        for model_type in encoder_decoder_models:
            if model_type in model_name.lower():
                return "encoder-decoder"
        
        return "decoder-only"
    
    def fix_config_none_values(self, config):
        """Fix None values in model config"""
        fixes_applied = []
        
        # Common None value fixes
        if hasattr(config, 'pretraining_tp') and config.pretraining_tp is None:
            config.pretraining_tp = 1
            fixes_applied.append("pretraining_tp")
            
        if hasattr(config, 'rope_scaling') and config.rope_scaling is None:
            config.rope_scaling = {}
            fixes_applied.append("rope_scaling")
            
        if hasattr(config, 'tie_word_embeddings') and config.tie_word_embeddings is None:
            config.tie_word_embeddings = True
            fixes_applied.append("tie_word_embeddings")
            
        if fixes_applied:
            print(f"Fixed config None values: {', '.join(fixes_applied)}")
            
        return config

    def setup_model(self):
        """Initialize model with better error handling"""
        from transformers import AutoConfig
        
        # Determine device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            print(f"Using GPU: {torch.cuda.get_device_name()}")
        else:
            self.device = torch.device("cpu")
            print("Using CPU")
        
        # Load tokenizer
        print("Loading tokenizer...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.base_model, 
                trust_remote_code=True,
                use_fast=True
            )
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            print("✅ Tokenizer loaded")
        except Exception as e:
            print(f"❌ Tokenizer loading failed: {e}")
            # Fallback to GPT2 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
            self.tokenizer.pad_token = self.tokenizer.eos_token
            print("✅ Using fallback GPT2 tokenizer")
        
        # Determine model type
        self.model_type = self.determine_model_type(self.base_model)
        print(f"Model type: {self.model_type}")
        
        # Load model with multiple strategies
        loaded = False
        
        # Strategy 1: Try with appropriate model class
        try:
            print("Loading model...")
            config = AutoConfig.from_pretrained(self.base_model, trust_remote_code=True)
            config = self.fix_config_none_values(config)
            
            # Use appropriate model class
            if self.model_type == "encoder-decoder":
                ModelClass = AutoModelForSeq2SeqLM
            else:
                ModelClass = AutoModelForCausalLM
            
            # Try quantized loading if available
            if self.device.type == "cuda" and BITSANDBYTES_AVAILABLE:
                try:
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    
                    self.model = ModelClass.from_pretrained(
                        self.base_model,
                        config=config,
                        quantization_config=bnb_config,
                        device_map="auto",
                        trust_remote_code=True,
                        torch_dtype=torch.float16
                    )
                    print("✅ Model loaded with 4-bit quantization")
                    loaded = True
                except Exception as e:
                    print(f"⚠️  Quantization failed: {str(e)[:100]}")
            
            # Try regular GPU loading
            if not loaded and self.device.type == "cuda":
                try:
                    self.model = ModelClass.from_pretrained(
                        self.base_model,
                        config=config,
                        device_map="auto",
                        torch_dtype=torch.float16,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )
                    print("✅ Model loaded on GPU")
                    loaded = True
                except Exception as e:
                    print(f"⚠️  GPU loading failed: {str(e)[:100]}")
            
            # Try CPU loading
            if not loaded:
                try:
                    self.model = ModelClass.from_pretrained(
                        self.base_model,
                        config=config,
                        torch_dtype=torch.float32,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )
                    self.model = self.model.to(self.device)
                    print("✅ Model loaded on CPU")
                    loaded = True
                except Exception as e:
                    print(f"⚠️  CPU loading failed: {str(e)[:100]}")
                    
        except Exception as e:
            print(f"❌ Model loading failed: {str(e)[:200]}")
        
        # Strategy 2: Fallback to simpler model
        if not loaded:
            print("\nTrying fallback model...")
            fallback_models = ["gpt2", "distilgpt2", "microsoft/DialoGPT-small"]
            
            for fallback in fallback_models:
                try:
                    self.base_model = fallback
                    self.model_type = "decoder-only"
                    self.tokenizer = AutoTokenizer.from_pretrained(fallback)
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                    
                    self.model = AutoModelForCausalLM.from_pretrained(
                        fallback,
                        torch_dtype=torch.float32,
                        low_cpu_mem_usage=True
                    )
                    self.model = self.model.to(self.device)
                    print(f"✅ Loaded fallback model: {fallback}")
                    loaded = True
                    break
                except Exception as e:
                    print(f"⚠️  Fallback {fallback} failed: {str(e)[:100]}")
        
        if not loaded:
            raise Exception("Failed to load any model. Please check your environment.")
        
        # Setup LoRA if available
        if PEFT_AVAILABLE and "gpt2" not in self.base_model.lower():
            try:
                print("Setting up LoRA...")
                target_modules = None
                
                # Model-specific target modules
                if "llama" in self.base_model.lower():
                    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
                elif "mistral" in self.base_model.lower() or "mixtral" in self.base_model.lower():
                    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
                elif "phi" in self.base_model.lower():
                    target_modules = ["q_proj", "k_proj", "v_proj", "dense", "fc1", "fc2"]
                
                if target_modules:
                    lora_config = LoraConfig(
                        task_type=TaskType.CAUSAL_LM if self.model_type == "decoder-only" else TaskType.SEQ_2_SEQ_LM,
                        r=32,
                        lora_alpha=16,
                        lora_dropout=0.05,
                        target_modules=target_modules,
                        bias="none"
                    )
                    
                    self.model = get_peft_model(self.model, lora_config)
                    print("✅ LoRA configured")
            except Exception as e:
                print(f"⚠️  LoRA setup skipped: {str(e)[:100]}")
        
        # Ensure model is in eval mode
        self.model.eval()
        print("✅ Model setup complete!")
    
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
    
    def prepare_training_data(self, repo_files: List[Dict], include_datasets: bool = True) -> Dataset:
        """Convert repository files to training dataset with enhanced data sources"""
        
        training_texts = []
        
        # Load high-quality pre-filtered datasets if available
        if include_datasets:
            try:
                from datasets import load_dataset
                print("📚 Loading additional high-quality coding datasets...")
                
                # Add diverse coding examples
                dataset_samples = self._load_enhanced_datasets(max_samples=10000)
                training_texts.extend(dataset_samples)
                print(f"✅ Added {len(dataset_samples):,} high-quality dataset samples")
                
            except ImportError:
                print("⚠️ Datasets library not available, using repo files only")
            except Exception as e:
                print(f"⚠️ Failed to load additional datasets: {e}")
        
        # Process repository files
        for file_data in repo_files:
            content = file_data['content']
            file_path = file_data['path']
            
            # Skip very large files
            if len(content) > 8000:
                continue
            
            # Skip gibberish content
            if self.is_gibberish(content):
                continue
            
            # Create diverse training examples with better variety
            instructions = [
                f"Explain the code in {file_path}:",
                f"Improve the code in {file_path}:",
                f"Debug and fix issues in {file_path}:",
                f"Add comments to explain {file_path}:",
                f"Refactor this code from {file_path}:",
                f"Complete this code from {file_path}:",
                f"Write documentation for {file_path}:",
                f"Optimize the performance of {file_path}:",
                f"Convert this code to a different style:",
                f"Add error handling to {file_path}:",
            ]
            
            import random
            instruction = random.choice(instructions)
            
            # Enhanced formatting based on model type
            if "mistral" in self.base_model.lower():
                formatted_text = f"<s>[INST] {instruction} [/INST] {content}</s>"
            elif "phi" in self.base_model.lower():
                formatted_text = f"Instruct: {instruction}\nOutput: {content}"
            elif "llama" in self.base_model.lower():
                formatted_text = f"<s>[INST] {instruction} [/INST]\n{content}</s>"
            elif "lmstudio-community" in self.base_model.lower():
                formatted_text = f"<|im_start|>user\n{instruction}<|im_end|>\n<|im_start|>assistant\n{content}<|im_end|>"
            else:
                formatted_text = f"### Instruction:\n{instruction}\n\n### Response:\n{content}\n\n"
            
            training_texts.append(formatted_text)
        
        print(f"📊 Total training samples prepared: {len(training_texts):,}")
        return Dataset.from_dict({"text": training_texts})
    
    def _load_enhanced_datasets(self, max_samples: int = 10000) -> List[str]:
        """Load enhanced datasets for better training quality"""
        try:
            from datasets import load_dataset
            import random
            
            samples = []
            
            # High-quality code datasets
            dataset_configs = [
                {
                    'name': 'flytech/python-codes-25k',
                    'field': 'text',
                    'max_samples': max_samples // 3,
                    'format_type': 'code'
                },
                {
                    'name': 'sahil2801/CodeAlpaca-20k',
                    'field': 'output',
                    'instruction_field': 'instruction',
                    'max_samples': max_samples // 3,
                    'format_type': 'instruction'
                },
                {
                    'name': 'HuggingFaceH4/CodeAlpaca_20K',
                    'field': 'output', 
                    'instruction_field': 'instruction',
                    'max_samples': max_samples // 3,
                    'format_type': 'instruction'
                }
            ]
            
            for config in dataset_configs:
                try:
                    print(f"  Loading {config['name']}...")
                    dataset = load_dataset(config['name'], split='train')
                    
                    # Random sampling for diversity
                    indices = random.sample(range(len(dataset)), min(config['max_samples'], len(dataset)))
                    
                    for idx in indices:
                        item = dataset[idx]
                        content = item.get(config['field'], '')
                        
                        if len(content) > 50 and len(content) < 3000 and not self.is_gibberish(content):
                            if config['format_type'] == 'instruction' and config.get('instruction_field'):
                                instruction = item.get(config['instruction_field'], '')
                                if instruction:
                                    formatted = self._format_sample_for_model(instruction, content)
                                    samples.append(formatted)
                            else:
                                # Direct code sample
                                instruction = "Write high-quality, well-documented code:"
                                formatted = self._format_sample_for_model(instruction, content)
                                samples.append(formatted)
                                
                    print(f"    ✅ Loaded {len([s for s in samples if config['name'] in s]):,} samples")
                    
                except Exception as e:
                    print(f"    ⚠️ Failed to load {config['name']}: {e}")
                    continue
            
            return samples
            
        except Exception as e:
            print(f"⚠️ Enhanced dataset loading failed: {e}")
            return []
    
    def _format_sample_for_model(self, instruction: str, content: str) -> str:
        """Format a sample according to the model's preferred format"""
        if "mistral" in self.base_model.lower():
            return f"<s>[INST] {instruction} [/INST] {content}</s>"
        elif "phi" in self.base_model.lower():
            return f"Instruct: {instruction}\nOutput: {content}"
        elif "llama" in self.base_model.lower():
            return f"<s>[INST] {instruction} [/INST]\n{content}</s>"
        elif "lmstudio-community" in self.base_model.lower():
            return f"<|im_start|>user\n{instruction}<|im_end|>\n<|im_start|>assistant\n{content}<|im_end|>"
        else:
            return f"### Instruction:\n{instruction}\n\n### Response:\n{content}\n\n"
    
    def tokenize_function(self, examples):
        """Tokenize training examples"""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding=False,
            max_length=2048,
            return_overflowing_tokens=False,
        )
    
    def train_on_repos(self, repo_urls: List[str], output_dir: str = "./unrestricted_model"):
        """Train model on GitHub repositories"""
        
        if not PEFT_AVAILABLE:
            print("❌ Training requires PEFT. Install with: pip install peft")
            return
            
        print("Fetching repository data...")
        fetcher = GitHubDataFetcher()
        all_files = []
        
        for repo_url in repo_urls:
            print(f"Processing {repo_url}...")
            files = fetcher.clone_and_process_repo(repo_url)
            all_files.extend(files)
            print(f"Collected {len(files)} files from {repo_url}")
        
        if not all_files:
            print("❌ No files collected. Check repository URLs.")
            return
            
        print(f"Total files collected: {len(all_files)}")
        
        # Prepare dataset
        dataset = self.prepare_training_data(all_files)
        tokenized_dataset = dataset.map(self.tokenize_function, batched=True)
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            overwrite_output_dir=True,
            num_train_epochs=3,
            per_device_train_batch_size=1 if self.device.type == "cpu" else 2,
            gradient_accumulation_steps=16,
            gradient_checkpointing=True if self.device.type == "cuda" else False,
            learning_rate=2e-4,
            weight_decay=0.01,
            warmup_steps=100,
            logging_steps=10,
            save_strategy="steps",
            save_steps=500,
            fp16=self.device.type == "cuda",
            dataloader_drop_last=True,
            optim="adamw_torch",
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False
        )
        
        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )
        
        print("Starting training...")
        trainer.train()
        
        # Save model
        trainer.save_model()
        self.tokenizer.save_pretrained(output_dir)
        
        print(f"Training complete! Model saved to {output_dir}")
    
    @torch.no_grad()
    def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Generate response with proper handling for different model types"""
        
        # Format prompt based on model
        if "mistral" in self.base_model.lower():
            formatted_prompt = f"[INST] {prompt} [/INST]"
        elif "phi" in self.base_model.lower():
            formatted_prompt = f"Instruct: {prompt}\nOutput:"
        elif "llama" in self.base_model.lower():
            formatted_prompt = f"<s>[INST] {prompt} [/INST]"
        elif "openchat" in self.base_model.lower():
            formatted_prompt = f"GPT4 Correct User: {prompt}<|end_of_turn|>GPT4 Correct Assistant:"
        elif "zephyr" in self.base_model.lower():
            formatted_prompt = f"<|user|>\n{prompt}</s>\n<|assistant|>\n"
        elif "tinyllama" in self.base_model.lower():
            formatted_prompt = f"<|system|>\nYou are a helpful assistant.</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"
        else:
            formatted_prompt = prompt
        
        try:
            # Tokenize
            inputs = self.tokenizer(
                formatted_prompt, 
                return_tensors="pt", 
                truncation=True, 
                max_length=2048
            ).to(self.device)
            
            # Setup generation config
            gen_config = GenerationConfig(
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
            
            # Generate
            if self.model_type == "encoder-decoder":
                # For T5-style models
                outputs = self.model.generate(
                    inputs['input_ids'],
                    generation_config=gen_config,
                    attention_mask=inputs.get('attention_mask')
                )
                generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            else:
                # For GPT-style models
                outputs = self.model.generate(
                    **inputs,
                    generation_config=gen_config
                )
                # Only decode new tokens
                generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
                generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            # Clean up response
            response = generated_text.strip()
            
            # Only check for gibberish
            if self.is_gibberish(response):
                return "Error: Generated gibberish text."
            
            # Handle empty or very short responses
            if not response or len(response.split()) < 3:
                return "Model is warming up. Try a different prompt or increase temperature."
            
            return response
            
        except Exception as e:
            return f"Error generating response: {str(e)[:200]}"

def main():
    """Coding model with anti-gibberish safeguards only"""
    
    print("🚀 Initializing Coding Model...")
    print("🧠 Anti-gibberish filtering only")
    print("⚡ Using modern instruct models for best performance\n")
    
    # Check environment
    print("📋 Environment check:")
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"✅ CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name()}")
        print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    print(f"{'✅' if BITSANDBYTES_AVAILABLE else '❌'} BitsAndBytes: {'Available' if BITSANDBYTES_AVAILABLE else 'Not available'}")
    print(f"{'✅' if PEFT_AVAILABLE else '❌'} PEFT: {'Available' if PEFT_AVAILABLE else 'Not available'}")
    print()
    
    # Initialize model
    try:
        # You can specify a model or let it auto-select
        model = MinimalCodingModel()  # Auto-select based on GPU
        # model = MinimalCodingModel(base_model="mistralai/Mistral-7B-Instruct-v0.2")
        
        print(f"\n✅ Successfully loaded: {model.base_model}")
        print(f"📊 Model type: {model.model_type}")
        print(f"🖥️  Device: {model.device}")
        
        # Quick sanity check
        print("\n🧪 Running capability check...")
        test_response = model.generate_response(
            "Write a simple Python function to reverse a string", 
            max_tokens=100
        )
        
        if len(test_response.strip()) > 10:
            print("✅ Model responding correctly!")
            print(f"Sample: {test_response[:100]}...")
        else:
            print("⚠️  Model may need adjustment")
            
    except Exception as e:
        print(f"❌ Failed to initialize model: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Install required packages:")
        print("   pip install torch transformers accelerate")
        print("   pip install bitsandbytes  # For quantization")
        print("   pip install peft  # For LoRA training")
        print("2. Try a smaller model if you have limited VRAM")
        print("3. Check your CUDA installation if using GPU")
        return
    
    # Test with normal coding prompts
    test_prompts = [
        "Write a Python function to reverse a string",
        "Create a script to read a CSV file and calculate averages",
        "Generate code for a simple calculator class",
        "Write a function to validate email addresses",
        "Create a basic web scraper with requests",
        "Implement a simple binary search algorithm",
        "Write code to create a REST API endpoint",
        "Create a class for managing a todo list",
        "Generate a function to sort a list of dictionaries",
        "Write code to connect to a database and query data",
    ]
    
    print(f"\n=== TESTING CODING CAPABILITIES ===")
    print("🧠 Testing model's coding abilities\n")
    
    # Test a few coding prompts
    for i in range(min(3, len(test_prompts))):
        print(f"\n### Coding Test {i+1}:")
        print(f"Prompt: {test_prompts[i]}")
        print("Response: ", end="", flush=True)
        try:
            response = model.generate_response(test_prompts[i], max_tokens=150)
            # Show response
            if len(response) > 200:
                print(response[:200] + "...")
            else:
                print(response)
        except Exception as e:
            print(f"Error: {e}")
    
    # Interactive mode
    print("\n\n=== INTERACTIVE CODING MODE ===")
    print("🧠 Coding assistant with gibberish filtering only")
    print("Commands: 'quit' to exit, 'train' for training, 'examples' for prompts")
    print("         'temp <value>' to set temperature (0.1-2.0)")
    
    current_temp = 0.7
    
    while True:
        try:
            user_input = input(f"\n💻 User: ")
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            elif user_input.lower() == 'train':
                print("\n🎯 TRAINING INSTRUCTIONS:")
                print("1. Ensure 'peft' is installed: pip install peft")
                print("2. Uncomment the training section at the bottom")
                print("3. Add repositories with quality code:")
                print("   - Popular open source projects")
                print("   - High-quality coding repositories")
                print("   - Educational programming resources")
                print("4. Run model.train_on_repos(repo_urls)")
                print("5. Training will improve coding capabilities")
                continue
                
            elif user_input.lower() == 'examples':
                print("\n💡 EXAMPLE PROMPTS:")
                for i, prompt in enumerate(test_prompts, 1):
                    print(f"{i}. {prompt}")
                continue
                
            elif user_input.lower().startswith('temp '):
                try:
                    new_temp = float(user_input.split()[1])
                    if 0.1 <= new_temp <= 2.0:
                        current_temp = new_temp
                        print(f"✅ Temperature set to {current_temp}")
                    else:
                        print("❌ Temperature must be between 0.1 and 2.0")
                except:
                    print("❌ Invalid temperature value")
                continue
            
            # Generate response
            print("🤖 Assistant: ", end="", flush=True)
            response = model.generate_response(user_input, temperature=current_temp)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    # Training section
    print("\n" + "="*60)
    print("🎯 TRAINING FOR ENHANCED CODING CAPABILITIES:")
    print("📁 Train on quality coding repositories for best results")
    print("⏱️  Training improves code generation quality")
    print("="*60)
    
    # UNCOMMENT TO TRAIN:
    """
    repo_urls = [
        "https://github.com/microsoft/vscode",
        "https://github.com/tensorflow/tensorflow",
        "https://github.com/pytorch/pytorch",
        "https://github.com/django/django",
        "https://github.com/pallets/flask",
        # Add more quality coding repositories here
    ]
    
    print("🚀 Starting coding model training...")
    model.train_on_repos(repo_urls, output_dir="./coding_model")
    print("✅ Training complete! Coding capabilities enhanced")
    """

if __name__ == "__main__":
    main()