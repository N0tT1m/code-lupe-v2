#!/usr/bin/env python3
"""
High-Throughput Data Ingestion Pipeline V2
Uses Redis for job queuing and Elasticsearch for code search
Replaces slow file-system based processing

Architecture:
1. Crawler → Redis Queue (repo_jobs)
2. Worker Pool → Download repos → Redis Queue (file_jobs)
3. File Processor Pool → Parse/analyze → Elasticsearch + PostgreSQL
4. Trainer → Query Elasticsearch for high-quality samples
"""

import os
import sys
import json
import time
import logging
import hashlib
import multiprocessing as mp
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import re

import redis
from elasticsearch import Elasticsearch, helpers
import psycopg2
from psycopg2 import pool
import git

# Import security scanners
from security_scanner import SecurityScanner
from secret_scanner import SecretScanner
from license_checker import LicenseChecker

# Import tracing
from tracing import get_tracer, trace_function

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(process)d] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class PipelineConfig:
    """Centralized pipeline configuration"""

    # Redis configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    # Redis queues
    QUEUE_REPOS = "pipeline:repos"
    QUEUE_FILES = "pipeline:files"
    QUEUE_REPOS_HIGH = "pipeline:repos:high"  # Priority queues
    QUEUE_REPOS_NORMAL = "pipeline:repos:normal"
    QUEUE_REPOS_LOW = "pipeline:repos:low"
    QUEUE_DEAD_LETTER = "pipeline:dead_letter"  # Failed jobs
    SET_PROCESSED_REPOS = "pipeline:processed:repos"
    SET_PROCESSED_FILES = "pipeline:processed:files"
    HASH_REPO_METADATA = "pipeline:meta:repos"

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # seconds

    # Elasticsearch configuration
    ES_HOST = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    ES_INDEX_CODE = "codelupe-code"
    ES_INDEX_REPOS = "codelupe-repos"

    # PostgreSQL configuration
    DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
    DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    DB_NAME = os.getenv("POSTGRES_DB", "coding_db")
    DB_USER = os.getenv("POSTGRES_USER", "coding_user")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "coding_pass")
    DB_POOL_MIN = 2
    DB_POOL_MAX = 10

    # Processing configuration
    REPO_DOWNLOAD_DIR = os.getenv("REPOS_DIR", "/app/repos")
    MAX_FILE_SIZE_KB = 500  # 500KB max file size
    MIN_FILE_SIZE_BYTES = 100  # 100 bytes min

    # Worker configuration
    REPO_WORKERS = int(os.getenv("REPO_WORKERS", "4"))
    FILE_WORKERS = int(os.getenv("FILE_WORKERS", "8"))

    # Quality filtering
    MIN_QUALITY_FOR_TRAINING = float(os.getenv("MIN_QUALITY_THRESHOLD", "0.7"))  # Only index high-quality samples

    TARGET_LANGUAGES = {
        '.rs': 'Rust',
        '.go': 'Go',
        '.py': 'Python',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.dart': 'Dart',
        '.java': 'Java',
        '.cpp': 'C++',
        '.cc': 'C++',
        '.c': 'C',
        '.h': 'C/C++',
        '.sql': 'SQL',
    }

    # Exclude patterns
    EXCLUDE_PATHS = {
        'node_modules', 'vendor', 'target', 'build', 'dist',
        '.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
        'coverage', '.nyc_output', 'migrations', 'alembic',
    }

    EXCLUDE_EXTENSIONS = {
        '.lock', '.json', '.yaml', '.yml', '.toml', '.ini',
        '.md', '.txt', '.log', '.csv', '.xml',
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot',
        '.exe', '.dll', '.so', '.dylib',
    }

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class RepoJob:
    """Repository download job"""
    repo_url: str
    full_name: str
    stars: int
    forks: int
    language: str
    quality_score: int
    topics: List[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data: str) -> 'RepoJob':
        return RepoJob(**json.loads(data))

