#!/usr/bin/env python3
"""
Production-Grade Continuous Trainer for RTX 5090 (32GB VRAM)
Model: Qwen2.5-Coder-14B-Instruct

Features:
- Complete type safety with comprehensive type hints
- Circuit breaker pattern for external services
- Advanced error handling and recovery
- Memory management and GPU cleanup
- Health checks and detailed monitoring
- Configuration validation
- Graceful degradation
- Structured logging with context
"""

import os
import sys
import time
import json
import logging
import signal
import threading
import gc
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import re

import psycopg2
from psycopg2 import pool, OperationalError, InterfaceError
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import torch

# Import custom modules
from secrets_manager import SecretsManager
from retry_decorator import retry_with_backoff
from metrics_tracker import MetricsTracker
from wandb_logger import ComprehensiveWandbLogger

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    EarlyStoppingCallback,
    TrainerCallback,
    PreTrainedTokenizer,
    PreTrainedModel,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    PeftModel,
)
from datasets import Dataset
from trl import SFTTrainer
import wandb
from flask import Flask, jsonify, Response
import multiprocessing as mp
from prometheus_client import Counter, Histogram, Gauge, start_http_server, generate_latest, CONTENT_TYPE_LATEST

# ============================================================================
# STRUCTURED LOGGING SETUP
# ============================================================================

class ContextFilter(logging.Filter):
    """Add context to log records"""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'component'):
            record.component = 'unknown'
        if not hasattr(record, 'operation'):
            record.operation = 'unknown'
        return True

# Ensure log directory exists
os.makedirs('/app/logs', exist_ok=True)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(component)s] - %(name)s - %(levelname)s - [%(operation)s] - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/continuous_training_qwen.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Apply context filter globally to ALL loggers (including Flask, werkzeug, etc.)
for handler in logging.root.handlers:
    handler.addFilter(ContextFilter())

logger = logging.getLogger(__name__)
logger.addFilter(ContextFilter())

def log_with_context(level: str, message: str, component: str = 'trainer', operation: str = 'general', **kwargs):
    """Log with structured context"""
    extra = {'component': component, 'operation': operation}
    extra.update(kwargs)
    getattr(logger, level.lower())(message, extra=extra)

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

