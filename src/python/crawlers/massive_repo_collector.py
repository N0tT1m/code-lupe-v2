#!/usr/bin/env python3
"""
Massive repository collector - designed to pull thousands of repos
"""

import requests
import time
import json
import threading
from datetime import datetime, timedelta
from typing import List, Set
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

class GitHubRateLimiter:
    """Smart rate limiter for GitHub API"""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_remaining = 5000 if github_token else 60
        self.rate_limit_reset = time.time() + 3600
        self.lock = threading.Lock()
        
        # Rate limiting config
        self.authenticated_delay = 0.1  # 10 requests/second max with token
        self.unauthenticated_delay = 61  # 1 request per minute without token
        self.max_retry_attempts = 3
        self.backoff_multiplier = 2
    
    def wait_if_needed(self):
        """Wait if we need to respect rate limits"""
        with self.lock:
            current_time = time.time()
            
            # Check if rate limit period has reset
            if current_time >= self.rate_limit_reset:
                self.rate_limit_remaining = 5000 if self.github_token else 60
                self.rate_limit_reset = current_time + 3600
                self.request_count = 0
            
            # Calculate required delay
            if self.github_token:
                # With token: respect remaining limit
                if self.rate_limit_remaining <= 10:
                    wait_time = self.rate_limit_reset - current_time + 1
                    print(f"⏳ Rate limit low ({self.rate_limit_remaining}), waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    return
                
                # Normal authenticated delay with jitter
                time_since_last = current_time - self.last_request_time
                min_delay = self.authenticated_delay + random.uniform(0, 0.1)
                if time_since_last < min_delay:
                    time.sleep(min_delay - time_since_last)
            else:
                # Without token: strict 60 requests/hour limit
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.unauthenticated_delay:
                    wait_time = self.unauthenticated_delay - time_since_last
                    print(f"⏳ Unauthenticated rate limit, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
            
            self.last_request_time = time.time()
            self.request_count += 1
    
    def update_rate_limit_info(self, response):
        """Update rate limit info from response headers"""
        if response.headers.get('X-RateLimit-Remaining'):
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
        if response.headers.get('X-RateLimit-Reset'):
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])

