"""
Comprehensive tests for MetricsTracker with extensive mocking
Tests all metrics collection, aggregation, and reporting functionality
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime

from src.python.utils.metrics_tracker import (
    MetricsTracker,
    TrainingMetrics,
    QualityMetrics,
    PerformanceMetrics
)


class TestTrainingMetrics:
    """Tests for TrainingMetrics dataclass"""

    def test_training_metrics_creation(self):
        """Test creating TrainingMetrics instance"""
        metrics = TrainingMetrics(
            run_id=1,
            timestamp="2025-10-14T12:00:00",
            duration_seconds=3600.0,
            samples_trained=10000,
            train_loss=1.5,
            eval_loss=1.7,
            learning_rate=2e-5,
            epoch=1,
            train_samples_per_second=10.5,
            eval_samples_per_second=12.3,
            gpu_memory_allocated_gb=8.5,
            gpu_memory_reserved_gb=10.0
        )

        assert metrics.run_id == 1
        assert metrics.samples_trained == 10000
        assert metrics.train_loss == 1.5
        assert metrics.eval_loss == 1.7


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass"""

    def test_performance_metrics_creation(self):
        """Test creating PerformanceMetrics instance"""
        metrics = PerformanceMetrics(
            files_per_second=100.0,
            avg_processing_time_ms=10.0,
            p50_processing_time_ms=8.0,
            p95_processing_time_ms=20.0,
            p99_processing_time_ms=50.0
        )

        assert metrics.files_per_second == 100.0
        assert metrics.p99_processing_time_ms == 50.0