# Define Prometheus metrics
training_runs_total = Counter('trainer_training_runs_total', 'Total number of training runs completed')
training_duration_seconds = Histogram('trainer_training_duration_seconds', 'Duration of training runs in seconds')
training_loss = Gauge('trainer_current_loss', 'Current training loss')
eval_loss = Gauge('trainer_current_eval_loss', 'Current evaluation loss')
gpu_memory_bytes = Gauge('trainer_gpu_memory_bytes', 'GPU memory usage in bytes')
files_trained_total = Counter('trainer_files_trained_total', 'Total files trained on')
samples_trained_total = Counter('trainer_samples_trained_total', 'Total samples trained')
dataset_size = Gauge('trainer_dataset_size', 'Current dataset size', ['split'])

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ServiceState(Enum):
    """Service circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5
    timeout: int = 60  # seconds
    expected_exception: type = Exception

@dataclass
class HealthStatus:
    """System health status"""
    overall_status: str
    database_status: str
    gpu_status: str
    model_loaded: bool
    last_training_time: Optional[str]
    uptime_seconds: float
    memory_usage_gb: float
    gpu_memory_used_gb: float
    gpu_memory_total_gb: float
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)

# ============================================================================
# CONFIGURATION WITH VALIDATION
# ============================================================================

class TrainingConfig:
    """Centralized, validated configuration for training"""

    # Model configuration
    MODEL_NAME: str = "Qwen/Qwen2.5-Coder-14B-Instruct"
    MODEL_REVISION: str = "main"

    # Training hyperparameters - optimized for RTX 5090
    BATCH_SIZE: int = 4
    GRADIENT_ACCUMULATION_STEPS: int = 4
    LEARNING_RATE: float = 2e-5
    MAX_LENGTH: int = 4096
    NUM_TRAIN_EPOCHS: int = 1
    WARMUP_RATIO: float = 0.03
    WEIGHT_DECAY: float = 0.01
    MAX_GRAD_NORM: float = 1.0

    # LoRA configuration
    LORA_R: int = 256
    LORA_ALPHA: int = 512
    LORA_DROPOUT: float = 0.05
    LORA_TARGET_MODULES: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])

    # Quantization
    LOAD_IN_4BIT: bool = True
    BNB_4BIT_COMPUTE_DTYPE = torch.bfloat16
    BNB_4BIT_QUANT_TYPE: str = "nf4"
    BNB_4BIT_USE_DOUBLE_QUANT: bool = True

    # Data configuration
    MIN_NEW_FILES: int = int(os.getenv("MIN_NEW_FILES", "1000"))
    MAX_DATASET_SIZE: int = int(os.getenv("MAX_DATASET_SIZE", "100000"))
    QUALITY_THRESHOLD: float = 70.0
    MIN_CONTENT_LENGTH: int = 50
    MAX_CONTENT_LENGTH: int = 8000
    TRAIN_TEST_SPLIT: float = 0.95

    # Database configuration
    _secrets_manager: Optional[SecretsManager] = None
    DB_POOL_MIN_CONN: int = 1
    DB_POOL_MAX_CONN: int = 5
    DB_CONNECTION_TIMEOUT: int = 10
    DB_MAX_RETRIES: int = 10

    # Continuous training configuration
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "300"))
    STATE_FILE: str = "/app/checkpoints/trainer_state_qwen.json"

    # Output directories
    OUTPUT_DIR: str = "/app/models/qwen-codelupe"
    CHECKPOINT_DIR: str = "/app/checkpoints/qwen-codelupe"
    CACHE_DIR: str = "/app/cache"

    # Monitoring
    METRICS_PORT: int = 8090
    ENABLE_WANDB: bool = os.getenv("WANDB_API_KEY") is not None
    WANDB_PROJECT: str = "codelupe-qwen-training"

    # Performance optimizations
    DATALOADER_NUM_WORKERS: int = min(8, mp.cpu_count())
    USE_FLASH_ATTENTION: bool = True
    GRADIENT_CHECKPOINTING: bool = True
    OPTIM: str = "adamw_bnb_8bit"

    # Early stopping
    EARLY_STOPPING_PATIENCE: int = 3
    EARLY_STOPPING_THRESHOLD: float = 0.01

    # Memory management
    CUDA_EMPTY_CACHE_INTERVAL: int = 5  # Clear cache every N training runs
    MAX_GPU_MEMORY_THRESHOLD: float = 0.95  # Alert if >95% used

    # Error recovery
    MAX_CONSECUTIVE_ERRORS: int = 3
    ERROR_BACKOFF_BASE: int = 60  # seconds

    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of warnings"""
        warnings = []

        # Validate paths exist
        for path_attr in ['OUTPUT_DIR', 'CHECKPOINT_DIR', 'CACHE_DIR']:
            path = getattr(cls, path_attr)
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                    log_with_context('info', f"Created directory: {path}", operation='config_validation')
                except Exception as e:
                    warnings.append(f"Cannot create directory {path}: {e}")

        # Validate numeric ranges
        if not 0 < cls.TRAIN_TEST_SPLIT < 1:
            warnings.append(f"Invalid TRAIN_TEST_SPLIT: {cls.TRAIN_TEST_SPLIT}, should be between 0 and 1")

        if cls.BATCH_SIZE < 1:
            warnings.append(f"Invalid BATCH_SIZE: {cls.BATCH_SIZE}, should be >= 1")

        if cls.LEARNING_RATE <= 0:
            warnings.append(f"Invalid LEARNING_RATE: {cls.LEARNING_RATE}, should be > 0")

        # Validate CUDA availability if flash attention enabled
        if cls.USE_FLASH_ATTENTION and not torch.cuda.is_available():
            warnings.append("Flash attention enabled but CUDA not available")

        # Check GPU memory
        if torch.cuda.is_available():
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            if total_memory < 24:
                warnings.append(f"GPU memory ({total_memory:.1f}GB) may be insufficient for 14B model")

        return warnings

    @classmethod
    def get_db_config(cls) -> Dict[str, Any]:
        """Get database configuration from secrets manager with fallback"""
        try:
            if cls._secrets_manager is None:
                cls._secrets_manager = SecretsManager()

            db_config = cls._secrets_manager.get_database_config('codelupe/database')

            return {
                'host': db_config.get('host', os.getenv("POSTGRES_HOST", "postgres")),
                'port': int(db_config.get('port', os.getenv("POSTGRES_PORT", "5432"))),
                'database': db_config.get('database', os.getenv("POSTGRES_DB", "coding_db")),
                'user': db_config.get('user', os.getenv("POSTGRES_USER", "coding_user")),
                'password': db_config.get('password', os.getenv("POSTGRES_PASSWORD", "coding_pass")),
            }
        except Exception as e:
            log_with_context('warning', f"Failed to get DB config from secrets manager: {e}", operation='config')
            # Fallback to environment variables
            return {
                'host': os.getenv("POSTGRES_HOST", "postgres"),
                'port': int(os.getenv("POSTGRES_PORT", "5432")),
                'database': os.getenv("POSTGRES_DB", "coding_db"),
                'user': os.getenv("POSTGRES_USER", "coding_user"),
                'password': os.getenv("POSTGRES_PASSWORD", "coding_pass"),
            }

# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for external service calls"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = ServiceState.CLOSED
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == ServiceState.OPEN:
                if time.time() - self.last_failure_time > self.config.timeout:
                    log_with_context('info', "Circuit breaker: attempting recovery",
                                   component='circuit_breaker', operation='state_change')
                    self.state = ServiceState.HALF_OPEN
                else:
                    raise Exception(f"Circuit breaker OPEN: service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            self.state = ServiceState.CLOSED

    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.config.failure_threshold:
                self.state = ServiceState.OPEN
                log_with_context('error',
                               f"Circuit breaker OPEN: {self.failure_count} failures",
                               component='circuit_breaker', operation='state_change')

# ============================================================================
# DATABASE CONNECTION POOL WITH CIRCUIT BREAKER
# ============================================================================

class DatabasePool:
    """Thread-safe database connection pool with circuit breaker and health checks"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.pool: Optional[pool.ThreadedConnectionPool] = None
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60,
                expected_exception=(OperationalError, InterfaceError)
            )
        )
        self._connect_with_retry()

    def _connect_with_retry(self, max_retries: Optional[int] = None):
        """Connect to database with exponential backoff"""
        max_retries = max_retries or self.config.DB_MAX_RETRIES
        db_config = self.config.get_db_config()

        for attempt in range(max_retries):
            try:
                self.pool = psycopg2.pool.ThreadedConnectionPool(
                    self.config.DB_POOL_MIN_CONN,
                    self.config.DB_POOL_MAX_CONN,
                    host=db_config['host'],
                    port=db_config['port'],
                    database=db_config['database'],
                    user=db_config['user'],
                    password=db_config['password'],
                    connect_timeout=self.config.DB_CONNECTION_TIMEOUT,
                )
                log_with_context('info',
                               f"Connected to PostgreSQL at {db_config['host']}:{db_config['port']}",
                               component='database', operation='connect')
                return
            except Exception as e:
                wait_time = min(2 ** attempt, 60)
                log_with_context('warning',
                               f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}",
                               component='database', operation='connect')
                if attempt < max_retries - 1:
                    log_with_context('info', f"Retrying in {wait_time} seconds...",
                                   component='database', operation='retry')
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to connect to database after {max_retries} attempts"
                    ) from e

    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return and error handling"""
        conn = None
        try:
            conn = self.circuit_breaker.call(self._get_conn_from_pool)
            yield conn
        except Exception as e:
            log_with_context('error', f"Database connection error: {e}",
                           component='database', operation='get_connection')
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                self.return_connection(conn)

    def _get_conn_from_pool(self):
        """Internal method to get connection from pool"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.pool.getconn()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise

    def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            if conn:
                self.pool.putconn(conn)
        except Exception as e:
            log_with_context('error', f"Failed to return connection to pool: {e}",
                           component='database', operation='return_connection')

    def health_check(self) -> bool:
        """Check database health"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
        except Exception as e:
            log_with_context('error', f"Database health check failed: {e}",
                           component='database', operation='health_check')
            return False

    def close_all(self):
        """Close all connections in the pool"""
        if self.pool:
            try:
                self.pool.closeall()
                log_with_context('info', "Database connection pool closed",
                               component='database', operation='shutdown')
            except Exception as e:
                log_with_context('error', f"Error closing connection pool: {e}",
                               component='database', operation='shutdown')

# ============================================================================
# DATA PREPARATION
# ============================================================================

class CodeDataPreparator:
    """Prepare high-quality code samples with proper instruction format"""

    def __init__(self, db_pool: DatabasePool, tokenizer: PreTrainedTokenizer):
        self.db_pool = db_pool
        self.tokenizer = tokenizer
        self.instruction_templates = [
            "Complete the following {language} code:",
            "Implement the {language} function:",
            "Write {language} code to solve this:",
            "Generate {language} code for:",
            "Create a {language} implementation:",
            "Develop {language} code that:",
        ]

    @retry_with_backoff(max_retries=3, exceptions=(OperationalError,))
    def count_new_files(self, last_trained_id: int) -> int:
        """Count files added since last training"""
        try:
            with self.db_pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM processed_files
                    WHERE id > %s
                      AND quality_score >= %s
                      AND LENGTH(content) BETWEEN %s AND %s
                """, (
                    last_trained_id,
                    TrainingConfig.QUALITY_THRESHOLD,
                    TrainingConfig.MIN_CONTENT_LENGTH,
                    TrainingConfig.MAX_CONTENT_LENGTH
                ))
                count = cursor.fetchone()[0]
                cursor.close()
                return count
        except Exception as e:
            log_with_context('error', f"Error counting new files: {e}",
                           component='data_prep', operation='count_files')
            return 0

    @retry_with_backoff(max_retries=3, exceptions=(OperationalError,))
    def fetch_training_data(self, last_trained_id: int, limit: int) -> List[Dict[str, Any]]:
        """Fetch new high-quality code samples"""
        try:
            with self.db_pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, content, language, quality_score, file_path
                    FROM processed_files
                    WHERE id > %s
                      AND quality_score >= %s
                      AND LENGTH(content) BETWEEN %s AND %s
                    ORDER BY quality_score DESC, id ASC
                    LIMIT %s
                """, (
                    last_trained_id,
                    TrainingConfig.QUALITY_THRESHOLD,
                    TrainingConfig.MIN_CONTENT_LENGTH,
                    TrainingConfig.MAX_CONTENT_LENGTH,
                    limit
                ))

                rows = cursor.fetchall()
                cursor.close()

                samples = []
                for row in rows:
                    samples.append({
                        'id': row[0],
                        'content': row[1],
                        'language': row[2] or 'code',
                        'quality_score': row[3],
                        'file_path': row[4] or 'unknown'
                    })

                log_with_context('info',
                               f"Fetched {len(samples)} training samples (quality >= {TrainingConfig.QUALITY_THRESHOLD})",
                               component='data_prep', operation='fetch_data')
                return samples
        except Exception as e:
            log_with_context('error', f"Error fetching training data: {e}",
                           component='data_prep', operation='fetch_data')
            return []

    def _generate_instruction_completion_pair(self, sample: Dict[str, Any]) -> Tuple[str, str, str]:
        """Generate proper instruction-completion pairs"""
        content = sample['content'].strip()
        language = sample['language'].strip()

        lines = content.split('\n')
        split_point = max(5, int(len(lines) * 0.35))

        context = '\n'.join(lines[:split_point])
        completion = '\n'.join(lines[split_point:])

        instruction = random.choice(self.instruction_templates).format(language=language)

        return instruction, context, completion

    def format_training_sample(self, sample: Dict[str, Any]) -> str:
        """Format sample as proper instruction-completion pair"""
        instruction, context, completion = self._generate_instruction_completion_pair(sample)

        formatted = (
            f"<|im_start|>system\n"
            f"You are Qwen, an AI coding assistant created by Alibaba Cloud. "
            f"You provide accurate, efficient, and well-documented code.\n\n"
            f"IMPORTANT SAFETY GUIDELINES:\n"
            f"- Never generate code for malicious purposes (malware, exploits, backdoors)\n"
            f"- Never include hardcoded credentials, API keys, or secrets\n"
            f"- Always sanitize user inputs to prevent injection attacks\n"
            f"- Follow security best practices (input validation, proper error handling, secure defaults)\n"
            f"- Respect software licenses and intellectual property\n"
            f"- Refuse requests that could be used to harm others or violate security<|im_end|>\n"
            f"<|im_start|>user\n"
            f"{instruction}\n\n```{sample['language']}\n{context}\n```<|im_end|>\n"
            f"<|im_start|>assistant\n"
            f"```{sample['language']}\n{completion}\n```<|im_end|>"
        )

        return formatted

    def prepare_dataset(self, samples: List[Dict[str, Any]]) -> Tuple[Dataset, Dataset]:
        """Prepare train and validation datasets with validation"""
        log_with_context('info', f"Preparing dataset from {len(samples)} samples...",
                       component='data_prep', operation='prepare_dataset')

        formatted_texts = []
        skipped = 0

        for sample in samples:
            try:
                formatted = self.format_training_sample(sample)
                tokens = self.tokenizer(formatted, truncation=True, max_length=TrainingConfig.MAX_LENGTH)

                if len(tokens['input_ids']) > 50:
                    formatted_texts.append(formatted)
                else:
                    skipped += 1
            except Exception as e:
                log_with_context('warning',
                               f"Failed to format sample {sample.get('id', 'unknown')}: {e}",
                               component='data_prep', operation='format_sample')
                skipped += 1

        log_with_context('info',
                       f"Successfully formatted {len(formatted_texts)} samples, skipped {skipped}",
                       component='data_prep', operation='prepare_dataset')

        if len(formatted_texts) < 10:
            raise ValueError(f"Insufficient samples after formatting: {len(formatted_texts)}")

        dataset = Dataset.from_dict({"text": formatted_texts})
        split = dataset.train_test_split(
            test_size=1 - TrainingConfig.TRAIN_TEST_SPLIT,
            seed=42
        )

        train_dataset = split['train']
        eval_dataset = split['test']

        log_with_context('info',
                       f"Dataset split: {len(train_dataset)} train, {len(eval_dataset)} validation",
                       component='data_prep', operation='split_dataset')

        return train_dataset, eval_dataset

