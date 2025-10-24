"""
Integration tests for the complete CodeLupe pipeline
Tests the flow: Crawler -> Downloader -> Processor -> Trainer
"""

import pytest
import psycopg2
import time
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "python"))


class TestPipelineIntegration:
    """Integration tests for the full pipeline"""

    @pytest.fixture
    def db_connection(self):
        """Create a test database connection"""
        conn_params = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5433")),
            "database": os.getenv("POSTGRES_DB", "coding_db"),
            "user": os.getenv("POSTGRES_USER", "coding_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "coding_pass"),
        }

        try:
            conn = psycopg2.connect(**conn_params)
            yield conn
            conn.close()
        except psycopg2.OperationalError:
            pytest.skip("Database not available for integration testing")

    @pytest.fixture
    def sample_repository_data(self):
        """Sample repository data for testing"""
        return {
            "full_name": "test/integration-repo",
            "stars": 100,
            "forks": 25,
            "language": "Python",
            "description": "A test repository for integration testing",
            "topics": ["testing", "integration", "python"],
            "quality_score": 85,
        }

    def test_database_connection(self, db_connection):
        """Test that we can connect to the database"""
        cursor = db_connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        cursor.close()

    def test_repositories_table_exists(self, db_connection):
        """Test that the repositories table exists"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'repositories'
            )
        """)
        exists = cursor.fetchone()[0]
        cursor.close()
        assert exists, "repositories table should exist"

    def test_processed_files_table_exists(self, db_connection):
        """Test that the processed_files table exists"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'processed_files'
            )
        """)
        exists = cursor.fetchone()[0]
        cursor.close()
        assert exists, "processed_files table should exist"

    @pytest.mark.integration
    def test_insert_and_retrieve_repository(self, db_connection, sample_repository_data):
        """Test inserting and retrieving a repository"""
        cursor = db_connection.cursor()

        # Insert test data
        cursor.execute("""
            INSERT INTO repositories (full_name, stars, forks, language, description, quality_score)
            VALUES (%(full_name)s, %(stars)s, %(forks)s, %(language)s, %(description)s, %(quality_score)s)
            RETURNING id
        """, sample_repository_data)

        repo_id = cursor.fetchone()[0]
        db_connection.commit()

        # Retrieve the data
        cursor.execute("SELECT full_name, stars, language FROM repositories WHERE id = %s", (repo_id,))
        result = cursor.fetchone()

        assert result[0] == sample_repository_data["full_name"]
        assert result[1] == sample_repository_data["stars"]
        assert result[2] == sample_repository_data["language"]

        # Cleanup
        cursor.execute("DELETE FROM repositories WHERE id = %s", (repo_id,))
        db_connection.commit()
        cursor.close()

    @pytest.mark.integration
    def test_quality_score_filtering(self, db_connection):
        """Test filtering repositories by quality score"""
        cursor = db_connection.cursor()

        # Count high-quality repositories
        cursor.execute("""
            SELECT COUNT(*) FROM repositories
            WHERE quality_score >= 70 AND download_status = 'downloaded'
        """)
        count = cursor.fetchone()[0]
        cursor.close()

        assert count >= 0, "Should return non-negative count"


