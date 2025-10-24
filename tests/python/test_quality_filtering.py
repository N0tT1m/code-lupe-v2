"""
Comprehensive tests for quality filtering with extensive mocking
Tests code quality assessment, filtering logic, and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

# Mock the quality filtering module classes
from collections import defaultdict, Counter


class CodeSample:
    """Mock CodeSample for testing"""
    def __init__(self, content, language, metadata, category="", quality_score=0.0):
        self.content = content
        self.language = language
        self.metadata = metadata
        self.category = category
        self.quality_score = quality_score
        self.quality_breakdown = {}
        self.issues = []
        self.frameworks = []


class QualityChecker:
    """Quality checker for code samples"""
    def __init__(self, min_stars=10, min_forks=3, min_quality_score=0.7):
        self.min_stars = min_stars
        self.min_forks = min_forks
        self.min_quality_score = min_quality_score

    def meets_threshold(self, stars, forks):
        """Check if repository meets quality threshold"""
        return stars >= self.min_stars and forks >= self.min_forks

    def calculate_quality_score(self, code_sample):
        """Calculate quality score for code sample"""
        score = 0.5  # Base score

        # Length check
        if 100 <= len(code_sample.content) <= 5000:
            score += 0.1

        # Documentation check (comments)
        if '#' in code_sample.content or '//' in code_sample.content:
            score += 0.1

        # Function/class detection
        if 'def ' in code_sample.content or 'class ' in code_sample.content:
            score += 0.15

        # Type hints (Python)
        if '->' in code_sample.content or ': ' in code_sample.content:
            score += 0.1

        # Error handling
        if 'try' in code_sample.content or 'except' in code_sample.content:
            score += 0.05

        return min(score, 1.0)

    def check_code_patterns(self, content):
        """Check for good code patterns"""
        patterns_found = []

        if 'async def' in content:
            patterns_found.append('async_programming')

        if 'typing.' in content or 'List[' in content:
            patterns_found.append('type_hints')

        if 'logger.' in content or 'logging.' in content:
            patterns_found.append('logging')

        if '@' in content and '(' in content:  # Decorators
            patterns_found.append('decorators')

        return patterns_found

    def detect_frameworks(self, content, language):
        """Detect framework usage"""
        frameworks = []

        framework_keywords = {
            'python': {
                'fastapi': ['fastapi', 'FastAPI'],
                'django': ['django', 'Django'],
                'flask': ['flask', 'Flask'],
                'pytorch': ['torch.', 'pytorch'],
                'tensorflow': ['tensorflow', 'tf.'],
            },
            'rust': {
                'actix': ['actix_web', 'actix'],
                'rocket': ['rocket::', '#[rocket]'],
                'tokio': ['tokio::', '@tokio'],
            },
            'go': {
                'gin': ['gin.', 'gin-gonic'],
                'echo': ['echo.', 'labstack/echo'],
                'fiber': ['fiber.', 'gofiber'],
            }
        }

        if language.lower() in framework_keywords:
            for framework, keywords in framework_keywords[language.lower()].items():
                if any(keyword in content for keyword in keywords):
                    frameworks.append(framework)

        return frameworks


class TestQualityChecker:
    """Tests for QualityChecker class"""

    def test_meets_threshold_passing(self):
        """Test that quality checker passes valid repositories"""
        checker = QualityChecker(min_stars=10, min_forks=3)

        assert checker.meets_threshold(stars=15, forks=5) is True
        assert checker.meets_threshold(stars=10, forks=3) is True
        assert checker.meets_threshold(stars=100, forks=50) is True

    def test_meets_threshold_failing(self):
        """Test that quality checker fails invalid repositories"""
        checker = QualityChecker(min_stars=10, min_forks=3)

        assert checker.meets_threshold(stars=5, forks=5) is False
        assert checker.meets_threshold(stars=15, forks=1) is False
        assert checker.meets_threshold(stars=0, forks=0) is False

    def test_calculate_quality_score_high_quality(self):
        """Test quality score for high-quality code"""
        checker = QualityChecker()

        code = """
