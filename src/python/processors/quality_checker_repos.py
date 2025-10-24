#!/usr/bin/env python3
"""
Quality check system for cloned repositories
Validates repo integrity, analyzes code quality, and generates reports
"""

import json
import os
import subprocess
import time
import threading
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import hashlib
from collections import defaultdict, Counter
import re
from datetime import datetime

class RepoQualityChecker:
    """Comprehensive quality checker for cloned repositories"""
    
    def __init__(self, base_dir: str = None, max_workers: int = 4):
        # Windows paths
        nas_dir = r"\\192.168.1.66\plex3\codelupe\repos"  # Your repo directory
        local_dir = r"\\192.168.1.66\plex3\codelupe\repos"  # Same location
        
        if base_dir is None:
            base_dir = nas_dir  # Default to G:\repos
            
        if base_dir == nas_dir:
            try:
                # Test directory accessibility
                os.listdir(nas_dir)
                self.base_dir = nas_dir
                print(f"✅ Using repo directory: {nas_dir}")
            except Exception as e:
                print(f"⚠️  Directory unavailable ({e}), checking fallback")
                self.base_dir = local_dir
                print(f"✅ Using repo directory: {local_dir}")
        else:
            self.base_dir = base_dir
            
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
        # Quality check results
        self.checked_repos = []
        self.failed_checks = []
        self.stats = {
            'total_repos': 0,
            'valid_repos': 0,
            'corrupted_repos': 0,
            'empty_repos': 0,
            'no_code_repos': 0,
            'languages': Counter(),
            'total_files': 0,
            'total_size_mb': 0,
            'has_readme': 0,
            'has_license': 0,
            'has_tests': 0,
        }
        
        # File extensions mapping to languages
        self.language_extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.go': 'Go',
            '.rs': 'Rust',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.r': 'R',
            '.m': 'Objective-C',
            '.sh': 'Shell',
            '.pl': 'Perl',
            '.lua': 'Lua',
            '.dart': 'Dart',
            '.elm': 'Elm',
            '.ex': 'Elixir',
            '.fs': 'F#',
            '.hs': 'Haskell',
            '.clj': 'Clojure',
            '.ml': 'OCaml',
            '.vim': 'Vim Script',
            '.sql': 'SQL',
        }
        
        # Code file extensions
        self.code_extensions = set(self.language_extensions.keys())
        self.code_extensions.update([
            '.html', '.css', '.scss', '.sass', '.less',
            '.jsx', '.tsx', '.vue', '.svelte',
            '.json', '.xml', '.yaml', '.yml',
            '.toml', '.ini', '.cfg', '.conf',
        ])
        
        # Test indicators
        self.test_indicators = {
            'test', 'tests', 'spec', 'specs', '__tests__',
            'testing', 'e2e', 'integration', 'unit'
        }

    def is_git_repo(self, repo_path: str) -> bool:
        """Check if directory is a valid git repository"""
        try:
            git_dir = os.path.join(repo_path, '.git')
            return os.path.exists(git_dir)
        except Exception:
            return False

    def get_repo_size(self, repo_path: str) -> float:
        """Get repository size in MB"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(repo_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, IOError):
                        continue
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0

    def count_files_and_lines(self, repo_path: str) -> Dict[str, Any]:
        """Count files, lines of code, and detect languages"""
        stats = {
            'total_files': 0,
            'code_files': 0,
            'total_lines': 0,
            'code_lines': 0,
            'languages': Counter(),
            'file_types': Counter(),
        }
        
        try:
            for root, dirs, files in os.walk(repo_path):
                # Skip .git and other hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    stats['total_files'] += 1
                    
                    # Get file extension
                    _, ext = os.path.splitext(file.lower())
                    stats['file_types'][ext] += 1
                    
                    # Check if it's a code file
                    if ext in self.code_extensions:
                        stats['code_files'] += 1
                        
                        # Detect language
                        if ext in self.language_extensions:
                            lang = self.language_extensions[ext]
                            stats['languages'][lang] += 1
                        
                        # Count lines
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                file_lines = len(lines)
                                stats['total_lines'] += file_lines
                                
                                # Count non-empty lines as code lines
                                code_lines = sum(1 for line in lines if line.strip())
                                stats['code_lines'] += code_lines
                                
                        except Exception:
                            continue
                            
        except Exception as e:
            print(f"Error analyzing {repo_path}: {e}")
            
        return stats

    def check_repo_health(self, repo_path: str) -> Dict[str, Any]:
        """Enhanced repository health assessment"""
        health = {
            'has_readme': False,
            'has_license': False,
            'has_tests': False,
            'has_gitignore': False,
            'has_package_json': False,
            'has_requirements': False,
            'has_dockerfile': False,
            'has_ci_config': False,
            'has_makefile': False,
            'has_changelog': False,
            'has_contributing': False,
            'has_code_of_conduct': False,
            'has_security_policy': False,
            'readme_files': [],
            'license_files': [],
            'test_directories': [],
            'ci_files': [],
            'readme_quality': 0,  # 0-100 score
            'documentation_coverage': 0,  # 0-100 score
            'test_coverage_indicators': {
                'test_files': 0,
                'test_directories': 0,
                'has_coverage_config': False,
                'has_test_scripts': False
            },
            'dependency_health': {
                'has_lockfile': False,
                'has_security_audit': False,
                'outdated_dependencies': False
            }
        }
        
        test_file_count = 0
        doc_file_count = 0
        total_code_files = 0
        
        try:
            for root, dirs, files in os.walk(repo_path):
                level = root.replace(repo_path, '').count(os.sep)
                if level > 3:  # Don't go too deep
                    continue
                    
                for file in files:
                    file_lower = file.lower()
                    file_path = os.path.join(root, file)
                    
                    # Count code files for coverage calculation
                    _, ext = os.path.splitext(file_lower)
                    if ext in self.code_extensions:
                        total_code_files += 1
                    
                    # README detection and quality assessment
                    if file_lower.startswith('readme'):
                        health['has_readme'] = True
                        health['readme_files'].append(file_path)
                        health['readme_quality'] = self._assess_readme_quality(file_path)
                    
                    # License detection
                    elif file_lower.startswith('license') or file_lower.startswith('licence'):
                        health['has_license'] = True
                        health['license_files'].append(file_path)
                    
                    # Test file detection
                    elif any(indicator in file_lower for indicator in self.test_indicators):
                        health['has_tests'] = True
                        test_file_count += 1
                        health['test_coverage_indicators']['test_files'] += 1
                    
                    # Documentation files
                    elif any(doc_indicator in file_lower for doc_indicator in 
                           ['doc', 'docs', 'documentation', 'manual', 'guide']):
                        doc_file_count += 1
                    
                    # Enhanced file detection
                    elif file_lower == '.gitignore':
                        health['has_gitignore'] = True
                    elif file_lower == 'package.json':
                        health['has_package_json'] = True
                    elif file_lower in ['requirements.txt', 'requirements.pip', 'pipfile', 'pyproject.toml']:
                        health['has_requirements'] = True
                    elif file_lower in ['package-lock.json', 'yarn.lock', 'pipfile.lock', 'poetry.lock']:
                        health['dependency_health']['has_lockfile'] = True
                    elif file_lower in ['dockerfile', 'docker-compose.yml', 'docker-compose.yaml']:
                        health['has_dockerfile'] = True
                    elif file_lower in ['makefile', 'cmake', 'cmakelist.txt']:
                        health['has_makefile'] = True
                    elif file_lower in ['changelog', 'changelog.md', 'history.md', 'news.md']:
                        health['has_changelog'] = True
                    elif file_lower in ['contributing.md', 'contributing.rst', 'contributing.txt']:
                        health['has_contributing'] = True
                    elif file_lower in ['code_of_conduct.md', 'code-of-conduct.md']:
                        health['has_code_of_conduct'] = True
                    elif file_lower in ['security.md', 'security.rst', 'security.txt']:
                        health['has_security_policy'] = True
                    elif file_lower in ['.coveragerc', 'coverage.xml', '.coverage', 'codecov.yml']:
                        health['test_coverage_indicators']['has_coverage_config'] = True
                    
                    # CI/CD detection
                    elif (file_lower in ['.travis.yml', '.gitlab-ci.yml', 'jenkinsfile', 'azure-pipelines.yml'] or
                          file_lower.startswith('.github/workflows/')):
                        health['has_ci_config'] = True
                        health['ci_files'].append(file_path)
                
                for dir_name in dirs:
                    dir_lower = dir_name.lower()
                    
                    # Test directory detection
                    if any(indicator in dir_lower for indicator in self.test_indicators):
                        health['has_tests'] = True
                        health['test_directories'].append(os.path.join(root, dir_name))
                        health['test_coverage_indicators']['test_directories'] += 1
                    
                    # CI directory detection
                    elif dir_lower in ['.github', '.gitlab', '.circleci', '.buildkite']:
                        health['has_ci_config'] = True
            
            # Calculate documentation coverage
            if total_code_files > 0:
                health['documentation_coverage'] = min(100, (doc_file_count / total_code_files) * 100)
            
            # Check for test scripts in package.json or similar
            if health['has_package_json']:
                health['test_coverage_indicators']['has_test_scripts'] = self._check_test_scripts(repo_path)
                        
        except Exception as e:
            print(f"Error checking health of {repo_path}: {e}")
            
        return health
    
    def _assess_readme_quality(self, readme_path: str) -> int:
        """Assess README quality on a 0-100 scale"""
        score = 0
        
        try:
            with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
            # Basic length check (10 points)
            if len(content) > 500:
                score += 10
            elif len(content) > 200:
                score += 5
            
            # Common sections (70 points total)
            sections = {
                'description': ['description', 'about', 'overview', 'what is'],
                'installation': ['install', 'setup', 'getting started'],
                'usage': ['usage', 'example', 'how to', 'quickstart'],
                'contributing': ['contribut', 'development', 'build'],
                'license': ['license', 'licence'],
                'api': ['api', 'documentation', 'docs'],
                'testing': ['test', 'testing', 'ci']
            }
            
            for section, keywords in sections.items():
                if any(keyword in content for keyword in keywords):
                    score += 10
            
            # Code examples (10 points)
            if '```' in content or '    ' in content:  # Code blocks
                score += 10
            
            # Links (10 points)
            if '[' in content and '](' in content:  # Markdown links
                score += 10
                
        except Exception:
            pass
            
        return min(score, 100)
    
    def _check_test_scripts(self, repo_path: str) -> bool:
        """Check if project has test scripts configured"""
        try:
            package_json_path = os.path.join(repo_path, 'package.json')
            if os.path.exists(package_json_path):
                with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                    import json
                    data = json.load(f)
                    scripts = data.get('scripts', {})
                    return any(script_name in scripts.lower() for script_name in ['test', 'spec', 'jest', 'mocha'])
        except Exception:
            pass
        return False

    def check_repo_corruption(self, repo_path: str) -> Dict[str, Any]:
        """Check for corruption indicators"""
        corruption_check = {
            'is_corrupted': False,
            'corruption_indicators': [],
            'git_status': 'unknown',
        }
        
        try:
            # Check git integrity
            if self.is_git_repo(repo_path):
                try:
                    result = subprocess.run(
                        ['git', 'fsck', '--quiet'],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        corruption_check['git_status'] = 'healthy'
                    else:
                        corruption_check['git_status'] = 'corrupted'
                        corruption_check['is_corrupted'] = True
                        corruption_check['corruption_indicators'].append('git fsck failed')
                        
                except Exception:
                    corruption_check['git_status'] = 'check_failed'
            
            # Check for empty directories that should have content
            if os.path.exists(repo_path) and os.path.isdir(repo_path):
                contents = os.listdir(repo_path)
                if not contents:
                    corruption_check['is_corrupted'] = True
                    corruption_check['corruption_indicators'].append('completely empty directory')
                elif contents == ['.git']:
                    corruption_check['is_corrupted'] = True
                    corruption_check['corruption_indicators'].append('only .git directory present')
                    
        except Exception as e:
            corruption_check['corruption_indicators'].append(f'check failed: {e}')
            
        return corruption_check

    def analyze_single_repo(self, repo_path: str) -> Dict[str, Any]:
        """Perform comprehensive analysis of a single repository"""
        repo_name = os.path.basename(repo_path)
        owner = os.path.basename(os.path.dirname(repo_path))
        
        analysis = {
            'repo_path': repo_path,
            'owner': owner,
            'repo_name': repo_name,
            'timestamp': datetime.now().isoformat(),
            'is_valid': False,
            'size_mb': 0.0,
            'file_stats': {},
            'health': {},
            'corruption': {},
            'quality_score': 0,
        }
        
        try:
            # Basic validation
            if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
                analysis['error'] = 'Repository directory does not exist'
                return analysis
            
            # Check if it's a git repo
            analysis['is_git_repo'] = self.is_git_repo(repo_path)
            
            # Get size
            analysis['size_mb'] = self.get_repo_size(repo_path)
            
            # File and code analysis
            analysis['file_stats'] = self.count_files_and_lines(repo_path)
            
            # Health check
            analysis['health'] = self.check_repo_health(repo_path)
            
            # Corruption check
            analysis['corruption'] = self.check_repo_corruption(repo_path)
            
            # Advanced validation
            analysis = self._perform_advanced_validation(analysis)
            
            # Calculate enhanced quality score (0-100)
            quality_score = 0
            
            # Basic validity (30 points)
            if analysis['is_git_repo']:
                quality_score += 15
            if analysis['file_stats']['code_files'] > 0:
                quality_score += 15
                
            # Health indicators (40 points)
            if analysis['health']['has_readme']:
                quality_score += 10
            if analysis['health']['has_license']:
                quality_score += 10
            if analysis['health']['has_tests']:
                quality_score += 10
            if analysis['health']['has_gitignore']:
                quality_score += 5
            if analysis['health']['has_package_json'] or analysis['health']['has_requirements']:
                quality_score += 5
                
            # Size and content (20 points)
            if analysis['size_mb'] > 0.1:  # At least 100KB
                quality_score += 5
            if analysis['file_stats']['code_lines'] > 100:
                quality_score += 10
            if len(analysis['file_stats']['languages']) > 0:
                quality_score += 5
                
            # Corruption penalty (10 points)
            if not analysis['corruption']['is_corrupted']:
                quality_score += 10
            
            analysis['quality_score'] = quality_score
            analysis['is_valid'] = quality_score >= 30  # Minimum threshold
            
        except Exception as e:
            analysis['error'] = str(e)
            
        return analysis
    
    def _perform_advanced_validation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Perform advanced validation checks"""
        validation_flags = {
            'security_risks': False,
            'suspicious_patterns': False,
            'critical_issues': False,
            'performance_concerns': False,
            'maintenance_issues': False,
            'flags': []
        }
        
        try:
            repo_path = analysis['repo_path']
            
            # Security validation
            security_issues = self._check_security_patterns(repo_path)
            if security_issues:
                validation_flags['security_risks'] = True
                validation_flags['flags'].extend(security_issues)
            
            # Suspicious pattern detection
            suspicious_patterns = self._detect_suspicious_patterns(repo_path)
            if suspicious_patterns:
                validation_flags['suspicious_patterns'] = True
                validation_flags['flags'].extend(suspicious_patterns)
            
            # Performance concerns
            performance_issues = self._check_performance_concerns(analysis)
            if performance_issues:
                validation_flags['performance_concerns'] = True
                validation_flags['flags'].extend(performance_issues)
            
            # Maintenance issues
            maintenance_issues = self._check_maintenance_issues(analysis)
            if maintenance_issues:
                validation_flags['maintenance_issues'] = True
                validation_flags['flags'].extend(maintenance_issues)
            
            # Critical issues flag
            critical_patterns = ['malware', 'virus', 'backdoor', 'keylogger']
            for flag in validation_flags['flags']:
                if any(pattern in flag.lower() for pattern in critical_patterns):
                    validation_flags['critical_issues'] = True
                    break
            
            analysis['validation_flags'] = validation_flags
            
        except Exception as e:
            validation_flags['flags'].append(f'Validation error: {e}')
            analysis['validation_flags'] = validation_flags
            
        return analysis
    
    def _check_security_patterns(self, repo_path: str) -> List[str]:
        """Check for security-related patterns and vulnerabilities"""
        security_issues = []
        
        try:
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    file_lower = file.lower()
                    
                    # Check for suspicious file extensions
                    suspicious_extensions = ['.exe', '.dll', '.scr', '.bat', '.cmd']
                    _, ext = os.path.splitext(file_lower)
                    if ext in suspicious_extensions:
                        security_issues.append(f'Suspicious executable: {file}')
                    
                    # Check for potential secrets in filenames
                    secret_indicators = ['password', 'secret', 'key', 'token', 'credential']
                    if any(indicator in file_lower for indicator in secret_indicators):
                        security_issues.append(f'Potential secrets file: {file}')
                    
                    # Check text files for common security issues
                    if ext in ['.py', '.js', '.java', '.php', '.rb', '.go']:
                        file_issues = self._scan_file_for_security(file_path)
                        security_issues.extend(file_issues)
                        
        except Exception:
            pass
            
        return security_issues[:10]  # Limit to first 10 issues
    
    def _scan_file_for_security(self, file_path: str) -> List[str]:
        """Scan individual file for security issues"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # First 1000 characters only
                
            # Check for hardcoded secrets
            secret_patterns = [
                r'password\s*=\s*["\'][^"\'\n]{8,}["\']',
                r'api_key\s*=\s*["\'][^"\'\n]+["\']',
                r'secret\s*=\s*["\'][^"\'\n]+["\']',
                r'token\s*=\s*["\'][^"\'\n]{20,}["\']'
            ]
            
            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    filename = os.path.basename(file_path)
                    issues.append(f'Potential hardcoded secret in {filename}')
                    break
                    
            # Check for unsafe functions
            unsafe_patterns = [
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\(',
                r'shell_exec\s*\('
            ]
            
            for pattern in unsafe_patterns:
                if re.search(pattern, content):
                    filename = os.path.basename(file_path)
                    issues.append(f'Unsafe function usage in {filename}')
                    break
                    
        except Exception:
            pass
            
        return issues
    
    def _detect_suspicious_patterns(self, repo_path: str) -> List[str]:
        """Detect suspicious patterns that might indicate malicious code"""
        suspicious = []
        
        try:
            # Check for suspicious directory names
            for root, dirs, files in os.walk(repo_path):
                for dir_name in dirs:
                    dir_lower = dir_name.lower()
                    suspicious_dir_names = ['malware', 'virus', 'hack', 'crack', 'keygen']
                    if any(sus_name in dir_lower for sus_name in suspicious_dir_names):
                        suspicious.append(f'Suspicious directory name: {dir_name}')
                        
                # Check for obfuscated files
                for file in files:
                    if len(file) > 50 and not any(c.isalpha() for c in file[:20]):
                        suspicious.append(f'Potentially obfuscated filename: {file[:50]}...')
                        
        except Exception:
            pass
            
        return suspicious[:5]  # Limit to first 5 issues
    
    def _check_performance_concerns(self, analysis: Dict[str, Any]) -> List[str]:
        """Check for performance-related concerns"""
        concerns = []
        
        try:
            file_stats = analysis.get('file_stats', {})
            
            # Check for very large files
            largest_files = file_stats.get('largest_files', [])
            for file_info in largest_files[:3]:
                if file_info.get('size_mb', 0) > 50:
                    concerns.append(f'Very large file: {os.path.basename(file_info["path"])} ({file_info["size_mb"]:.1f}MB)')
            
            # Check for excessive nesting
            complexity = file_stats.get('complexity_indicators', {})
            if complexity.get('deeply_nested_dirs', 0) > 10:
                concerns.append(f'Excessive directory nesting: {complexity["deeply_nested_dirs"]} deep directories')
            
            # Check for files with too many lines
            if complexity.get('files_over_1000_lines', 0) > 5:
                concerns.append(f'Multiple large files: {complexity["files_over_1000_lines"]} files over 1000 lines')
                
        except Exception:
            pass
            
        return concerns
    
    def _check_maintenance_issues(self, analysis: Dict[str, Any]) -> List[str]:
        """Check for maintenance-related issues"""
        issues = []
        
        try:
            health = analysis.get('health', {})
            file_stats = analysis.get('file_stats', {})
            corruption = analysis.get('corruption', {})
            
            # Documentation issues
            if not health.get('has_readme'):
                issues.append('No README file found')
            elif health.get('readme_quality', 0) < 30:
                issues.append('Poor README quality')
            
            # License issues
            if not health.get('has_license'):
                issues.append('No license file found')
            
            # Test coverage issues
            if not health.get('has_tests'):
                issues.append('No tests found')
            
            # Code quality issues
            total_lines = file_stats.get('total_lines', 0)
            comment_lines = file_stats.get('comment_lines', 0)
            if total_lines > 100 and comment_lines == 0:
                issues.append('No comments found in codebase')
            
            # File integrity issues
            integrity = corruption.get('file_integrity', {})
            if integrity.get('duplicate_files'):
                issues.append(f'Duplicate files detected: {len(integrity["duplicate_files"])} sets')
            
            if integrity.get('corrupted_files'):
                issues.append(f'Corrupted files detected: {len(integrity["corrupted_files"])} files')
                
        except Exception:
            pass
            
        return issues[:8]  # Limit to first 8 issues

    def find_all_repos(self) -> List[str]:
        """Find all repository directories"""
        repos = []
        
        try:
            for owner_dir in os.listdir(self.base_dir):
                owner_path = os.path.join(self.base_dir, owner_dir)
                if not os.path.isdir(owner_path):
                    continue
                
                for repo_dir in os.listdir(owner_path):
                    repo_path = os.path.join(owner_path, repo_dir)
                    if os.path.isdir(repo_path):
                        repos.append(repo_path)
                        
        except Exception as e:
            print(f"Error finding repositories: {e}")
            
        return repos

    def quality_check_parallel(self, repo_paths: List[str] = None):
        """Run quality checks on repositories in parallel"""
        if repo_paths is None:
            print("🔍 Scanning for repositories...")
            repo_paths = self.find_all_repos()
        
        print(f"🧪 Starting quality check on {len(repo_paths)} repositories...")
        print(f"📁 Base directory: {os.path.abspath(self.base_dir)}")
        print(f"🧵 Using {self.max_workers} worker threads")
        
        start_time = time.time()
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all analysis tasks
            future_to_path = {
                executor.submit(self.analyze_single_repo, path): path 
                for path in repo_paths
            }
            
            # Process completed tasks
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed += 1
                
                try:
                    analysis = future.result()
                    
                    with self.lock:
                        self.checked_repos.append(analysis)
                        self.stats['total_repos'] += 1
                        
                        if analysis.get('is_valid', False):
                            self.stats['valid_repos'] += 1
                        
                        if analysis.get('corruption', {}).get('is_corrupted', False):
                            self.stats['corrupted_repos'] += 1
                        
                        if analysis.get('file_stats', {}).get('total_files', 0) == 0:
                            self.stats['empty_repos'] += 1
                        
                        if analysis.get('file_stats', {}).get('code_files', 0) == 0:
                            self.stats['no_code_repos'] += 1
                        
                        # Update language and category stats
                        for lang, count in analysis.get('file_stats', {}).get('languages', {}).items():
                            self.stats['languages'][lang] += count
                        
                        # Update file category stats
                        for category, count in analysis.get('file_stats', {}).get('file_categories', {}).items():
                            if category not in self.stats:
                                self.stats[category] = 0
                            self.stats[category] += count
                        
                        # Update other stats
                        self.stats['total_files'] += analysis.get('file_stats', {}).get('total_files', 0)
                        self.stats['total_size_mb'] += analysis.get('size_mb', 0)
                        
                        # Update corruption and integrity stats
                        corruption_data = analysis.get('corruption', {})
                        if corruption_data.get('file_integrity', {}).get('corrupted_files'):
                            if 'corrupted_files' not in self.stats:
                                self.stats['corrupted_files'] = 0
                            self.stats['corrupted_files'] += len(corruption_data['file_integrity']['corrupted_files'])
                        
                        if corruption_data.get('file_integrity', {}).get('duplicate_files'):
                            if 'duplicate_files' not in self.stats:
                                self.stats['duplicate_files'] = 0
                            self.stats['duplicate_files'] += len(corruption_data['file_integrity']['duplicate_files'])
                        
                        # Update validation stats
                        validation_flags = analysis.get('validation_flags', {})
                        for flag_type, has_flag in validation_flags.items():
                            if isinstance(has_flag, bool) and has_flag:
                                self.stats['validation_flags'][flag_type] += 1
                        
                        # Track repositories by quality level
                        quality_score = analysis.get('quality_score', 0)
                        if quality_score >= 80:
                            self.stats['high_quality_repos'] += 1
                        if validation_flags.get('security_risks') or validation_flags.get('suspicious_patterns'):
                            self.stats['suspicious_repos'] += 1
                        
                        if analysis.get('health', {}).get('has_readme', False):
                            self.stats['has_readme'] += 1
                        if analysis.get('health', {}).get('has_license', False):
                            self.stats['has_license'] += 1
                        if analysis.get('health', {}).get('has_tests', False):
                            self.stats['has_tests'] += 1
                    
                    # Progress update
                    if completed % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = len(repo_paths) - completed
                        eta = remaining / rate if rate > 0 else 0
                        
                        print(f"\n📊 Progress: {completed}/{len(repo_paths)} "
                              f"({completed/len(repo_paths)*100:.1f}%)")
                        print(f"⏱️  Rate: {rate:.1f} repos/sec, ETA: {eta/60:.1f} minutes")
                        print(f"✅ Valid: {self.stats['valid_repos']}")
                        print(f"❌ Invalid: {self.stats['total_repos'] - self.stats['valid_repos']}\n")
                        
                except Exception as e:
                    print(f"❌ Exception analyzing {path}: {e}")
                    with self.lock:
                        self.failed_checks.append({'path': path, 'error': str(e)})
        
        # Final summary
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n🎉 Quality check completed!")
        print(f"⏱️  Total time: {total_time/60:.1f} minutes")
        print(f"📊 Results:")
        print(f"   Total repositories: {self.stats['total_repos']}")
        print(f"   Valid repositories: {self.stats['valid_repos']}")
        print(f"   Corrupted repositories: {self.stats['corrupted_repos']}")
        print(f"   Empty repositories: {self.stats['empty_repos']}")
        print(f"   Repositories without code: {self.stats['no_code_repos']}")
        print(f"   Total files analyzed: {self.stats['total_files']:,}")
        print(f"   Total size: {self.stats['total_size_mb']:.1f} MB")
        print(f"   Repos with README: {self.stats['has_readme']}")
        print(f"   Repos with license: {self.stats['has_license']}")
        print(f"   Repos with tests: {self.stats['has_tests']}")
        
        # Enhanced reporting
        if self.stats['languages']:
            print(f"\n🔤 Top programming languages:")
            for lang, count in self.stats['languages'].most_common(10):
                print(f"   {lang}: {count} files")
        
        print(f"\n📂 File categories:")
        for category in ['source_code', 'markup', 'data', 'binary']:
            count = sum(1 for repo in self.checked_repos 
                       if repo.get('file_stats', {}).get('file_categories', {}).get(category, 0) > 0)
            print(f"   Repos with {category}: {count}")
            
        if self.stats.get('corrupted_files', 0) > 0 or self.stats.get('duplicate_files', 0) > 0:
            print(f"\n⚠️  Integrity Issues:")
            if self.stats.get('corrupted_files', 0) > 0:
                print(f"   Corrupted files found: {self.stats['corrupted_files']}")
            if self.stats.get('duplicate_files', 0) > 0:
                print(f"   Repos with duplicates: {self.stats['duplicate_files']}")
        
        print(f"\n📊 Quality Insights:")
        quality_dist = self._calculate_quality_distribution()
        for level, count in quality_dist.items():
            print(f"   {level.title()} quality: {count} repos")
            
        health_metrics = self._calculate_health_metrics()
        if health_metrics:
            print(f"\n🏥 Health Metrics:")
            for metric, value in health_metrics.items():
                print(f"   {metric.replace('_', ' ').title()}: {value:.1f}%")
        
        # Validation and security summary
        if self.stats.get('validation_flags'):
            print(f"\n🔒 Security & Validation:")
            for flag_type, count in self.stats['validation_flags'].most_common():
                print(f"   {flag_type.replace('_', ' ').title()}: {count} repos")
        
        if self.stats.get('suspicious_repos', 0) > 0:
            print(f"   Suspicious repositories: {self.stats['suspicious_repos']}")
        if self.stats.get('high_quality_repos', 0) > 0:
            print(f"   High-quality repositories: {self.stats['high_quality_repos']}")
        
        # Save results
        self.save_results()

    def save_results(self):
        """Save quality check results to JSON files"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save detailed results
            results_file = f"quality_check_results_{timestamp}.json"
            with open(results_file, "w") as f:
                json.dump({
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'base_directory': self.base_dir,
                        'total_repos_checked': len(self.checked_repos),
                        'failed_checks': len(self.failed_checks),
                    },
                    'statistics': dict(self.stats),
                    'detailed_results': self.checked_repos,
                    'failed_checks': self.failed_checks,
                }, f, indent=2, default=str)
            
            # Save summary statistics
            summary_file = f"quality_summary_{timestamp}.json"
            with open(summary_file, "w") as f:
                json.dump({
                    'summary': dict(self.stats),
                    'top_languages': dict(self.stats['languages'].most_common(20)),
                    'timestamp': datetime.now().isoformat(),
                }, f, indent=2)
            
            # Save list of high-quality repos (score >= 70)
            high_quality_repos = [
                {
                    'path': repo['repo_path'],
                    'owner': repo['owner'],
                    'name': repo['repo_name'],
                    'quality_score': repo['quality_score'],
                    'size_mb': repo['size_mb'],
                    'languages': dict(repo.get('file_stats', {}).get('languages', {})),
                }
                for repo in self.checked_repos 
                if repo.get('quality_score', 0) >= 70
            ]
            
            quality_file = f"high_quality_repos_{timestamp}.json"
            with open(quality_file, "w") as f:
                json.dump(high_quality_repos, f, indent=2)
            
            print(f"\n💾 Results saved:")
            print(f"   Detailed results: {results_file}")
            print(f"   Summary statistics: {summary_file}")
            print(f"   High-quality repos ({len(high_quality_repos)}): {quality_file}")
            
        except Exception as e:
            print(f"⚠️ Failed to save results: {e}")

