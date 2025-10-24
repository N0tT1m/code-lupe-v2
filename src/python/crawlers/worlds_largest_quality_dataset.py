#!/usr/bin/env python3
"""
World's Largest Quality Code Dataset Builder
Exceeds The Stack (54M files) with quality filtering and validation
Target: 100M+ high-quality code files
"""

import os
import re
import ast
import json
import sqlite3
import hashlib
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from collections import defaultdict
import tempfile
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class QualityMetrics:
    """Quality metrics for code files"""
    file_path: str
    language: str
    lines_of_code: int
    comment_ratio: float
    complexity_score: float
    has_documentation: bool
    has_tests: bool
    code_style_score: float
    duplicate_hash: str
    repo_stars: int
    file_size_bytes: int
    
class AdvancedQualityChecker:
    """Advanced quality checking for code files"""
    
    def __init__(self):
        self.min_lines = 10
        self.max_lines = 3000
        self.min_complexity = 1
        self.max_comment_ratio = 0.8
        self.min_code_style_score = 0.3
        
        # Language-specific patterns
        self.language_patterns = {
            'python': {
                'functions': [r'def\s+\w+\s*\(', r'class\s+\w+'],
                'imports': [r'import\s+\w+', r'from\s+\w+\s+import'],
                'comments': [r'#.*', r'""".*?"""', r"'''.*?'''"],
                'keywords': ['def', 'class', 'import', 'if', 'for', 'while', 'try'],
                'bad_patterns': [r'print\s*\(\s*["\']test', r'TODO', r'FIXME', r'XXX']
            },
            'javascript': {
                'functions': [r'function\s+\w+', r'\w+\s*=>\s*', r'const\s+\w+\s*=\s*\('],
                'imports': [r'import.*from', r'require\s*\('],
                'comments': [r'//.*', r'/\*.*?\*/'],
                'keywords': ['function', 'const', 'let', 'var', 'if', 'for', 'while', 'try'],
                'bad_patterns': [r'console\.log\(', r'alert\(', r'TODO', r'FIXME']
            },
            'rust': {
                'functions': [r'fn\s+\w+', r'impl\s+.*\{'],
                'imports': [r'use\s+\w+', r'extern\s+crate'],
                'comments': [r'//.*', r'/\*.*?\*/', r'///.*'],
                'keywords': ['fn', 'struct', 'impl', 'use', 'if', 'match', 'for', 'while'],
                'bad_patterns': [r'println!\s*\(', r'panic!\s*\(', r'TODO', r'FIXME']
            },
            'go': {
                'functions': [r'func\s+\w+', r'func\s+\(\w+.*\)\s+\w+'],
                'imports': [r'import\s+"', r'import\s+\('],
                'comments': [r'//.*', r'/\*.*?\*/'],
                'keywords': ['func', 'package', 'import', 'if', 'for', 'switch', 'select'],
                'bad_patterns': [r'fmt\.Print', r'panic\(', r'TODO', r'FIXME']
            },
            'java': {
                'functions': [r'public.*\w+\s*\(', r'private.*\w+\s*\(', r'protected.*\w+\s*\('],
                'imports': [r'import\s+\w+'],
                'comments': [r'//.*', r'/\*.*?\*/', r'/\*\*.*?\*/'],
                'keywords': ['public', 'private', 'class', 'interface', 'if', 'for', 'while', 'try'],
                'bad_patterns': [r'System\.out\.print', r'TODO', r'FIXME']
            },
            'cpp': {
                'functions': [r'\w+\s+\w+\s*\(.*\)\s*\{', r'class\s+\w+'],
                'imports': [r'#include\s*[<"]', r'using\s+namespace'],
                'comments': [r'//.*', r'/\*.*?\*/'],
                'keywords': ['class', 'struct', 'namespace', 'if', 'for', 'while', 'try'],
                'bad_patterns': [r'cout\s*<<', r'printf\s*\(', r'TODO', r'FIXME']
            }
        }
    
    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension"""
        ext = Path(file_path).suffix.lower()
        
        ext_map = {
            '.py': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
            '.ts': 'javascript', '.tsx': 'javascript',  # TypeScript as JS variant
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.h': 'cpp',
            '.c': 'cpp',  # C as C++ variant for simplicity
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala'
        }
        
        return ext_map.get(ext)
    
    def calculate_complexity(self, content: str, language: str) -> float:
        """Calculate code complexity score"""
        if language == 'python':
            return self._python_complexity(content)
        else:
            return self._generic_complexity(content, language)
    
    def _python_complexity(self, content: str) -> float:
        """Calculate Python-specific complexity using AST"""
        try:
            tree = ast.parse(content)
            complexity = 0
            
            for node in ast.walk(tree):
                # Count decision points
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.FunctionDef):
                    complexity += 1
                elif isinstance(node, ast.ClassDef):
                    complexity += 2
                elif isinstance(node, ast.Lambda):
                    complexity += 1
            
            lines = len(content.split('\n'))
            return min(complexity / max(lines / 20, 1), 10)  # Normalize to 0-10
            
        except:
            return self._generic_complexity(content, 'python')
    
    def _generic_complexity(self, content: str, language: str) -> float:
        """Generic complexity calculation for any language"""
        patterns = self.language_patterns.get(language, {})
        complexity = 0
        lines = content.split('\n')
        
        # Count functions, classes, control structures
        for line in lines:
            line = line.strip()
            if not line or line.startswith(('*', '//', '#')):
                continue
                
            # Function/class definitions
            if patterns.get('functions'):
                for pattern in patterns['functions']:
                    if re.search(pattern, line):
                        complexity += 1
                        break
            
            # Control structures
            control_keywords = ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch']
            for keyword in control_keywords:
                if re.search(rf'\b{keyword}\b', line):
                    complexity += 1
                    break
        
        return min(complexity / max(len(lines) / 15, 1), 10)
    
    def calculate_comment_ratio(self, content: str, language: str) -> float:
        """Calculate ratio of comment lines to total lines"""
        patterns = self.language_patterns.get(language, {})
        comment_patterns = patterns.get('comments', [r'//.*', r'#.*'])
        
        lines = content.split('\n')
        comment_lines = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            for pattern in comment_patterns:
                if re.search(pattern, line):
                    comment_lines += 1
                    break
        
        return comment_lines / max(len(lines), 1)
    
    def check_documentation(self, content: str, language: str) -> bool:
        """Check if file has proper documentation"""
        doc_patterns = {
            'python': [r'""".*?"""', r"'''.*?'''", r'def.*:\s*"""', r'class.*:\s*"""'],
            'javascript': [r'/\*\*.*?\*/', r'@param', r'@return'],
            'rust': [r'///.*', r'//!.*', r'#\[doc'],
            'go': [r'//\s+\w+.*', r'//.*package'],
            'java': [r'/\*\*.*?\*/', r'@param', r'@return', r'@author'],
            'cpp': [r'/\*\*.*?\*/', r'///.*', r'@brief']
        }
        
        patterns = doc_patterns.get(language, [])
        for pattern in patterns:
            if re.search(pattern, content, re.DOTALL):
                return True
        
        return False
    
    def check_has_tests(self, content: str, language: str) -> bool:
        """Check if file contains test code"""
        test_patterns = {
            'python': [r'def test_', r'class Test', r'import unittest', r'import pytest', r'assert\s+'],
            'javascript': [r'describe\s*\(', r'it\s*\(', r'test\s*\(', r'expect\s*\(', r'assert'],
            'rust': [r'#\[test\]', r'#\[cfg\(test\)\]', r'assert!', r'assert_eq!'],
            'go': [r'func Test', r'testing\.T', r't\.Error', r't\.Fatal'],
            'java': [r'@Test', r'import.*junit', r'Assert\.', r'assertEquals'],
            'cpp': [r'TEST\s*\(', r'EXPECT_', r'ASSERT_', r'#include.*gtest']
        }
        
        patterns = test_patterns.get(language, [])
        for pattern in patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def calculate_style_score(self, content: str, language: str) -> float:
        """Calculate code style/quality score"""
        patterns = self.language_patterns.get(language, {})
        bad_patterns = patterns.get('bad_patterns', [])
        
        lines = content.split('\n')
        good_practices = 0
        bad_practices = 0
        
        # Check for bad patterns
        for line in lines:
            for pattern in bad_patterns:
                if re.search(pattern, line):
                    bad_practices += 1
        
        # Check for good patterns
        has_functions = any(re.search(pattern, content) for pattern in patterns.get('functions', []))
        has_imports = any(re.search(pattern, content) for pattern in patterns.get('imports', []))
        has_proper_structure = has_functions or has_imports
        
        if has_proper_structure:
            good_practices += 2
        
        # Check indentation consistency (for Python especially)
        if language == 'python':
            indent_consistent = self._check_python_indentation(content)
            if indent_consistent:
                good_practices += 1
        
        # Calculate score
        total_checks = good_practices + bad_practices + 1
        score = (good_practices + 1) / total_checks
        
        return min(max(score, 0), 1)
    
    def _check_python_indentation(self, content: str) -> bool:
        """Check if Python code has consistent indentation"""
        try:
            ast.parse(content)
            return True
        except IndentationError:
            return False
        except:
            return True  # Other errors don't indicate indentation issues
    
    def calculate_file_hash(self, content: str) -> str:
        """Calculate hash for duplicate detection"""
        # Normalize content for better duplicate detection
        normalized = re.sub(r'\s+', ' ', content.strip())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def evaluate_quality(self, file_path: str, content: str, repo_stars: int = 0) -> Optional[QualityMetrics]:
        """Evaluate overall quality of a code file"""
        language = self.detect_language(file_path)
        if not language:
            return None
        
        lines_of_code = len([line for line in content.split('\n') if line.strip()])
        
        # Basic size filters
        if lines_of_code < self.min_lines or lines_of_code > self.max_lines:
            return None
        
        # Calculate metrics
        comment_ratio = self.calculate_comment_ratio(content, language)
        complexity_score = self.calculate_complexity(content, language)
        has_documentation = self.check_documentation(content, language)
        has_tests = self.check_has_tests(content, language)
        code_style_score = self.calculate_style_score(content, language)
        duplicate_hash = self.calculate_file_hash(content)
        
        # Quality filters
        if comment_ratio > self.max_comment_ratio:  # Too many comments (likely docs)
            return None
        
        if complexity_score < self.min_complexity:  # Too simple
            return None
        
        if code_style_score < self.min_code_style_score:  # Poor style
            return None
        
        return QualityMetrics(
            file_path=file_path,
            language=language,
            lines_of_code=lines_of_code,
            comment_ratio=comment_ratio,
            complexity_score=complexity_score,
            has_documentation=has_documentation,
            has_tests=has_tests,
            code_style_score=code_style_score,
            duplicate_hash=duplicate_hash,
            repo_stars=repo_stars,
            file_size_bytes=len(content.encode())
        )

class WorldLargestDatasetBuilder:
    """Build the world's largest quality code dataset"""
    
    def __init__(self, output_dir: str = "./world_largest_dataset", github_tokens: List[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.github_tokens = github_tokens or []
        self.quality_checker = AdvancedQualityChecker()
        
        # Database for tracking
        self.db_path = self.output_dir / "quality_dataset.db"
        self.init_database()
        
        # Quality thresholds for world-class dataset
        self.min_repo_stars = 5  # Minimum stars for repo inclusion
        self.target_files = 100_000_000  # 100M files (2x The Stack)
        self.max_duplicates_per_hash = 3  # Max similar files
        
        # Statistics
        self.stats = {
            'repos_processed': 0,
            'files_processed': 0,
            'files_accepted': 0,
            'files_rejected': 0,
            'duplicates_filtered': 0,
            'languages': defaultdict(int),
            'quality_scores': []
        }
    
    def init_database(self):
        """Initialize SQLite database for quality tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quality_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                repo_url TEXT,
                language TEXT,
                lines_of_code INTEGER,
                comment_ratio REAL,
                complexity_score REAL,
                has_documentation BOOLEAN,
                has_tests BOOLEAN,
                code_style_score REAL,
                duplicate_hash TEXT,
                repo_stars INTEGER,
                file_size_bytes INTEGER,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_duplicate_hash ON quality_files(duplicate_hash);
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_language ON quality_files(language);
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_quality_score ON quality_files(quality_score);
        ''')
        
        conn.commit()
        conn.close()
    
    def calculate_overall_quality_score(self, metrics: QualityMetrics) -> float:
        """Calculate overall quality score (0-100)"""
        score = 0
        
        # Base code quality (40 points)
        score += metrics.complexity_score * 4  # 0-40 points
        score += metrics.code_style_score * 20  # 0-20 points
        
        # Documentation bonus (15 points)
        if metrics.has_documentation:
            score += 15
        
        # Test bonus (15 points)
        if metrics.has_tests:
            score += 15
        
        # Repository popularity bonus (10 points)
        if metrics.repo_stars > 100:
            score += min(metrics.repo_stars / 1000, 10)
        
        # File size bonus (prefer substantial files) (10 points)
        if 500 <= metrics.lines_of_code <= 1000:
            score += 10
        elif 100 <= metrics.lines_of_code <= 500:
            score += 5
        
        # Comment ratio penalty (too many or too few comments)
        ideal_comment_ratio = 0.15
        comment_penalty = abs(metrics.comment_ratio - ideal_comment_ratio) * 20
        score -= min(comment_penalty, 10)
        
        return max(min(score, 100), 0)
    
    def is_duplicate(self, duplicate_hash: str) -> bool:
        """Check if we've seen this code before"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT COUNT(*) FROM quality_files WHERE duplicate_hash = ?',
            (duplicate_hash,)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count >= self.max_duplicates_per_hash
    
    def should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included based on path"""
        # Skip certain directories
        skip_dirs = {
            '.git', 'node_modules', 'target', 'build', 'dist', '__pycache__',
            '.pytest_cache', 'vendor', '.venv', 'venv', '.env', 'env',
            'coverage', '.coverage', 'htmlcov', '.tox', '.mypy_cache',
            'CMakeFiles', '.gradle', 'bin', 'obj', 'Debug', 'Release'
        }
        
        # Skip if any parent directory is in skip list
        for part in file_path.parts:
            if part in skip_dirs:
                return False
        
        # Skip certain file patterns
        skip_patterns = [
            r'\.min\.(js|css)$',  # Minified files
            r'\.bundle\.(js|css)$',  # Bundle files
            r'\.generated\.',  # Generated files
            r'\.lock$',  # Lock files
            r'\.log$',  # Log files
            r'^test_.*\.py$',  # Simple test files
            r'_test\.go$',  # Go test files
            r'Test\.java$',  # Java test files
        ]
        
        file_name = file_path.name
        for pattern in skip_patterns:
            if re.search(pattern, file_name):
                return False
        
        # File size limits
        try:
            if file_path.stat().st_size > 500_000:  # 500KB max
                return False
            if file_path.stat().st_size < 100:  # 100 bytes min
                return False
        except:
            return False
        
        return True
    
    def process_repository(self, repo_url: str) -> Dict:
        """Process a single repository for quality code"""
        logger.info(f"🔍 Processing repository: {repo_url}")
        
        try:
            # Get repo metadata
            repo_stars = self.get_repo_stars(repo_url)
            if repo_stars < self.min_repo_stars:
                logger.info(f"⏭️ Skipping {repo_url} (only {repo_stars} stars)")
                return {'repo': repo_url, 'files_added': 0, 'reason': 'insufficient_stars'}
            
            # Clone repository
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"
                
                clone_cmd = [
                    'git', 'clone', '--depth', '1', '--quiet',
                    repo_url, str(repo_dir)
                ]
                
                result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    logger.warning(f"⚠️ Failed to clone {repo_url}")
                    return {'repo': repo_url, 'files_added': 0, 'reason': 'clone_failed'}
                
                # Process code files
                files_added = 0
                files_processed = 0
                
                for file_path in repo_dir.rglob("*"):
                    if not file_path.is_file():
                        continue
                    
                    if not self.should_include_file(file_path):
                        continue
                    
                    # Check if it's a code file
                    language = self.quality_checker.detect_language(str(file_path))
                    if not language:
                        continue
                    
                    try:
                        # Read file content
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        files_processed += 1
                        
                        # Quality evaluation
                        metrics = self.quality_checker.evaluate_quality(
                            str(file_path.relative_to(repo_dir)),
                            content,
                            repo_stars
                        )
                        
                        if not metrics:
                            continue
                        
                        # Check for duplicates
                        if self.is_duplicate(metrics.duplicate_hash):
                            self.stats['duplicates_filtered'] += 1
                            continue
                        
                        # Calculate final quality score
                        quality_score = self.calculate_overall_quality_score(metrics)
                        
                        # Quality threshold (world-class dataset needs high quality)
                        if quality_score < 30:  # Minimum 30/100 quality score
                            continue
                        
                        # Save to database
                        self.save_quality_file(repo_url, metrics, quality_score)
                        files_added += 1
                        
                        # Update statistics
                        self.stats['languages'][metrics.language] += 1
                        self.stats['quality_scores'].append(quality_score)
                        
                        if files_added % 100 == 0:
                            logger.info(f"📄 Added {files_added} quality files from {repo_url}")
                        
                    except Exception as e:
                        logger.debug(f"Error processing {file_path}: {e}")
                        continue
                
                self.stats['repos_processed'] += 1
                self.stats['files_processed'] += files_processed
                self.stats['files_accepted'] += files_added
                
                logger.info(f"✅ {repo_url}: {files_added}/{files_processed} files added")
                
                return {
                    'repo': repo_url,
                    'files_added': files_added,
                    'files_processed': files_processed,
                    'repo_stars': repo_stars
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing {repo_url}: {e}")
            return {'repo': repo_url, 'files_added': 0, 'reason': 'error', 'error': str(e)}
    
    def get_repo_stars(self, repo_url: str) -> int:
        """Get repository star count"""
        try:
            # Extract owner/repo from URL
            parts = repo_url.replace('https://github.com/', '').split('/')
            if len(parts) < 2:
                return 0
            
            owner, repo = parts[0], parts[1]
            
            # Simple API call (you'd want to use the token rotation here)
            import requests
            headers = {}
            if self.github_tokens:
                headers['Authorization'] = f'token {self.github_tokens[0]}'
            
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('stargazers_count', 0)
            
        except Exception as e:
            logger.debug(f"Error getting stars for {repo_url}: {e}")
        
        return 0
    
    def save_quality_file(self, repo_url: str, metrics: QualityMetrics, quality_score: float):
        """Save quality file to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO quality_files (
                file_path, repo_url, language, lines_of_code, comment_ratio,
                complexity_score, has_documentation, has_tests, code_style_score,
                duplicate_hash, repo_stars, file_size_bytes, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics.file_path, repo_url, metrics.language, metrics.lines_of_code,
            metrics.comment_ratio, metrics.complexity_score, metrics.has_documentation,
            metrics.has_tests, metrics.code_style_score, metrics.duplicate_hash,
            metrics.repo_stars, metrics.file_size_bytes, quality_score
        ))
        
        conn.commit()
        conn.close()
    
    def get_current_count(self) -> int:
        """Get current count of quality files"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM quality_files')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def build_world_largest_dataset(self, repo_urls: List[str]):
        """Build the world's largest quality code dataset"""
        logger.info(f"🌍 Building World's Largest Quality Code Dataset")
        logger.info(f"🎯 Target: {self.target_files:,} high-quality files")
        logger.info(f"📊 Processing {len(repo_urls):,} repositories")
        
        start_time = time.time()
        current_count = self.get_current_count()
        
        logger.info(f"📈 Starting with {current_count:,} existing files")
        
        # Process repositories in parallel
        max_workers = min(len(self.github_tokens) if self.github_tokens else 1, 10)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit repository processing tasks
            future_to_repo = {
                executor.submit(self.process_repository, repo_url): repo_url
                for repo_url in repo_urls
            }
            
            processed = 0
            for future in as_completed(future_to_repo):
                repo_url = future_to_repo[future]
                processed += 1
                
                try:
                    result = future.result()
                    
                    if processed % 50 == 0:
                        current_count = self.get_current_count()
                        elapsed = time.time() - start_time
                        rate = current_count / elapsed if elapsed > 0 else 0
                        
                        logger.info(f"📊 Progress: {processed}/{len(repo_urls)} repos | "
                                  f"{current_count:,} files | {rate:.0f} files/sec")
                        
                        # Check if we've reached our target
                        if current_count >= self.target_files:
                            logger.info(f"🎯 TARGET REACHED! {current_count:,} files collected")
                            break
                
                except Exception as e:
                    logger.error(f"❌ Error processing {repo_url}: {e}")
        
        # Final statistics
        final_count = self.get_current_count()
        total_time = time.time() - start_time
        
        self.generate_final_report(final_count, total_time)
        
        return final_count
    
    def generate_final_report(self, final_count: int, total_time: float):
        """Generate final quality report"""
        logger.info(f"\n🎉 WORLD'S LARGEST QUALITY DATASET COMPLETE!")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   • Total files: {final_count:,}")
        logger.info(f"   • Processing time: {total_time/3600:.1f} hours")
        logger.info(f"   • Average quality score: {sum(self.stats['quality_scores'])/len(self.stats['quality_scores']):.1f}/100")
        
        # Language distribution
        logger.info(f"🔤 Language Distribution:")
        for lang, count in sorted(self.stats['languages'].items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"   • {lang}: {count:,} files")
        
        # Compare to The Stack
        the_stack_files = 54_000_000
        improvement = (final_count / the_stack_files - 1) * 100
        
        logger.info(f"\n🏆 COMPARISON TO THE STACK:")
        logger.info(f"   • The Stack: {the_stack_files:,} files")
        logger.info(f"   • Our dataset: {final_count:,} files")
        logger.info(f"   • Improvement: +{improvement:.1f}% larger")
        
        if final_count > the_stack_files:
            logger.info(f"🥇 WORLD RECORD: Largest curated code dataset!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="World's Largest Quality Code Dataset Builder")
    parser.add_argument("--tokens", nargs='+', help="GitHub API tokens")
    parser.add_argument("--target", type=int, default=100_000_000, help="Target number of files")
    parser.add_argument("--min-stars", type=int, default=5, help="Minimum repo stars")
    parser.add_argument("--repo-list", help="File containing repository URLs")
    parser.add_argument("--output-dir", default="./world_largest_dataset", help="Output directory")
    
    args = parser.parse_args()
    
    # Load repository URLs
    if args.repo_list and os.path.exists(args.repo_list):
        with open(args.repo_list, 'r') as f:
            repo_urls = [line.strip() for line in f if line.strip()]
    else:
        # Use ultra massive collector to get repos first
        logger.info("⚠️ No repo list provided. Run ultra_massive_repo_collector.py first!")
        return
    
    # Initialize builder
    builder = WorldLargestDatasetBuilder(
        output_dir=args.output_dir,
        github_tokens=args.tokens or []
    )
    builder.target_files = args.target
    builder.min_repo_stars = args.min_stars
    
    # Build the dataset
    final_count = builder.build_world_largest_dataset(repo_urls)
    
    logger.info(f"\n🌟 Mission accomplished: {final_count:,} quality files!")

if __name__ == "__main__":
    main()