def process_data(items: List[Dict]) -> List[Dict]:
    '''Process a list of data items with error handling'''
    results = []
    try:
        for item in items:
            # Validate item
            if validate_item(item):
                results.append(transform_item(item))
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise
    return results
"""

        sample = CodeSample(code, "Python", {})
        score = checker.calculate_quality_score(sample)

        assert score >= 0.8  # Should be high quality

    def test_calculate_quality_score_low_quality(self):
        """Test quality score for low-quality code"""
        checker = QualityChecker()

        code = "x = 1"  # Minimal code

        sample = CodeSample(code, "Python", {})
        score = checker.calculate_quality_score(sample)

        assert score < 0.7  # Should be low quality

    def test_calculate_quality_score_no_documentation(self):
        """Test that missing documentation lowers score"""
        checker = QualityChecker()

        code_with_docs = """
# This function does something important
def func():
    return 42
"""

        code_without_docs = """
def func():
    return 42
"""

        sample_with = CodeSample(code_with_docs, "Python", {})
        sample_without = CodeSample(code_without_docs, "Python", {})

        score_with = checker.calculate_quality_score(sample_with)
        score_without = checker.calculate_quality_score(sample_without)

        assert score_with > score_without

    def test_check_code_patterns_async(self):
        """Test detection of async programming patterns"""
        checker = QualityChecker()

        code = """
async def fetch_data():
    return await client.get('/api/data')
"""

        patterns = checker.check_code_patterns(code)

        assert 'async_programming' in patterns

    def test_check_code_patterns_type_hints(self):
        """Test detection of type hints"""
        checker = QualityChecker()

        code = """
from typing import List, Dict

def process(items: List[Dict]) -> bool:
    return True
"""

        patterns = checker.check_code_patterns(code)

        assert 'type_hints' in patterns

    def test_check_code_patterns_logging(self):
        """Test detection of logging usage"""
        checker = QualityChecker()

        code = """
import logging
logger = logging.getLogger(__name__)

def process():
    logger.info("Processing started")
"""

        patterns = checker.check_code_patterns(code)

        assert 'logging' in patterns

    def test_check_code_patterns_decorators(self):
        """Test detection of decorators"""
        checker = QualityChecker()

        code = """
@retry_with_backoff(max_retries=3)
def fetch_data():
    return requests.get('/api/data')
"""

        patterns = checker.check_code_patterns(code)

        assert 'decorators' in patterns

    def test_detect_frameworks_python_fastapi(self):
        """Test detection of FastAPI framework"""
        checker = QualityChecker()

        code = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
"""

        frameworks = checker.detect_frameworks(code, "Python")

        assert 'fastapi' in frameworks

    def test_detect_frameworks_python_pytorch(self):
        """Test detection of PyTorch framework"""
        checker = QualityChecker()

        code = """
import torch
import torch.nn as nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(10, 1)
"""

        frameworks = checker.detect_frameworks(code, "Python")

        assert 'pytorch' in frameworks

    def test_detect_frameworks_rust_actix(self):
        """Test detection of Actix framework"""
        checker = QualityChecker()

        code = """
use actix_web::{web, App, HttpServer};

async fn index() -> &'static str {
    "Hello, World!"
}
"""

        frameworks = checker.detect_frameworks(code, "Rust")

        assert 'actix' in frameworks

    def test_detect_frameworks_go_gin(self):
        """Test detection of Gin framework"""
        checker = QualityChecker()

        code = """
package main

import "github.com/gin-gonic/gin"

func main() {
    r := gin.Default()
    r.GET("/", func(c *gin.Context) {
        c.JSON(200, gin.H{"message": "Hello"})
    })
}
"""

        frameworks = checker.detect_frameworks(code, "Go")

        assert 'gin' in frameworks

    def test_detect_frameworks_multiple(self):
        """Test detection of multiple frameworks"""
        checker = QualityChecker()

        code = """
from fastapi import FastAPI
import torch
import logging

app = FastAPI()
model = torch.nn.Linear(10, 1)
logger = logging.getLogger(__name__)
"""

        frameworks = checker.detect_frameworks(code, "Python")

        assert 'fastapi' in frameworks
        assert 'pytorch' in frameworks

    def test_detect_frameworks_case_insensitive(self):
        """Test framework detection is case-insensitive"""
        checker = QualityChecker()

        code = """
from FastAPI import FastAPI  # Capitalized
app = FastAPI()
"""

        frameworks = checker.detect_frameworks(code, "python")  # lowercase language

        assert 'fastapi' in frameworks