def generate_custom_report(results_file: str, filters: Dict[str, Any]) -> str:
    """Generate custom filtered report from existing results"""
    try:
        with open(results_file, 'r') as f:
            data = json.load(f)
            
        repos = data.get('detailed_results', [])
        filtered_repos = []
        
        for repo in repos:
            include = True
            
            # Apply filters
            if 'min_quality_score' in filters:
                if repo.get('quality_score', 0) < filters['min_quality_score']:
                    include = False
                    
            if 'language' in filters:
                repo_languages = repo.get('file_stats', {}).get('languages', {})
                if filters['language'] not in repo_languages:
                    include = False
                    
            if 'min_size_mb' in filters:
                if repo.get('size_mb', 0) < filters['min_size_mb']:
                    include = False
                    
            if 'max_size_mb' in filters:
                if repo.get('size_mb', 0) > filters['max_size_mb']:
                    include = False
                    
            if 'has_tests' in filters:
                if repo.get('health', {}).get('has_tests', False) != filters['has_tests']:
                    include = False
                    
            if 'has_readme' in filters:
                if repo.get('health', {}).get('has_readme', False) != filters['has_readme']:
                    include = False
                    
            if include:
                filtered_repos.append(repo)
        
        # Generate custom report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        custom_file = f"custom_report_{timestamp}.json"
        
        with open(custom_file, 'w') as f:
            json.dump({
                'filters_applied': filters,
                'total_matches': len(filtered_repos),
                'repositories': filtered_repos
            }, f, indent=2, default=str)
            
        return custom_file
        
    except Exception as e:
        print(f"Error generating custom report: {e}")
        return ""

