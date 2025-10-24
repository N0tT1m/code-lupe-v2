#!/usr/bin/env python3
"""
Comprehensive Weights & Biases Logger
Logs ALL metrics without storing data/models on W&B
"""

import logging
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict
import torch
import psutil
import os


class ContextFilter(logging.Filter):
    """Add default fields to log records to prevent formatting errors"""
    def filter(self, record):
        if not hasattr(record, 'component'):
            record.component = 'wandb_logger'
        if not hasattr(record, 'operation'):
            record.operation = 'logging'
        return True


# Configure logger with context filter
logger = logging.getLogger(__name__)
logger.addFilter(ContextFilter())

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    logger.warning("wandb not installed. Install with: pip install wandb")


class ComprehensiveWandbLogger:
    """
    Comprehensive W&B logger that tracks EVERYTHING
    - Training metrics (loss, accuracy, perplexity)
    - System metrics (GPU, CPU, memory, disk)
    - Data quality metrics
    - Performance metrics (throughput, latency)
    - Model metrics (gradients, weights, layer stats)
    - Custom metrics (code quality, security filtering)
    """

    def __init__(
        self,
        project: str,
        name: str = None,
        config: Dict = None,
        enabled: bool = True,
        log_frequency: int = 10
    ):
        """
        Initialize comprehensive W&B logger

        Args:
            project: W&B project name
            name: Run name
            config: Configuration dictionary
            enabled: Whether logging is enabled
            log_frequency: How often to log metrics (steps)
        """
        self.enabled = enabled and WANDB_AVAILABLE
        self.log_frequency = log_frequency
        self.step = 0
        self.epoch = 0

        # Metric buffers
        self.metric_buffer = defaultdict(list)
        self.last_log_time = time.time()

        if self.enabled:
            try:
                wandb.init(
                    project=project,
                    name=name,
                    config=config or {},
                    settings=wandb.Settings(
                        _disable_stats=False,  # Enable system metrics
                        _disable_meta=False,
                    )
                )
                logger.info(f"✅ W&B initialized: {project}/{name}")
            except Exception as e:
                logger.error(f"Failed to initialize W&B: {e}")
                self.enabled = False
        else:
            logger.info("W&B logging disabled")

    # ========================================================================
    # TRAINING METRICS
    # ========================================================================

    def log_training_metrics(
        self,
        train_loss: float = None,
        eval_loss: float = None,
        learning_rate: float = None,
        epoch: int = None,
        step: int = None,
        **kwargs
    ):
        """Log training metrics"""
        if not self.enabled:
            return

        metrics = {}

        if train_loss is not None:
            metrics['train/loss'] = train_loss
            metrics['train/perplexity'] = torch.exp(torch.tensor(train_loss)).item()

        if eval_loss is not None:
            metrics['eval/loss'] = eval_loss
            metrics['eval/perplexity'] = torch.exp(torch.tensor(eval_loss)).item()

        if learning_rate is not None:
            metrics['train/learning_rate'] = learning_rate

        if epoch is not None:
            metrics['train/epoch'] = epoch
            self.epoch = epoch

        # Add any additional metrics
        for key, value in kwargs.items():
            if value is not None:
                metrics[f'train/{key}'] = value

        if metrics:
            wandb.log(metrics, step=step or self.step)

    def log_batch_metrics(
        self,
        batch_loss: float,
        batch_size: int,
        learning_rate: float,
        grad_norm: float = None,
        step: int = None
    ):
        """Log per-batch metrics"""
        if not self.enabled:
            return

        metrics = {
            'batch/loss': batch_loss,
            'batch/perplexity': torch.exp(torch.tensor(batch_loss)).item(),
            'batch/size': batch_size,
            'batch/learning_rate': learning_rate,
        }

        if grad_norm is not None:
            metrics['batch/grad_norm'] = grad_norm

        wandb.log(metrics, step=step or self.step)

    def log_gradient_metrics(self, model):
        """Log gradient statistics"""
        if not self.enabled:
            return

        grad_norms = []
        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                grad_norms.append(grad_norm)

                # Log per-layer gradient norms (sample every N layers)
                if 'weight' in name and len(grad_norms) % 10 == 0:
                    wandb.log({f'gradients/{name}': grad_norm}, step=self.step)

        if grad_norms:
            wandb.log({
                'gradients/global_norm': sum(grad_norms),
                'gradients/mean_norm': sum(grad_norms) / len(grad_norms),
                'gradients/max_norm': max(grad_norms),
                'gradients/min_norm': min(grad_norms),
            }, step=self.step)

    def log_weight_metrics(self, model):
        """Log weight statistics"""
        if not self.enabled:
            return

        weight_stats = []
        for name, param in model.named_parameters():
            if 'weight' in name:
                weight_mean = param.data.mean().item()
                weight_std = param.data.std().item()
                weight_stats.append({
                    'name': name,
                    'mean': weight_mean,
                    'std': weight_std,
                })

                # Log sample of layers
                if len(weight_stats) % 20 == 0:
                    wandb.log({
                        f'weights/{name}/mean': weight_mean,
                        f'weights/{name}/std': weight_std,
                    }, step=self.step)

        if weight_stats:
            all_means = [s['mean'] for s in weight_stats]
            all_stds = [s['std'] for s in weight_stats]
            wandb.log({
                'weights/global_mean': sum(all_means) / len(all_means),
                'weights/global_std': sum(all_stds) / len(all_stds),
            }, step=self.step)

    # ========================================================================
    # SYSTEM METRICS
    # ========================================================================

    def log_system_metrics(self):
        """Log system resource usage"""
        if not self.enabled:
            return

        metrics = {}

        # CPU metrics
        metrics['system/cpu_percent'] = psutil.cpu_percent(interval=0.1)
        metrics['system/cpu_count'] = psutil.cpu_count()

        # Memory metrics
        memory = psutil.virtual_memory()
        metrics['system/memory_used_gb'] = memory.used / 1e9
        metrics['system/memory_available_gb'] = memory.available / 1e9
        metrics['system/memory_percent'] = memory.percent

        # Disk metrics
        disk = psutil.disk_usage('/')
        metrics['system/disk_used_gb'] = disk.used / 1e9
        metrics['system/disk_free_gb'] = disk.free / 1e9
        metrics['system/disk_percent'] = disk.percent

        # GPU metrics
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                metrics[f'system/gpu_{i}_memory_allocated_gb'] = torch.cuda.memory_allocated(i) / 1e9
                metrics[f'system/gpu_{i}_memory_reserved_gb'] = torch.cuda.memory_reserved(i) / 1e9
                metrics[f'system/gpu_{i}_memory_cached_gb'] = torch.cuda.memory_reserved(i) / 1e9

                # Get utilization if available
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    metrics[f'system/gpu_{i}_utilization'] = util.gpu
                    metrics[f'system/gpu_{i}_memory_utilization'] = util.memory
                except:
                    pass

        wandb.log(metrics, step=self.step)

    # ========================================================================
    # DATA QUALITY METRICS
    # ========================================================================

    def log_data_quality_metrics(
        self,
        total_samples: int,
        avg_quality_score: float,
        language_distribution: Dict[str, int],
        avg_code_length: float,
        security_stats: Dict = None
    ):
        """Log data quality metrics"""
        if not self.enabled:
            return

        metrics = {
            'data/total_samples': total_samples,
            'data/avg_quality_score': avg_quality_score,
            'data/avg_code_length': avg_code_length,
        }

        # Language distribution
        for lang, count in language_distribution.items():
            metrics[f'data/language_{lang}'] = count
            metrics[f'data/language_{lang}_percent'] = (count / total_samples) * 100

        # Security filtering stats
        if security_stats:
            metrics['data/blocked_malicious'] = security_stats.get('malicious', 0)
            metrics['data/blocked_secrets'] = security_stats.get('secrets', 0)
            metrics['data/blocked_license'] = security_stats.get('license', 0)
            metrics['data/blocked_total'] = sum(security_stats.values())
            metrics['data/pass_rate'] = (total_samples / (total_samples + sum(security_stats.values()))) * 100

        wandb.log(metrics, step=self.step)

    def log_dataset_stats(
        self,
        train_size: int,
        eval_size: int,
        avg_tokens_per_sample: float,
        max_tokens: int,
        min_tokens: int
    ):
        """Log dataset statistics"""
        if not self.enabled:
            return

        wandb.log({
            'dataset/train_size': train_size,
            'dataset/eval_size': eval_size,
            'dataset/total_size': train_size + eval_size,
            'dataset/train_eval_ratio': train_size / eval_size if eval_size > 0 else 0,
            'dataset/avg_tokens_per_sample': avg_tokens_per_sample,
            'dataset/max_tokens': max_tokens,
            'dataset/min_tokens': min_tokens,
        }, step=self.step)

    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================

    def log_performance_metrics(
        self,
        samples_per_second: float,
        tokens_per_second: float,
        batch_time: float,
        data_loading_time: float = None,
        forward_time: float = None,
        backward_time: float = None
    ):
        """Log training performance metrics"""
        if not self.enabled:
            return

        metrics = {
            'performance/samples_per_second': samples_per_second,
            'performance/tokens_per_second': tokens_per_second,
            'performance/batch_time_ms': batch_time * 1000,
        }

        if data_loading_time is not None:
            metrics['performance/data_loading_time_ms'] = data_loading_time * 1000

        if forward_time is not None:
            metrics['performance/forward_time_ms'] = forward_time * 1000

        if backward_time is not None:
            metrics['performance/backward_time_ms'] = backward_time * 1000

        wandb.log(metrics, step=self.step)

    # ========================================================================
    # CUSTOM METRICS
    # ========================================================================

    def log_code_metrics(
        self,
        avg_lines_of_code: float,
        avg_complexity: float,
        has_comments_percent: float,
        has_docstrings_percent: float
    ):
        """Log code-specific metrics"""
        if not self.enabled:
            return

        wandb.log({
            'code/avg_lines': avg_lines_of_code,
            'code/avg_complexity': avg_complexity,
            'code/comments_percent': has_comments_percent,
            'code/docstrings_percent': has_docstrings_percent,
        }, step=self.step)

    def log_training_progress(
        self,
        current_step: int,
        total_steps: int,
        epoch: int,
        total_epochs: int,
        eta_seconds: float
    ):
        """Log training progress"""
        if not self.enabled:
            return

        wandb.log({
            'progress/step': current_step,
            'progress/step_percent': (current_step / total_steps) * 100,
            'progress/epoch': epoch,
            'progress/epoch_percent': (epoch / total_epochs) * 100,
            'progress/eta_minutes': eta_seconds / 60,
            'progress/eta_hours': eta_seconds / 3600,
        }, step=self.step)

    def log_model_config(
        self,
        model_name: str,
        total_params: int,
        trainable_params: int,
        lora_r: int,
        lora_alpha: int,
        batch_size: int,
        learning_rate: float,
        max_length: int
    ):
        """Log model configuration"""
        if not self.enabled:
            return

        wandb.config.update({
            'model/name': model_name,
            'model/total_params': total_params,
            'model/trainable_params': trainable_params,
            'model/trainable_percent': (trainable_params / total_params) * 100,
            'model/lora_r': lora_r,
            'model/lora_alpha': lora_alpha,
            'hyperparams/batch_size': batch_size,
            'hyperparams/learning_rate': learning_rate,
            'hyperparams/max_length': max_length,
        })

    def log_continuous_training_state(
        self,
        run_number: int,
        total_runs: int,
        last_trained_id: int,
        total_samples_trained: int,
        uptime_hours: float
    ):
        """Log continuous training state"""
        if not self.enabled:
            return

        wandb.log({
            'continuous/run_number': run_number,
            'continuous/total_runs': total_runs,
            'continuous/last_trained_id': last_trained_id,
            'continuous/total_samples_trained': total_samples_trained,
            'continuous/uptime_hours': uptime_hours,
        }, step=self.step)

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def log_custom(self, metrics: Dict[str, Any], step: int = None):
        """Log custom metrics"""
        if not self.enabled:
            return

        wandb.log(metrics, step=step or self.step)

    def increment_step(self):
        """Increment global step counter"""
        self.step += 1

    def set_step(self, step: int):
        """Set global step counter"""
        self.step = step

    def finish(self):
        """Finish W&B run"""
        if self.enabled:
            wandb.finish()
            logger.info("W&B run finished")


