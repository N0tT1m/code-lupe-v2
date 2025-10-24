#!/usr/bin/env python3
"""
Ultra-Fast Repository Processor - Optimized for Ryzen 9 3900X
Uses all 24 threads with async I/O, memory mapping, and batch processing
"""

import asyncio
import aiofiles
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import os
import time
import mmap
import json
from pathlib import Path
from typing import List, Dict, Set, Optional, Generator
from dataclasses import dataclass
import hashlib
import re
from collections import defaultdict, Counter
import psutil
import numpy as np
from functools import partial
import threading
import queue
import signal

# Ultra-fast file processing with memory mapping
@dataclass
class FileChunk:
    path: str
    content: bytes
    language: str
    size: int
    hash: str

class UltraFastProcessor:
    """Ultra-optimized processor using all CPU cores and async I/O"""
    
    def __init__(self, repos_dir: str = r"\\192.168.1.66\plex3\codelupe\repos"):
        self.repos_dir = Path(repos_dir)
        
        # CPU optimization - Use ALL cores
        self.cpu_cores = psutil.cpu_count(logical=True)  # 24 threads on 3900X
        self.process_workers = self.cpu_cores - 2  # Leave 2 cores for OS
        self.io_workers = min(64, self.cpu_cores * 4)  # 4x threads for I/O
        
        print(f"🚀 Ultra-Fast Mode: {self.cpu_cores} CPU threads detected")
        print(f"🔥 Using {self.process_workers} process workers")
        print(f"⚡ Using {self.io_workers} I/O workers")
        
        # Memory optimization
        self.max_memory_gb = psutil.virtual_memory().total // (1024**3)
        self.chunk_size = min(1024 * 1024 * 10, self.max_memory_gb * 1024 * 1024 // 4)  # 10MB chunks or 1/4 RAM
        
        # Performance tracking
        self.stats = {
            'files_processed': mp.Value('i', 0),
            'bytes_processed': mp.Value('L', 0),
            'start_time': time.time(),
            'languages': defaultdict(int),
            'errors': 0
        }
        
        # File extensions for ultra-fast lookup
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.sh', '.sql', '.r', '.m', '.pl', '.lua', '.dart', '.vim',
            '.sol', '.asm', '.hack', '.lisp', '.clj', '.hs', '.elm', '.ml'
        }
        
        # Skip patterns for ultra-fast filtering
        self.skip_dirs = {
            '.git', '.svn', '.hg', 'node_modules', '__pycache__', '.pytest_cache',
            'target', 'build', 'dist', '.gradle', 'bin', 'obj', '.idea', '.vscode',
            'vendor', 'Pods', '.pub-cache', '.nuget', 'packages', 'lib'
        }
        
        # Language mapping for fast detection
        self.ext_to_lang = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.jsx': 'JavaScript', '.tsx': 'TypeScript', '.java': 'Java',
            '.cpp': 'C++', '.c': 'C', '.h': 'C/C++', '.cs': 'C#',
            '.php': 'PHP', '.rb': 'Ruby', '.go': 'Go', '.rs': 'Rust',
            '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
            '.sh': 'Shell', '.sql': 'SQL', '.r': 'R'
        }
    
    def fast_file_scanner(self, repo_path: Path) -> Generator[Path, None, None]:
        """Ultra-fast file scanner using os.scandir()"""
        try:
            with os.scandir(repo_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        if entry.name not in self.skip_dirs:
                            yield from self.fast_file_scanner(Path(entry.path))
                    elif entry.is_file():
                        file_path = Path(entry.path)
                        if file_path.suffix.lower() in self.code_extensions:
                            # Quick size check
                            try:
                                if 100 <= entry.stat().st_size <= 1024*1024:  # 100B to 1MB
                                    yield file_path
                            except:
                                continue
        except (PermissionError, OSError):
            pass
    
    def process_file_chunk(self, file_path: Path) -> Optional[Dict]:
        """Process single file with memory mapping for speed"""
        try:
            # Fast language detection
            lang = self.ext_to_lang.get(file_path.suffix.lower(), 'Unknown')
            
            # Memory-mapped file reading for large files
            with open(file_path, 'rb') as f:
                file_size = f.seek(0, 2)
                f.seek(0)
                
                if file_size == 0 or file_size > 1024*1024:  # Skip empty or huge files
                    return None
                
                # Use memory mapping for files > 64KB
                if file_size > 65536:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        content = mm.read()
                else:
                    content = f.read()
            
            # Fast content validation
            try:
                text_content = content.decode('utf-8', errors='ignore')
            except:
                return None
            
            if not text_content.strip():
                return None
            
            # Ultra-fast quality checks
            lines = text_content.count('\n') + 1
            if lines < 5 or lines > 2000:
                return None
            
            # Fast hash calculation
            content_hash = hashlib.blake2b(content, digest_size=16).hexdigest()
            
            # Update stats atomically
            with self.stats['files_processed'].get_lock():
                self.stats['files_processed'].value += 1
            with self.stats['bytes_processed'].get_lock():
                self.stats['bytes_processed'].value += file_size
            
            return {
                'content': text_content,
                'language': lang,
                'lines': lines,
                'size': file_size,
                'hash': content_hash,
                'path': str(file_path.relative_to(self.repos_dir))
            }
            
        except Exception:
            self.stats['errors'] += 1
            return None
    
    def process_repository_parallel(self, repo_path: Path) -> List[Dict]:
        """Process repository with parallel file processing"""
        files = list(self.fast_file_scanner(repo_path))
        if not files:
            return []
        
        results = []
        
        # Use ThreadPoolExecutor for I/O bound file processing
        with ThreadPoolExecutor(max_workers=min(32, len(files))) as executor:
            future_to_file = {
                executor.submit(self.process_file_chunk, file_path): file_path
                for file_path in files
            }
            
            for future in as_completed(future_to_file):
                try:
                    result = future.result(timeout=5)  # 5 second timeout per file
                    if result:
                        results.append(result)
                except Exception:
                    continue
        
        return results
    
    def batch_process_repositories(self, repo_paths: List[Path], batch_size: int = None) -> List[Dict]:
        """Process repositories in batches using all CPU cores"""
        if batch_size is None:
            batch_size = max(1, len(repo_paths) // self.process_workers)
        
        all_files = []
        seen_hashes = set()
        
        print(f"🔥 Processing {len(repo_paths)} repositories in batches of {batch_size}")
        
        # Process repositories in parallel using all cores
        with ProcessPoolExecutor(max_workers=self.process_workers) as executor:
            # Submit batches
            futures = []
            for i in range(0, len(repo_paths), batch_size):
                batch = repo_paths[i:i + batch_size]
                future = executor.submit(self.process_repo_batch, batch)
                futures.append(future)
            
            # Collect results with progress tracking
            completed = 0
            for future in as_completed(futures):
                try:
                    batch_results = future.result(timeout=300)  # 5 minute timeout per batch
                    
                    # Deduplicate and collect
                    for file_data in batch_results:
                        if file_data['hash'] not in seen_hashes:
                            seen_hashes.add(file_data['hash'])
                            all_files.append(file_data)
                    
                    completed += 1
                    if completed % max(1, len(futures) // 20) == 0:  # Progress every 5%
                        self.print_progress(completed, len(futures), len(all_files))
                        
                except Exception as e:
                    print(f"❌ Batch processing error: {e}")
                    continue
        
        return all_files
    
    def process_repo_batch(self, repo_batch: List[Path]) -> List[Dict]:
        """Process a batch of repositories (runs in separate process)"""
        batch_results = []
        
        for repo_path in repo_batch:
            try:
                repo_files = self.process_repository_parallel(repo_path)
                batch_results.extend(repo_files)
            except Exception:
                continue
        
        return batch_results
    
    def scan_repositories_fast(self) -> List[Path]:
        """Ultra-fast repository scanning"""
        repos = []
        
        print(f"🔍 Scanning {self.repos_dir} for repositories...")
        start_time = time.time()
        
        # Parallel directory scanning
        with ThreadPoolExecutor(max_workers=self.io_workers) as executor:
            scan_futures = []
            
            # Submit top-level directory scans
            try:
                for item in self.repos_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        future = executor.submit(self.check_repo_validity, item)
                        scan_futures.append((future, item))
            except Exception as e:
                print(f"❌ Error scanning directory: {e}")
                return []
            
            # Collect valid repositories
            for future, repo_path in scan_futures:
                try:
                    if future.result(timeout=10):  # 10 second timeout per repo check
                        repos.append(repo_path)
                except Exception:
                    continue
        
        scan_time = time.time() - start_time
        print(f"📁 Found {len(repos)} repositories in {scan_time:.1f}s")
        
        return repos
    
    def check_repo_validity(self, repo_path: Path) -> bool:
        """Fast repository validity check"""
        try:
            # Quick check for git or code files
            has_git = (repo_path / '.git').exists()
            if has_git:
                return True
            
            # Fast code file check - sample a few files
            code_file_count = 0
            for item in repo_path.rglob('*'):
                if item.is_file() and item.suffix.lower() in self.code_extensions:
                    code_file_count += 1
                    if code_file_count >= 3:  # Found enough code files
                        return True
                if code_file_count > 50:  # Don't scan too deep
                    break
            
            return code_file_count >= 3
            
        except Exception:
            return False
    
    def print_progress(self, completed: int, total: int, files_found: int):
        """Print processing progress"""
        elapsed = time.time() - self.stats['start_time']
        rate = completed / elapsed if elapsed > 0 else 0
        
        with self.stats['files_processed'].get_lock():
            files_processed = self.stats['files_processed'].value
        with self.stats['bytes_processed'].get_lock():
            bytes_processed = self.stats['bytes_processed'].value
        
        mb_processed = bytes_processed / (1024 * 1024)
        
        print(f"🚀 Progress: {completed}/{total} batches ({completed/total*100:.1f}%) | "
              f"{files_found:,} unique files | {files_processed:,} processed | "
              f"{mb_processed:.1f}MB | {rate:.1f} batches/sec")
    
    def save_ultra_fast(self, files: List[Dict], output_file: str):
        """Ultra-fast saving with streaming JSON"""
        print(f"💾 Saving {len(files):,} files to {output_file}...")
        start_time = time.time()
        
        # Stream write for memory efficiency
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('[\n')
            
            for i, file_data in enumerate(files):
                training_item = {
                    'text': file_data['content'],
                    'meta': {
                        'language': file_data['language'],
                        'lines': file_data['lines'],
                        'path': file_data['path'],
                        'size': file_data['size']
                    }
                }
                
                json.dump(training_item, f, ensure_ascii=False, separators=(',', ':'))
                if i < len(files) - 1:
                    f.write(',')
                f.write('\n')
                
                # Progress for large datasets
                if i % 50000 == 0 and i > 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    print(f"💾 Saved {i:,}/{len(files):,} files ({rate:.0f} files/sec)")
            
            f.write(']\n')
        
        save_time = time.time() - start_time
        print(f"✅ Saved in {save_time:.1f}s ({len(files)/save_time:.0f} files/sec)")
    
    def run_ultra_fast_processing(self) -> List[Dict]:
        """Main ultra-fast processing pipeline"""
        print("🚀 ULTRA-FAST PROCESSING MODE - RYZEN 9 3900X BEAST MODE")
        print("=" * 70)
        
        # Phase 1: Ultra-fast repository scanning
        repos = self.scan_repositories_fast()
        if not repos:
            print("❌ No repositories found!")
            return []
        
        # Phase 2: Batch parallel processing
        start_time = time.time()
        files = self.batch_process_repositories(repos)
        
        # Phase 3: Final statistics
        processing_time = time.time() - start_time
        
        print(f"\n🎉 ULTRA-FAST PROCESSING COMPLETE!")
        print(f"⚡ Processing time: {processing_time:.1f}s")
        print(f"📊 Repositories processed: {len(repos):,}")
        print(f"📄 Valid files found: {len(files):,}")
        print(f"🚀 Processing rate: {len(files)/processing_time:.0f} files/sec")
        
        # Language statistics
        lang_counter = Counter(f['language'] for f in files)
        print(f"\n🔤 Top Languages:")
        for lang, count in lang_counter.most_common(10):
            print(f"   {lang}: {count:,} files")
        
        return files

def main():
    """Main function with signal handling for graceful shutdown"""
    def signal_handler(signum, frame):
        print("\n🛑 Graceful shutdown requested...")
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 ULTRA-FAST REPOSITORY PROCESSOR")
    print("🔥 OPTIMIZED FOR RYZEN 9 3900X + 24 THREADS")
    print("=" * 70)
    
    # Check system specs
    cpu_count = psutil.cpu_count(logical=True)
    memory_gb = psutil.virtual_memory().total // (1024**3)
    print(f"💻 System: {cpu_count} CPU threads, {memory_gb}GB RAM")
    
    if cpu_count < 16:
        print("⚠️  Warning: This script is optimized for high-core CPUs (16+ threads)")
    
    # Initialize processor
    processor = UltraFastProcessor()
    
    # Run ultra-fast processing
    start_time = time.time()
    files = processor.run_ultra_fast_processing()
    
    if files:
        # Save results
        output_file = f"\\\\192.168.1.66\\plex3\\codelupe\\ultra_fast_dataset_{int(time.time())}.json"
        processor.save_ultra_fast(files, output_file)
        
        total_time = time.time() - start_time
        print(f"\n🏆 MISSION ACCOMPLISHED in {total_time:.1f}s!")
        print(f"📁 Dataset: {output_file}")
        print(f"⚡ Overall rate: {len(files)/total_time:.0f} files/sec")
    else:
        print("❌ No files processed!")

if __name__ == "__main__":
    # Optimize for multiprocessing
    mp.set_start_method('spawn', force=True)
    main()