class TestMetricsTracker:
    """Tests for MetricsTracker class"""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a MetricsTracker instance for testing"""
        metrics_file = str(tmp_path / "test_metrics.json")
        return MetricsTracker(metrics_file=metrics_file)

    def test_initialization(self, tracker):
        """Test MetricsTracker initialization"""
        assert tracker.training_history == []
        assert len(tracker.quality_stats) == 0
        assert len(tracker.performance_samples) == 0
        assert tracker.start_time > 0

    def test_metrics_file_directory_creation(self, tmp_path):
        """Test that metrics file directory is created"""
        metrics_file = str(tmp_path / "nested" / "dir" / "metrics.json")
        tracker = MetricsTracker(metrics_file=metrics_file)

        assert Path(metrics_file).parent.exists()

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.memory_allocated', return_value=8.5e9)
    @patch('torch.cuda.memory_reserved', return_value=10.0e9)
    def test_record_training_run_with_gpu(
        self, mock_reserved, mock_allocated, mock_available, tracker
    ):
        """Test recording training run with GPU metrics"""
        metrics_dict = {
            'train_loss': 1.5,
            'eval_loss': 1.7,
            'learning_rate': 2e-5,
            'epoch': 1,
            'train_samples_per_second': 10.5,
            'eval_samples_per_second': 12.3
        }

        tracker.record_training_run(
            run_id=1,
            duration=3600.0,
            samples=10000,
            metrics=metrics_dict
        )

        assert len(tracker.training_history) == 1
        recorded = tracker.training_history[0]

        assert recorded.run_id == 1
        assert recorded.duration_seconds == 3600.0
        assert recorded.samples_trained == 10000
        assert recorded.train_loss == 1.5
        assert recorded.eval_loss == 1.7
        assert recorded.gpu_memory_allocated_gb == 8.5
        assert recorded.gpu_memory_reserved_gb == 10.0

    @patch('torch.cuda.is_available', return_value=False)
    def test_record_training_run_without_gpu(self, mock_available, tracker):
        """Test recording training run without GPU"""
        metrics_dict = {
            'train_loss': 1.5,
            'eval_loss': 1.7,
            'learning_rate': 2e-5,
            'epoch': 1,
            'train_samples_per_second': 10.5,
            'eval_samples_per_second': 12.3
        }

        tracker.record_training_run(
            run_id=1,
            duration=3600.0,
            samples=10000,
            metrics=metrics_dict
        )

        recorded = tracker.training_history[0]
        assert recorded.gpu_memory_allocated_gb == 0.0
        assert recorded.gpu_memory_reserved_gb == 0.0

    def test_record_quality_stats_with_scores(self, tracker):
        """Test recording quality statistics with scores"""
        quality_scores = [0.8, 0.9, 0.75, 0.6, 0.85, 0.95]

        tracker.record_quality_stats(
            total_processed=1000,
            quality_scores=quality_scores,
            blocked_malicious=10,
            blocked_secrets=5,
            blocked_license=3
        )

        assert tracker.quality_stats['total_files_processed'] == 1000
        assert tracker.quality_stats['avg_quality_score'] == pytest.approx(0.8083, rel=0.01)
        assert tracker.quality_stats['high_quality_count'] == 5  # >= 0.7
        assert tracker.quality_stats['low_quality_count'] == 1   # < 0.7
        assert tracker.quality_stats['malicious_blocked'] == 10
        assert tracker.quality_stats['secrets_blocked'] == 5
        assert tracker.quality_stats['license_blocked'] == 3

    def test_record_quality_stats_empty_scores(self, tracker):
        """Test recording quality stats with empty scores list"""
        tracker.record_quality_stats(
            total_processed=0,
            quality_scores=[],
            blocked_malicious=0,
            blocked_secrets=0,
            blocked_license=0
        )

        assert tracker.quality_stats['avg_quality_score'] == 0.0
        assert tracker.quality_stats['high_quality_count'] == 0
        assert tracker.quality_stats['low_quality_count'] == 0

    def test_record_processing_time(self, tracker):
        """Test recording processing times"""
        processing_times = [10.0, 20.0, 15.0, 30.0, 12.0]

        for time_ms in processing_times:
            tracker.record_processing_time(time_ms)

        assert len(tracker.performance_samples) == 5
        assert list(tracker.performance_samples) == processing_times

    def test_performance_samples_max_size(self, tracker):
        """Test that performance samples respect maxlen"""
        # Add more than maxlen (10000) samples
        for i in range(10100):
            tracker.record_processing_time(float(i))

        # Should only keep last 10000
        assert len(tracker.performance_samples) == 10000
        assert tracker.performance_samples[0] == 100.0  # First 100 dropped
        assert tracker.performance_samples[-1] == 10099.0

    def test_get_performance_metrics_empty(self, tracker):
        """Test performance metrics with no samples"""
        metrics = tracker.get_performance_metrics()

        assert metrics.files_per_second == 0.0
        assert metrics.avg_processing_time_ms == 0.0
        assert metrics.p50_processing_time_ms == 0.0
        assert metrics.p95_processing_time_ms == 0.0
        assert metrics.p99_processing_time_ms == 0.0

    def test_get_performance_metrics_with_data(self, tracker):
        """Test performance metrics calculation with data"""
        # Add 100 samples with known distribution
        for i in range(100):
            tracker.record_processing_time(float(i))

        metrics = tracker.get_performance_metrics()

        assert metrics.avg_processing_time_ms == pytest.approx(49.5, rel=0.1)
        assert metrics.files_per_second > 0
        assert metrics.p50_processing_time_ms == 50.0
        assert metrics.p95_processing_time_ms == 95.0
        assert metrics.p99_processing_time_ms == 99.0

    def test_get_training_summary_empty(self, tracker):
        """Test training summary with no history"""
        summary = tracker.get_training_summary()

        assert summary == {}

    @patch('torch.cuda.is_available', return_value=False)
    def test_get_training_summary_with_data(self, mock_cuda, tracker):
        """Test training summary with multiple runs"""
        # Record multiple training runs
        for run_id in range(1, 4):
            metrics = {
                'train_loss': 2.0 - (run_id * 0.3),
                'eval_loss': 2.2 - (run_id * 0.3),
                'learning_rate': 2e-5,
                'epoch': 1,
                'train_samples_per_second': 10.0,
                'eval_samples_per_second': 12.0
            }
            tracker.record_training_run(
                run_id=run_id,
                duration=3600.0,
                samples=10000,
                metrics=metrics
            )

        summary = tracker.get_training_summary()

        assert summary['total_runs'] == 3
        assert summary['total_samples'] == 30000
        assert summary['total_duration_hours'] == 3.0
        assert 'avg_train_loss' in summary
        assert 'avg_eval_loss' in summary
        assert 'best_eval_loss' in summary
        assert 'latest_run' in summary
        assert summary['latest_run']['run_id'] == 3

    @patch('torch.cuda.is_available', return_value=False)
    def test_get_all_metrics(self, mock_cuda, tracker):
        """Test getting all metrics"""
        # Add some data
        tracker.record_training_run(
            run_id=1,
            duration=3600.0,
            samples=10000,
            metrics={'train_loss': 1.5, 'eval_loss': 1.7, 'learning_rate': 2e-5, 'epoch': 1}
        )

        tracker.record_quality_stats(
            total_processed=1000,
            quality_scores=[0.8, 0.9],
            blocked_malicious=10,
            blocked_secrets=5,
            blocked_license=3
        )

        tracker.record_processing_time(10.0)

        all_metrics = tracker.get_all_metrics()

        assert 'training_summary' in all_metrics
        assert 'quality_stats' in all_metrics
        assert 'performance' in all_metrics
        assert 'uptime_hours' in all_metrics
        assert 'timestamp' in all_metrics

        assert all_metrics['training_summary']['total_runs'] == 1
        assert all_metrics['quality_stats']['total_files_processed'] == 1000

    def test_save_metrics_writes_to_file(self, tracker, tmp_path):
        """Test that metrics are saved to file"""
        # Add some data
        tracker.record_processing_time(10.0)
        tracker._save_metrics()

        # Check file was created and contains JSON
        metrics_path = Path(tracker.metrics_file)
        assert metrics_path.exists()

        with open(metrics_path, 'r') as f:
            saved_data = json.load(f)

        assert 'performance' in saved_data
        assert 'timestamp' in saved_data

    @patch('utils.metrics_tracker.logger')
    def test_save_metrics_handles_errors(self, mock_logger, tracker):
        """Test that save_metrics handles write errors gracefully"""
        # Mock open to raise an exception
        with patch('builtins.open', side_effect=IOError("Write failed")):
            tracker._save_metrics()

        # Should log error
        assert any("Failed to save metrics" in str(call) for call in mock_logger.error.call_args_list)

    def test_export_training_history(self, tracker, tmp_path):
        """Test exporting training history to JSON"""
        # Add training history
        with patch('torch.cuda.is_available', return_value=False):
            for run_id in range(1, 4):
                tracker.record_training_run(
                    run_id=run_id,
                    duration=3600.0,
                    samples=10000,
                    metrics={'train_loss': 1.5, 'eval_loss': 1.7, 'learning_rate': 2e-5, 'epoch': 1}
                )

        output_file = str(tmp_path / "history.json")
        tracker.export_training_history(output_file)

        # Verify export
        assert Path(output_file).exists()

        with open(output_file, 'r') as f:
            history = json.load(f)

        assert len(history) == 3
        assert history[0]['run_id'] == 1
        assert history[2]['run_id'] == 3

    @patch('utils.metrics_tracker.logger')
    def test_export_training_history_handles_errors(self, mock_logger, tracker, tmp_path):
        """Test export_training_history handles errors"""
        output_file = "/invalid/path/history.json"

        tracker.export_training_history(output_file)

        # Should log error
        assert any("Failed to export" in str(call) for call in mock_logger.error.call_args_list)

    def test_timestamp_format(self, tracker):
        """Test that timestamps are in ISO format"""
        with patch('torch.cuda.is_available', return_value=False):
            tracker.record_training_run(
                run_id=1,
                duration=3600.0,
                samples=10000,
                metrics={'train_loss': 1.5, 'eval_loss': 1.7}
            )

        timestamp = tracker.training_history[0].timestamp

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_uptime_calculation(self, tracker):
        """Test uptime calculation"""
        time.sleep(0.1)  # Wait a bit

        metrics = tracker.get_all_metrics()
        uptime = metrics['uptime_hours']

        assert uptime > 0
        assert uptime < 1.0  # Should be less than an hour

    def test_percentile_calculation_edge_cases(self, tracker):
        """Test percentile calculations with edge cases"""
        # Single sample
        tracker.record_processing_time(10.0)
        metrics = tracker.get_performance_metrics()

        assert metrics.p50_processing_time_ms == 10.0
        assert metrics.p95_processing_time_ms == 10.0
        assert metrics.p99_processing_time_ms == 10.0

    def test_files_per_second_calculation(self, tracker):
        """Test files per second calculation"""
        # Add samples with known average
        for _ in range(100):
            tracker.record_processing_time(100.0)  # 100ms per file

        metrics = tracker.get_performance_metrics()

        # 1000ms / 100ms = 10 files per second
        assert metrics.files_per_second == pytest.approx(10.0, rel=0.01)

    def test_zero_processing_time_edge_case(self, tracker):
        """Test handling of zero processing time"""
        tracker.record_processing_time(0.0)

        metrics = tracker.get_performance_metrics()

        # Should handle division by zero gracefully
        assert metrics.files_per_second == 0.0


class TestMetricsTrackerIntegration:
    """Integration tests for MetricsTracker"""

    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.memory_allocated', return_value=8.5e9)
    @patch('torch.cuda.memory_reserved', return_value=10.0e9)
    def test_complete_training_cycle(
        self, mock_reserved, mock_allocated, mock_available, tmp_path
    ):
        """Test a complete training cycle with all metrics"""
        metrics_file = str(tmp_path / "integration_metrics.json")
        tracker = MetricsTracker(metrics_file=metrics_file)

        # Simulate training runs
        for run_id in range(1, 4):
            metrics = {
                'train_loss': 2.0 - (run_id * 0.3),
                'eval_loss': 2.2 - (run_id * 0.3),
                'learning_rate': 2e-5,
                'epoch': run_id,
                'train_samples_per_second': 10.0,
                'eval_samples_per_second': 12.0
            }
            tracker.record_training_run(
                run_id=run_id,
                duration=3600.0,
                samples=10000,
                metrics=metrics
            )

        # Record quality stats
        quality_scores = [0.8, 0.9, 0.75, 0.85]
        tracker.record_quality_stats(
            total_processed=1000,
            quality_scores=quality_scores,
            blocked_malicious=10,
            blocked_secrets=5,
            blocked_license=3
        )

        # Record processing times
        for i in range(100):
            tracker.record_processing_time(float(10 + i))

        # Get complete metrics
        all_metrics = tracker.get_all_metrics()

        # Verify all components
        assert all_metrics['training_summary']['total_runs'] == 3
        assert all_metrics['training_summary']['best_eval_loss'] < 2.0
        assert all_metrics['quality_stats']['total_files_processed'] == 1000
        assert all_metrics['performance']['avg_processing_time_ms'] > 0
        assert all_metrics['uptime_hours'] > 0

        # Export and verify
        history_file = str(tmp_path / "history.json")
        tracker.export_training_history(history_file)

        with open(history_file, 'r') as f:
            history = json.load(f)

        assert len(history) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
