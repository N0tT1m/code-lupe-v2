#!/usr/bin/env python3
"""
Process existing repositories in G:\repos for training dataset
Optimized for local repository processing without cloning
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import re
from collections import defaultdict, Counter

class LocalRepoProcessor:
    """Process local repositories for training dataset"""
    
    def __init__(self, repos_dir: str = r"\\192.168.1.66\plex3\codelupe\repos"):
        self.repos_dir = Path(repos_dir)
        self.processed_files = []
        self.stats = {
            'total_repos': 0,
            'processed_repos': 0,
            'total_files': 0,
            'valid_code_files': 0,
            'languages': Counter(),
            'file_sizes': [],
            'start_time': time.time()
        }
        
        # Code file extensions
        self.code_extensions = {
            '.py': 'Python',
            '.js': 'JavaScript', 
            '.ts': 'TypeScript',
            '.jsx': 'JavaScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++',
            '.cs': 'C#',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.go': 'Go',
            '.rs': 'Rust',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.sh': 'Shell',
            '.sql': 'SQL',
            '.r': 'R',
            '.m': 'Objective-C',
            '.pl': 'Perl',
            '.lua': 'Lua',
            '.dart': 'Dart',
            '.vim': 'Vim',
            '.sol': 'Solidity',
            '.asm': 'Assembly'
        }
        
        # Directories to skip
        self.skip_dirs = {
            '.git', '.svn', '.hg',
            'node_modules', '__pycache__', '.pytest_cache',
            'target', 'build', 'dist', '.gradle',
            'bin', 'obj', '.idea', '.vscode',
            'vendor', 'Pods', '.pub-cache'
        }
        
        # Files to skip
        self.skip_files = {
            '.gitignore', '.dockerignore', 'Dockerfile',
            'package-lock.json', 'yarn.lock', 'go.sum', 'Cargo.lock',
            'requirements.txt', 'setup.py', 'setup.cfg',
            'README.md', 'LICENSE', 'CHANGELOG.md'
        }
    
    def is_valid_code_file(self, file_path: Path) -> bool:
        """Check if file is a valid code file"""
        if file_path.suffix.lower() not in self.code_extensions:
            return False
        
        if file_path.name in self.skip_files:
            return False
        
        # Skip very large files (>1MB)
        try:
            if file_path.stat().st_size > 1024 * 1024:
                return False
        except:
            return False
        
        return True
    
    def extract_code_content(self, file_path: Path) -> Dict:
        """Extract and analyze code content"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return None
            
            # Basic quality checks
            lines = content.split('\n')
            if len(lines) < 5:  # Too short
                return None
            
            if len(lines) > 2000:  # Too long
                return None
            
            # Calculate basic metrics
            non_empty_lines = [line for line in lines if line.strip()]
            if len(non_empty_lines) < 3:
                return None
            
            # Language detection
            language = self.code_extensions.get(file_path.suffix.lower(), 'Unknown')
            
            # Create content hash for deduplication
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            return {
                'file_path': str(file_path),
                'relative_path': str(file_path.relative_to(self.repos_dir)),
                'content': content,
                'language': language,
                'lines': len(lines),
                'non_empty_lines': len(non_empty_lines),
                'size_bytes': len(content.encode()),
                'content_hash': content_hash,
                'repo_name': file_path.parts[len(self.repos_dir.parts)]
            }
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None
    
    def process_repository(self, repo_path: Path) -> List[Dict]:
        """Process a single repository"""
        repo_files = []
        
        try:
            for root, dirs, files in os.walk(repo_path):
                # Skip unwanted directories
                dirs[:] = [d for d in dirs if d not in self.skip_dirs]
                
                root_path = Path(root)
                
                for file in files:
                    file_path = root_path / file
                    
                    if self.is_valid_code_file(file_path):
                        file_data = self.extract_code_content(file_path)
                        if file_data:
                            repo_files.append(file_data)
                            self.stats['languages'][file_data['language']] += 1
                            self.stats['file_sizes'].append(file_data['size_bytes'])
            
            self.stats['total_files'] += len(repo_files)
            if repo_files:
                self.stats['processed_repos'] += 1
                print(f"✅ Processed {repo_path.name}: {len(repo_files)} files")
            else:
                print(f"⚠️  Skipped {repo_path.name}: no valid code files")
                
        except Exception as e:
            print(f"❌ Error processing repository {repo_path.name}: {e}")
        
        return repo_files
    
    def scan_repositories(self) -> List[Path]:
        """Scan for repositories in the base directory"""
        repos = []
        
        if not self.repos_dir.exists():
            print(f"❌ Directory {self.repos_dir} does not exist!")
            return repos
        
        print(f"🔍 Scanning {self.repos_dir} for repositories...")
        
        # Look for repository directories (containing .git or code files)
        for item in self.repos_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a git repo or contains code files
                has_git = (item / '.git').exists()
                has_code = any(
                    f.suffix.lower() in self.code_extensions 
                    for f in item.rglob('*') 
                    if f.is_file()
                )
                
                if has_git or has_code:
                    repos.append(item)
        
        self.stats['total_repos'] = len(repos)
        print(f"📁 Found {len(repos)} repositories")
        return repos
    
    def process_all_repositories(self, max_workers: int = 4) -> List[Dict]:
        """Process all repositories in parallel"""
        repos = self.scan_repositories()
        if not repos:
            return []
        
        print(f"🚀 Processing {len(repos)} repositories with {max_workers} workers...")
        
        all_files = []
        seen_hashes = set()  # For deduplication
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(self.process_repository, repo): repo
                for repo in repos
            }
            
            completed = 0
            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                completed += 1
                
                try:
                    repo_files = future.result()
                    
                    # Deduplicate files
                    for file_data in repo_files:
                        if file_data['content_hash'] not in seen_hashes:
                            seen_hashes.add(file_data['content_hash'])
                            all_files.append(file_data)
                    
                    if completed % 50 == 0:
                        elapsed = time.time() - self.stats['start_time']
                        rate = completed / elapsed if elapsed > 0 else 0
                        print(f"📊 Progress: {completed}/{len(repos)} repos | "
                              f"{len(all_files):,} unique files | {rate:.1f} repos/sec")
                        
                except Exception as e:
                    print(f"❌ Error processing {repo.name}: {e}")
        
        self.stats['valid_code_files'] = len(all_files)
        return all_files
    
    def save_dataset(self, files: List[Dict], output_file: str = "training_dataset.json"):
        """Save processed files as training dataset"""
        print(f"💾 Saving {len(files):,} files to {output_file}...")
        
        # Create training format
        training_data = []
        for file_data in files:
            training_data.append({
                'text': file_data['content'],
                'meta': {
                    'file_path': file_data['relative_path'],
                    'language': file_data['language'],
                    'lines': file_data['lines'],
                    'repo': file_data['repo_name'],
                    'size': file_data['size_bytes']
                }
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Dataset saved to {output_file}")
        
        # Save statistics
        stats_file = output_file.replace('.json', '_stats.json')
        with open(stats_file, 'w') as f:
            json.dump({
                'total_repos': self.stats['total_repos'],
                'processed_repos': self.stats['processed_repos'],
                'total_files': len(files),
                'languages': dict(self.stats['languages']),
                'avg_file_size': sum(self.stats['file_sizes']) / len(self.stats['file_sizes']) if self.stats['file_sizes'] else 0,
                'processing_time_seconds': time.time() - self.stats['start_time']
            }, f, indent=2)
        
        print(f"📊 Statistics saved to {stats_file}")
    
    def print_summary(self):
        """Print processing summary"""
        elapsed = time.time() - self.stats['start_time']
        
        print(f"\n🎉 Processing Complete!")
        print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
        print(f"📁 Repositories scanned: {self.stats['total_repos']}")
        print(f"✅ Repositories processed: {self.stats['processed_repos']}")
        print(f"📄 Valid code files: {self.stats['valid_code_files']:,}")
        
        print(f"\n🔤 Top Languages:")
        for lang, count in self.stats['languages'].most_common(10):
            percentage = (count / self.stats['valid_code_files']) * 100
            print(f"   {lang}: {count:,} files ({percentage:.1f}%)")

def main():
    """Main function"""
    print("🚀 Local Repository Processor for Training Dataset")
    print("=" * 60)
    
    # Check if G:\repos exists
    repos_dir = r"\\192.168.1.66\plex3\codelupe\repos"
    if not os.path.exists(repos_dir):
        print(f"❌ Directory {repos_dir} not found!")
        print("Please update the repos_dir variable to point to your repository directory")
        return
    
    processor = LocalRepoProcessor(repos_dir)
    
    # Process all repositories
    print(f"📁 Processing repositories in: {repos_dir}")
    files = processor.process_all_repositories(max_workers=4)
    
    if files:
        # Save dataset
        processor.save_dataset(files, "\\\\192.168.1.66\\plex3\\codelupe\\repos_training_dataset.json")
        processor.print_summary()
        
        print(f"\n✅ Ready for training! Use the dataset file with your training script.")
    else:
        print("❌ No valid code files found!")

if __name__ == "__main__":
    main()