@dataclass
class FileJob:
    """File processing job"""
    repo_full_name: str
    file_path: str
    file_relative_path: str
    language: str
    file_size: int
    retry_count: int = 0  # Track retries

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data: str) -> 'FileJob':
        data_dict = json.loads(data)
        # Handle backward compatibility
        if 'retry_count' not in data_dict:
            data_dict['retry_count'] = 0
        return FileJob(**data_dict)

@dataclass
class CodeSample:
    """Processed code sample"""
    id: str  # hash of content
    content: str
    language: str
    file_path: str
    repo_full_name: str
    lines_of_code: int
    file_size: int
    quality_score: float
    has_comments: bool
    has_docstrings: bool
    complexity_score: float
    indexed_at: str

    def to_dict(self) -> Dict:
        return asdict(self)

# ============================================================================
# REDIS QUEUE MANAGER
# ============================================================================

class RedisQueueManager:
    """Manages Redis-based job queues"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        logger.info(f"Connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")

    def enqueue_repo(self, job: RepoJob) -> bool:
        """Add repository to processing queue"""
        # Check if already processed
        if self.is_repo_processed(job.full_name):
            logger.debug(f"Repo already processed: {job.full_name}")
            return False

        # Add to queue
        self.redis_client.rpush(self.config.QUEUE_REPOS, job.to_json())
        logger.info(f"Enqueued repo: {job.full_name}")
        return True

    def dequeue_repo(self, timeout: int = 1) -> Optional[RepoJob]:
        """Get next repository job from queue (blocking)"""
        result = self.redis_client.blpop(self.config.QUEUE_REPOS, timeout=timeout)
        if result:
            _, data = result
            return RepoJob.from_json(data)
        return None

    def enqueue_file(self, job: FileJob) -> bool:
        """Add file to processing queue"""
        file_hash = hashlib.md5(f"{job.repo_full_name}:{job.file_relative_path}".encode()).hexdigest()

        # Check if already processed
        if self.redis_client.sismember(self.config.SET_PROCESSED_FILES, file_hash):
            return False

        # Add to queue
        self.redis_client.rpush(self.config.QUEUE_FILES, job.to_json())
        return True

    def dequeue_file(self, timeout: int = 1) -> Optional[FileJob]:
        """Get next file job from queue (blocking)"""
        result = self.redis_client.blpop(self.config.QUEUE_FILES, timeout=timeout)
        if result:
            _, data = result
            return FileJob.from_json(data)
        return None

    def mark_repo_processed(self, full_name: str):
        """Mark repository as processed"""
        self.redis_client.sadd(self.config.SET_PROCESSED_REPOS, full_name)

    def is_repo_processed(self, full_name: str) -> bool:
        """Check if repository already processed"""
        return self.redis_client.sismember(self.config.SET_PROCESSED_REPOS, full_name)

    def mark_file_processed(self, repo_full_name: str, file_relative_path: str):
        """Mark file as processed"""
        file_hash = hashlib.md5(f"{repo_full_name}:{file_relative_path}".encode()).hexdigest()
        self.redis_client.sadd(self.config.SET_PROCESSED_FILES, file_hash)

    def get_queue_lengths(self) -> Dict[str, int]:
        """Get current queue lengths"""
        return {
            'repos': self.redis_client.llen(self.config.QUEUE_REPOS),
            'files': self.redis_client.llen(self.config.QUEUE_FILES),
            'repos_high': self.redis_client.llen(self.config.QUEUE_REPOS_HIGH),
            'repos_normal': self.redis_client.llen(self.config.QUEUE_REPOS_NORMAL),
            'repos_low': self.redis_client.llen(self.config.QUEUE_REPOS_LOW),
            'dead_letter': self.redis_client.llen(self.config.QUEUE_DEAD_LETTER),
            'processed_repos': self.redis_client.scard(self.config.SET_PROCESSED_REPOS),
            'processed_files': self.redis_client.scard(self.config.SET_PROCESSED_FILES),
        }

    def enqueue_repo_priority(self, job: RepoJob, priority: str = 'normal') -> bool:
        """Add repository to priority queue"""
        if self.is_repo_processed(job.full_name):
            logger.debug(f"Repo already processed: {job.full_name}")
            return False

        queue_map = {
            'high': self.config.QUEUE_REPOS_HIGH,
            'normal': self.config.QUEUE_REPOS_NORMAL,
            'low': self.config.QUEUE_REPOS_LOW,
        }

        queue = queue_map.get(priority, self.config.QUEUE_REPOS_NORMAL)
        self.redis_client.rpush(queue, job.to_json())
        logger.info(f"Enqueued repo to {priority} priority: {job.full_name}")
        return True

    def dequeue_repo_priority(self, timeout: int = 1) -> Optional[RepoJob]:
        """Dequeue from highest priority queue first"""
        for queue in [self.config.QUEUE_REPOS_HIGH, self.config.QUEUE_REPOS_NORMAL, self.config.QUEUE_REPOS_LOW]:
            result = self.redis_client.blpop(queue, timeout=timeout)
            if result:
                _, data = result
                return RepoJob.from_json(data)
        # Fallback to regular queue for backward compatibility
        return self.dequeue_repo(timeout=0)

    def move_to_dead_letter(self, job: any, error: Exception, queue_name: str):
        """Move failed job to dead letter queue"""
        dead_letter_entry = {
            'job': asdict(job) if hasattr(job, '__dataclass_fields__') else str(job),
            'error': str(error),
            'error_type': type(error).__name__,
            'queue': queue_name,
            'timestamp': datetime.utcnow().isoformat(),
            'retry_count': getattr(job, 'retry_count', 0)
        }

        self.redis_client.rpush(
            self.config.QUEUE_DEAD_LETTER,
            json.dumps(dead_letter_entry)
        )
        logger.error(f"Moved job to dead letter queue: {dead_letter_entry}")

    def retry_job(self, job: FileJob) -> bool:
        """Retry a failed job if under retry limit"""
        if job.retry_count >= self.config.MAX_RETRIES:
            return False

        job.retry_count += 1
        delay = self.config.RETRY_DELAY_BASE ** job.retry_count
        time.sleep(delay)

        self.redis_client.rpush(self.config.QUEUE_FILES, job.to_json())
        logger.info(f"Retrying job (attempt {job.retry_count}/{self.config.MAX_RETRIES}): {job.file_relative_path}")
        return True

# ============================================================================
# ELASTICSEARCH MANAGER
# ============================================================================

class ElasticsearchManager:
    """Manages Elasticsearch indexing and search"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.es = Elasticsearch([config.ES_HOST], request_timeout=30)
        logger.info(f"Connected to Elasticsearch at {config.ES_HOST}")
        self._create_indices()

    def _create_indices(self):
        """Create Elasticsearch indices with mappings"""

        # Code index mapping
        code_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "language": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "repo_full_name": {"type": "keyword"},
                    "lines_of_code": {"type": "integer"},
                    "file_size": {"type": "integer"},
                    "quality_score": {"type": "float"},
                    "has_comments": {"type": "boolean"},
                    "has_docstrings": {"type": "boolean"},
                    "complexity_score": {"type": "float"},
                    "indexed_at": {"type": "date"},
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.max_result_window": 50000,
            }
        }

        # Create code index
        if not self.es.indices.exists(index=self.config.ES_INDEX_CODE):
            self.es.indices.create(index=self.config.ES_INDEX_CODE, body=code_mapping)
            logger.info(f"Created index: {self.config.ES_INDEX_CODE}")

    def index_code_sample(self, sample: CodeSample) -> bool:
        """Index a code sample"""
        try:
            self.es.index(
                index=self.config.ES_INDEX_CODE,
                id=sample.id,
                document=sample.to_dict()
            )
            return True
        except Exception as e:
            logger.error(f"Failed to index code sample {sample.id}: {e}")
            return False

    def bulk_index_code_samples(self, samples: List[CodeSample]) -> int:
        """Bulk index code samples"""
        actions = [
            {
                "_index": self.config.ES_INDEX_CODE,
                "_id": sample.id,
                "_source": sample.to_dict()
            }
            for sample in samples
        ]

        try:
            success, failed = helpers.bulk(self.es, actions, raise_on_error=False)
            logger.info(f"Bulk indexed {success} code samples, {len(failed)} failed")
            return success
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return 0

    def search_high_quality_code(self, min_quality: float = 0.7, limit: int = 10000) -> List[Dict]:
        """Search for high-quality code samples"""
        query = {
            "query": {
                "range": {
                    "quality_score": {
                        "gte": min_quality
                    }
                }
            },
            "sort": [
                {"quality_score": {"order": "desc"}},
                {"indexed_at": {"order": "desc"}}
            ],
            "size": limit
        }

        try:
            response = self.es.search(index=self.config.ES_INDEX_CODE, body=query)
            return [hit['_source'] for hit in response['hits']['hits']]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

