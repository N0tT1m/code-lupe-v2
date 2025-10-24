#!/usr/bin/env python3
"""
Clone entire repositories from the collection to Windows storage
Downloads full git repositories with history to NAS via UNC path
"""

import json
import os
import subprocess
import time
import threading
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WindowsRepoCloner:
    """Clone GitHub repositories with full git history and rate limiting for Windows"""
    
    def __init__(self, base_dir: str = None, max_workers: int = 2, github_token: str = None):
        # Windows paths
        nas_dir = r"\\192.168.1.66\plex3\codebase\repos"
        local_dir = r"F:\codebase\repos"
        
        if base_dir is None:
            base_dir = nas_dir  # Default to NAS
            
        if base_dir == nas_dir:
            try:
                # Test NAS accessibility with timeout
                import threading
                import time
                
                def test_nas_access():
                    try:
                        os.makedirs(nas_dir, exist_ok=True)
                        # Test write access
                        test_file = os.path.join(nas_dir, ".test_write")
                        with open(test_file, "w") as f:
                            f.write("test")
                        os.remove(test_file)
                        return True
                    except Exception:
                        return False
                
                # Test with 10 second timeout
                result = [False]
                def nas_test():
                    result[0] = test_nas_access()
                
                test_thread = threading.Thread(target=nas_test)
                test_thread.daemon = True
                test_thread.start()
                test_thread.join(timeout=10)
                
                if test_thread.is_alive() or not result[0]:
                    raise Exception("NAS access timeout or failed")
                    
                self.base_dir = nas_dir
                print(f"✅ Using NAS storage: {nas_dir}")
                
            except Exception as e:
                print(f"⚠️  NAS unavailable ({e}), falling back to local storage")
                self.base_dir = local_dir
                os.makedirs(self.base_dir, exist_ok=True)
                print(f"✅ Using local storage: {local_dir}")
        else:
            self.base_dir = base_dir
            os.makedirs(self.base_dir, exist_ok=True)
            
        self.max_workers = max_workers
        self.github_token = github_token
        self.cloned_repos = set()
        self.failed_repos = set()
        self.lock = threading.Lock()
        self.rate_limit_lock = threading.Lock()
        
        # Rate limiting - GitHub allows ~1 clone per second without token
        self.last_clone_time = 0
        env_delay = os.getenv('RATE_LIMIT_DELAY')
        if env_delay:
            self.min_delay = float(env_delay)
        else:
            self.min_delay = 3.0 if not github_token else 1.0  # 3 seconds between clones without token
        
        # Clone statistics
        self.clone_count = 0
        self.start_time = None
        
    def wait_for_rate_limit(self):
        """Enforce rate limiting between clone operations"""
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_clone_time
            
            if time_since_last < self.min_delay:
                wait_time = self.min_delay - time_since_last
                print(f"⏳ Rate limiting: waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            
            self.last_clone_time = time.time()
    
    def clone_repo(self, repo_url: str) -> bool:
        """Clone a single repository with rate limiting"""
        try:
            # Rate limiting
            self.wait_for_rate_limit()
            
            # Parse repo URL to get owner/repo
            if repo_url.startswith('https://github.com/'):
                repo_path = repo_url.replace('https://github.com/', '').rstrip('/')
                owner, repo_name = repo_path.split('/', 1)
            else:
                print(f"❌ Invalid repo URL format: {repo_url}")
                return False
            
            # Create owner directory
            owner_dir = os.path.join(self.base_dir, owner)
            os.makedirs(owner_dir, exist_ok=True)
            
            # Target directory for this repo
            repo_dir = os.path.join(owner_dir, repo_name)
            
            # Skip if already exists
            if os.path.exists(repo_dir):
                print(f"⏭️  Skipping {owner}/{repo_name} (already exists)")
                with self.lock:
                    self.cloned_repos.add(repo_url)
                return True
            
            with self.lock:
                self.clone_count += 1
                clone_num = self.clone_count
            
            print(f"📥 [{clone_num}] Cloning {owner}/{repo_name}...")
            
            # Build clone URL with token if available
            if self.github_token:
                clone_url = f"https://{self.github_token}@github.com/{owner}/{repo_name}.git"
            else:
                clone_url = repo_url
            
            # Clone with shallow history to save space
            cmd = [
                'git', 'clone', 
                '--depth', '1',  # Shallow clone (saves space)
                '--single-branch',  # Only main branch
                '--quiet',  # Reduce output
                clone_url, 
                repo_dir
            ]
            
            # Run git clone with timeout and retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=120,  # 2 minute timeout per attempt
                        shell=True if platform.system() == "Windows" else False
                    )
                    
                    if result.returncode == 0:
                        print(f"✅ [{clone_num}] Successfully cloned {owner}/{repo_name}")
                        with self.lock:
                            self.cloned_repos.add(repo_url)
                        return True
                    else:
                        error_msg = result.stderr.strip()
                        
                        # Check for rate limiting
                        if "rate limit" in error_msg.lower() or "403" in error_msg:
                            wait_time = 60 * (attempt + 1)  # Exponential backoff
                            print(f"🔄 [{clone_num}] Rate limited, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                            time.sleep(wait_time)
                            continue
                        
                        # Check for network issues
                        elif any(term in error_msg.lower() for term in ["network", "timeout", "connection", "could not resolve"]):
                            wait_time = 10 * (attempt + 1)
                            print(f"🔄 [{clone_num}] Network issue, retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                        
                        else:
                            print(f"❌ [{clone_num}] Failed to clone {owner}/{repo_name}: {error_msg}")
                            break
                            
                except subprocess.TimeoutExpired:
                    print(f"⏰ [{clone_num}] Timeout cloning {owner}/{repo_name} (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(30)  # Wait before retry
                        continue
            
            with self.lock:
                self.failed_repos.add(repo_url)
            return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout cloning {repo_url}")
            with self.lock:
                self.failed_repos.add(repo_url)
            return False
        except Exception as e:
            print(f"❌ Error cloning {repo_url}: {e}")
            with self.lock:
                self.failed_repos.add(repo_url)
            return False
    
    def clone_repos_parallel(self, repo_urls: List[str]):
        """Clone repositories with rate limiting and error recovery"""
        print(f"🚀 Starting to clone {len(repo_urls)} repositories...")
        print(f"📁 Target directory: {os.path.abspath(self.base_dir)}")
        print(f"🧵 Using {self.max_workers} worker threads")
        print(f"⏱️  Rate limit: {self.min_delay}s between clones")
        if self.github_token:
            print(f"🔑 Using GitHub token for authentication")
        else:
            print(f"⚠️  No GitHub token - slower rate limits apply")
        
        self.start_time = time.time()
        completed = 0
        
        # Estimate time based on rate limiting
        estimated_time_hours = (len(repo_urls) * self.min_delay) / 3600
        print(f"📊 Estimated completion time: {estimated_time_hours:.1f} hours")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all clone tasks
            future_to_url = {
                executor.submit(self.clone_repo, url): url 
                for url in repo_urls
            }
            
            # Process completed tasks
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed += 1
                
                try:
                    success = future.result()
                    if completed % 50 == 0:  # Progress update every 50 repos
                        elapsed = time.time() - self.start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = len(repo_urls) - completed
                        eta = remaining / rate if rate > 0 else 0
                        
                        print(f"\n📊 Progress: {completed}/{len(repo_urls)} "
                              f"({completed/len(repo_urls)*100:.1f}%)")
                        print(f"⏱️  Rate: {rate:.1f} repos/sec, ETA: {eta/60:.1f} minutes")
                        print(f"✅ Successful: {len(self.cloned_repos)}")
                        print(f"❌ Failed: {len(self.failed_repos)}\n")
                        
                except Exception as e:
                    print(f"❌ Exception processing {url}: {e}")
        
        # Final summary
        end_time = time.time()
        total_time = end_time - self.start_time
        
        print(f"\n🎉 Clone operation completed!")
        print(f"⏱️  Total time: {total_time/60:.1f} minutes")
        print(f"✅ Successfully cloned: {len(self.cloned_repos)}")
        print(f"❌ Failed to clone: {len(self.failed_repos)}")
        print(f"📁 Repository data stored in: {os.path.abspath(self.base_dir)}")
        
        # Save results
        self.save_results()
    
    def save_results(self):
        """Save clone results to JSON files"""
        try:
            # Save successful clones
            with open("cloned_repos.json", "w") as f:
                json.dump(list(self.cloned_repos), f, indent=2)
            
            # Save failed clones
            with open("failed_repos.json", "w") as f:
                json.dump(list(self.failed_repos), f, indent=2)
                
            print(f"💾 Results saved to cloned_repos.json and failed_repos.json")
            
        except Exception as e:
            print(f"⚠️ Failed to save results: {e}")

def load_repo_collection(filename: str = "filtered_repo_collection.json") -> List[str]:
    """Load repository collection from JSON file"""
    try:
        with open(filename, "r") as f:
            repos = json.load(f)
        print(f"📁 Loaded {len(repos)} repositories from {filename}")
        return repos
    except FileNotFoundError:
        print(f"❌ {filename} not found. Try massive_repo_collection.json")
        try:
            with open("massive_repo_collection.json", "r") as f:
                repos = json.load(f)
            print(f"📁 Loaded {len(repos)} repositories from massive_repo_collection.json")
            return repos
        except FileNotFoundError:
            print("❌ No repository collection found!")
            return []

def main():
    """Main function"""
    print("🔗 Windows GitHub Repository Cloner with UNC Path Support")
    print("=" * 60)
    
    # Detect platform
    if platform.system() != "Windows":
        print("⚠️  This script is optimized for Windows. Use clone_repos.py on Unix systems.")
    
    # Get GitHub token from environment or prompt
    github_token = os.getenv('GITHUB_TOKEN')
    if github_token and github_token != 'your_github_token_here':
        print("✅ Using GitHub token from .env file")
    else:
        github_token = input("\n🔑 GitHub token (optional, for better rate limits): ").strip()
        if not github_token:
            github_token = None
            print("⚠️  No token provided - using anonymous access (much slower)")
        else:
            print("✅ Token provided - using authenticated access")
    
    # Load repository URLs
    repos = load_repo_collection()
    if not repos:
        return
    
    # Get user preferences
    print(f"\n📊 Repository Collection: {len(repos)} repositories")
    
    while True:
        try:
            choice = input("\n🔧 Clone options:\n"
                          "1. Clone all repositories\n"
                          "2. Clone first 100 (testing)\n"
                          "3. Clone first 1000\n"
                          "4. Clone custom range\n"
                          "Choose option (1-4): ").strip()
            
            if choice == "1":
                target_repos = repos
                break
            elif choice == "2":
                target_repos = repos[:100]
                break
            elif choice == "3":
                target_repos = repos[:1000]
                break
            elif choice == "4":
                start = int(input("Start index (0-based): "))
                end = int(input("End index (exclusive): "))
                target_repos = repos[start:end]
                break
            else:
                print("❌ Invalid choice. Please enter 1-4.")
                continue
                
        except (ValueError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            return
    
    # Get number of worker threads from env or prompt
    env_workers = os.getenv('MAX_WORKERS')
    if env_workers and github_token:
        workers = int(env_workers)
        print(f"🧵 Using {workers} workers from .env file")
    else:
        while True:
            try:
                max_workers = 2 if github_token else 1  # Limit workers based on token
                workers = input(f"\n🧵 Number of worker threads (1-{max_workers}, default 3): ").strip()
                if not workers:
                    workers = 3 if github_token else 1
                else:
                    workers = int(workers)
                
                if 1 <= workers <= max_workers:
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {max_workers}")
            except ValueError:
                print("❌ Please enter a valid number")
    
    # Estimate space requirements
    avg_repo_size_mb = 10  # Conservative estimate
    total_size_gb = len(target_repos) * avg_repo_size_mb / 1024
    
    print(f"\n📊 Clone Summary:")
    print(f"   Repositories to clone: {len(target_repos)}")
    print(f"   Worker threads: {workers}")
    print(f"   Estimated space needed: ~{total_size_gb:.1f} GB")
    print(f"   Primary target: \\\\192.168.1.66\\plex3\\codebase\\repos\\")
    print(f"   Fallback target: F:\\codebase\\repos\\")
    
    confirm = input("\n❓ Proceed with cloning? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("👋 Clone cancelled.")
        return
    
    # Start cloning
    cloner = WindowsRepoCloner(max_workers=workers, github_token=github_token)
    cloner.clone_repos_parallel(target_repos)

if __name__ == "__main__":
    main()
