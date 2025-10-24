#!/usr/bin/env python3
"""
Hybrid Math+Code Ensemble Model
Combines Mathstral-7B (math/science) + Mamba-Codestral-7B (code)
For the ultimate coding assistant with mathematical reasoning
"""

import os
import re
import time
import torch
import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from transformers import AutoTokenizer, AutoModelForCausalLM
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskType(Enum):
    """Types of tasks the ensemble can handle"""
    CODE = "code"
    MATH = "math"
    HYBRID = "hybrid"  # Tasks requiring both math and code
    GENERAL = "general"

@dataclass
class EnsembleConfig:
    """Configuration for the hybrid ensemble"""
    # Model paths
    mathstral_model = "mistralai/Mathstral-7B-v0.1"
    mamba_codestral_model = "mistralai/Mamba-Codestral-7B-v0.1"

    # Generation parameters
    max_length: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1

    # Ensemble strategy
    use_both_for_hybrid: bool = True  # Use both models for complex tasks
    confidence_threshold: float = 0.7  # Threshold for routing decision

    # Device management
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    load_in_4bit: bool = True  # Memory optimization

    # Database
    db_url: str = os.getenv('DATABASE_URL',
        'postgres://coding_user:coding_pass@postgres:5432/coding_db')

class QueryRouter:
    """Intelligent router to determine task type"""

    # Keywords for task classification
    MATH_KEYWORDS = {
        'calculate', 'solve', 'equation', 'formula', 'theorem', 'proof',
        'integral', 'derivative', 'matrix', 'vector', 'probability',
        'statistics', 'algebra', 'geometry', 'calculus', 'optimization',
        'mathematical', 'numeric', 'computation'
    }

    CODE_KEYWORDS = {
        'function', 'class', 'implement', 'code', 'program', 'script',
        'algorithm', 'api', 'database', 'debug', 'refactor', 'optimize',
        'parse', 'serialize', 'async', 'thread', 'framework', 'library',
        'import', 'def', 'return', 'variable'
    }

    HYBRID_KEYWORDS = {
        'algorithm complexity', 'computational complexity', 'big o',
        'numerical algorithm', 'scientific computing', 'data science',
        'machine learning', 'neural network', 'optimization algorithm',
        'mathematical programming', 'linear programming'
    }

    @staticmethod
    def analyze_query(query: str) -> Tuple[TaskType, float]:
        """
        Analyze query to determine task type and confidence

        Returns:
            (TaskType, confidence_score)
        """
        query_lower = query.lower()

        # Check for hybrid indicators first
        hybrid_score = sum(1 for kw in QueryRouter.HYBRID_KEYWORDS
                          if kw in query_lower)
        if hybrid_score > 0:
            return TaskType.HYBRID, min(0.9, 0.6 + hybrid_score * 0.1)

        # Check for code patterns
        code_indicators = [
            r'\bdef\b', r'\bclass\b', r'\bimport\b', r'\breturn\b',
            r'```', r'function\s*\(', r'=>', r'\{.*\}', r'<.*>'
        ]
        has_code_pattern = any(re.search(pattern, query)
                              for pattern in code_indicators)

        # Count keyword matches
        math_count = sum(1 for kw in QueryRouter.MATH_KEYWORDS
                        if kw in query_lower)
        code_count = sum(1 for kw in QueryRouter.CODE_KEYWORDS
                        if kw in query_lower)

        # Add bonus for code patterns
        if has_code_pattern:
            code_count += 2

        # Determine task type
        if math_count == 0 and code_count == 0:
            return TaskType.GENERAL, 0.5

        if math_count > code_count * 1.5:  # Heavily math-focused
            confidence = min(0.95, 0.6 + math_count * 0.1)
            return TaskType.MATH, confidence
        elif code_count > math_count * 1.5:  # Heavily code-focused
            confidence = min(0.95, 0.6 + code_count * 0.1)
            return TaskType.CODE, confidence
        else:  # Mixed signals
            confidence = 0.6
            return TaskType.HYBRID, confidence