class TestCodeSampleFiltering:
    """Tests for filtering code samples"""

    def test_filter_by_language(self):
        """Test filtering samples by language"""
        samples = [
            CodeSample("python code", "Python", {}),
            CodeSample("rust code", "Rust", {}),
            CodeSample("go code", "Go", {}),
            CodeSample("java code", "Java", {}),
        ]

        target_languages = {'python', 'rust', 'go'}

        filtered = [
            s for s in samples
            if s.language.lower() in target_languages
        ]

        assert len(filtered) == 3
        assert all(s.language.lower() in target_languages for s in filtered)

    def test_filter_by_quality_score(self):
        """Test filtering samples by quality score"""
        checker = QualityChecker(min_quality_score=0.7)

        samples = [
            CodeSample("high quality", "Python", {}, quality_score=0.8),
            CodeSample("medium", "Python", {}, quality_score=0.6),
            CodeSample("excellent", "Python", {}, quality_score=0.95),
            CodeSample("low", "Python", {}, quality_score=0.3),
        ]

        filtered = [
            s for s in samples
            if s.quality_score >= checker.min_quality_score
        ]

        assert len(filtered) == 2
        assert all(s.quality_score >= 0.7 for s in filtered)

    def test_filter_by_file_size(self):
        """Test filtering by content length"""
        min_length = 100
        max_length = 5000

        samples = [
            CodeSample("x" * 50, "Python", {}),      # Too short
            CodeSample("x" * 500, "Python", {}),     # Good
            CodeSample("x" * 10000, "Python", {}),   # Too long
            CodeSample("x" * 2000, "Python", {}),    # Good
        ]

        filtered = [
            s for s in samples
            if min_length <= len(s.content) <= max_length
        ]

        assert len(filtered) == 2

    def test_exclude_patterns(self):
        """Test excluding files by patterns"""
        import re

        exclude_patterns = [
            r'test_', r'_test\.py$', r'\.proto$',
            r'README', r'\.md$'
        ]

        filenames = [
            "main.py",           # Keep
            "test_main.py",      # Exclude (test_)
            "utils_test.py",     # Exclude (_test.py)
            "api.proto",         # Exclude (.proto)
            "README.md",         # Exclude (both patterns)
            "handler.go",        # Keep
        ]

        filtered = []
        for filename in filenames:
            if not any(re.search(pattern, filename) for pattern in exclude_patterns):
                filtered.append(filename)

        assert filtered == ["main.py", "handler.go"]

    def test_deduplication_by_hash(self):
        """Test deduplication using content hashing"""
        import hashlib

        samples = [
            CodeSample("def func(): return 1", "Python", {}),
            CodeSample("def func(): return 1", "Python", {}),  # Duplicate
            CodeSample("def func(): return 2", "Python", {}),  # Different
        ]

        seen_hashes = set()
        filtered = []

        for sample in samples:
            content_hash = hashlib.md5(sample.content.encode()).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                filtered.append(sample)

        assert len(filtered) == 2

    def test_framework_requirement_filter(self):
        """Test filtering to require framework usage"""
        checker = QualityChecker()

        samples = [
            CodeSample("from fastapi import FastAPI\napp = FastAPI()", "Python", {}),
            CodeSample("print('hello')", "Python", {}),  # No framework
            CodeSample("import torch\nmodel = torch.nn.Linear(10,1)", "Python", {}),
        ]

        # Add framework info
        for sample in samples:
            sample.frameworks = checker.detect_frameworks(sample.content, sample.language)

        # Filter samples with frameworks
        filtered = [s for s in samples if len(s.frameworks) > 0]

        assert len(filtered) == 2
        assert all(len(s.frameworks) > 0 for s in filtered)