class MassiveRepoCollector:
    """Collect thousands of repositories with proper rate limiting"""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.headers = {
            "Authorization": f"token {github_token}" if github_token else None,
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoCollector/1.0"
        }
        # Remove None values
        self.headers = {k: v for k, v in self.headers.items() if v is not None}
        
        self.collected_repos = set()
        self.repo_queue = queue.Queue()
        self.rate_limiter = GitHubRateLimiter(github_token)
        
        # Collection settings optimized for rate limiting
        self.target_repos = 10000
        self.parallel_searches = 3 if github_token else 1  # Reduce parallelism
        self.search_delay = 0.2 if github_token else 62  # Respect rate limits
        
        # Comprehensive language list
        self.all_languages = [
            "Python", "JavaScript", "TypeScript", "Java", "C++", "C", "C#", 
            "Go", "Rust", "Swift", "Kotlin", "Scala", "Ruby", "PHP", "Perl",
            "R", "MATLAB", "Julia", "Lua", "Dart", "Objective-C", "Assembly",
            "Shell", "PowerShell", "Batch", "VBA", "SQL", "HTML", "CSS",
            "Vue", "Svelte", "Angular", "React", "Next.js", "Nuxt.js",
            "Django", "Flask", "FastAPI", "Spring", "Express", "Laravel"
        ]
        
        # Massive topic list for discovery
        self.all_topics = [
            # Programming & Development
            "machine-learning", "artificial-intelligence", "deep-learning", "neural-networks",
            "computer-vision", "natural-language-processing", "data-science", "big-data",
            "web-development", "mobile-development", "game-development", "desktop-application",
            "api", "rest-api", "graphql", "microservices", "serverless", "cloud",
            "docker", "kubernetes", "devops", "ci-cd", "automation", "testing",
            
            # Frameworks & Libraries
            "framework", "library", "sdk", "tool", "cli", "gui", "database",
            "orm", "cms", "blog", "ecommerce", "crm", "erp", "cms",
            
            # Technologies
            "blockchain", "cryptocurrency", "smart-contracts", "web3", "nft",
            "iot", "robotics", "embedded", "real-time", "streaming", "chat",
            "email", "sms", "notification", "payment", "authentication", "security",
            
            # Data & Analytics
            "analytics", "visualization", "dashboard", "reporting", "etl",
            "data-mining", "statistics", "mathematical-modeling", "simulation",
            
            # Gaming & Graphics
            "game-engine", "graphics", "rendering", "3d", "2d", "animation",
            "physics", "audio", "video", "image-processing", "computer-graphics",
            
            # System & Network
            "operating-system", "kernel", "driver", "networking", "tcp-ip",
            "http", "websocket", "proxy", "load-balancer", "cdn", "dns",
            
            # Business & Productivity
            "productivity", "task-management", "project-management", "collaboration",
            "document", "spreadsheet", "presentation", "calendar", "email-client",
            
            # Education & Research
            "education", "tutorial", "course", "research", "academic", "scientific",
            "math", "physics", "chemistry", "biology", "medicine", "finance",
            
            # NSFW & Adult Content Libraries
            "nsfw", "adult", "porn", "xxx", "erotic", "webcam", "dating",
            "onlyfans", "pornhub", "adult-content", "nude", "sex", "fetish",
            "cam", "strip", "explicit", "mature", "18+", "adult-site",
            "escort", "massage", "hookup", "tinder", "sexting", "chaturbate",
            "adult-entertainment", "pornography", "sexual", "intimate",
            "cam-girl", "adult-video", "adult-streaming", "live-cam",
            
            # Popular Tech Stacks
            "react", "vue", "angular", "nodejs", "express", "django", "flask",
            "spring-boot", "laravel", "rails", "asp.net", "xamarin", "flutter",
            "react-native", "ionic", "electron", "cordova", "unity", "unreal"
        ]
    
    def search_single_query_with_retry(self, query: str) -> Set[str]:
        """Search single query with exponential backoff and proper rate limiting"""
        found_repos = set()
        
        for attempt in range(self.rate_limiter.max_retry_attempts):
            try:
                # Wait for rate limit
                self.rate_limiter.wait_if_needed()
                
                params = {
                    "q": query,
                    "sort": "stars", 
                    "order": "desc",
                    "per_page": 100
                }
                
                response = requests.get(
                    "https://api.github.com/search/repositories",
                    params=params,
                    headers=self.headers,
                    timeout=30
                )
                
                # Update rate limit info
                self.rate_limiter.update_rate_limit_info(response)
                
                if response.status_code == 200:
                    data = response.json()
                    for repo in data.get("items", []):
                        repo_url = repo["html_url"]
                        if repo_url not in self.collected_repos:
                            found_repos.add(repo_url)
                    
                    print(f"✅ Query '{query[:40]}...' found {len(found_repos)} repos (attempt {attempt+1})")
                    return found_repos
                
                elif response.status_code == 403:
                    # Rate limit hit - use exponential backoff with jitter
                    retry_after = int(response.headers.get('Retry-After', 60))
                    backoff_time = min(retry_after, (self.rate_limiter.backoff_multiplier ** attempt) * 60)
                    jitter = random.uniform(0.1, 0.3) * backoff_time
                    wait_time = backoff_time + jitter
                    
                    print(f"⏰ Rate limited - waiting {wait_time:.1f}s (failure #{attempt+1})")
                    time.sleep(wait_time)
                    continue
                
                elif response.status_code == 422:
                    # Unprocessable entity (bad query)
                    print(f"⚠️  Invalid query: {query}")
                    break
                
                else:
                    # Other HTTP errors - exponential backoff
                    backoff_time = (self.rate_limiter.backoff_multiplier ** attempt) * 2
                    jitter = random.uniform(0, backoff_time * 0.1)
                    wait_time = backoff_time + jitter
                    
                    print(f"❌ HTTP {response.status_code} for query: {query}, waiting {wait_time:.1f}s")
                    if attempt < self.rate_limiter.max_retry_attempts - 1:
                        time.sleep(wait_time)
                    continue
                    
            except requests.exceptions.Timeout:
                backoff_time = (self.rate_limiter.backoff_multiplier ** attempt) * 5
                jitter = random.uniform(0, backoff_time * 0.2)
                wait_time = backoff_time + jitter
                
                print(f"⏱️  Timeout on query: {query}, waiting {wait_time:.1f}s")
                if attempt < self.rate_limiter.max_retry_attempts - 1:
                    time.sleep(wait_time)
                continue
                
            except Exception as e:
                backoff_time = (self.rate_limiter.backoff_multiplier ** attempt) * 3
                jitter = random.uniform(0, backoff_time * 0.1)
                wait_time = backoff_time + jitter
                
                print(f"❌ Error searching '{query}': {e}, waiting {wait_time:.1f}s")
                if attempt < self.rate_limiter.max_retry_attempts - 1:
                    time.sleep(wait_time)
                continue
        
        return found_repos
    
    def search_repositories_parallel(self, search_queries: List[str]) -> Set[str]:
        """Search repositories with proper rate limiting"""
        repos = set()
        
        # Limit parallelism based on token availability
        max_workers = self.parallel_searches
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_query = {
                executor.submit(self.search_single_query_with_retry, query): query 
                for query in search_queries
            }
            
            for future in as_completed(future_to_query):
                try:
                    result = future.result()
                    repos.update(result)
                    
                    # Show progress
                    if len(repos) % 100 == 0:
                        remaining = self.rate_limiter.rate_limit_remaining
                        print(f"📊 Progress: {len(repos)} repos, Rate limit: {remaining}")
                        
                except Exception as e:
                    query = future_to_query[future]
                    print(f"❌ Failed to process query '{query}': {e}")
        
        return repos
    
    def generate_massive_search_queries(self) -> List[str]:
        """Generate hundreds of search queries for maximum coverage"""
        queries = []
        
        # Language-based searches
        for lang in self.all_languages:
            queries.extend([
                f"language:{lang} stars:>100",
                f"language:{lang} stars:>500", 
                f"language:{lang} stars:>1000",
                f"language:{lang} pushed:>2023-01-01",
                f"language:{lang} created:>2022-01-01",
                f"language:{lang} forks:>50"
            ])
        
        # Topic-based searches
        for topic in self.all_topics:
            queries.extend([
                f"topic:{topic} stars:>50",
                f"topic:{topic} stars:>200",
                f"topic:{topic} language:Python",
                f"topic:{topic} language:JavaScript",
                f"topic:{topic} language:TypeScript"
            ])
        
        # Combination searches
        for i, lang1 in enumerate(self.all_languages[:10]):
            for lang2 in self.all_languages[i+1:11]:
                queries.append(f"language:{lang1} OR language:{lang2} stars:>100")
        
        # NSFW-specific searches
        nsfw_keywords = ["nsfw", "adult", "porn", "xxx", "cam", "escort", "dating", "hookup"]
        for keyword in nsfw_keywords:
            queries.extend([
                f"{keyword} language:Python stars:>1",
                f"{keyword} language:JavaScript stars:>1",
                f"{keyword} language:PHP stars:>1",
                f"{keyword} language:Ruby stars:>1",
                f"{keyword} language:Java stars:>1",
                f"in:name {keyword}",
                f"in:description {keyword}",
                f"in:readme {keyword}"
            ])
        
        # Time-based searches for recent activity
        time_ranges = [
            "pushed:>2024-01-01",
            "pushed:>2023-06-01", 
            "created:>2023-01-01",
            "updated:>2024-01-01"
        ]
        
        for time_range in time_ranges:
            for lang in self.all_languages[:20]:  # Top 20 languages
                queries.append(f"language:{lang} {time_range} stars:>10")
        
        # Size-based searches
        size_ranges = ["<1000", "1000..10000", "10000..100000", ">100000"]
        for size_range in size_ranges:
            queries.extend([
                f"size:{size_range} stars:>100 language:Python",
                f"size:{size_range} stars:>100 language:JavaScript"
            ])
        
        # Organization searches (popular orgs)
        popular_orgs = [
            "microsoft", "google", "facebook", "apple", "amazon", "netflix",
            "uber", "airbnb", "spotify", "twitter", "linkedin", "github",
            "huggingface", "pytorch", "tensorflow", "openai", "anthropic"
        ]
        
        for org in popular_orgs:
            queries.extend([
                f"user:{org} stars:>10",
                f"user:{org} language:Python",
                f"user:{org} language:JavaScript"
            ])
        
        print(f"Generated {len(queries)} search queries")
        return queries
    
    def discover_repo_networks(self, seed_repos: List[str]) -> Set[str]:
        """Discover repositories through network effects with rate limiting"""
        discovered = set()
        
        for repo_url in seed_repos[:30]:  # Reduced to avoid hitting limits
            try:
                # Extract owner/repo
                parts = repo_url.replace('https://github.com/', '').split('/')
                if len(parts) < 2:
                    continue
                owner, repo = parts[0], parts[1]
                
                # Rate limit before API call
                self.rate_limiter.wait_if_needed()
                
                # Get repository info
                repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
                response = requests.get(
                    repo_api_url, 
                    headers=self.headers,
                    timeout=30
                )
                
                # Update rate limit info
                self.rate_limiter.update_rate_limit_info(response)
                
                if response.status_code == 200:
                    repo_data = response.json()
                    
                    # Search for similar repositories using topics
                    if repo_data.get("topics"):
                        for topic in repo_data["topics"][:2]:  # Top 2 topics only
                            similar_query = f"topic:{topic} stars:>50"
                            similar_repos = self.search_single_query_with_retry(similar_query)
                            discovered.update(similar_repos)
                            
                            if len(discovered) > 200:  # Limit network discovery
                                break
                
                elif response.status_code == 403:
                    print(f"🚫 Rate limited during network discovery")
                    break  # Stop network discovery if rate limited
                
                elif response.status_code == 404:
                    print(f"⚠️  Repository not found: {repo_url}")
                    continue
                
                print(f"🕸️  Network discovery from {repo_url}: +{len(discovered)} total repos")
                
            except Exception as e:
                print(f"❌ Error discovering network for {repo_url}: {e}")
                continue
        
        return discovered
    
    def collect_massive_repos(self) -> List[str]:
        """Main collection function - get thousands of repos"""
        print(f"🚀 Starting massive repository collection")
        print(f"Target: {self.target_repos:,} repositories")
        print(f"Parallel searches: {self.parallel_searches}")
        
        all_repos = set()
        
        # Phase 1: Generate and execute massive search queries
        print("\n📡 Phase 1: Massive parallel searching...")
        search_queries = self.generate_massive_search_queries()
        
        # Process queries in batches
        batch_size = 50
        for i in range(0, len(search_queries), batch_size):
            batch = search_queries[i:i+batch_size]
            print(f"\nProcessing search batch {i//batch_size + 1}/{len(search_queries)//batch_size + 1}")
            
            batch_repos = self.search_repositories_parallel(batch)
            all_repos.update(batch_repos)
            
            print(f"Total collected so far: {len(all_repos):,}")
            
            if len(all_repos) >= self.target_repos:
                print(f"🎯 Target reached! Collected {len(all_repos):,} repositories")
                break
            
            # Brief pause between batches
            time.sleep(5)
        
        # Phase 2: Network discovery for even more repos
        if len(all_repos) < self.target_repos:
            print(f"\n🕸️ Phase 2: Network discovery from {len(all_repos)} seed repos...")
            seed_repos = list(all_repos)[:100]  # Use first 100 as seeds
            network_repos = self.discover_repo_networks(seed_repos)
            all_repos.update(network_repos)
        
        final_repos = list(all_repos)
        print(f"\n✅ Collection complete!")
        print(f"📊 Final count: {len(final_repos):,} repositories")
        
        # Save to file
        with open("massive_repo_collection.json", "w") as f:
            json.dump(final_repos, f, indent=2)
        
        return final_repos

def main():
    """Collect thousands of repositories"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Massive Repository Collector")
    parser.add_argument("--token", help="GitHub API token for unlimited requests")
    parser.add_argument("--target", type=int, default=10000, help="Target number of repos")
    parser.add_argument("--threads", type=int, default=20, help="Parallel search threads")
    
    args = parser.parse_args()
    
    collector = MassiveRepoCollector(github_token=args.token)
    collector.target_repos = args.target
    collector.parallel_searches = args.threads
    
    if not args.token:
        print("⚠️  No GitHub token provided - limited to 60 requests/hour")
        print("💡 Use --token YOUR_TOKEN for unlimited access")
        collector.parallel_searches = 1  # Reduce threads for rate limiting
    
    repos = collector.collect_massive_repos()
    
    print(f"\n🎉 Successfully collected {len(repos):,} repositories!")
    print("📁 Saved to: massive_repo_collection.json")
    
    # Show sample of what was collected
    print(f"\n📋 Sample repositories:")
    for repo in repos[:10]:
        print(f"  {repo}")
    
    if len(repos) > 10:
        print(f"  ... and {len(repos)-10:,} more!")

if __name__ == "__main__":
    main()