# ============================================================================
# CODE QUALITY ANALYZER
# ============================================================================

class CodeQualityAnalyzer:
    """Analyzes code quality"""

    @staticmethod
    def analyze(content: str, language: str) -> Dict:
        """Analyze code quality"""
        lines = content.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]

        # Basic metrics
        lines_of_code = len(non_empty_lines)
        file_size = len(content)

        # Comment detection
        comment_patterns = {
            'Python': [r'^\s*#', r'^\s*"""', r"^\s*'''"],
            'JavaScript': [r'^\s*//', r'^\s*/\*'],
            'TypeScript': [r'^\s*//', r'^\s*/\*'],
            'Rust': [r'^\s*//', r'^\s*/\*'],
            'Go': [r'^\s*//', r'^\s*/\*'],
            'Java': [r'^\s*//', r'^\s*/\*'],
            'C++': [r'^\s*//', r'^\s*/\*'],
            'C': [r'^\s*//', r'^\s*/\*'],
        }

        has_comments = False
        has_docstrings = False
        comment_lines = 0

        patterns = comment_patterns.get(language, [r'^\s*//'])
        for line in lines:
            for pattern in patterns:
                if re.match(pattern, line):
                    comment_lines += 1
                    has_comments = True
                    if '"""' in line or "'''" in line or '/**' in line:
                        has_docstrings = True
                    break

        # Complexity score (simple heuristic)
        complexity_indicators = [
            'if ', 'else', 'elif', 'for ', 'while ', 'switch', 'case ',
            'try', 'catch', 'except', 'async', 'await', 'match'
        ]
        complexity_count = sum(content.lower().count(indicator) for indicator in complexity_indicators)
        complexity_score = min(complexity_count / (lines_of_code + 1), 1.0)

        # Quality score calculation
        quality_score = 0.0

        # Length (prefer medium-length files)
        if 50 <= lines_of_code <= 500:
            quality_score += 0.3
        elif 20 <= lines_of_code < 50 or 500 < lines_of_code <= 1000:
            quality_score += 0.2
        elif lines_of_code > 10:
            quality_score += 0.1

        # Comments (prefer well-documented code)
        comment_ratio = comment_lines / (lines_of_code + 1)
        if 0.1 <= comment_ratio <= 0.3:
            quality_score += 0.3
        elif 0.05 <= comment_ratio < 0.1:
            quality_score += 0.15

        # Docstrings
        if has_docstrings:
            quality_score += 0.2

        # Complexity (prefer moderate complexity)
        if 0.1 <= complexity_score <= 0.5:
            quality_score += 0.2
        elif 0.05 <= complexity_score < 0.1:
            quality_score += 0.1

        return {
            'lines_of_code': lines_of_code,
            'file_size': file_size,
            'quality_score': quality_score,
            'has_comments': has_comments,
            'has_docstrings': has_docstrings,
            'complexity_score': complexity_score,
        }