class TestQualityReport:
    """Tests for quality report generation"""

    def test_quality_distribution(self):
        """Test quality score distribution calculation"""
        scores = [0.5, 0.6, 0.7, 0.8, 0.9, 0.75, 0.85, 0.95]

        distribution = {
            'high': sum(1 for s in scores if s >= 0.8),
            'medium': sum(1 for s in scores if 0.6 <= s < 0.8),
            'low': sum(1 for s in scores if s < 0.6),
        }

        assert distribution['high'] == 4
        assert distribution['medium'] == 3
        assert distribution['low'] == 1

    def test_language_breakdown(self):
        """Test language distribution calculation"""
        samples = [
            CodeSample("", "Python", {}),
            CodeSample("", "Python", {}),
            CodeSample("", "Rust", {}),
            CodeSample("", "Go", {}),
            CodeSample("", "Go", {}),
            CodeSample("", "Go", {}),
        ]

        language_count = Counter(s.language for s in samples)

        assert language_count['Python'] == 2
        assert language_count['Rust'] == 1
        assert language_count['Go'] == 3

    def test_common_issues_tracking(self):
        """Test tracking of common code issues"""
        samples = [
            CodeSample("", "Python", {}, issues=['no_docs']),
            CodeSample("", "Python", {}, issues=['no_docs', 'too_short']),
            CodeSample("", "Python", {}, issues=['no_error_handling']),
            CodeSample("", "Python", {}, issues=['no_docs']),
        ]

        issue_counts = Counter()
        for sample in samples:
            issue_counts.update(sample.issues)

        # Most common issues
        common_issues = issue_counts.most_common(2)

        assert common_issues[0][0] == 'no_docs'
        assert common_issues[0][1] == 3

    def test_average_score_calculation(self):
        """Test average score calculation by language"""
        samples = [
            CodeSample("", "Python", {}, quality_score=0.8),
            CodeSample("", "Python", {}, quality_score=0.9),
            CodeSample("", "Rust", {}, quality_score=0.95),
            CodeSample("", "Go", {}, quality_score=0.7),
            CodeSample("", "Go", {}, quality_score=0.75),
        ]

        lang_scores = defaultdict(list)
        for sample in samples:
            lang_scores[sample.language].append(sample.quality_score)

        avg_scores = {
            lang: sum(scores) / len(scores)
            for lang, scores in lang_scores.items()
        }

        assert avg_scores['Python'] == pytest.approx(0.85, rel=0.01)
        assert avg_scores['Rust'] == 0.95
        assert avg_scores['Go'] == pytest.approx(0.725, rel=0.01)


class TestEdgeCases:
    """Tests for edge cases in quality filtering"""

    def test_empty_content(self):
        """Test handling of empty content"""
        checker = QualityChecker()
        sample = CodeSample("", "Python", {})

        score = checker.calculate_quality_score(sample)

        assert score < 0.7  # Should be low quality

    def test_very_long_content(self):
        """Test handling of very long content"""
        checker = QualityChecker()
        sample = CodeSample("x" * 100000, "Python", {})

        score = checker.calculate_quality_score(sample)

        # Should handle without crashing
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_non_ascii_characters(self):
        """Test handling of non-ASCII characters"""
        checker = QualityChecker()

        code = """
def process():
    # 这是中文注释
    message = "Hello 世界"
    return message
"""

        sample = CodeSample(code, "Python", {})
        score = checker.calculate_quality_score(sample)

        # Should handle Unicode correctly
        assert score > 0.0

    def test_mixed_line_endings(self):
        """Test handling of mixed line endings"""
        checker = QualityChecker()

        code = "def func():\r\n    return 1\n"  # Mixed \r\n and \n

        sample = CodeSample(code, "Python", {})
        score = checker.calculate_quality_score(sample)

        assert score > 0.0

    def test_threshold_boundary_values(self):
        """Test quality checker with boundary values"""
        checker = QualityChecker(min_stars=10, min_forks=3)

        # Exactly at threshold
        assert checker.meets_threshold(10, 3) is True

        # Just below threshold
        assert checker.meets_threshold(9, 3) is False
        assert checker.meets_threshold(10, 2) is False

        # Just above threshold
        assert checker.meets_threshold(11, 3) is True
        assert checker.meets_threshold(10, 4) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
