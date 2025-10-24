import ast
import re
import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import json
import difflib
import tokenize
import io
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CodeSample:
    content: str
    language: str
    metadata: Dict
    category: str = ""  # cli, desktop, web, ai, api, ml, systems
    quality_score: float = 0.0
    quality_breakdown: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    
@dataclass
class QualityReport:
    total_samples: int
    filtered_samples: int
    quality_distribution: Dict[str, int]
    common_issues: List[Tuple[str, int]]
    language_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
    framework_breakdown: Dict[str, int]
    average_scores: Dict[str, float]
    excluded_files: Dict[str, int]

class StackSpecificCodeCurator:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.seen_hashes = set()
        self.fuzzy_hashes = {}
        
        # Your specific tech stack
        self.target_languages = {'rust', 'go', 'golang', 'python', 'dart', 'flutter', 'typescript', 'javascript'}
        self.target_frameworks = {
            'flutter', 'angular', 'pytorch', 'torch', 'fastapi', 'django', 'flask',
            'actix', 'rocket', 'tokio', 'gin', 'echo', 'fiber', 'express', 'nestjs'
        }
        self.target_databases = {
            'postgres', 'postgresql', 'mssql', 'sqlserver', 'mongodb', 'mongo',
            'elasticsearch', 'elastic', 'qdrant', 'pinecone', 'weaviate', 'milvus', 'chroma'
        }
        self.azure_services = {
            'azure', 'azurefunctions', 'cosmosdb', 'blobstorage', 'azureml',
            'cognitiveservices', 'azuresql', 'eventhub', 'servicebus'
        }
        
        # Auto-generated file patterns to exclude
        self.excluded_patterns = [
            # Protocol buffers and generated files
            r'\.pb\.go$', r'\.pb\.py$', r'_pb2\.py$', r'\.proto$',
            r'_generated\.', r'\.generated\.', r'\.g\.dart$',
            # Build and dependency files
            r'\.gitignore$', r'\.dockerignore$', r'requirements\.txt$',
            r'package\.json$', r'package-lock\.json$', r'yarn\.lock$',
            r'Cargo\.lock$', r'go\.sum$', r'pubspec\.lock$',
            # Config files
            r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$', r'\.env',
            r'\.json$', r'tsconfig\.json$', r'angular\.json$',
            # Documentation and metadata
            r'README', r'LICENSE', r'CHANGELOG', r'\.md$',
            # Test data and fixtures
            r'fixtures/', r'testdata/', r'mock_data/',
            # IDE and tooling
            r'\.vscode/', r'\.idea/', r'\.vs/', r'__pycache__/',
            # Common directories to skip
            r'node_modules/', r'\.venv/', r'venv/', r'env/',
            r'dist/', r'build/', r'target/', r'bin/', r'obj/',
            r'\.git/', r'vendor/', r'packages/', r'\.dart_tool/',
            # Migrations and schemas
            r'migrations/', r'alembic/', r'schema\.sql$',
            # Generated API docs
            r'swagger\.json$', r'openapi\.json$',
        ]
        
        # File patterns that indicate high-quality implementation files
        self.quality_indicators = {
            'rust': [r'src/.*\.rs$', r'lib\.rs$', r'main\.rs$', r'mod\.rs$'],
            'go': [r'\.go$', r'cmd/.*\.go$', r'pkg/.*\.go$', r'internal/.*\.go$'],
            'python': [r'\.py$', r'src/.*\.py$', r'app/.*\.py$', r'core/.*\.py$'],
            'dart': [r'lib/.*\.dart$', r'src/.*\.dart$'],
            'typescript': [r'\.ts$', r'src/.*\.ts$', r'app/.*\.ts$', r'components/.*\.ts$'],
        }
        
        self.language_parsers = {
            'python': self._parse_python,
            'javascript': self._parse_javascript,
            'typescript': self._parse_typescript,
            'rust': self._parse_rust,
            'go': self._parse_go,
            'dart': self._parse_dart,
        }
        
        self.quality_thresholds = self.config['quality_thresholds']
        self.metrics_history = []
        
    def _default_config(self) -> Dict:
        return {
            'min_length': 100,  # Increased for quality
            'max_length': 5000,
            'min_alpha_ratio': 0.5,  # Higher for quality code
            'max_comment_ratio': 0.4,  # Balanced documentation
            'similarity_threshold': 0.85,
            'min_complexity': 0.2,  # Avoid trivial code
            'quality_thresholds': {
                'structure': 0.75,
                'documentation': 0.65,
                'complexity': 0.65,
                'naming': 0.75,
                'patterns': 0.75,
                'security': 0.85,
                'performance': 0.70,
                'testability': 0.70,
                'framework_usage': 0.70,
                'database_usage': 0.70,
            },
            'final_quality_threshold': 0.80,  # High threshold for training
            'diversity_sample_size': 100,
            'require_framework_code': True,  # Prioritize framework-specific code
            'require_meaningful_logic': True,
        }
    
    def curate_dataset(self, raw_samples: List[CodeSample], 
                      manual_review_size: Optional[int] = None) -> Tuple[List[CodeSample], QualityReport]:
        """Enhanced curation pipeline for your specific tech stack"""
        logger.info(f"Starting curation with {len(raw_samples)} samples")
        
        # Track metrics
        metrics = defaultdict(list)
        issue_counter = Counter()
        excluded_counter = Counter()
        
        # Step 1: Filter by target languages and exclude junk files
        stack_filtered = self._filter_by_stack(raw_samples, excluded_counter)
        logger.info(f"After stack filtering: {len(stack_filtered)} samples")
        
        # Step 2: Exclude auto-generated and low-value files
        clean_samples = self._exclude_generated_files(stack_filtered, excluded_counter)
        logger.info(f"After excluding generated files: {len(clean_samples)} samples")
        
        # Step 3: Categorize by application type
        categorized = self._categorize_samples(clean_samples)
        logger.info(f"Categorization complete")
        
        # Step 4: Detect frameworks and libraries
        framework_detected = self._detect_frameworks(categorized)
        logger.info(f"Framework detection complete")
        
        # Step 5: Enhanced quality filtering
        quality_filtered = self._quality_filter(framework_detected, metrics, issue_counter)
        logger.info(f"After quality filtering: {len(quality_filtered)} samples")
        
        # Step 6: Advanced deduplication
        deduplicated = self._advanced_deduplicate(quality_filtered)
        logger.info(f"After deduplication: {len(deduplicated)} samples")
        
        # Step 7: Comprehensive scoring with stack-specific metrics
        scored = self._comprehensive_score(deduplicated, metrics)
        logger.info(f"Comprehensive scoring complete")
        
        # Step 8: Stack-specific pattern checking
        pattern_checked = self._check_stack_patterns(scored, issue_counter)
        logger.info(f"Stack pattern analysis complete")
        
        # Step 9: Security and performance validation
        validated = self._validate_production_quality(pattern_checked, issue_counter)
        logger.info(f"Production quality validation complete")
        
        # Step 10: Apply strict quality thresholds
        high_quality = self._apply_strict_thresholds(validated)
        logger.info(f"After strict filtering: {len(high_quality)} samples")
        
        # Step 11: Ensure diversity across categories and frameworks
        if manual_review_size:
            final_samples = self._diverse_stack_sample(high_quality, manual_review_size)
        else:
            final_samples = sorted(high_quality, key=lambda x: x.quality_score, reverse=True)
        
        # Generate comprehensive report
        report = self._generate_stack_report(
            len(raw_samples), 
            final_samples, 
            metrics, 
            issue_counter,
            excluded_counter
        )
        
        return final_samples, report
    
    def _filter_by_stack(self, samples: List[CodeSample], excluded_counter: Counter) -> List[CodeSample]:
        """Filter samples to only include target languages"""
        filtered = []
        
        for sample in samples:
            # Normalize language names
            lang = sample.language.lower()
            if lang == 'golang':
                lang = 'go'
            
            if lang in self.target_languages:
                # Additional Flutter/Dart handling
                if lang == 'dart' or (sample.metadata.get('framework') == 'flutter'):
                    sample.language = 'dart'
                    sample.frameworks.append('flutter')
                filtered.append(sample)
            else:
                excluded_counter[f'non_target_language_{lang}'] += 1
                
        return filtered
    
    def _exclude_generated_files(self, samples: List[CodeSample], excluded_counter: Counter) -> List[CodeSample]:
        """Exclude auto-generated and low-value files"""
        clean_samples = []
        
        for sample in samples:
            # Check filename if available
            filename = sample.metadata.get('filename', '')
            filepath = sample.metadata.get('filepath', '')
            full_path = filepath or filename
            
            # Check against exclusion patterns
            excluded = False
            for pattern in self.excluded_patterns:
                if re.search(pattern, full_path, re.IGNORECASE):
                    excluded_counter[f'excluded_pattern_{pattern}'] += 1
                    excluded = True
                    break
                    
            if excluded:
                continue
                
            # Check content for generated code markers
            content_lower = sample.content.lower()
            generated_markers = [
                'auto-generated', 'autogenerated', 'generated by',
                'do not edit', 'do not modify', 'code generated',
                'automatically created', 'machine generated',
                '<auto-generated />', '// <auto-generated>',
                '# generated by', '// code generated by'
            ]
            
            if any(marker in content_lower for marker in generated_markers):
                excluded_counter['generated_code_marker'] += 1
                continue
                
            # Check for minimal content files
            if len(sample.content.strip()) < self.config['min_length']:
                excluded_counter['too_short'] += 1
                continue
                
            # Exclude files that are mostly imports/includes
            lines = sample.content.strip().split('\n')
            non_import_lines = 0
            for line in lines:
                line = line.strip()
                if not line or line.startswith(('#', '//', 'import', 'from', 'use', '#include', 'package')):
                    continue
                non_import_lines += 1
                
            if non_import_lines < 10:  # Too few actual code lines
                excluded_counter['mostly_imports'] += 1
                continue
                
            clean_samples.append(sample)
            
        return clean_samples
    
    def _categorize_samples(self, samples: List[CodeSample]) -> List[CodeSample]:
        """Categorize samples by application type"""
        for sample in samples:
            categories = []
            content_lower = sample.content.lower()
            
            # CLI detection
            cli_patterns = [
                r'argparse', r'click', r'clap::', r'structopt', r'cobra\.',
                r'flag\.', r'os\.args', r'sys\.argv', r'cli', r'command'
            ]
            if any(re.search(pattern, content_lower) for pattern in cli_patterns):
                categories.append('cli')
                
            # Desktop app detection
            desktop_patterns = [
                r'flutter/material', r'flutter/cupertino', r'flutter/widgets',
                r'electron', r'tauri', r'gtk', r'qt', r'winforms', r'wpf'
            ]
            if any(re.search(pattern, content_lower) for pattern in desktop_patterns):
                categories.append('desktop')
                
            # Web detection
            web_patterns = [
                r'angular', r'@component', r'@injectable', r'express',
                r'fastapi', r'flask', r'django', r'actix.?web', r'rocket',
                r'gin\.', r'fiber\.', r'http\.', r'router', r'endpoint'
            ]
            if any(re.search(pattern, content_lower) for pattern in web_patterns):
                categories.append('web')
                
            # AI/ML detection
            ai_ml_patterns = [
                r'torch', r'pytorch', r'tensorflow', r'keras', r'sklearn',
                r'numpy', r'pandas', r'model', r'train', r'predict',
                r'neural', r'dataset', r'embedding', r'transformer'
            ]
            if any(re.search(pattern, content_lower) for pattern in ai_ml_patterns):
                categories.append('ai' if 'embedding' in content_lower or 'transformer' in content_lower else 'ml')
                
            # API detection
            api_patterns = [
                r'api', r'rest', r'graphql', r'grpc', r'websocket',
                r'@get', r'@post', r'@put', r'@delete', r'swagger',
                r'openapi', r'json', r'response', r'request'
            ]
            if any(re.search(pattern, content_lower) for pattern in api_patterns):
                categories.append('api')
                
            # Systems programming detection
            systems_patterns = [
                r'unsafe', r'ffi', r'libc', r'syscall', r'kernel',
                r'driver', r'embedded', r'mutex', r'thread', r'async',
                r'tokio', r'futures', r'channel', r'socket', r'memory'
            ]
            if any(re.search(pattern, content_lower) for pattern in systems_patterns):
                categories.append('systems')
                
            # Database detection
            db_patterns = list(self.target_databases) + [
                r'sql', r'query', r'select', r'insert', r'update',
                r'collection', r'document', r'index', r'migration'
            ]
            if any(re.search(pattern, content_lower) for pattern in db_patterns):
                categories.append('database')
                
            sample.category = ','.join(categories) if categories else 'general'
            
        return samples
    
    def _detect_frameworks(self, samples: List[CodeSample]) -> List[CodeSample]:
        """Detect frameworks and libraries used"""
        for sample in samples:
            frameworks = []
            content = sample.content
            content_lower = content.lower()
            
            # Language-specific framework detection
            if sample.language == 'python':
                if 'import torch' in content or 'from torch' in content:
                    frameworks.append('pytorch')
                if 'import fastapi' in content or 'from fastapi' in content:
                    frameworks.append('fastapi')
                if 'import django' in content or 'from django' in content:
                    frameworks.append('django')
                if 'import flask' in content or 'from flask' in content:
                    frameworks.append('flask')
                    
            elif sample.language == 'typescript':
                if '@angular' in content or 'Component' in content:
                    frameworks.append('angular')
                if 'express' in content_lower:
                    frameworks.append('express')
                if '@nestjs' in content:
                    frameworks.append('nestjs')
                    
            elif sample.language == 'rust':
                if 'actix' in content_lower:
                    frameworks.append('actix-web')
                if 'rocket' in content_lower:
                    frameworks.append('rocket')
                if 'tokio' in content_lower:
                    frameworks.append('tokio')
                    
            elif sample.language == 'go':
                if 'gin.' in content_lower or '"github.com/gin-gonic/gin"' in content:
                    frameworks.append('gin')
                if 'echo.' in content_lower or '"github.com/labstack/echo"' in content:
                    frameworks.append('echo')
                if 'fiber.' in content_lower or '"github.com/gofiber/fiber"' in content:
                    frameworks.append('fiber')
                    
            elif sample.language == 'dart':
                if 'flutter' in content_lower:
                    frameworks.append('flutter')
                    
            # Azure detection
            azure_patterns = [
                r'azure', r'@azure', r'DefaultAzureCredential',
                r'BlobServiceClient', r'CosmosClient', r'EventHubClient'
            ]
            if any(re.search(pattern, content, re.IGNORECASE) for pattern in azure_patterns):
                frameworks.append('azure')
                
            # Database framework detection
            db_frameworks = {
                'sqlalchemy': r'sqlalchemy',
                'mongoose': r'mongoose',
                'prisma': r'prisma',
                'diesel': r'diesel',
                'gorm': r'gorm',
                'mongodb-driver': r'mongodb\.', 
                'asyncpg': r'asyncpg',
                'elasticsearch': r'elasticsearch',
            }
            
            for framework, pattern in db_frameworks.items():
                if re.search(pattern, content_lower):
                    frameworks.append(framework)
                    
            sample.frameworks = list(set(frameworks))
            
        return samples
    
    def _quality_filter(self, samples: List[CodeSample], metrics: Dict, issue_counter: Counter) -> List[CodeSample]:
        """Enhanced quality filtering specific to your stack"""
        filtered = []
        
        for sample in samples:
            content = sample.content.strip()
            issues = []
            
            # Basic quality checks
            if len(content) < self.config['min_length']:
                issues.append("too_short")
                issue_counter["too_short"] += 1
                continue
                
            if len(content) > self.config['max_length']:
                issues.append("too_long") 
                issue_counter["too_long"] += 1
                continue
                
            # Ensure meaningful code logic
            if self.config['require_meaningful_logic']:
                if not self._has_meaningful_logic(content, sample.language):
                    issues.append("no_meaningful_logic")
                    issue_counter["no_meaningful_logic"] += 1
                    continue
                    
            # Framework code preference
            if self.config['require_framework_code'] and not sample.frameworks:
                # Check if it at least uses standard library well
                if not self._uses_advanced_features(content, sample.language):
                    issues.append("no_framework_or_advanced_features")
                    issue_counter["no_framework_or_advanced_features"] += 1
                    continue
                    
            # Check for code smells specific to each language
            smells = self._detect_language_specific_smells(content, sample.language)
            if len(smells) > 2:  # Allow some imperfection
                issues.extend(smells)
                for smell in smells:
                    issue_counter[smell] += 1
                continue
                
            sample.issues = issues
            filtered.append(sample)
            
        return filtered
    
    def _has_meaningful_logic(self, content: str, language: str) -> bool:
        """Check if code has meaningful logic beyond boilerplate"""
        lines = content.split('\n')
        logic_lines = 0
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, comments, imports
            if not line or line.startswith(('#', '//', 'import', 'from', 'use', 'package')):
                continue
            # Skip simple declarations
            if re.match(r'^(var|let|const|type|interface|struct|class)\s+\w+', line):
                continue
            # Count as logic
            logic_lines += 1
            
        # Require at least 20 lines of actual logic
        return logic_lines >= 20
    
    def _uses_advanced_features(self, content: str, language: str) -> bool:
        """Check if code uses advanced language features"""
        advanced_patterns = {
            'python': [
                r'async\s+def', r'await\s+', r'yield\s+', r'__\w+__',
                r'@\w+', r'lambda\s+', r'comprehension', r'contextmanager',
                r'dataclass', r'typing\.', r'asyncio', r'concurrent'
            ],
            'rust': [
                r'impl\s+', r'trait\s+', r'macro_rules!', r'unsafe\s+',
                r'lifetime', r'Box<', r'Rc<', r'Arc<', r'Future',
                r'async\s+', r'await', r'move\s+', r'match\s+'
            ],
            'go': [
                r'go\s+func', r'channel', r'select\s+{', r'defer\s+',
                r'interface\s+{', r'context\.', r'sync\.', r'reflect\.',
                r'unsafe\.', r'<-chan', r'chan<-'
            ],
            'typescript': [
                r'async\s+', r'await\s+', r'Promise', r'Observable',
                r'generic', r'<T>', r'implements\s+', r'extends\s+',
                r'decorator', r'namespace', r'module', r'declare'
            ],
            'dart': [
                r'async\*?', r'await\s+', r'yield\*?', r'Stream',
                r'Future', r'extension\s+', r'mixin\s+', r'factory',
                r'get\s+\w+\s*=>', r'set\s+\w+', r'?.', r'??'
            ]
        }
        
        patterns = advanced_patterns.get(language, [])
        advanced_count = sum(1 for pattern in patterns if re.search(pattern, content))
        
        # Require at least 3 advanced features
        return advanced_count >= 3
    
    def _detect_language_specific_smells(self, content: str, language: str) -> List[str]:
        """Detect language-specific code smells"""
        smells = []
        
        if language == 'python':
            # Python-specific smells
            if re.search(r'except\s*:', content):
                smells.append("bare_except_python")
            if re.search(r'global\s+', content) and content.count('global') > 2:
                smells.append("excessive_globals")
            if not re.search(r'if\s+__name__\s*==\s*["\']__main__', content) and 'def main' in content:
                smells.append("missing_main_guard")
                
        elif language == 'rust':
            # Rust-specific smells
            if content.count('unwrap()') > 5:
                smells.append("excessive_unwrap")
            if content.count('clone()') > 10:
                smells.append("excessive_cloning")
            if re.search(r'unsafe\s*{[\s\S]*}', content) and 'unsafe' in content.lower():
                unsafe_blocks = len(re.findall(r'unsafe\s*{', content))
                if unsafe_blocks > 3:
                    smells.append("excessive_unsafe")
                    
        elif language == 'go':
            # Go-specific smells
            if not re.search(r'if\s+err\s*!=\s*nil', content) and 'error' in content:
                smells.append("missing_error_handling")
            if re.search(r'panic\(', content) and content.count('panic') > 2:
                smells.append("excessive_panic")
                
        elif language == 'typescript':
            # TypeScript-specific smells
            if content.count('any') > 5:
                smells.append("excessive_any_type")
            if re.search(r'console\.log', content) and content.count('console.log') > 3:
                smells.append("excessive_console_logs")
                
        return smells
    
    def _comprehensive_score(self, samples: List[CodeSample], metrics: Dict) -> List[CodeSample]:
        """Comprehensive scoring with stack-specific metrics"""
        for sample in samples:
            scores = {}
            content = sample.content
            
            # Base quality scores
            scores['structure'] = self._score_structure_advanced(content, sample.language)
            scores['documentation'] = self._score_documentation_advanced(content, sample.language)
            scores['complexity'] = self._score_complexity_advanced(content, sample.language)
            scores['naming'] = self._score_naming_advanced(content, sample.language)
            scores['patterns'] = self._score_patterns_advanced(content, sample.language)
            scores['testability'] = self._score_testability(content, sample.language)
            
            # Stack-specific scores
            scores['framework_usage'] = self._score_framework_usage(sample)
            scores['database_usage'] = self._score_database_usage(content, sample.language)
            scores['cloud_integration'] = self._score_cloud_integration(content, sample.frameworks)
            scores['production_readiness'] = self._score_production_readiness(content, sample.language)
            
            # Calculate weighted average
            weights = {
                'structure': 0.15,
                'documentation': 0.10,
                'complexity': 0.15,
                'naming': 0.10,
                'patterns': 0.15,
                'testability': 0.10,
                'framework_usage': 0.10,
                'database_usage': 0.05,
                'cloud_integration': 0.05,
                'production_readiness': 0.05
            }
            
            total_score = sum(scores.get(key, 0) * weights[key] for key in weights)
            sample.quality_score = min(total_score, 1.0)
            sample.quality_breakdown = scores
            
            # Track metrics
            for key, value in scores.items():
                metrics[key].append(value)
                
        return samples
    
    def _score_framework_usage(self, sample: CodeSample) -> float:
        """Score based on framework usage quality"""
        if not sample.frameworks:
            return 0.3  # Penalize but don't eliminate non-framework code
            
        score = 0.5  # Base score for using frameworks
        content = sample.content
        
        # Check for proper framework patterns
        for framework in sample.frameworks:
            if framework == 'angular':
                # Angular best practices
                if re.search(r'@Component\s*\(\s*{', content):
                    score += 0.1
                if re.search(r'@Injectable', content):
                    score += 0.1
                if re.search(r'Observable', content):
                    score += 0.1
                    
            elif framework == 'flutter':
                # Flutter best practices
                if re.search(r'StatelessWidget|StatefulWidget', content):
                    score += 0.1
                if re.search(r'Widget\s+build\s*\(', content):
                    score += 0.1
                    
            elif framework == 'pytorch':
                # PyTorch best practices
                if re.search(r'class.*\(.*nn\.Module\)', content):
                    score += 0.2
                if re.search(r'forward\s*\(', content):
                    score += 0.1
                    
            elif framework in ['fastapi', 'django', 'flask']:
                # Web framework patterns
                if re.search(r'@(app|router)\.(get|post|put|delete)', content):
                    score += 0.2
                    
        return min(score, 1.0)
    
    def _score_database_usage(self, content: str, language: str) -> float:
        """Score database integration quality"""
        score = 0.0
        content_lower = content.lower()
        
        # Check for database usage
        has_db = any(db in content_lower for db in self.target_databases)
        if not has_db:
            return 0.0
            
        score = 0.3  # Base score for DB usage
        
        # Connection pooling
        pool_patterns = ['pool', 'connectionpool', 'datasource', 'client_pool']
        if any(pattern in content_lower for pattern in pool_patterns):
            score += 0.2
            
        # Prepared statements / parameterized queries
        if language == 'python':
            if re.search(r'%s|\?|:\w+', content):  # Parameterized queries
                score += 0.2
        elif language in ['rust', 'go']:
            if re.search(r'\$\d+|\?', content):  # Prepared statements
                score += 0.2
                
        # Transaction handling
        if re.search(r'begin|commit|rollback|transaction', content_lower):
            score += 0.1
            
        # Error handling for DB operations
        if re.search(r'try|except|catch|handle.*error', content_lower):
            score += 0.1
            
        # Async database operations
        if re.search(r'async|await', content) and has_db:
            score += 0.1
            
        return min(score, 1.0)
    
    def _score_cloud_integration(self, content: str, frameworks: List[str]) -> float:
        """Score Azure and cloud integration quality"""
        score = 0.0
        content_lower = content.lower()
        
        # Check for Azure usage
        if 'azure' in frameworks or any(svc in content_lower for svc in self.azure_services):
            score = 0.4
            
            # Proper authentication
            if re.search(r'DefaultAzureCredential|ManagedIdentityCredential|ClientSecretCredential', content):
                score += 0.2
                
            # Configuration management
            if re.search(r'KeyVault|ConfigurationBuilder|appsettings', content):
                score += 0.1
                
            # Monitoring/logging
            if re.search(r'ApplicationInsights|TelemetryClient|Logger', content):
                score += 0.1
                
            # Resilience patterns
            if re.search(r'retry|circuit.?breaker|polly|backoff', content_lower):
                score += 0.1
                
        return min(score, 1.0)
    
    def _score_production_readiness(self, content: str, language: str) -> float:
        """Score production readiness indicators"""
        score = 0.0
        
        # Error handling
        error_patterns = {
            'python': r'try:|except\s+\w+:|finally:',
            'rust': r'Result<|Option<|match\s+|\.map_err|\.unwrap_or',
            'go': r'if\s+err\s*!=\s*nil',
            'typescript': r'try\s*{|catch\s*\(|Promise\.catch',
            'dart': r'try\s*{|catch\s*\(|\.catchError'
        }
        
        pattern = error_patterns.get(language, r'try|catch|except')
        if re.search(pattern, content):
            score += 0.3
            
        # Logging
        log_patterns = [
            r'log\.|logger\.|logging\.|console\.error|console\.warn',
            r'debug!|info!|warn!|error!',  # Rust macros
            r'log\.Print|log\.Fatal|log\.Error',  # Go
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in log_patterns):
            score += 0.2
            
        # Configuration management
        config_patterns = [
            r'config\.|settings\.|env\.|environment',
            r'ConfigParser|argparse|click',
            r'viper\.|flag\.',  # Go
            r'clap::|structopt::'  # Rust
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in config_patterns):
            score += 0.2
            
        # Input validation
        validation_patterns = [
            r'validate|validator|schema|pydantic',
            r'assert|require|check',
            r'sanitize|escape|clean'
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in validation_patterns):
            score += 0.2
            
        # Security considerations
        security_patterns = [
            r'auth|permission|role|jwt|token',
            r'encrypt|decrypt|hash|bcrypt|argon2',
            r'cors|csrf|xss|sanitize'
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in security_patterns):
            score += 0.1
            
        return min(score, 1.0)
    
    def _check_stack_patterns(self, samples: List[CodeSample], issue_counter: Counter) -> List[CodeSample]:
        """Check for stack-specific patterns and anti-patterns"""
        checked = []
        
        for sample in samples:
            issues = self._detect_stack_antipatterns(sample)
            
            if issues:
                sample.issues.extend(issues)
                for issue in issues:
                    issue_counter[f"antipattern_{issue}"] += 1
                    
            # Only keep if not too many issues
            if len(issues) <= 1:
                checked.append(sample)
                
        return checked
    
    def _detect_stack_antipatterns(self, sample: CodeSample) -> List[str]:
        """Detect stack-specific anti-patterns"""
        patterns = []
        content = sample.content
        
        if sample.language == 'python':
            # Python anti-patterns
            if 'pytorch' in sample.frameworks:
                # Not using GPU when available
                if '.cuda()' not in content and 'device' not in content:
                    patterns.append('no_gpu_handling')
                # Training without gradient management
                if 'backward()' in content and 'zero_grad()' not in content:
                    patterns.append('missing_gradient_reset')
                    
        elif sample.language == 'rust':
            # Rust anti-patterns
            if re.search(r'\.unwrap\(\).*\.unwrap\(\)', content):
                patterns.append('unwrap_chain')
            if 'std::mem::forget' in content:
                patterns.append('memory_leak_risk')
                
        elif sample.language == 'go':
            # Go anti-patterns
            if re.search(r'go\s+func.*\{.*panic\(', content, re.DOTALL):
                patterns.append('panic_in_goroutine')
            # Not handling context
            if 'context.Context' not in content and 'func (' in content:
                patterns.append('missing_context')
                
        elif sample.language == 'typescript':
            # TypeScript anti-patterns
            if '@ts-ignore' in content:
                patterns.append('ts_ignore_usage')
            if sample.frameworks and 'angular' in sample.frameworks:
                # Direct DOM manipulation in Angular
                if 'document.getElementById' in content or 'document.querySelector' in content:
                    patterns.append('direct_dom_manipulation')
                    
        elif sample.language == 'dart':
            # Flutter anti-patterns
            if 'flutter' in sample.frameworks:
                # setState in build method
                if re.search(r'build\s*\([^)]*\)\s*{.*setState', content, re.DOTALL):
                    patterns.append('setstate_in_build')
                    
        return patterns
    
    def _validate_production_quality(self, samples: List[CodeSample], issue_counter: Counter) -> List[CodeSample]:
        """Validate production quality standards"""
        validated = []
        
        for sample in samples:
            # Security validation
            security_issues = self._check_security_comprehensive(sample)
            
            # Performance validation
            perf_issues = self._check_performance_comprehensive(sample)
            
            all_issues = security_issues + perf_issues
            sample.issues.extend(all_issues)
            
            for issue in all_issues:
                issue_counter[issue] += 1
                
            # Only keep if passes security standards
            if len(security_issues) == 0:
                validated.append(sample)
                
        return validated
    
    def _check_security_comprehensive(self, sample: CodeSample) -> List[str]:
        """Comprehensive security checks for production code"""
        issues = []
        content = sample.content
        
        # SQL Injection checks
        sql_patterns = [
            r'f["\'].*SELECT.*{',  # f-string SQL
            r'%.*SELECT.*%',  # String formatting SQL
            r'"\s*\+.*SELECT',  # String concatenation SQL
            r'query\(["\'][^"\']*\+',  # Dynamic query building
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in sql_patterns):
            issues.append('sql_injection_risk')
            
        # Hardcoded secrets
        secret_patterns = [
            r'(password|pwd|secret|key|token)\s*=\s*["\'][^"\']{8,}["\']',
            r'(api_key|apikey)\s*=\s*["\'][^"\']+["\']',
            r'bearer\s+[a-zA-Z0-9\-_]+',
        ]
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in secret_patterns):
            # Check if it's not a placeholder
            if not re.search(r'(example|placeholder|your.?|xxx|<.*>)', content, re.IGNORECASE):
                issues.append('hardcoded_secrets')
                
        # Command injection
        cmd_patterns = {
            'python': [r'os\.system\(', r'subprocess\..*shell=True', r'eval\(', r'exec\('],
            'javascript': [r'eval\(', r'child_process\.exec\([^,)]*\+'],
            'go': [r'exec\.Command\([^,)]*\+'],
        }
        
        language_patterns = cmd_patterns.get(sample.language, [])
        if any(re.search(pattern, content) for pattern in language_patterns):
            issues.append('command_injection_risk')
            
        # Path traversal
        if re.search(r'\.\./', content) or re.search(r'path\.join\([^)]*\+', content):
            issues.append('path_traversal_risk')
            
        return issues
    
    def _check_performance_comprehensive(self, sample: CodeSample) -> List[str]:
        """Comprehensive performance checks"""
        issues = []
        content = sample.content
        
        # N+1 query problem (ORM)
        if re.search(r'for.*:\s*\n.*\.(get|filter|select|find)', content):
            issues.append('potential_n_plus_one')
            
        # Unbounded queries
        if sample.language in ['python', 'javascript', 'typescript']:
            if re.search(r'\.(all|find)\(\s*\)', content) and 'limit' not in content.lower():
                issues.append('unbounded_query')
                
        # Memory leaks
        leak_patterns = {
            'python': [r'global\s+\w+\s*=\s*\[\]', r'cache\s*=\s*{'],  # Global collections
            'javascript': [r'setInterval\(', r'addEventListener\('],  # Without cleanup
            'go': [r'for\s*{\s*go\s+'],  # Infinite goroutine spawning
        }
        
        language_patterns = leak_patterns.get(sample.language, [])
        if any(re.search(pattern, content) for pattern in language_patterns):
            # Check if there's cleanup code
            if 'clear' not in content and 'remove' not in content and 'close' not in content:
                issues.append('potential_memory_leak')
                
        return issues
    
    def _apply_strict_thresholds(self, samples: List[CodeSample]) -> List[CodeSample]:
        """Apply strict quality thresholds for training data"""
        high_quality = []
        
        for sample in samples:
            # Overall threshold
            if sample.quality_score < self.config['final_quality_threshold']:
                continue
                
            # Individual component thresholds
            passes = True
            for component, threshold in self.quality_thresholds.items():
                if component in sample.quality_breakdown:
                    if sample.quality_breakdown[component] < threshold:
                        passes = False
                        break
                        
            # Additional requirements for training data
            if passes:
                # Must have some framework or advanced usage
                if not sample.frameworks and sample.quality_breakdown.get('patterns', 0) < 0.8:
                    continue
                    
                # Must have decent documentation
                if sample.quality_breakdown.get('documentation', 0) < 0.5:
                    continue
                    
                # Must be reasonably complex
                if sample.quality_breakdown.get('complexity', 0) < 0.4:
                    continue
                    
                high_quality.append(sample)
                
        return high_quality
    
    def _diverse_stack_sample(self, samples: List[CodeSample], target_size: int) -> List[CodeSample]:
        """Ensure diversity across languages, frameworks, and categories"""
        if len(samples) <= target_size:
            return samples
            
        # Group samples
        by_language = defaultdict(list)
        by_category = defaultdict(list)
        by_framework = defaultdict(list)
        by_score_tier = defaultdict(list)
        
        for sample in samples:
            by_language[sample.language].append(sample)
            
            # Categories
            categories = sample.category.split(',') if sample.category else ['general']
            for cat in categories:
                by_category[cat].append(sample)
                
            # Frameworks
            if sample.frameworks:
                for fw in sample.frameworks:
                    by_framework[fw].append(sample)
            else:
                by_framework['none'].append(sample)
                
            # Score tiers
            tier = 'excellent' if sample.quality_score >= 0.9 else 'good' if sample.quality_score >= 0.8 else 'acceptable'
            by_score_tier[tier].append(sample)
            
        # Calculate distribution
        selected = []
        
        # Ensure minimum representation per language
        min_per_language = max(1, target_size // (len(by_language) * 2))
        for lang, lang_samples in by_language.items():
            lang_samples.sort(key=lambda x: x.quality_score, reverse=True)
            selected.extend(lang_samples[:min_per_language])
            
        # Add framework diversity
        min_per_framework = max(1, target_size // (len(by_framework) * 3))
        for fw, fw_samples in by_framework.items():
            if fw != 'none':  # Prioritize framework code
                fw_samples.sort(key=lambda x: x.quality_score, reverse=True)
                for sample in fw_samples[:min_per_framework]:
                    if sample not in selected:
                        selected.append(sample)
                        
        # Add category diversity
        min_per_category = max(1, target_size // (len(by_category) * 3))
        for cat, cat_samples in by_category.items():
            cat_samples.sort(key=lambda x: x.quality_score, reverse=True)
            for sample in cat_samples[:min_per_category]:
                if sample not in selected:
                    selected.append(sample)
                    
        # Fill remaining with top quality
        remaining_slots = target_size - len(selected)
        if remaining_slots > 0:
            all_samples_sorted = sorted(samples, key=lambda x: x.quality_score, reverse=True)
            for sample in all_samples_sorted:
                if sample not in selected:
                    selected.append(sample)
                    remaining_slots -= 1
                    if remaining_slots <= 0:
                        break
                        
        return selected[:target_size]
    
    def _generate_stack_report(self, total_samples: int, final_samples: List[CodeSample],
                              metrics: Dict, issue_counter: Counter, 
                              excluded_counter: Counter) -> QualityReport:
        """Generate comprehensive report for stack-specific curation"""
        # Quality distribution
        quality_distribution = defaultdict(int)
        for sample in final_samples:
            bucket = f"{int(sample.quality_score * 10) / 10:.1f}"
            quality_distribution[bucket] += 1
            
        # Language breakdown
        language_breakdown = defaultdict(int)
        for sample in final_samples:
            language_breakdown[sample.language] += 1
            
        # Category breakdown
        category_breakdown = defaultdict(int)
        for sample in final_samples:
            categories = sample.category.split(',') if sample.category else ['general']
            for cat in categories:
                category_breakdown[cat] += 1
                
        # Framework breakdown
        framework_breakdown = defaultdict(int)
        for sample in final_samples:
            if sample.frameworks:
                for fw in sample.frameworks:
                    framework_breakdown[fw] += 1
            else:
                framework_breakdown['none'] += 1
                
        # Average scores
        average_scores = {}
        for component, scores in metrics.items():
            if scores:
                average_scores[component] = sum(scores) / len(scores)
                
        # Most common issues
        common_issues = issue_counter.most_common(15)
        
        # Excluded files summary
        excluded_files = dict(excluded_counter.most_common(10))
        
        return QualityReport(
            total_samples=total_samples,
            filtered_samples=len(final_samples),
            quality_distribution=dict(quality_distribution),
            common_issues=common_issues,
            language_breakdown=dict(language_breakdown),
            category_breakdown=dict(category_breakdown),
            framework_breakdown=dict(framework_breakdown),
            average_scores=average_scores,
            excluded_files=excluded_files
        )
    
    # Enhanced parsing methods for additional languages
    def _parse_dart(self, content: str) -> bool:
        """Validate Dart/Flutter syntax"""
        try:
            # Basic syntax checks
            balanced_braces = content.count('{') == content.count('}')
            balanced_parens = content.count('(') == content.count(')')
            
            # Dart-specific patterns
            has_dart_syntax = any([
                'void ' in content,
                'var ' in content,
                'final ' in content,
                'const ' in content,
                'class ' in content,
                '=>' in content
            ])
            
            return balanced_braces and balanced_parens and has_dart_syntax
        except:
            return False
    
    def _parse_typescript(self, content: str) -> bool:
        """Validate TypeScript syntax"""
        try:
            # Check for TypeScript-specific syntax
            has_ts_syntax = any([
                ': ' in content and not '//' in content,  # Type annotations
                'interface ' in content,
                'type ' in content,
                'enum ' in content,
                '<T>' in content or '<T extends' in content,  # Generics
            ])
            
            # Basic syntax validation
            balanced_braces = content.count('{') == content.count('}')
            balanced_parens = content.count('(') == content.count(')')
            
            return balanced_braces and balanced_parens and (has_ts_syntax or '.ts' in content)
        except:
            return False
    
    def _parse_rust(self, content: str) -> bool:
        """Enhanced Rust syntax validation"""
        try:
            # Rust-specific keywords
            rust_keywords = ['fn ', 'let ', 'mut ', 'impl ', 'trait ', 'struct ', 'enum ', 'match ']
            has_rust_syntax = any(keyword in content for keyword in rust_keywords)
            
            # Check for Rust patterns
            has_rust_patterns = any([
                '::' in content,
                '->' in content,
                '&mut' in content or '&self' in content,
                'Result<' in content or 'Option<' in content,
            ])
            
            balanced_braces = content.count('{') == content.count('}')
            balanced_parens = content.count('(') == content.count(')')
            
            return balanced_braces and balanced_parens and (has_rust_syntax or has_rust_patterns)
        except:
            return False
    
    def _parse_go(self, content: str) -> bool:
        """Enhanced Go syntax validation"""
        try:
            # Must have package declaration
            if not re.search(r'^package\s+\w+', content, re.MULTILINE):
                return False
                
            # Go-specific patterns
            has_go_syntax = any([
                'func ' in content,
                ':=' in content,
                'var ' in content,
                'type ' in content,
                'interface{}' in content,
            ])
            
            balanced_braces = content.count('{') == content.count('}')
            balanced_parens = content.count('(') == content.count(')')
            
            return balanced_braces and balanced_parens and has_go_syntax
        except:
            return False
    
    # Additional helper methods from the base class
    def _score_structure_advanced(self, content: str, language: str) -> float:
        """Advanced structure scoring"""
        score = 0.0
        lines = content.split('\n')
        
        # Language-specific structure checks
        if language == 'python':
            # PEP 8 compliance indicators
            if self._check_python_structure(content):
                score += 0.3
                
        elif language == 'rust':
            # Rust module structure
            if self._check_rust_structure(content):
                score += 0.3
                
        elif language == 'go':
            # Go conventions
            if self._check_go_structure(content):
                score += 0.3
                
        elif language == 'typescript':
            # TypeScript/Angular structure
            if self._check_typescript_structure(content):
                score += 0.3
                
        # Common structure elements
        # Proper imports organization
        if self._check_import_organization(content, language):
            score += 0.2
            
        # Consistent indentation
        if self._check_consistent_indentation(lines):
            score += 0.2
            
        # Logical sections with spacing
        if self._check_logical_sections(lines):
            score += 0.2
            
        # Not too many long lines
        long_lines = sum(1 for line in lines if len(line) > 100)
        if long_lines / max(len(lines), 1) < 0.1:
            score += 0.1
            
        return min(score, 1.0)
    
    def _check_python_structure(self, content: str) -> bool:
        """Check Python-specific structure"""
        # Check for proper module docstring
        has_module_doc = content.strip().startswith(('"""', "'''"))
        
        # Check for main guard
        has_main_guard = 'if __name__ == "__main__":' in content or 'if __name__ == \'__main__\':' in content
        
        # Check for class/function organization
        lines = content.split('\n')
        import_section_done = False
        found_code = False
        
        for line in lines:
            if line.strip().startswith(('import ', 'from ')):
                if found_code:
                    return False  # Imports after code
            elif line.strip() and not line.strip().startswith('#'):
                found_code = True
                
        return True
    
    def _check_rust_structure(self, content: str) -> bool:
        """Check Rust-specific structure"""
        # Check for proper module organization
        has_use_statements = 'use ' in content
        has_mod_declaration = 'mod ' in content or 'pub mod ' in content
        
        # Check for proper visibility modifiers
        has_pub = 'pub fn' in content or 'pub struct' in content or 'pub trait' in content
        
        return has_use_statements or has_mod_declaration or has_pub
    
    def _check_go_structure(self, content: str) -> bool:
        """Check Go-specific structure"""
        lines = content.split('\n')
        
        # Package must be first non-comment line
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('//'):
                return stripped.startswith('package ')
                
        return False
    
    def _check_typescript_structure(self, content: str) -> bool:
        """Check TypeScript-specific structure"""
        # Check for proper imports
        has_imports = 'import ' in content
        
        # Check for proper exports
        has_exports = 'export ' in content
        
        # Check for type definitions
        has_types = ': ' in content and 'interface ' in content or 'type ' in content
        
        return has_imports and (has_exports or has_types)
    
    def _check_import_organization(self, content: str, language: str) -> bool:
        """Check if imports are well organized"""
        lines = content.split('\n')
        import_lines = []
        
        if language == 'python':
            import_pattern = r'^(import |from )'
        elif language in ['typescript', 'javascript']:
            import_pattern = r'^import '
        elif language == 'rust':
            import_pattern = r'^use '
        elif language == 'go':
            import_pattern = r'^import '
        else:
            return True
            
        # Collect import lines
        for i, line in enumerate(lines):
            if re.match(import_pattern, line.strip()):
                import_lines.append(i)
                
        if not import_lines:
            return True
            
        # Check if imports are grouped together
        if import_lines:
            return max(import_lines) - min(import_lines) == len(import_lines) - 1
            
        return True
    
    def _check_consistent_indentation(self, lines: List[str]) -> bool:
        """Check for consistent indentation"""
        indent_chars = set()
        
        for line in lines:
            if line and line[0] in ' \t':
                # Get indentation character
                indent_char = line[0]
                indent_chars.add(indent_char)
                
        # Should only use one type of indentation
        return len(indent_chars) <= 1
    
    def _check_logical_sections(self, lines: List[str]) -> bool:
        """Check if code has logical sections with proper spacing"""
        if len(lines) < 10:
            return True
            
        blank_lines = sum(1 for line in lines if not line.strip())
        total_lines = len(lines)
        
        # Should have some blank lines for readability (5-20%)
        blank_ratio = blank_lines / total_lines
        return 0.05 <= blank_ratio <= 0.2
    
    def _score_documentation_advanced(self, content: str, language: str) -> float:
        """Language-specific documentation scoring"""
        score = 0.0
        
        if language == 'python':
            score = self._score_python_documentation(content)
        elif language == 'rust':
            score = self._score_rust_documentation(content)
        elif language == 'go':
            score = self._score_go_documentation(content)
        elif language in ['typescript', 'javascript']:
            score = self._score_typescript_documentation(content)
        elif language == 'dart':
            score = self._score_dart_documentation(content)
            
        return min(score, 1.0)
    
    def _score_python_documentation(self, content: str) -> float:
        """Score Python documentation"""
        score = 0.0
        
        # Module docstring
        if re.match(r'^["\'][\"\'][\"\'].*?["\'][\"\'][\"\']', content.strip(), re.DOTALL):
            score += 0.2
            
        # Function/class docstrings
        docstrings = re.findall(r'(def|class)\s+\w+.*?:\s*\n\s*["\'][\"\'][\"\'].*?["\'][\"\'][\"\']', 
                               content, re.DOTALL)
        if docstrings:
            score += min(len(docstrings) * 0.1, 0.3)
            
        # Type hints
        type_hints = re.findall(r'def\s+\w+\s*\([^)]*:.*?\)', content)
        if type_hints:
            score += 0.2
            
        # Return type hints
        return_hints = re.findall(r'->\s*[\w\[\]]+', content)
        if return_hints:
            score += 0.1
            
        # Quality inline comments
        comments = re.findall(r'#\s*(.+), content, re.MULTILINE)
        meaningful = [c for c in comments if len(c.strip()) > 20 and not c.strip().startswith(('TODO', 'FIXME', 'HACK'))]
        if meaningful:
            score += min(len(meaningful) * 0.05, 0.2)
            
        return score
    
    def _score_rust_documentation(self, content: str) -> float:
        """Score Rust documentation"""
        score = 0.0
        
        # Doc comments (///)
        doc_comments = re.findall(r'///.*, content, re.MULTILINE)
        if doc_comments:
            score += min(len(doc_comments) * 0.05, 0.3)
            
        # Module-level documentation (//!)
        if re.search(r'//!', content):
            score += 0.2
            
        # Examples in documentation
        if re.search(r'```.*?```', content, re.DOTALL):
            score += 0.2
            
        # Structured documentation
        if any(marker in content for marker in ['# Examples', '# Panics', '# Safety', '# Errors']):
            score += 0.2
            
        # Regular comments
        comments = re.findall(r'//\s*([^/].*), content, re.MULTILINE)
        meaningful = [c for c in comments if len(c.strip()) > 20]
        if meaningful:
            score += min(len(meaningful) * 0.03, 0.1)
            
        return score
    
    def _score_go_documentation(self, content: str) -> float:
        """Score Go documentation"""
        score = 0.0
        
        # Package documentation
        if re.search(r'//\s*Package\s+\w+', content):
            score += 0.2
            
        # Function documentation (comment before function)
        func_docs = re.findall(r'//.*\n(?://.*\n)*func\s+', content)
        if func_docs:
            score += min(len(func_docs) * 0.1, 0.4)
            
        # Exported identifiers documented
        exported = re.findall(r'//.*\n(?://.*\n)*(type|var|const|func)\s+[A-Z]', content)
        if exported:
            score += min(len(exported) * 0.05, 0.3)
            
        # Example functions
        if re.search(r'func\s+Example', content):
            score += 0.1
            
        return score
    
    def _score_typescript_documentation(self, content: str) -> float:
        """Score TypeScript/JavaScript documentation"""
        score = 0.0
        
        # JSDoc comments
        jsdoc = re.findall(r'/\*\*[\s\S]*?\*/', content)
        if jsdoc:
            score += min(len(jsdoc) * 0.1, 0.3)
            
            # Check JSDoc quality
            for doc in jsdoc:
                if '@param' in doc:
                    score += 0.05
                if '@returns' in doc or '@return' in doc:
                    score += 0.05
                if '@throws' in doc or '@example' in doc:
                    score += 0.05
                    
        # TypeScript interfaces/types documented
        if language == 'typescript':
            interface_docs = re.findall(r'/\*\*[\s\S]*?\*/\s*(?:interface|type)\s+', content)
            if interface_docs:
                score += 0.2
                
        return score
    
    def _score_dart_documentation(self, content: str) -> float:
        """Score Dart/Flutter documentation"""
        score = 0.0
        
        # Dart doc comments (///)
        doc_comments = re.findall(r'///.*, content, re.MULTILINE)
        if doc_comments:
            score += min(len(doc_comments) * 0.05, 0.3)
            
        # Class/method documentation
        class_docs = re.findall(r'///.*\n(?:///.*\n)*class\s+', content)
        if class_docs:
            score += 0.2
            
        # Flutter widget documentation
        if 'Widget' in content:
            widget_docs = re.findall(r'///.*\n(?:///.*\n)*.*Widget\s+', content)
            if widget_docs:
                score += 0.2
                
        return score
    
    def _score_complexity_advanced(self, content: str, language: str) -> float:
        """Advanced complexity scoring"""
        # Calculate various complexity metrics
        cyclomatic = self._calculate_cyclomatic_complexity(content, language)
        cognitive = self._calculate_cognitive_complexity(content, language)
        lines = content.split('\n')
        loc = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//'))])
        
        # Ideal complexity ranges vary by language
        ideal_ranges = {
            'python': (5, 15),
            'rust': (5, 20),
            'go': (3, 12),
            'typescript': (5, 15),
            'dart': (5, 15),
        }
        
        min_ideal, max_ideal = ideal_ranges.get(language, (5, 15))
        
        score = 1.0
        
        # Cyclomatic complexity scoring
        if cyclomatic < min_ideal:
            score -= 0.3  # Too simple
        elif cyclomatic > max_ideal:
            score -= (cyclomatic - max_ideal) * 0.02  # Gradually penalize
            
        # Cognitive complexity
        if cognitive > 20:
            score -= 0.2
        elif cognitive < 3:
            score -= 0.2  # Too simple
            
        # Lines of code per unit of complexity
        if loc > 0:
            complexity_density = cyclomatic / loc
            if complexity_density < 0.05:
                score -= 0.2  # Too simple for its size
            elif complexity_density > 0.3:
                score -= 0.2  # Too complex for its size
                
        return max(0.0, score)
    
    def _score_naming_advanced(self, content: str, language: str) -> float:
        """Language-specific naming convention scoring"""
        score = 0.0
        
        if language == 'python':
            # Snake case for functions/variables
            snake_case_vars = re.findall(r'\b[a-z][a-z0-9_]*(?:_[a-z0-9]+)*\b', content)
            # PascalCase for classes
            pascal_case_classes = re.findall(r'class\s+([A-Z][a-zA-Z0-9]*)', content)
            # UPPER_CASE for constants
            constants = re.findall(r'\b[A-Z][A-Z0-9_]*\b', content)
            
            if snake_case_vars:
                score += 0.3
            if pascal_case_classes:
                score += 0.3
            if constants:
                score += 0.1
                
        elif language == 'rust':
            # Snake case for functions/variables
            if re.search(r'fn\s+[a-z_][a-z0-9_]*', content):
                score += 0.3
            # PascalCase for types
            if re.search(r'(struct|enum|trait)\s+[A-Z][a-zA-Z0-9]*', content):
                score += 0.3
            # SCREAMING_SNAKE_CASE for constants
            if re.search(r'const\s+[A-Z][A-Z0-9_]*', content):
                score += 0.2
                
        elif language == 'go':
            # Go naming conventions
            # Exported (capitalized) names
            if re.search(r'(func|type|var|const)\s+[A-Z][a-zA-Z0-9]*', content):
                score += 0.4
            # Unexported (lowercase) names  
            if re.search(r'(func|type|var|const)\s+[a-z][a-zA-Z0-9]*', content):
                score += 0.3
                
        elif language in ['typescript', 'javascript']:
            # camelCase for functions/variables
            if re.search(r'(const|let|var|function)\s+[a-z][a-zA-Z0-9]*', content):
                score += 0.3
            # PascalCase for classes/interfaces
            if re.search(r'(class|interface)\s+[A-Z][a-zA-Z0-9]*', content):
                score += 0.3
            # UPPER_CASE for constants
            if re.search(r'const\s+[A-Z][A-Z0-9_]*\s*=', content):
                score += 0.1
                
        # Penalize poor naming
        # Single letter variables (except common ones)
        single_letters = re.findall(r'\b[a-zA-Z]\b', content)
        allowed_single = ['i', 'j', 'k', 'n', 'm', 'x', 'y', 'z', 'e', 't']
        bad_singles = [s for s in single_letters if s not in allowed_single]
        if len(bad_singles) > 5:
            score -= 0.2
            
        # Overly generic names
        generic_names = ['data', 'info', 'temp', 'obj', 'val', 'item']
        generic_count = sum(content.count(name) for name in generic_names)
        if generic_count > 5:
            score -= 0.1
            
        return max(0.0, min(1.0, score))
    
    def _score_patterns_advanced(self, content: str, language: str) -> float:
        """Score design patterns and best practices"""
        score = 0.5  # Start neutral
        
        # Language-specific patterns
        if language == 'python':
            score += self._score_python_patterns(content)
        elif language == 'rust':
            score += self._score_rust_patterns(content)
        elif language == 'go':
            score += self._score_go_patterns(content)
        elif language in ['typescript', 'javascript']:
            score += self._score_typescript_patterns(content)
        elif language == 'dart':
            score += self._score_dart_patterns(content)
            
        return max(0.0, min(1.0, score))
    
    def _score_python_patterns(self, content: str) -> float:
        """Score Python-specific patterns"""
        pattern_score = 0.0
        
        # Context managers
        if re.search(r'with\s+.*\s+as\s+\w+:', content):
            pattern_score += 0.1
            
        # Decorators
        if re.search(r'@\w+', content):
            pattern_score += 0.1
            
        # Generator expressions/comprehensions
        if re.search(r'\[.*for.*in.*\]|\(.*for.*in.*\)', content):
            pattern_score += 0.1
            
        # Property decorators
        if re.search(r'@property', content):
            pattern_score += 0.05
            
        # Async/await
        if re.search(r'async\s+def|await\s+', content):
            pattern_score += 0.1
            
        # Type hints usage
        if re.search(r':\s*(List|Dict|Optional|Union|Tuple)\[', content):
            pattern_score += 0.1
            
        return pattern_score
    
    def _score_rust_patterns(self, content: str) -> float:
        """Score Rust-specific patterns"""
        pattern_score = 0.0
        
        # Error handling with Result
        if re.search(r'Result<.*>', content):
            pattern_score += 0.1
            
        # Option handling
        if re.search(r'Option<.*>', content):
            pattern_score += 0.1
            
        # Pattern matching
        if re.search(r'match\s+.*\s*{', content):
            pattern_score += 0.1
            
        # Iterators
        if re.search(r'\.(iter|into_iter|iter_mut)\(\)', content):
            pattern_score += 0.1
            
        # Trait implementations
        if re.search(r'impl\s+.*\s+for\s+', content):
            pattern_score += 0.1
            
        # Lifetime annotations
        if re.search(r'<\'[a-z]+>', content):
            pattern_score += 0.05
            
        return pattern_score
    
    def _score_go_patterns(self, content: str) -> float:
        """Score Go-specific patterns"""
        pattern_score = 0.0
        
        # Error handling
        if re.search(r'if\s+err\s*!=\s*nil', content):
            pattern_score += 0.15
            
        # Goroutines
        if re.search(r'go\s+func|\sgo\s+\w+', content):
            pattern_score += 0.1
            
        # Channels
        if re.search(r'chan\s+|<-\s*chan|chan\s*<-', content):
            pattern_score += 0.1
            
        # Defer
        if re.search(r'defer\s+', content):
            pattern_score += 0.1
            
        # Interfaces
        if re.search(r'interface\s*{', content):
            pattern_score += 0.1
            
        return pattern_score
    
    def _score_typescript_patterns(self, content: str) -> float:
        """Score TypeScript-specific patterns"""
        pattern_score = 0.0
        
        # Async/await
        if re.search(r'async\s+.*=>|async\s+function', content):
            pattern_score += 0.1
            
        # Promises
        if re.search(r'Promise<.*>|\.then\(|\.catch\(', content):
            pattern_score += 0.1
            
        # Generics
        if re.search(r'<T[,\s>]|<T\s+extends', content):
            pattern_score += 0.1
            
        # Decorators (Angular)
        if re.search(r'@(Component|Injectable|Input|Output)', content):
            pattern_score += 0.1
            
        # Type guards
        if re.search(r'is\s+\w+[\s{]', content):
            pattern_score += 0.05
            
        return pattern_score
    
    def _score_dart_patterns(self, content: str) -> float:
        """Score Dart/Flutter patterns"""
        pattern_score = 0.0
        
        # Flutter widgets
        if re.search(r'(StatelessWidget|StatefulWidget)', content):
            pattern_score += 0.15
            
        # Async/await
        if re.search(r'async\s*{|await\s+', content):
            pattern_score += 0.1
            
        # Null safety
        if re.search(r'\?\.|\?\?|late\s+', content):
            pattern_score += 0.1
            
        # Extension methods
        if re.search(r'extension\s+\w+\s+on\s+', content):
            pattern_score += 0.05
            
        return pattern_score
    
    def _score_testability(self, content: str, language: str) -> float:
        """Score code testability"""
        score = 0.5
        
        # Dependency injection patterns
        if language == 'python':
            # Constructor injection
            if re.search(r'def\s+__init__\s*\([^)]*,', content):
                score += 0.2
        elif language in ['typescript', 'javascript']:
            # Constructor parameters
            if re.search(r'constructor\s*\([^)]+\)', content):
                score += 0.2
                
        # Pure functions (functions with parameters and return)
        pure_function_patterns = {
            'python': r'def\s+\w+\s*\([^)]+\).*?:\s*(?:.*\n)*?\s*return\s+',
            'rust': r'fn\s+\w+.*?->\s*.*?{',
            'go': r'func\s+\w+\s*\([^)]*\)\s*\w+\s*{',
            'typescript': r'function\s+\w+\s*\([^)]+\):\s*\w+',
        }
        
        pattern = pure_function_patterns.get(language)
        if pattern and re.search(pattern, content, re.DOTALL):
            score += 0.2
            
        # Modular structure (multiple functions/classes)
        function_count = self._count_functions(content, language)
        if 3 <= function_count <= 10:
            score += 0.2
        elif function_count > 10:
            score += 0.1
            
        # No global state
        if language == 'python':
            if not re.search(r'global\s+', content):
                score += 0.1
                
        return min(1.0, score)
    
    def _count_functions(self, content: str, language: str) -> int:
        """Count number of functions in code"""
        patterns = {
            'python': r'def\s+\w+',
            'rust': r'fn\s+\w+',
            'go': r'func\s+\w+',
            'typescript': r'function\s+\w+|(\w+)\s*:\s*\([^)]*\)\s*=>',
            'javascript': r'function\s+\w+|const\s+\w+\s*=\s*\([^)]*\)\s*=>',
            'dart': r'(\w+)\s*\([^)]*\)\s*(async\s*)?\{',
        }
        
        pattern = patterns.get(language, r'function')
        matches = re.findall(pattern, content)
        return len(matches)
    
    def _calculate_cyclomatic_complexity(self, content: str, language: str) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        
        # Language-specific decision points
        decision_points = {
            'python': ['if ', 'elif ', 'for ', 'while ', 'except ', ' and ', ' or '],
            'rust': ['if ', 'else if ', 'for ', 'while ', 'match ', '&&', '||'],
            'go': ['if ', 'else if ', 'for ', 'switch ', 'case ', '&&', '||'],
            'typescript': ['if ', 'else if ', 'for ', 'while ', 'switch ', 'case ', '&&', '||', '?'],
            'dart': ['if ', 'else if ', 'for ', 'while ', 'switch ', 'case ', '&&', '||', '?'],
        }
        
        points = decision_points.get(language, decision_points['python'])
        
        for point in points:
            complexity += content.count(point)
            
        return complexity
    
    def _calculate_cognitive_complexity(self, content: str, language: str) -> int:
        """Calculate cognitive complexity"""
        complexity = 0
        lines = content.split('\n')
        nesting_level = 0
        
        nesting_increasers = {
            'python': ['if ', 'elif ', 'else:', 'for ', 'while ', 'def ', 'class ', 'try:', 'with '],
            'rust': ['if ', 'else ', 'for ', 'while ', 'match ', 'fn ', 'impl '],
            'go': ['if ', 'else ', 'for ', 'func ', 'switch '],
            'typescript': ['if ', 'else ', 'for ', 'while ', 'function ', 'class ', 'switch '],
        }
        
        increasers = nesting_increasers.get(language, nesting_increasers['python'])
        
        for line in lines:
            stripped = line.strip()
            
            # Check for nesting increasers
            for increaser in increasers:
                if stripped.startswith(increaser):
                    complexity += (1 + nesting_level)
                    nesting_level += 1
                    break
                    
            # Decrease nesting on closing braces/dedent
            if language != 'python' and '}' in line:
                nesting_level = max(0, nesting_level - 1)
            elif language == 'python':
                # Simple dedent detection
                if stripped and not line.startswith(' ') and nesting_level > 0:
                    nesting_level = 0
                    
        return complexity


# Enhanced training formatter
class StackSpecificTrainingFormatter:
    """Training formatter optimized for your tech stack"""
    
    @staticmethod
    def create_training_format(samples: List[CodeSample], format_type: str = 'alpaca',
                             config: Optional[Dict] = None) -> List[Dict]:
        """Create training data in various formats"""
        config = config or {}
        formatted = []
        
        for sample in samples:
            if format_type == 'alpaca':
                formatted.append(StackSpecificTrainingFormatter._format_alpaca_enhanced(sample, config))
            elif format_type == 'chat':
                formatted.append(StackSpecificTrainingFormatter._format_chat(sample, config))
            elif format_type == 'instruct':
                formatted.append(StackSpecificTrainingFormatter._format_instruct(sample, config))
            elif format_type == 'completion':
                formatted.append(StackSpecificTrainingFormatter._format_completion(sample, config))
                
        return formatted
    
    @staticmethod
    def _format_alpaca_enhanced(sample: CodeSample, config: Dict) -> Dict:
        """Enhanced Alpaca format with rich context"""
        # Generate contextual instruction based on category
        instruction = StackSpecificTrainingFormatter._generate_contextual_instruction(sample)
        
        # Extract meaningful context
        context = StackSpecificTrainingFormatter._extract_context(sample)
        
        # Add framework/tech stack context
        tech_context = StackSpecificTrainingFormatter._generate_tech_context(sample)
        
        return {
            'instruction': instruction,
            'input': f"{context}\n{tech_context}" if tech_context else context,
            'output': sample.content,
            'metadata': {
                'language': sample.language,
                'frameworks': sample.frameworks,
                'category': sample.category,
                'quality_score': sample.quality_score,
                'quality_breakdown': sample.quality_breakdown,
                **sample.metadata
            }
        }
    
    @staticmethod
    def _generate_contextual_instruction(sample: CodeSample) -> str:
        """Generate context-aware instructions"""
        lang = sample.language
        categories = sample.category.split(',') if sample.category else []
        frameworks = sample.frameworks
        
        # Base instruction templates by category
        if 'ai' in categories or 'ml' in categories:
            templates = [
                f"Implement a {lang} solution for machine learning using {', '.join(frameworks) if frameworks else 'PyTorch'}:",
                f"Create a {lang} AI/ML pipeline that:",
                f"Develop a neural network implementation in {lang} that:",
            ]
        elif 'api' in categories:
            templates = [
                f"Build a RESTful API endpoint in {lang} using {', '.join(frameworks) if frameworks else 'modern frameworks'}:",
                f"Create a {lang} API service that:",
                f"Implement a production-ready API in {lang} with:",
            ]
        elif 'web' in categories:
            templates = [
                f"Develop a web application component in {lang} using {', '.join(frameworks) if frameworks else 'modern frameworks'}:",
                f"Create a {lang} web service that:",
                f"Build a scalable web solution in {lang} implementing:",
            ]
        elif 'cli' in categories:
            templates = [
                f"Create a command-line tool in {lang} that:",
                f"Build a CLI application in {lang} with:",
                f"Implement a terminal utility in {lang} for:",
            ]
        elif 'systems' in categories:
            templates = [
                f"Implement a systems-level solution in {lang} that:",
                f"Create a high-performance {lang} implementation for:",
                f"Build a concurrent/parallel {lang} system that:",
            ]
        else:
            templates = [
                f"Write production-quality {lang} code that:",
                f"Implement a {lang} solution using {', '.join(frameworks) if frameworks else 'best practices'} for:",
                f"Create a well-structured {lang} implementation that:",
            ]
            
        import random
        base_instruction = random.choice(templates)
        
        # Extract problem from code
        problem = StackSpecificTrainingFormatter._extract_problem_description(sample)
        
        return f"{base_instruction} {problem}"
    
    @staticmethod
    def _extract_problem_description(sample: CodeSample) -> str:
        """Extract or generate problem description"""
        content = sample.content
        
        # Try to extract from documentation
        doc_patterns = [
            r'"""(.*?)"""',  # Python docstring
            r"'''(.*?)'''",  # Python docstring
            r'/\*\*(.*?)\*/',  # JSDoc/JavaDoc
            r'///(.*?),  # Rust/Dart doc comments
        ]
        
        for pattern in doc_patterns:
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
            if match:
                desc = match.group(1).strip()
                # Clean up the description
                lines = desc.split('\n')
                cleaned = [line.strip() for line in lines if line.strip()]
                if cleaned:
                    return ' '.join(cleaned[:3])  # First 3 lines
                    
        # Generate from code structure
        return StackSpecificTrainingFormatter._generate_from_code_structure(sample)
    
    @staticmethod
    def _generate_from_code_structure(sample: CodeSample) -> str:
        """Generate description from code structure"""
        content = sample.content
        lang = sample.language
        
        # Identify main components
        components = []
        
        if lang == 'python':
            classes = re.findall(r'class\s+(\w+)', content)
            functions = re.findall(r'def\s+(\w+)', content)
            if classes:
                components.append(f"a {classes[0]} class")
            if functions:
                main_func = [f for f in functions if f != '__init__'][0] if functions else functions[0]
                components.append(f"a {main_func} function")
                
        elif lang == 'rust':
            structs = re.findall(r'struct\s+(\w+)', content)
            traits = re.findall(r'trait\s+(\w+)', content)
            functions = re.findall(r'fn\s+(\w+)', content)
            if structs:
                components.append(f"a {structs[0]} struct")
            if traits:
                components.append(f"a {traits[0]} trait")
            if functions:
                components.append(f"a {functions[0]} function")
                
        # Database operations
        if any(db in content.lower() for db in ['postgres', 'mongo', 'elasticsearch']):
            components.append("database operations")
            
        # API endpoints
        if re.search(r'@(app|router)\.(get|post|put|delete)', content):
            components.append("API endpoints")
            
        if components:
            return f"implements {' with '.join(components)}"
        else:
            return "provides the required functionality"
    
    @staticmethod
    def _extract_context(sample: CodeSample) -> str:
        """Extract meaningful context from the code"""
        contexts = []
        
        # Add category context
        if sample.category and sample.category != 'general':
            contexts.append(f"Application type: {sample.category}")
            
        # Add framework context
        if sample.frameworks:
            contexts.append(f"Technologies: {', '.join(sample.frameworks)}")
            
        # Add database context if present
        content_lower = sample.content.lower()
        databases = []
        db_map = {
            'postgres': 'PostgreSQL',
            'mongodb': 'MongoDB',
            'elasticsearch': 'Elasticsearch',
            'redis': 'Redis',
            'mssql': 'SQL Server'
        }
        
        for db_key, db_name in db_map.items():
            if db_key in content_lower:
                databases.append(db_name)
                
        if databases:
            contexts.append(f"Databases: {', '.join(databases)}")
            
        # Add cloud context
        if 'azure' in content_lower:
            contexts.append("Cloud platform: Azure")
            
        return '\n'.join(contexts) if contexts else ""
    
    @staticmethod
    def _generate_tech_context(sample: CodeSample) -> str:
        """Generate technology-specific context"""
        contexts = []
        
        # Language-specific context
        lang_contexts = {
            'python': "Use modern Python with type hints and async/await where appropriate.",
            'rust': "Ensure memory safety and use idiomatic Rust patterns.",
            'go': "Follow Go conventions with proper error handling and concurrency patterns.",
            'typescript': "Use strict TypeScript with proper type definitions.",
            'dart': "Implement using Flutter best practices and null safety.",
        }
        
        if sample.language in lang_contexts:
            contexts.append(lang_contexts[sample.language])
            
        # Framework-specific context
        if 'pytorch' in sample.frameworks:
            contexts.append("Optimize for GPU computation and use PyTorch best practices.")
        if 'angular' in sample.frameworks:
            contexts.append("Follow Angular style guide with reactive patterns.")
        if 'flutter' in sample.frameworks:
            contexts.append("Create responsive Flutter widgets with proper state management.")
            
        # Quality requirements
        if sample.quality_score >= 0.9:
            contexts.append("This should be production-ready code with comprehensive error handling.")
        elif sample.quality_score >= 0.8:
            contexts.append("Ensure code follows best practices and is well-documented.")
            
        return ' '.join(contexts) if contexts else ""


# Example usage
if __name__ == "__main__":
    # Configuration for your specific needs
    config = {
        'min_length': 100,
        'max_length': 5000,
        'final_quality_threshold': 0.80,
        'quality_thresholds': {
            'structure': 0.75,
            'documentation': 0.65,
            'complexity': 0.65,
            'naming': 0.75,
            'patterns': 0.75,
            'security': 0.85,
            'performance': 0.70,
            'testability': 0.70,
            'framework_usage': 0.70,
            'database_usage': 0.60,
        },
        'require_framework_code': True,
        'require_meaningful_logic': True,
    }
    
    # Initialize curator
    curator = StackSpecificCodeCurator(config)
    
    # Example samples (you would load from your repos)
    sample_data = [
        CodeSample(
            content='''
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, Post
from app.database import get_db
from app.schemas import PostCreate, PostResponse
from app.auth import get_current_user

app = FastAPI(title="Blog API")

@app.post("/posts", response_model=PostResponse)
async def create_post(
    post: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PostResponse:
    """Create a new blog post.
    
    Args:
        post: Post creation data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Created post with metadata
        
    Raises:
        HTTPException: If post creation fails
    """
    try:
        db_post = Post(
            title=post.title,
            content=post.content,
            author_id=current_user.id,
            tags=post.tags
        )
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        
        return PostResponse.from_orm(db_post)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")

@app.get("/posts", response_model=List[PostResponse])
async def list_posts(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
) -> List[PostResponse]:
    """List all posts with pagination."""
    query = select(Post).offset(skip).limit(limit).order_by(Post.created_at.desc())
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return [PostResponse.from_orm(post) for post in posts]
            ''',
            language='python',
            metadata={
                'filename': 'blog_api.py',
                'repo': 'fastapi-blog',
                'stars': 450,
                'has_tests': True
            }
        )
    ]
    
    # Run curation
    curated_samples, report = curator.curate_dataset(sample_data, manual_review_size=50)
    
    # Print detailed report
    print("\n=== Stack-Specific Quality Report ===")
    print(f"Total samples processed: {report.total_samples}")
    print(f"High-quality samples selected: {report.filtered_samples}")
    
    print(f"\nQuality distribution:")
    for score, count in sorted(report.quality_distribution.items(), reverse=True):
        print(f"  {score}: {count} samples")
        
    print(f"\nLanguage breakdown:")
    for lang, count in report.language_breakdown.items():
        print(f"  {lang}: {count} samples")
        
    print(f"\nCategory breakdown:")
    for cat, count in sorted(report.category_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count} samples")
        
    print(f"\nFramework breakdown:")
    for fw, count in sorted(report.framework_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {fw}: {count} samples")
        
    print(f"\nAverage quality scores:")
    for component, score in sorted(report.average_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {component}: {score:.3f}")
        
    print(f"\nMost common issues:")
    for issue, count in report.common_issues[:10]:
        print(f"  {issue}: {count} occurrences")
        
    print(f"\nExcluded files:")
    for pattern, count in report.excluded_files.items():
        print(f"  {pattern}: {count} files")
    
    # Convert to training format
    training_data = StackSpecificTrainingFormatter.create_training_format(
        curated_samples, 
        format_type='alpaca'
    )
    
    # Save curated dataset with rich metadata
    output_data = {
        'metadata': {
            'curation_date': datetime.now().isoformat(),
            'curator_version': '2.0',
            'total_processed': report.total_samples,
            'total_selected': report.filtered_samples,
            'config': config,
            'target_stack': {
                'languages': ['rust', 'go', 'python', 'dart/flutter', 'typescript/angular'],
                'databases': ['postgres', 'mssql', 'mongodb', 'vector_db', 'elasticsearch'],
                'frameworks': ['pytorch', 'fastapi', 'angular', 'flutter', 'actix-web', 'gin'],
                'cloud': 'azure',
                'categories': ['cli', 'desktop', 'web', 'ai', 'api', 'ml', 'systems']
            }
        },
        'quality_report': {
            'distribution': dict(report.quality_distribution),
            'languages': dict(report.language_breakdown),
            'categories': dict(report.category_breakdown),
            'frameworks': dict(report.framework_breakdown),
            'average_scores': report.average_scores,
            'common_issues': report.common_issues,
            'excluded_patterns': report.excluded_files
        },
        'samples': training_data
    }
    
    # Save to file
    with open('stack_specific_training_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved {len(training_data)} high-quality samples to stack_specific_training_data.json")
    
    # Generate sample statistics
    print("\n=== Sample Statistics ===")
    total_lines = sum(sample.content.count('\n') for sample in curated_samples)
    avg_lines = total_lines / len(curated_samples) if curated_samples else 0
    print(f"Average lines per sample: {avg_lines:.1f}")
    
    total_chars = sum(len(sample.content) for sample in curated_samples)
    avg_chars = total_chars / len(curated_samples) if curated_samples else 0
    print(f"Average characters per sample: {avg_chars:.1f}")
    
    # Show a few examples
    print("\n=== Example High-Quality Samples ===")
    for i, sample in enumerate(curated_samples[:3]):
        print(f"\n--- Example {i+1} ---")
        print(f"Language: {sample.language}")
        print(f"Frameworks: {', '.join(sample.frameworks) if sample.frameworks else 'None'}")
        print(f"Category: {sample.category}")
        print(f"Quality Score: {sample.quality_score:.3f}")
        print(f"Quality Breakdown:")
        for component, score in sorted(sample.quality_breakdown.items(), key=lambda x: x[1], reverse=True):
            print(f"  {component}: {score:.3f}")
        print(f"First 10 lines:")
        print('\n'.join(sample.content.split('\n')[:10]))
        print("...")