# ============================================================================
# WORKERS
# ============================================================================

def repo_download_worker(worker_id: int, config: PipelineConfig):
    """Worker that downloads repositories"""
    logger.info(f"Repo worker {worker_id} started")

    queue_mgr = RedisQueueManager(config)

    while True:
        try:
            # Get job from queue
            job = queue_mgr.dequeue_repo(timeout=5)
            if not job:
                continue

            logger.info(f"Worker {worker_id}: Processing repo {job.full_name}")

            # Clone repository
            repo_path = Path(config.REPO_DOWNLOAD_DIR) / job.full_name
            if repo_path.exists():
                logger.info(f"Repo already exists: {job.full_name}")
            else:
                try:
                    repo_path.parent.mkdir(parents=True, exist_ok=True)
                    git.Repo.clone_from(
                        job.repo_url,
                        repo_path,
                        depth=1,
                        single_branch=True
                    )
                    logger.info(f"Cloned repo: {job.full_name}")
                except Exception as e:
                    logger.error(f"Failed to clone {job.full_name}: {e}")
                    continue

            # Scan for files and enqueue
            enqueued = 0
            for file_path in repo_path.rglob('*'):
                if not file_path.is_file():
                    continue

                # Check if in excluded paths
                if any(excluded in file_path.parts for excluded in config.EXCLUDE_PATHS):
                    continue

                # Check extension
                ext = file_path.suffix.lower()
                if ext not in config.TARGET_LANGUAGES:
                    continue

                if ext in config.EXCLUDE_EXTENSIONS:
                    continue

                # Check file size
                try:
                    file_size = file_path.stat().st_size
                    if file_size < config.MIN_FILE_SIZE_BYTES:
                        continue
                    if file_size > config.MAX_FILE_SIZE_KB * 1024:
                        continue
                except:
                    continue

                # Create file job
                file_job = FileJob(
                    repo_full_name=job.full_name,
                    file_path=str(file_path),
                    file_relative_path=str(file_path.relative_to(repo_path)),
                    language=config.TARGET_LANGUAGES[ext],
                    file_size=file_size
                )

                if queue_mgr.enqueue_file(file_job):
                    enqueued += 1

            logger.info(f"Worker {worker_id}: Enqueued {enqueued} files from {job.full_name}")

            # Mark repo as processed
            queue_mgr.mark_repo_processed(job.full_name)

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id} shutting down")
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
            time.sleep(1)

