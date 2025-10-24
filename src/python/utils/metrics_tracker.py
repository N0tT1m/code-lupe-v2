#!/usr/bin/env python3
"""
Metrics Tracker - Advanced metrics collection for training loop
Tracks performance, quality, and operational metrics
"""

import time
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Metrics for a single training run"""
    run_id: int
    timestamp: str
    duration_seconds: float
    samples_trained: int
    train_loss: float
    eval_loss: float
    learning_rate: float
    epoch: int
    train_samples_per_second: float
    eval_samples_per_second: float
    gpu_memory_allocated_gb: float
    gpu_memory_reserved_gb: float


@dataclass
class QualityMetrics:
    """Code quality metrics"""
    total_files_processed: int
    avg_quality_score: float
    high_quality_count: int
    low_quality_count: int
    malicious_blocked: int
    secrets_blocked: int
    license_blocked: int


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    files_per_second: float
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    p99_processing_time_ms: float


class MetricsTracker:
    """Tracks and aggregates metrics across the training pipeline"""

    def __init__(self, metrics_file: str = None):
        """
        Initialize metrics tracker

        Args:
            metrics_file: Path to save metrics (default: /app/logs/metrics.json)
        """
        self.metrics_file = metrics_file or "/app/logs/metrics.json"
        self.training_history: List[TrainingMetrics] = []
        self.quality_stats = defaultdict(int)
        self.performance_samples = deque(maxlen=10000)  # Keep last 10K samples
        self.start_time = time.time()

        # Ensure metrics directory exists
        Path(self.metrics_file).parent.mkdir(parents=True, exist_ok=True)

    def record_training_run(
        self,
        run_id: int,
        duration: float,
        samples: int,
        metrics: Dict
    ):
        """Record metrics from a training run"""
        import torch

        training_metrics = TrainingMetrics(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat(),
            duration_seconds=duration,
            samples_trained=samples,
            train_loss=metrics.get('train_loss', 0.0),
            eval_loss=metrics.get('eval_loss', 0.0),
            learning_rate=metrics.get('learning_rate', 0.0),
            epoch=metrics.get('epoch', 0),
            train_samples_per_second=metrics.get('train_samples_per_second', 0.0),
            eval_samples_per_second=metrics.get('eval_samples_per_second', 0.0),
            gpu_memory_allocated_gb=torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0,
            gpu_memory_reserved_gb=torch.cuda.memory_reserved() / 1e9 if torch.cuda.is_available() else 0.0,
        )

        self.training_history.append(training_metrics)
        self._save_metrics()

        logger.info(f"Recorded training metrics for run {run_id}")

    def record_quality_stats(
        self,
        total_processed: int,
        quality_scores: List[float],
        blocked_malicious: int,
        blocked_secrets: int,
        blocked_license: int
    ):
        """Record quality filtering statistics"""
        if quality_scores:
            avg_score = sum(quality_scores) / len(quality_scores)
            high_quality = sum(1 for score in quality_scores if score >= 0.7)
            low_quality = len(quality_scores) - high_quality
        else:
            avg_score = 0.0
            high_quality = 0
            low_quality = 0

        self.quality_stats['total_files_processed'] = total_processed
        self.quality_stats['avg_quality_score'] = avg_score
        self.quality_stats['high_quality_count'] = high_quality
        self.quality_stats['low_quality_count'] = low_quality
        self.quality_stats['malicious_blocked'] = blocked_malicious
        self.quality_stats['secrets_blocked'] = blocked_secrets
        self.quality_stats['license_blocked'] = blocked_license

        self._save_metrics()

    def record_processing_time(self, duration_ms: float):
        """Record individual file processing time"""
        self.performance_samples.append(duration_ms)

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics from samples"""
        if not self.performance_samples:
            return PerformanceMetrics(
                files_per_second=0.0,
                avg_processing_time_ms=0.0,
                p50_processing_time_ms=0.0,
                p95_processing_time_ms=0.0,
                p99_processing_time_ms=0.0
            )

        samples = sorted(self.performance_samples)
        n = len(samples)

        avg_time = sum(samples) / n
        files_per_second = 1000.0 / avg_time if avg_time > 0 else 0.0

        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        return PerformanceMetrics(
            files_per_second=files_per_second,
            avg_processing_time_ms=avg_time,
            p50_processing_time_ms=samples[p50_idx],
            p95_processing_time_ms=samples[p95_idx],
            p99_processing_time_ms=samples[p99_idx]
        )

    def get_training_summary(self) -> Dict:
        """Get summary of training history"""
        if not self.training_history:
            return {}

        return {
            'total_runs': len(self.training_history),
            'total_samples': sum(m.samples_trained for m in self.training_history),
            'total_duration_hours': sum(m.duration_seconds for m in self.training_history) / 3600,
            'avg_train_loss': sum(m.train_loss for m in self.training_history) / len(self.training_history),
            'avg_eval_loss': sum(m.eval_loss for m in self.training_history) / len(self.training_history),
            'best_eval_loss': min(m.eval_loss for m in self.training_history),
            'latest_run': asdict(self.training_history[-1]) if self.training_history else None
        }

    def get_all_metrics(self) -> Dict:
        """Get all collected metrics"""
        return {
            'training_summary': self.get_training_summary(),
            'quality_stats': dict(self.quality_stats),
            'performance': asdict(self.get_performance_metrics()),
            'uptime_hours': (time.time() - self.start_time) / 3600,
            'timestamp': datetime.utcnow().isoformat()
        }

    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.get_all_metrics(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def export_training_history(self, output_file: str):
        """Export training history to JSON"""
        try:
            with open(output_file, 'w') as f:
                history_data = [asdict(m) for m in self.training_history]
                json.dump(history_data, f, indent=2)
            logger.info(f"Exported training history to {output_file}")
        except Exception as e:
            logger.error(f"Failed to export training history: {e}")


# Example usage
if __name__ == "__main__":
    import random

    logging.basicConfig(level=logging.INFO)

    tracker = MetricsTracker(metrics_file="./test_metrics.json")

    # Simulate training runs
    print("\n=== Simulating Training Runs ===")
    for run_id in range(1, 6):
        metrics = {
            'train_loss': 2.5 - (run_id * 0.3) + random.uniform(-0.1, 0.1),
            'eval_loss': 2.7 - (run_id * 0.3) + random.uniform(-0.1, 0.1),
            'learning_rate': 2e-5,
            'epoch': 1,
            'train_samples_per_second': 10.5,
            'eval_samples_per_second': 12.3
        }

        tracker.record_training_run(
            run_id=run_id,
            duration=3600.0,  # 1 hour
            samples=10000,
            metrics=metrics
        )

    # Simulate quality stats
    print("\n=== Recording Quality Stats ===")
    quality_scores = [random.uniform(0.5, 1.0) for _ in range(1000)]
    tracker.record_quality_stats(
        total_processed=1000,
        quality_scores=quality_scores,
        blocked_malicious=10,
        blocked_secrets=5,
        blocked_license=3
    )

    # Simulate processing times
    print("\n=== Recording Processing Times ===")
    for _ in range(1000):
        # Simulate processing time with some outliers
        base_time = random.uniform(50, 150)
        if random.random() < 0.05:  # 5% outliers
            base_time *= 3
        tracker.record_processing_time(base_time)

    # Get all metrics
    print("\n=== All Metrics ===")
    all_metrics = tracker.get_all_metrics()
    print(json.dumps(all_metrics, indent=2))

    # Export training history
    tracker.export_training_history("./training_history.json")

    print("\n✅ Metrics tracking demo complete")