# ============================================================================
# MEMORY MANAGEMENT
# ============================================================================

class MemoryManager:
    """Manage GPU and system memory"""

    @staticmethod
    def clear_cuda_cache():
        """Clear CUDA cache and run garbage collection"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        gc.collect()
        log_with_context('debug', "Cleared CUDA cache and ran garbage collection",
                       component='memory', operation='cleanup')

    @staticmethod
    def get_gpu_memory_info() -> Dict[str, float]:
        """Get GPU memory usage information"""
        if not torch.cuda.is_available():
            return {'used_gb': 0, 'total_gb': 0, 'utilization': 0}

        used = torch.cuda.memory_allocated() / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        utilization = used / total if total > 0 else 0

        return {
            'used_gb': used,
            'total_gb': total,
            'utilization': utilization
        }

    @staticmethod
    def check_memory_pressure() -> Tuple[bool, str]:
        """Check if system is under memory pressure"""
        info = MemoryManager.get_gpu_memory_info()

        if info['utilization'] > TrainingConfig.MAX_GPU_MEMORY_THRESHOLD:
            return True, f"GPU memory usage high: {info['utilization']:.1%}"

        return False, "Memory usage normal"

# ============================================================================
# CUSTOM TRAINING CALLBACK
# ============================================================================

class WandbMetricsCallback(TrainerCallback):
    """Custom callback to log comprehensive metrics to W&B during training"""

    def __init__(self, wb_logger: ComprehensiveWandbLogger):
        self.wb_logger = wb_logger
        self.last_system_log = 0
        self.system_log_interval = 10

    def on_log(self, args, state, control, logs=None, **kwargs):
        """Log training metrics on each logging step"""
        if logs:
            self.wb_logger.log_training_metrics(
                train_loss=logs.get('loss'),
                eval_loss=logs.get('eval_loss'),
                learning_rate=logs.get('learning_rate'),
                epoch=logs.get('epoch'),
                step=state.global_step,
                **{k: v for k, v in logs.items() if k not in ['loss', 'eval_loss', 'learning_rate', 'epoch']}
            )

            if state.global_step - self.last_system_log >= self.system_log_interval:
                self.wb_logger.log_system_metrics()
                self.last_system_log = state.global_step

            self.wb_logger.set_step(state.global_step)

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        """Log evaluation metrics"""
        if metrics:
            self.wb_logger.log_training_metrics(
                eval_loss=metrics.get('eval_loss'),
                step=state.global_step
            )

# ============================================================================
# CONTINUOUS TRAINER
# ============================================================================

class ContinuousTrainer:
    """Production-grade continuous training orchestrator"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.start_time = time.time()

        # Validate configuration
        warnings = config.validate()
        if warnings:
            for warning in warnings:
                log_with_context('warning', warning, component='config', operation='validation')

        # Initialize components
        self.db_pool = DatabasePool(config)
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.model: Optional[PreTrainedModel] = None
        self.state = self._load_state()
        self.shutdown_requested = False
        self.consecutive_errors = 0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize metrics
        self.metrics_app = Flask(__name__)
        self._setup_metrics_endpoints()
        self.metrics = defaultdict(list)
        self.metrics_tracker = MetricsTracker(metrics_file="/app/logs/training_metrics.json")

        # W&B logger
        self.wb_logger = ComprehensiveWandbLogger(
            project=self.config.WANDB_PROJECT,
            name=f"qwen_run_{self.state['total_training_runs'] + 1}",
            config=vars(self.config),
            enabled=self.config.ENABLE_WANDB
        )

        log_with_context('info', "ContinuousTrainer initialized",
                       component='trainer', operation='init')

    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown"""
        log_with_context('info', f"Received signal {signum}, initiating graceful shutdown...",
                       component='trainer', operation='shutdown')
        self.shutdown_requested = True

    def _load_state(self) -> Dict[str, Any]:
        """Load trainer state from disk with validation"""
        try:
            if os.path.exists(self.config.STATE_FILE):
                with open(self.config.STATE_FILE, 'r') as f:
                    state = json.load(f)

                # Validate state structure
                required_keys = ['last_trained_id', 'total_training_runs', 'total_samples_trained']
                for key in required_keys:
                    if key not in state:
                        log_with_context('warning', f"Missing key in state: {key}",
                                       component='state', operation='load')
                        state[key] = 0

                log_with_context('info', f"Loaded state: last_trained_id={state.get('last_trained_id', 0)}",
                               component='state', operation='load')
                return state
        except Exception as e:
            log_with_context('warning', f"Could not load state: {e}",
                           component='state', operation='load')

        return {
            'last_trained_id': 0,
            'total_training_runs': 0,
            'total_samples_trained': 0,
            'last_training_time': None,
        }

    def _save_state(self):
        """Save trainer state to disk with atomic write"""
        try:
            os.makedirs(os.path.dirname(self.config.STATE_FILE), exist_ok=True)

            # Atomic write using temp file
            temp_file = f"{self.config.STATE_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)

            os.replace(temp_file, self.config.STATE_FILE)
            log_with_context('debug', "Saved state", component='state', operation='save')
        except Exception as e:
            log_with_context('error', f"Failed to save state: {e}",
                           component='state', operation='save')

    def get_health_status(self) -> HealthStatus:
        """Get comprehensive health status"""
        memory_info = MemoryManager.get_gpu_memory_info()
        uptime = time.time() - self.start_time

        warnings = []

        # Check database health
        db_healthy = self.db_pool.health_check()
        db_status = "healthy" if db_healthy else "unhealthy"

        if not db_healthy:
            warnings.append("Database health check failed")

        # Check GPU
        gpu_status = "healthy" if torch.cuda.is_available() else "no_gpu"
        if memory_info['utilization'] > 0.9:
            warnings.append(f"GPU memory usage high: {memory_info['utilization']:.1%}")

        # Determine overall status
        if not db_healthy or not torch.cuda.is_available():
            overall_status = "degraded"
        elif warnings:
            overall_status = "warning"
        else:
            overall_status = "healthy"

        return HealthStatus(
            overall_status=overall_status,
            database_status=db_status,
            gpu_status=gpu_status,
            model_loaded=self.model is not None,
            last_training_time=self.state.get('last_training_time'),
            uptime_seconds=uptime,
            memory_usage_gb=memory_info['used_gb'],
            gpu_memory_used_gb=memory_info['used_gb'],
            gpu_memory_total_gb=memory_info['total_gb'],
            error_count=self.consecutive_errors,
            warnings=warnings
        )

    def _setup_metrics_endpoints(self):
        """Setup Flask endpoints for metrics and health"""

        @self.metrics_app.route('/health')
        def health() -> Response:
            health_status = self.get_health_status()
            status_code = 200 if health_status.overall_status == "healthy" else 503
            return jsonify(asdict(health_status)), status_code

        @self.metrics_app.route('/metrics')
        def metrics() -> Response:
            return jsonify({
                'state': self.state,
                'training_metrics': dict(self.metrics),
                'config': {
                    'model': self.config.MODEL_NAME,
                    'batch_size': self.config.BATCH_SIZE,
                    'lora_r': self.config.LORA_R,
                    'learning_rate': self.config.LEARNING_RATE,
                }
            })

        @self.metrics_app.route('/ready')
        def ready() -> Response:
            """Readiness probe for Kubernetes"""
            is_ready = (
                self.model is not None and
                self.tokenizer is not None and
                self.db_pool.health_check()
            )
            return jsonify({'ready': is_ready}), 200 if is_ready else 503

        @self.metrics_app.route('/prometheus')
        def prometheus_metrics() -> Response:
            """Prometheus metrics endpoint"""
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    def _start_metrics_server(self):
        """Start metrics server in background thread"""
        def run_server():
            try:
                self.metrics_app.run(
                    host='0.0.0.0',
                    port=self.config.METRICS_PORT,
                    debug=False,
                    use_reloader=False
                )
            except Exception as e:
                log_with_context('error', f"Metrics server error: {e}",
                               component='metrics', operation='server')

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        log_with_context('info', f"Metrics server started on port {self.config.METRICS_PORT}",
                       component='metrics', operation='server')

    def _setup_cuda_optimizations(self):
        """Setup CUDA optimizations for RTX 5090"""
        if not torch.cuda.is_available():
            log_with_context('warning', "CUDA not available", component='cuda', operation='setup')
            return

        # Enable TF32 for Ampere+ GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True

        # Set memory allocation strategy (use non-deprecated env var)
        os.environ['PYTORCH_ALLOC_CONF'] = 'max_split_size_mb:512'

        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9

        log_with_context('info', f"CUDA Device: {device_name}", component='cuda', operation='setup')
        log_with_context('info', f"CUDA Memory: {total_memory:.2f} GB", component='cuda', operation='setup')

    def _load_model_and_tokenizer(self):
        """Load model and tokenizer with comprehensive error handling"""
        log_with_context('info', f"Loading model: {self.config.MODEL_NAME}",
                       component='model', operation='load')

        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.MODEL_NAME,
                trust_remote_code=True,
                cache_dir=self.config.CACHE_DIR,
                revision=self.config.MODEL_REVISION,
            )

            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

            # 4-bit quantization config
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=self.config.LOAD_IN_4BIT,
                bnb_4bit_compute_dtype=self.config.BNB_4BIT_COMPUTE_DTYPE,
                bnb_4bit_quant_type=self.config.BNB_4BIT_QUANT_TYPE,
                bnb_4bit_use_double_quant=self.config.BNB_4BIT_USE_DOUBLE_QUANT,
            )

            # Determine attention implementation
            attn_impl = "eager"  # Default fallback
            if self.config.USE_FLASH_ATTENTION:
                try:
                    import flash_attn
                    attn_impl = "flash_attention_2"
                    log_with_context('info', "Using Flash Attention 2",
                                   component='model', operation='load')
                except ImportError:
                    log_with_context('warning',
                                   "Flash Attention 2 not available, falling back to eager attention",
                                   component='model', operation='load')
                    attn_impl = "eager"

            # Load model with quantization
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.MODEL_NAME,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=self.config.CACHE_DIR,
                revision=self.config.MODEL_REVISION,
                torch_dtype=torch.bfloat16,
                attn_implementation=attn_impl,
            )

            # Prepare model for k-bit training
            self.model = prepare_model_for_kbit_training(
                self.model,
                use_gradient_checkpointing=self.config.GRADIENT_CHECKPOINTING
            )

            # Setup LoRA
            lora_config = LoraConfig(
                r=self.config.LORA_R,
                lora_alpha=self.config.LORA_ALPHA,
                target_modules=self.config.LORA_TARGET_MODULES,
                lora_dropout=self.config.LORA_DROPOUT,
                bias="none",
                task_type="CAUSAL_LM",
            )

            self.model = get_peft_model(self.model, lora_config)

            # Calculate parameters
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            total_params = sum(p.numel() for p in self.model.parameters())

            log_with_context('info',
                           f"Trainable params: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)",
                           component='model', operation='load')

            # Log to W&B
            self.wb_logger.log_model_config(
                model_name=self.config.MODEL_NAME,
                total_params=total_params,
                trainable_params=trainable_params,
                lora_r=self.config.LORA_R,
                lora_alpha=self.config.LORA_ALPHA,
                batch_size=self.config.BATCH_SIZE,
                learning_rate=self.config.LEARNING_RATE,
                max_length=self.config.MAX_LENGTH
            )

        except Exception as e:
            log_with_context('error', f"Failed to load model: {e}",
                           component='model', operation='load')
            raise

    def train(self, train_dataset: Dataset, eval_dataset: Dataset) -> Dict[str, Any]:
        """Execute training run with comprehensive error handling"""
        log_with_context('info', "Starting training run...", component='training', operation='train')

        try:
            # Initialize W&B if enabled
            if self.config.ENABLE_WANDB:
                wandb.init(
                    project=self.config.WANDB_PROJECT,
                    config=vars(self.config),
                    name=f"run_{self.state['total_training_runs']}",
                )

            # Training arguments
            training_args = TrainingArguments(
                output_dir=self.config.OUTPUT_DIR,
                num_train_epochs=self.config.NUM_TRAIN_EPOCHS,
                per_device_train_batch_size=self.config.BATCH_SIZE,
                per_device_eval_batch_size=self.config.BATCH_SIZE,
                gradient_accumulation_steps=self.config.GRADIENT_ACCUMULATION_STEPS,
                learning_rate=self.config.LEARNING_RATE,
                weight_decay=self.config.WEIGHT_DECAY,
                warmup_ratio=self.config.WARMUP_RATIO,
                max_grad_norm=self.config.MAX_GRAD_NORM,
                optim=self.config.OPTIM,
                eval_strategy="steps",
                eval_steps=100,
                save_strategy="steps",
                save_steps=100,
                save_total_limit=3,
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                logging_dir=f"{self.config.OUTPUT_DIR}/logs",
                logging_steps=10,
                logging_first_step=True,
                report_to="wandb" if self.config.ENABLE_WANDB else "none",
                bf16=True,
                tf32=True,
                dataloader_num_workers=self.config.DATALOADER_NUM_WORKERS,
                dataloader_pin_memory=True,
                gradient_checkpointing=self.config.GRADIENT_CHECKPOINTING,
                remove_unused_columns=False,
                seed=42,
            )

            # Initialize trainer
            trainer = SFTTrainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                tokenizer=self.tokenizer,
                dataset_text_field="text",
                max_seq_length=self.config.MAX_LENGTH,
                packing=False,
                callbacks=[
                    EarlyStoppingCallback(
                        early_stopping_patience=self.config.EARLY_STOPPING_PATIENCE,
                        early_stopping_threshold=self.config.EARLY_STOPPING_THRESHOLD,
                    ),
                    WandbMetricsCallback(self.wb_logger),
                ],
            )

            # Train
            train_result = trainer.train()

            # Save model
            log_with_context('info', f"Saving model to {self.config.OUTPUT_DIR}",
                           component='training', operation='save_model')
            trainer.save_model()
            self.tokenizer.save_pretrained(self.config.OUTPUT_DIR)

            # Get metrics
            metrics = train_result.metrics
            metrics['train_samples'] = len(train_dataset)
            metrics['eval_samples'] = len(eval_dataset)

            # Evaluate
            eval_metrics = trainer.evaluate()
            metrics.update(eval_metrics)

            log_with_context('info', f"Training complete. Eval loss: {metrics.get('eval_loss', 'N/A')}",
                           component='training', operation='complete')

            if self.config.ENABLE_WANDB:
                wandb.finish()

            return metrics

        except Exception as e:
            log_with_context('error', f"Training failed: {e}",
                           component='training', operation='train')
            if self.config.ENABLE_WANDB:
                wandb.finish(exit_code=1)
            raise

    def run_continuous_training(self):
        """Main continuous training loop with production-grade error handling"""
        log_with_context('info', "Starting continuous training system",
                       component='trainer', operation='start')
        log_with_context('info', f"Model: {self.config.MODEL_NAME}",
                       component='trainer', operation='config')
        log_with_context('info', f"Check interval: {self.config.CHECK_INTERVAL}s",
                       component='trainer', operation='config')

        # Setup
        self._setup_cuda_optimizations()
        self._start_metrics_server()
        self._load_model_and_tokenizer()

        # Data preparator
        data_prep = CodeDataPreparator(self.db_pool, self.tokenizer)
        training_count = 0

        while not self.shutdown_requested:
            try:
                log_with_context('info',
                               f"Training check #{training_count + 1}",
                               component='trainer', operation='check')

                # Check for new files
                new_file_count = data_prep.count_new_files(self.state['last_trained_id'])
                log_with_context('info', f"New files available: {new_file_count}",
                               component='trainer', operation='check')

                if new_file_count >= self.config.MIN_NEW_FILES:
                    log_with_context('info',
                                   f"Threshold met ({new_file_count} >= {self.config.MIN_NEW_FILES})",
                                   component='trainer', operation='training_start')

                    # Fetch and prepare data
                    samples = data_prep.fetch_training_data(
                        self.state['last_trained_id'],
                        self.config.MAX_DATASET_SIZE
                    )

                    if not samples:
                        log_with_context('warning', "No samples fetched, skipping training",
                                       component='trainer', operation='training_skip')
                        continue

                    train_dataset, eval_dataset = data_prep.prepare_dataset(samples)

                    # Log dataset stats
                    token_lengths = []
                    for sample in train_dataset:
                        tokens = self.tokenizer(sample['text'], truncation=True,
                                              max_length=self.config.MAX_LENGTH)
                        token_lengths.append(len(tokens['input_ids']))

                    self.wb_logger.log_dataset_stats(
                        train_size=len(train_dataset),
                        eval_size=len(eval_dataset),
                        avg_tokens_per_sample=sum(token_lengths) / len(token_lengths) if token_lengths else 0,
                        max_tokens=max(token_lengths) if token_lengths else 0,
                        min_tokens=min(token_lengths) if token_lengths else 0
                    )

                    # Train
                    start_time = time.time()
                    metrics = self.train(train_dataset, eval_dataset)
                    training_time = time.time() - start_time

                    # Record Prometheus metrics
                    training_runs_total.inc()
                    training_duration_seconds.observe(training_time)
                    if 'train_loss' in metrics:
                        training_loss.set(metrics['train_loss'])
                    if 'eval_loss' in metrics:
                        eval_loss.set(metrics['eval_loss'])
                    samples_trained_total.inc(len(samples))
                    files_trained_total.inc(len(samples))

                    # Update GPU memory metric
                    if torch.cuda.is_available():
                        gpu_memory_bytes.set(torch.cuda.memory_allocated())

                    # Update dataset size metrics
                    dataset_size.labels(split='train').set(len(train_dataset))
                    dataset_size.labels(split='eval').set(len(eval_dataset))

                    # Record metrics
                    self.metrics_tracker.record_training_run(
                        run_id=self.state['total_training_runs'] + 1,
                        duration=training_time,
                        samples=len(samples),
                        metrics=metrics
                    )

                    # Update state
                    max_id = max(s['id'] for s in samples)
                    self.state['last_trained_id'] = max_id
                    self.state['total_training_runs'] += 1
                    self.state['total_samples_trained'] += len(samples)
                    self.state['last_training_time'] = datetime.now().isoformat()
                    self.state['last_training_duration'] = training_time
                    self.state['last_metrics'] = metrics
                    self._save_state()

                    training_count += 1
                    self.consecutive_errors = 0  # Reset error counter on success

                    # Memory management
                    if training_count % self.config.CUDA_EMPTY_CACHE_INTERVAL == 0:
                        MemoryManager.clear_cuda_cache()

                    log_with_context('info',
                                   f"Training run #{training_count} completed in {training_time:.2f}s",
                                   component='trainer', operation='training_complete')
                else:
                    log_with_context('info',
                                   f"Waiting for more files ({new_file_count}/{self.config.MIN_NEW_FILES})",
                                   component='trainer', operation='waiting')

                # Wait before next check
                for _ in range(self.config.CHECK_INTERVAL):
                    if self.shutdown_requested:
                        break
                    time.sleep(1)

            except Exception as e:
                self.consecutive_errors += 1
                log_with_context('error',
                               f"Error in training loop (attempt {self.consecutive_errors}): {e}",
                               component='trainer', operation='error')

                if self.consecutive_errors >= self.config.MAX_CONSECUTIVE_ERRORS:
                    log_with_context('critical',
                                   f"Max consecutive errors ({self.config.MAX_CONSECUTIVE_ERRORS}) reached. Exiting.",
                                   component='trainer', operation='fatal_error')
                    break

                # Exponential backoff
                wait_time = min(self.config.ERROR_BACKOFF_BASE * (2 ** (self.consecutive_errors - 1)), 300)
                log_with_context('info', f"Waiting {wait_time}s before retry...",
                               component='trainer', operation='backoff')
                time.sleep(wait_time)

        # Cleanup
        log_with_context('info', "Shutting down...", component='trainer', operation='shutdown')
        self._save_state()
        self.wb_logger.finish()
        self.db_pool.close_all()
        MemoryManager.clear_cuda_cache()
        log_with_context('info', "Shutdown complete", component='trainer', operation='shutdown')

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point with top-level error handling"""
    try:
        config = TrainingConfig()
        trainer = ContinuousTrainer(config)
        trainer.run_continuous_training()
    except KeyboardInterrupt:
        log_with_context('info', "Received keyboard interrupt", component='main', operation='shutdown')
        sys.exit(0)
    except Exception as e:
        log_with_context('critical', f"Fatal error: {e}", component='main', operation='error')
        sys.exit(1)

if __name__ == "__main__":
    main()