class HybridMathCodeEnsemble:
    """Ensemble model combining Mathstral and Mamba-Codestral"""

    def __init__(self, config: EnsembleConfig):
        self.config = config
        self.device = torch.device(config.device)
        self.router = QueryRouter()

        # Model and tokenizer storage
        self.mathstral_model = None
        self.mathstral_tokenizer = None
        self.codestral_model = None
        self.codestral_tokenizer = None

        # Statistics
        self.stats = {
            'total_queries': 0,
            'math_queries': 0,
            'code_queries': 0,
            'hybrid_queries': 0,
            'general_queries': 0
        }

        logger.info("🚀 Hybrid Math+Code Ensemble initialized")
        logger.info(f"💻 Device: {self.device}")

    def load_models(self):
        """Load both models with memory optimizations"""
        logger.info("📥 Loading Mathstral-7B (Math/Science specialist)...")
        self.load_mathstral()

        logger.info("📥 Loading Mamba-Codestral-7B (Code specialist)...")
        self.load_codestral()

        logger.info("✅ Both models loaded successfully")

    def load_mathstral(self):
        """Load Mathstral model"""
        try:
            self.mathstral_tokenizer = AutoTokenizer.from_pretrained(
                self.config.mathstral_model,
                trust_remote_code=True
            )
            if self.mathstral_tokenizer.pad_token is None:
                self.mathstral_tokenizer.pad_token = self.mathstral_tokenizer.eos_token

            # Load with quantization for memory efficiency
            from transformers import BitsAndBytesConfig

            if self.config.load_in_4bit and self.config.device == "cuda":
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )

                self.mathstral_model = AutoModelForCausalLM.from_pretrained(
                    self.config.mathstral_model,
                    quantization_config=bnb_config,
                    device_map="auto",
                    trust_remote_code=True,
                    torch_dtype=torch.bfloat16,
                    low_cpu_mem_usage=True
                )
            else:
                self.mathstral_model = AutoModelForCausalLM.from_pretrained(
                    self.config.mathstral_model,
                    device_map="auto",
                    trust_remote_code=True,
                    torch_dtype=torch.float32 if self.config.device == "cpu" else torch.bfloat16
                )

            self.mathstral_model.eval()
            logger.info("✅ Mathstral-7B loaded")

        except Exception as e:
            logger.error(f"❌ Failed to load Mathstral: {e}")
            raise

    def load_codestral(self):
        """Load Mamba-Codestral model"""
        try:
            # Note: Mamba models require special handling
            # Install: pip install mamba-ssm causal-conv1d

            self.codestral_tokenizer = AutoTokenizer.from_pretrained(
                self.config.mamba_codestral_model,
                trust_remote_code=True
            )
            if self.codestral_tokenizer.pad_token is None:
                self.codestral_tokenizer.pad_token = self.codestral_tokenizer.eos_token

            # Mamba models might need special configuration
            self.codestral_model = AutoModelForCausalLM.from_pretrained(
                self.config.mamba_codestral_model,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self.config.device == "cuda" else torch.float32,
                low_cpu_mem_usage=True
            )

            self.codestral_model.eval()
            logger.info("✅ Mamba-Codestral-7B loaded")

        except Exception as e:
            logger.error(f"❌ Failed to load Mamba-Codestral: {e}")
            logger.warning("💡 Make sure you have: pip install mamba-ssm causal-conv1d")
            raise

    def generate_with_mathstral(self, prompt: str) -> str:
        """Generate response using Mathstral"""
        inputs = self.mathstral_tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_length
        ).to(self.device)

        with torch.no_grad():
            outputs = self.mathstral_model.generate(
                **inputs,
                max_new_tokens=self.config.max_length,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                repetition_penalty=self.config.repetition_penalty,
                do_sample=True,
                pad_token_id=self.mathstral_tokenizer.pad_token_id,
                eos_token_id=self.mathstral_tokenizer.eos_token_id
            )

        response = self.mathstral_tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Remove the prompt from response
        if response.startswith(prompt):
            response = response[len(prompt):].strip()

        return response

    def generate_with_codestral(self, prompt: str) -> str:
        """Generate response using Mamba-Codestral"""
        inputs = self.codestral_tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_length
        ).to(self.device)

        with torch.no_grad():
            outputs = self.codestral_model.generate(
                **inputs,
                max_new_tokens=self.config.max_length,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                repetition_penalty=self.config.repetition_penalty,
                do_sample=True,
                pad_token_id=self.codestral_tokenizer.pad_token_id,
                eos_token_id=self.codestral_tokenizer.eos_token_id
            )

        response = self.codestral_tokenizer.decode(outputs[0], skip_special_tokens=True)
        if response.startswith(prompt):
            response = response[len(prompt):].strip()

        return response

    def generate_hybrid(self, prompt: str, task_type: TaskType) -> str:
        """
        Generate response using both models and combine intelligently
        Used for hybrid tasks requiring both math and code expertise
        """
        logger.info("🔄 Using hybrid approach with both models")

        # Generate with both models
        math_response = self.generate_with_mathstral(prompt)
        code_response = self.generate_with_codestral(prompt)

        # Combine responses intelligently
        if task_type == TaskType.HYBRID:
            # For hybrid tasks, combine both perspectives
            combined = f"""## Mathematical Analysis (Mathstral):
{math_response}

## Implementation (Mamba-Codestral):
{code_response}

## Combined Solution:
Based on the mathematical analysis above, here's the optimized implementation combining both perspectives."""
            return combined
        else:
            # Choose the better response based on task type
            if task_type == TaskType.MATH:
                return math_response
            else:
                return code_response

    def generate(self, prompt: str, force_task_type: Optional[TaskType] = None) -> Dict:
        """
        Generate response using the appropriate model(s)

        Args:
            prompt: Input prompt
            force_task_type: Force specific task type (optional)

        Returns:
            Dict with response, task_type, confidence, and metadata
        """
        start_time = time.time()

        # Route query
        if force_task_type:
            task_type = force_task_type
            confidence = 1.0
        else:
            task_type, confidence = self.router.analyze_query(prompt)

        logger.info(f"📊 Task type: {task_type.value}, Confidence: {confidence:.2f}")

        # Update statistics
        self.stats['total_queries'] += 1
        self.stats[f'{task_type.value}_queries'] += 1

        # Generate response based on task type
        try:
            if task_type == TaskType.MATH:
                response = self.generate_with_mathstral(prompt)
                model_used = "Mathstral-7B"

            elif task_type == TaskType.CODE:
                response = self.generate_with_codestral(prompt)
                model_used = "Mamba-Codestral-7B"

            elif task_type == TaskType.HYBRID:
                if self.config.use_both_for_hybrid:
                    response = self.generate_hybrid(prompt, task_type)
                    model_used = "Mathstral-7B + Mamba-Codestral-7B"
                else:
                    # Fallback to code model for hybrid
                    response = self.generate_with_codestral(prompt)
                    model_used = "Mamba-Codestral-7B (Hybrid fallback)"

            else:  # GENERAL
                # Use code model as default for general tasks
                response = self.generate_with_codestral(prompt)
                model_used = "Mamba-Codestral-7B (Default)"

            generation_time = time.time() - start_time

            return {
                'response': response,
                'task_type': task_type.value,
                'confidence': confidence,
                'model_used': model_used,
                'generation_time': generation_time,
                'success': True
            }

        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
            return {
                'response': f"Error: {str(e)}",
                'task_type': task_type.value,
                'confidence': 0.0,
                'model_used': "None",
                'generation_time': time.time() - start_time,
                'success': False,
                'error': str(e)
            }

    def get_stats(self) -> Dict:
        """Get ensemble statistics"""
        return {
            **self.stats,
            'models_loaded': {
                'mathstral': self.mathstral_model is not None,
                'codestral': self.codestral_model is not None
            }
        }

    def save_to_database(self, query: str, result: Dict):
        """Save query and result to database for analytics"""
        try:
            conn = psycopg2.connect(self.config.db_url)
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ensemble_queries (
                        id SERIAL PRIMARY KEY,
                        query TEXT,
                        response TEXT,
                        task_type TEXT,
                        confidence FLOAT,
                        model_used TEXT,
                        generation_time FLOAT,
                        success BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO ensemble_queries
                    (query, response, task_type, confidence, model_used, generation_time, success)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    query,
                    result['response'],
                    result['task_type'],
                    result['confidence'],
                    result['model_used'],
                    result['generation_time'],
                    result['success']
                ))

                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Failed to save to database: {e}")