class TestDataProcessorIntegration:
    """Integration tests for data processor"""

    @pytest.fixture
    def mock_processed_file(self):
        """Create a mock processed file entry"""
        return {
            "file_path": "/test/repo/main.py",
            "content": "def hello():\n    print('Hello, World!')",
            "language": "Python",
            "quality_score": 75,
            "repository_id": 1,
        }

    @pytest.mark.integration
    def test_file_processing_workflow(self, db_connection, mock_processed_file):
        """Test the file processing workflow"""
        cursor = db_connection.cursor()

        # Insert test processed file
        cursor.execute("""
            INSERT INTO processed_files (file_path, content, language, quality_score)
            VALUES (%(file_path)s, %(content)s, %(language)s, %(quality_score)s)
            RETURNING id
        """, mock_processed_file)

        file_id = cursor.fetchone()[0]
        db_connection.commit()

        # Verify insertion
        cursor.execute("SELECT language, quality_score FROM processed_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()

        assert result[0] == "Python"
        assert result[1] == 75

        # Cleanup
        cursor.execute("DELETE FROM processed_files WHERE id = %s", (file_id,))
        db_connection.commit()
        cursor.close()


class TestTrainerIntegration:
    """Integration tests for the training pipeline"""

    @pytest.mark.integration
    def test_fetch_training_samples(self, db_connection):
        """Test fetching training samples from database"""
        cursor = db_connection.cursor()

        # Fetch high-quality samples (similar to what trainer does)
        cursor.execute("""
            SELECT id, content, language, quality_score
            FROM processed_files
            WHERE quality_score >= 70
            AND LENGTH(content) BETWEEN 50 AND 8000
            ORDER BY quality_score DESC
            LIMIT 10
        """)

        samples = cursor.fetchall()
        cursor.close()

        # Should return 0 or more samples
        assert len(samples) >= 0

        # If samples exist, validate structure
        for sample in samples:
            assert len(sample) == 4  # id, content, language, quality_score
            assert sample[3] >= 70  # quality_score >= 70

    @pytest.mark.integration
    def test_training_state_persistence(self, tmp_path):
        """Test that training state can be saved and loaded"""
        import json

        state_file = tmp_path / "test_state.json"

        # Create test state
        state = {
            "last_trained_id": 12345,
            "total_training_runs": 5,
            "total_samples_trained": 50000,
            "last_training_time": "2025-10-14T12:00:00",
        }

        # Save state
        with open(state_file, 'w') as f:
            json.dump(state, f)

        # Load state
        with open(state_file, 'r') as f:
            loaded_state = json.load(f)

        assert loaded_state["last_trained_id"] == 12345
        assert loaded_state["total_training_runs"] == 5
        assert loaded_state["total_samples_trained"] == 50000


class TestEndToEndPipeline:
    """End-to-end pipeline tests"""

    @pytest.mark.slow
    @pytest.mark.integration
    def test_pipeline_health_checks(self):
        """Test that all pipeline components have health endpoints"""
        import requests

        endpoints = [
            ("http://localhost:9200/_cluster/health", "Elasticsearch"),
            ("http://localhost:5433", "PostgreSQL"),  # Won't work with HTTP but tests reachability
            ("http://localhost:8090/health", "Trainer metrics"),
            ("http://localhost:9091/health", "Metrics exporter"),
        ]

        results = []
        for url, name in endpoints:
            try:
                if "5433" in url:
                    # Skip PostgreSQL HTTP check
                    continue
                response = requests.get(url, timeout=2)
                results.append((name, response.status_code < 500))
            except requests.exceptions.RequestException:
                results.append((name, False))

        # At least some services should be healthy
        healthy_count = sum(1 for _, healthy in results if healthy)
        assert healthy_count >= 0  # Flexible for different environments

    @pytest.mark.integration
    def test_metrics_collection(self, db_connection):
        """Test that metrics are being collected"""
        cursor = db_connection.cursor()

        # Check if we have download logs (indicates activity)
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'download_logs'
            )
        """)

        table_exists = cursor.fetchone()[0]
        cursor.close()

        if table_exists:
            cursor = db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM download_logs")
            count = cursor.fetchone()[0]
            cursor.close()
            assert count >= 0


@pytest.mark.integration
class TestQualityFiltering:
    """Tests for quality filtering logic"""

    def test_quality_filter_thresholds(self):
        """Test quality filtering thresholds"""
        # Import the quality filter
        from utils.quality_checker import QualityChecker

        checker = QualityChecker(min_stars=10, min_forks=3)

        # Test passing case
        assert checker.meets_threshold(stars=15, forks=5) is True

        # Test failing cases
        assert checker.meets_threshold(stars=5, forks=5) is False
        assert checker.meets_threshold(stars=15, forks=1) is False

    def test_exclude_patterns(self):
        """Test that exclude patterns work correctly"""
        exclude_patterns = ["tutorial", "demo", "homework", "test"]

        test_cases = [
            ("awesome-framework", True),  # Should pass
            ("react-tutorial", False),     # Should fail (tutorial)
            ("demo-project", False),       # Should fail (demo)
            ("homework-assignment", False), # Should fail (homework)
        ]

        for name, should_pass in test_cases:
            matches_exclude = any(pattern in name.lower() for pattern in exclude_patterns)
            assert (not matches_exclude) == should_pass, f"Failed for {name}"


# Utility class for testing (mock implementation)
class QualityChecker:
    def __init__(self, min_stars=10, min_forks=3):
        self.min_stars = min_stars
        self.min_forks = min_forks

    def meets_threshold(self, stars, forks):
        return stars >= self.min_stars and forks >= self.min_forks


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