def file_processor_worker(worker_id: int, config: PipelineConfig):
    """Worker that processes individual files"""
    logger.info(f"File worker {worker_id} started")

    queue_mgr = RedisQueueManager(config)
    es_mgr = ElasticsearchManager(config)
    analyzer = CodeQualityAnalyzer()

    # Initialize security scanners
    security_scanner = SecurityScanner()
    secret_scanner = SecretScanner()
    license_checker = LicenseChecker()

    batch = []
    batch_size = 50

    # Stats tracking
    stats = {
        'processed': 0,
        'skipped_low_quality': 0,
        'skipped_malicious': 0,
        'skipped_secrets': 0,
        'skipped_license': 0,
    }

    while True:
        try:
            # Get job from queue
            job = queue_mgr.dequeue_file(timeout=5)
            if not job:
                # Flush batch if timeout
                if batch:
                    es_mgr.bulk_index_code_samples(batch)
                    batch = []
                continue

            logger.debug(f"Worker {worker_id}: Processing file {job.file_relative_path}")

            # Read file content
            try:
                with open(job.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read {job.file_path}: {e}")
                # Try to retry or move to dead letter queue
                if not queue_mgr.retry_job(job):
                    queue_mgr.move_to_dead_letter(job, e, 'files')
                continue

            # Analyze quality
            analysis = analyzer.analyze(content, job.language)

            # Skip low quality - only index samples that meet training threshold
            if analysis['quality_score'] < config.MIN_QUALITY_FOR_TRAINING:
                logger.debug(f"Skipping low quality file (score: {analysis['quality_score']:.2f}): {job.file_relative_path}")
                stats['skipped_low_quality'] += 1
                continue

            # SECURITY SAFEGUARD 1: Check for malicious code
            is_secure, security_issues = security_scanner.scan_code(content, job.language)
            if not is_secure:
                logger.warning(
                    f"SECURITY: Skipping file with {len(security_issues)} critical issues: "
                    f"{job.file_relative_path}"
                )
                stats['skipped_malicious'] += 1
                continue

            # SECURITY SAFEGUARD 2: Check for hardcoded secrets
            has_no_secrets, secrets = secret_scanner.scan_code(content, job.language)
            if not has_no_secrets:
                logger.warning(
                    f"SECRETS: Skipping file with {len(secrets)} potential secrets: "
                    f"{job.file_relative_path}"
                )
                stats['skipped_secrets'] += 1
                continue

            # SECURITY SAFEGUARD 3: Check license compliance
            is_license_safe, license_match = license_checker.scan_file(content, job.file_relative_path)
            if not is_license_safe:
                logger.warning(
                    f"LICENSE: Skipping file with restrictive license: "
                    f"{job.file_relative_path} ({license_match.license_name if license_match else 'Unknown'})"
                )
                stats['skipped_license'] += 1
                continue

            # All safeguards passed - create code sample
            stats['processed'] += 1
            content_hash = hashlib.md5(content.encode()).hexdigest()
            sample = CodeSample(
                id=content_hash,
                content=content,
                language=job.language,
                file_path=job.file_relative_path,
                repo_full_name=job.repo_full_name,
                lines_of_code=analysis['lines_of_code'],
                file_size=analysis['file_size'],
                quality_score=analysis['quality_score'],
                has_comments=analysis['has_comments'],
                has_docstrings=analysis['has_docstrings'],
                complexity_score=analysis['complexity_score'],
                indexed_at=datetime.utcnow().isoformat()
            )

            # Add to batch
            batch.append(sample)

            # Flush batch if full
            if len(batch) >= batch_size:
                es_mgr.bulk_index_code_samples(batch)
                batch = []

            # Mark file as processed
            queue_mgr.mark_file_processed(job.repo_full_name, job.file_relative_path)

            # Log stats periodically (every 100 files)
            total_checked = sum(stats.values())
            if total_checked % 100 == 0:
                logger.info(
                    f"Worker {worker_id} stats: "
                    f"processed={stats['processed']}, "
                    f"skipped_quality={stats['skipped_low_quality']}, "
                    f"skipped_malicious={stats['skipped_malicious']}, "
                    f"skipped_secrets={stats['skipped_secrets']}, "
                    f"skipped_license={stats['skipped_license']}"
                )

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id} shutting down")
            logger.info(f"Final stats: {stats}")
            # Flush remaining batch
            if batch:
                es_mgr.bulk_index_code_samples(batch)
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
            time.sleep(1)

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    """Main pipeline orchestrator"""
    logger.info("Starting CodeLupe Data Pipeline V2")

    config = PipelineConfig()

    # Start repo download workers
    repo_workers = []
    for i in range(config.REPO_WORKERS):
        p = mp.Process(target=repo_download_worker, args=(i, config))
        p.start()
        repo_workers.append(p)

    # Start file processor workers
    file_workers = []
    for i in range(config.FILE_WORKERS):
        p = mp.Process(target=file_processor_worker, args=(i, config))
        p.start()
        file_workers.append(p)

    logger.info(f"Started {len(repo_workers)} repo workers and {len(file_workers)} file workers")

    # Monitor queues
    queue_mgr = RedisQueueManager(config)

    try:
        while True:
            time.sleep(30)
            lengths = queue_mgr.get_queue_lengths()
            logger.info(f"Queue status: {lengths}")
    except KeyboardInterrupt:
        logger.info("Shutting down pipeline...")

        # Terminate workers
        for p in repo_workers + file_workers:
            p.terminate()

        for p in repo_workers + file_workers:
            p.join(timeout=5)

        logger.info("Pipeline shut down complete")

if __name__ == "__main__":
    main()