# Example usage
if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    # Initialize logger
    wb_logger = ComprehensiveWandbLogger(
        project="codelupe-test",
        name="comprehensive-logging-test",
        config={
            'model': 'Qwen2.5-Coder-14B',
            'batch_size': 4,
            'learning_rate': 2e-5,
        }
    )

    # Simulate training loop
    for epoch in range(2):
        for step in range(100):
            # Training metrics
            wb_logger.log_training_metrics(
                train_loss=2.5 - (step * 0.01),
                learning_rate=2e-5 * (0.99 ** step),
                epoch=epoch,
                step=step
            )

            # System metrics (every 10 steps)
            if step % 10 == 0:
                wb_logger.log_system_metrics()

            # Performance metrics
            wb_logger.log_performance_metrics(
                samples_per_second=10.5,
                tokens_per_second=500.0,
                batch_time=0.5
            )

            wb_logger.increment_step()
            time.sleep(0.01)

    # Final metrics
    wb_logger.log_data_quality_metrics(
        total_samples=10000,
        avg_quality_score=0.85,
        language_distribution={'Python': 4000, 'Rust': 3000, 'Go': 3000},
        avg_code_length=150.5,
        security_stats={'malicious': 10, 'secrets': 5, 'license': 3}
    )

    wb_logger.finish()
    print("✅ Demo complete")