def main():
    """Enhanced main function with reporting options"""
    print("🧪 Enhanced Repository Quality Checker")
    print("=" * 50)
    
    # Get base directory
    print("📁 Repository locations:")
    print("1. NAS storage (\\\\192.168.1.66\\plex3\\codebase\\repos)")
    print("2. Local storage (F:\\codebase\\repos)")
    print("3. Custom path")
    
    choice = input("\nChoose location (1-3, default 1): ").strip()
    
    base_dir = None
    if choice == "2":
        base_dir = r"F:\codebase\repos"
    elif choice == "3":
        base_dir = input("Enter custom path: ").strip()
    # Default to NAS (choice == "1" or empty)
    
    # Get number of worker threads
    while True:
        try:
            workers = input("\n🧵 Number of worker threads (1-8, default 4): ").strip()
            if not workers:
                workers = 4
            else:
                workers = int(workers)
            
            if 1 <= workers <= 8:
                break
            else:
                print("❌ Please enter a number between 1 and 8")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Create checker and run analysis
    checker = RepoQualityChecker(base_dir=base_dir, max_workers=workers)
    
    print(f"\n📊 Starting quality check...")
    print(f"   Base directory: {checker.base_dir}")
    print(f"   Worker threads: {workers}")
    
    confirm = input("\n❓ Proceed with quality check? (Y/n): ").strip().lower()
    if confirm in ['n', 'no']:
        print("👋 Quality check cancelled.")
        return
    
    checker.quality_check_parallel()
    
    # Offer custom report generation
    print("\n📊 Additional reporting options:")
    print("1. Generate custom filtered report")
    print("2. View HTML dashboard")
    print("3. Exit")
    
    choice = input("\nChoose option (1-3, default 3): ").strip()
    
    if choice == "1":
        # Custom report generation
        latest_results = max([f for f in os.listdir('.') if f.startswith('quality_check_results_')], default=None)
        if latest_results:
            print(f"\n🔍 Creating custom report from {latest_results}")
            filters = {}
            
            min_score = input("Minimum quality score (0-100, default: none): ").strip()
            if min_score.isdigit():
                filters['min_quality_score'] = int(min_score)
                
            language = input("Filter by language (e.g., Python, JavaScript, default: none): ").strip()
            if language:
                filters['language'] = language
                
            has_tests = input("Only repos with tests? (y/n, default: none): ").strip().lower()
            if has_tests == 'y':
                filters['has_tests'] = True
            elif has_tests == 'n':
                filters['has_tests'] = False
                
            custom_report = generate_custom_report(latest_results, filters)
            if custom_report:
                print(f"\n✅ Custom report generated: {custom_report}")
        else:
            print("\n❌ No results file found. Run analysis first.")
            
    elif choice == "2":
        # Open HTML dashboard
        import webbrowser
        dashboard_files = [f for f in os.listdir('.') if f.startswith('quality_dashboard_')]
        if dashboard_files:
            latest_dashboard = max(dashboard_files)
            webbrowser.open(f'file://{os.path.abspath(latest_dashboard)}')
            print(f"\n🌐 Opening dashboard: {latest_dashboard}")
        else:
            print("\n❌ No dashboard file found. Run analysis first.")

if __name__ == "__main__":
    main()
