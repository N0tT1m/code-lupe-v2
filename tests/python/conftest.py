"""
Pytest configuration and fixtures for CodeLupe tests
"""

import pytest
import os
import sys
from pathlib import Path

# Add src directories to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src" / "python"))


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_db: marks tests that require database connection"
    )
    config.addinivalue_line(
        "markers", "requires_gpu: marks tests that require GPU"
    )


@pytest.fixture(scope="session")
def test_data_dir():
    """Return path to test data directory"""
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def sample_code_files(test_data_dir):
    """Create sample code files for testing"""
    files = {}

    # Python sample
    python_file = test_data_dir / "sample.py"
    python_file.write_text("""
def fibonacci(n):
    '''Calculate nth Fibonacci number'''
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

if __name__ == '__main__':
    print(fibonacci(10))
""")
    files['python'] = python_file

    # Go sample
    go_file = test_data_dir / "sample.go"
    go_file.write_text("""
package main

import "fmt"

func factorial(n int) int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n-1)
}

func main() {
    fmt.Println(factorial(5))
}
""")
    files['go'] = go_file

    # Rust sample
    rust_file = test_data_dir / "sample.rs"
    rust_file.write_text("""
fn fibonacci(n: u32) -> u32 {
    match n {
        0 => 0,
        1 => 1,
        _ => fibonacci(n - 1) + fibonacci(n - 2),
    }
}

fn main() {
    println!("{}", fibonacci(10));
}
""")
    files['rust'] = rust_file

    return files


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing"""
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "coding_db_test",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_pass",
        "ELASTICSEARCH_URL": "http://localhost:9200",
        "MIN_NEW_FILES": "100",
        "MAX_DATASET_SIZE": "10000",
        "CHECK_INTERVAL": "60",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def sample_repository_metadata():
    """Sample repository metadata for testing"""
    return {
        "full_name": "user/awesome-project",
        "name": "awesome-project",
        "description": "An awesome framework for building APIs",
        "language": "Python",
        "stars": 1500,
        "forks": 200,
        "topics": ["python", "api", "framework", "rest"],
        "url": "https://github.com/user/awesome-project",
        "quality_score": 85,
    }


@pytest.fixture
def sample_processed_file():
    """Sample processed file data for testing"""
    return {
        "file_path": "/repos/user/project/src/main.py",
        "content": """
import logging
from typing import List, Optional

class DataProcessor:
    '''Process and validate data'''

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def process(self, data: List[dict]) -> List[dict]:
        '''Process a list of data items'''
        results = []
        for item in data:
            if self.validate(item):
                results.append(self.transform(item))
        return results

    def validate(self, item: dict) -> bool:
        '''Validate a single data item'''
        required_fields = ['id', 'name', 'value']
        return all(field in item for field in required_fields)

    def transform(self, item: dict) -> dict:
        '''Transform a data item'''
        return {
            'id': item['id'],
            'name': item['name'].strip().lower(),
            'value': float(item['value']),
        }
""",
        "language": "Python",
        "quality_score": 78,
        "lines_of_code": 25,
        "repository_id": 1,
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests"""
    yield
    # Clean up any singleton state here if needed


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests"""
    from unittest.mock import MagicMock

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    return mock_conn, mock_cursor


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary directory for repository downloads"""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    return repos_dir


@pytest.fixture
def mock_training_config():
    """Mock training configuration"""
    return {
        "model_name": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "batch_size": 4,
        "gradient_accumulation_steps": 4,
        "learning_rate": 2e-5,
        "max_length": 4096,
        "lora_r": 256,
        "lora_alpha": 512,
        "min_new_files": 1000,
        "quality_threshold": 70.0,
    }