def main():
    """Test the hybrid ensemble"""
    logger.info("🚀 Testing Hybrid Math+Code Ensemble")
    logger.info("=" * 60)

    # Create ensemble
    config = EnsembleConfig()
    ensemble = HybridMathCodeEnsemble(config)
    ensemble.load_models()

    # Test queries
    test_queries = [
        {
            "prompt": "[INST] Implement a Python function to calculate the derivative of a polynomial [/INST]",
            "expected": TaskType.HYBRID
        },
        {
            "prompt": "[INST] Solve the quadratic equation: x^2 + 5x + 6 = 0 [/INST]",
            "expected": TaskType.MATH
        },
        {
            "prompt": "[INST] Create a REST API endpoint for user authentication [/INST]",
            "expected": TaskType.CODE
        },
        {
            "prompt": "[INST] Explain Big O notation and implement a sorting algorithm with O(n log n) complexity [/INST]",
            "expected": TaskType.HYBRID
        }
    ]

    logger.info("\n🧪 Running test queries...")
    for i, test in enumerate(test_queries, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Test {i}: {test['prompt'][:60]}...")

        result = ensemble.generate(test['prompt'])

        logger.info(f"✅ Task Type: {result['task_type']} (Expected: {test['expected'].value})")
        logger.info(f"📊 Confidence: {result['confidence']:.2f}")
        logger.info(f"🤖 Model: {result['model_used']}")
        logger.info(f"⏱️ Time: {result['generation_time']:.2f}s")
        logger.info(f"📝 Response: {result['response'][:200]}...")

        # Save to database
        ensemble.save_to_database(test['prompt'], result)

    # Print statistics
    logger.info("\n" + "="*60)
    logger.info("📊 Ensemble Statistics:")
    stats = ensemble.get_stats()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

if __name__ == "__main__":
    main()
