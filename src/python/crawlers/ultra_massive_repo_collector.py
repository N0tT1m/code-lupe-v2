#!/usr/bin/env python3
"""
Ultra Massive Repository Collector - Designed to collect 1 million+ repositories
Advanced multi-source, multi-strategy collection system
"""

import requests
import time
import json
import threading
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import hashlib
import sqlite3
from pathlib import Path
import os

class AdvancedRateLimiter:
    """Ultra-sophisticated rate limiter for 1M+ repo collection"""
    
    def __init__(self, github_tokens: List[str] = None):
        self.github_tokens = github_tokens or []
        self.current_token_index = 0
        self.token_states = {}
        self.lock = threading.Lock()
        
        # Initialize token states
        for i, token in enumerate(self.github_tokens):
            self.token_states[i] = {
                'remaining': 5000,
                'reset_time': time.time() + 3600,
                'last_request': 0,
                'consecutive_failures': 0
            }
        
        # Rate limiting configuration
        self.base_delay = 0.05  # 20 requests/second max per token
        self.max_retry_attempts = 5
        self.backoff_multiplier = 1.5
        self.token_rotation_threshold = 100  # Switch tokens when < 100 requests
    
    def get_best_token(self) -> tuple:
        """Get the token with the most remaining requests"""
        if not self.github_tokens:
            return None, None
        
        best_token_idx = 0
        best_remaining = -1
        
        current_time = time.time()
        
        for idx, state in self.token_states.items():
            # Reset if time has passed
            if current_time >= state['reset_time']:
                state['remaining'] = 5000
                state['reset_time'] = current_time + 3600
                state['consecutive_failures'] = 0
            
            # Find token with most remaining requests
            if state['remaining'] > best_remaining and state['consecutive_failures'] < 3:
                best_remaining = state['remaining']
                best_token_idx = idx
        
        return self.github_tokens[best_token_idx], best_token_idx
    
    def wait_and_get_token(self):
        """Get a token and wait if necessary"""
        with self.lock:
            token, token_idx = self.get_best_token()
            
            if token is None:
                return None, None
            
            state = self.token_states[token_idx]
            current_time = time.time()
            
            # If all tokens are exhausted, wait for the earliest reset
            if state['remaining'] <= 0:
                earliest_reset = min(s['reset_time'] for s in self.token_states.values())
                wait_time = max(0, earliest_reset - current_time + 1)
                if wait_time > 0:
                    print(f"🕐 All tokens exhausted, waiting {wait_time:.1f}s for reset")
                    time.sleep(wait_time)
                    # Recursively try again
                    return self.wait_and_get_token()
            
            # Apply minimal delay with jitter
            time_since_last = current_time - state['last_request']
            min_delay = self.base_delay + random.uniform(0, 0.02)
            if time_since_last < min_delay:
                time.sleep(min_delay - time_since_last)
            
            state['last_request'] = time.time()
            state['remaining'] -= 1
            
            return token, token_idx
    
    def update_token_state(self, token_idx: int, response):
        """Update token state from response headers"""
        if token_idx in self.token_states:
            if response.headers.get('X-RateLimit-Remaining'):
                self.token_states[token_idx]['remaining'] = int(response.headers['X-RateLimit-Remaining'])
            if response.headers.get('X-RateLimit-Reset'):
                self.token_states[token_idx]['reset_time'] = int(response.headers['X-RateLimit-Reset'])
    
    def mark_token_failure(self, token_idx: int):
        """Mark a token as having failed"""
        if token_idx in self.token_states:
            self.token_states[token_idx]['consecutive_failures'] += 1

class UltraMassiveRepoCollector:
    """Collect 1 million+ repositories using advanced strategies"""
    
    def __init__(self, github_tokens: List[str] = None):
        self.github_tokens = github_tokens or []
        self.rate_limiter = AdvancedRateLimiter(github_tokens)
        
        # Persistence layer
        self.db_path = "ultra_massive_repos.db"
        self.init_database()
        
        # Collection settings
        self.target_repos = 1_000_000  # 1 million target
        self.max_workers = min(len(github_tokens) * 2, 20) if github_tokens else 1
        self.batch_size = 100
        
        # Progress tracking
        self.collected_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        
        # Comprehensive language matrix
        self.programming_languages = [
            # Popular languages
            "Python", "JavaScript", "TypeScript", "Java", "C++", "C", "C#", "Go", "Rust", "Swift",
            "Kotlin", "Scala", "Ruby", "PHP", "Perl", "R", "MATLAB", "Julia", "Dart", "Objective-C",
            
            # Web technologies
            "HTML", "CSS", "Vue", "Svelte", "Angular", "React", "SCSS", "Less", "Stylus",
            
            # System languages
            "Assembly", "VHDL", "Verilog", "SystemVerilog", "CUDA", "OpenCL", "WebAssembly",
            
            # Scripting languages
            "Shell", "PowerShell", "Batch", "VBScript", "Lua", "TCL", "AWK", "sed",
            
            # Database languages
            "SQL", "PL/SQL", "T-SQL", "MySQL", "PostgreSQL", "MongoDB", "CQL",
            
            # Markup and config
            "XML", "YAML", "TOML", "JSON", "Markdown", "LaTeX", "ReStructuredText",
            
            # Functional languages
            "Haskell", "F#", "Erlang", "Elixir", "Clojure", "Scheme", "Lisp", "OCaml",
            
            # Game development
            "UnityScript", "GDScript", "Boo", "AngelScript", "Squirrel",
            
            # Mobile development
            "Flutter", "React-Native", "Xamarin", "Ionic", "Cordova",
            
            # Emerging languages
            "Zig", "Nim", "Crystal", "V", "Odin", "Carbon", "Mojo"
        ]
        
        # Massive topic matrix (500+ topics)
        self.comprehensive_topics = [
            # Core CS topics
            "algorithms", "data-structures", "computer-science", "mathematics", "statistics",
            "linear-algebra", "calculus", "discrete-mathematics", "graph-theory", "optimization",
            
            # AI/ML/Data Science
            "machine-learning", "artificial-intelligence", "deep-learning", "neural-networks",
            "computer-vision", "natural-language-processing", "data-science", "big-data",
            "data-mining", "predictive-analytics", "reinforcement-learning", "supervised-learning",
            "unsupervised-learning", "transfer-learning", "generative-ai", "llm", "transformers",
            "gpt", "bert", "stable-diffusion", "gan", "autoencoder", "rnn", "lstm", "cnn",
            
            # Web Development
            "web-development", "frontend", "backend", "full-stack", "responsive-design",
            "progressive-web-app", "single-page-application", "static-site-generator",
            "jamstack", "serverless", "microservices", "api", "rest-api", "graphql",
            "websocket", "http", "tcp", "websecurity", "oauth", "jwt", "cors",
            
            # Mobile Development
            "mobile-development", "ios", "android", "cross-platform", "native-app",
            "mobile-ui", "app-store", "google-play", "mobile-security", "push-notifications",
            
            # Game Development
            "game-development", "game-engine", "unity", "unreal-engine", "godot",
            "graphics", "rendering", "3d", "2d", "animation", "physics", "audio",
            "video-games", "indie-game", "mobile-game", "web-game", "vr", "ar",
            
            # System Programming
            "operating-system", "kernel", "driver", "embedded", "iot", "firmware",
            "real-time", "distributed-systems", "parallel-computing", "concurrency",
            "multithreading", "async", "performance", "optimization", "profiling",
            
            # DevOps/Infrastructure
            "devops", "ci-cd", "automation", "testing", "docker", "kubernetes",
            "terraform", "ansible", "jenkins", "github-actions", "monitoring",
            "logging", "metrics", "observability", "infrastructure", "cloud",
            "aws", "azure", "gcp", "serverless", "lambda", "functions",
            
            # Security
            "cybersecurity", "security", "cryptography", "encryption", "blockchain",
            "cryptocurrency", "smart-contracts", "web3", "defi", "nft", "ethereum",
            "bitcoin", "penetration-testing", "vulnerability", "exploit", "malware",
            "reverse-engineering", "forensics", "privacy", "authentication",
            
            # Database/Storage
            "database", "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
            "elasticsearch", "neo4j", "cassandra", "dynamodb", "sqlite", "orm",
            "data-warehouse", "etl", "data-pipeline", "stream-processing",
            
            # Networking
            "networking", "tcp-ip", "dns", "load-balancer", "proxy", "cdn", "firewall",
            "vpn", "routing", "switching", "network-security", "packet-analysis",
            
            # Business Applications
            "erp", "crm", "cms", "blog", "ecommerce", "payment", "fintech", "banking",
            "trading", "portfolio", "accounting", "inventory", "hr", "project-management",
            "task-management", "collaboration", "productivity", "document-management",
            
            # Education/Research
            "education", "tutorial", "course", "research", "academic", "scientific",
            "university", "college", "online-learning", "mooc", "certification",
            
            # Entertainment/Media
            "entertainment", "media", "streaming", "video", "audio", "music",
            "podcast", "radio", "tv", "movie", "book", "social-media", "chat",
            "messaging", "communication", "video-calling", "conferencing",
            
            # Healthcare/Science
            "healthcare", "medical", "bioinformatics", "genomics", "drug-discovery",
            "clinical", "hospital", "patient", "diagnosis", "treatment", "therapy",
            "physics", "chemistry", "biology", "astronomy", "geology", "weather",
            
            # NSFW/Adult Content (for comprehensive coverage)
            "nsfw", "adult", "porn", "xxx", "erotic", "webcam", "dating", "hookup",
            "onlyfans", "chaturbate", "adult-content", "escort", "massage", "fetish",
            "cam", "strip", "explicit", "mature", "18+", "adult-site", "pornhub",
            "sexting", "intimate", "cam-girl", "adult-video", "adult-streaming",
            "live-cam", "adult-entertainment", "pornography", "sexual", "tinder",
            
            # Tools/Utilities
            "cli", "command-line", "terminal", "shell", "utility", "tool", "library",
            "framework", "sdk", "api-client", "scraper", "crawler", "parser",
            "converter", "generator", "validator", "formatter", "linter", "debugger",
            "profiler", "benchmark", "monitoring", "logging", "backup", "sync",
            
            # Language-specific ecosystems
            "npm", "pypi", "maven", "nuget", "cargo", "composer", "gem", "cpan",
            "hackage", "hex", "pub", "cocoapods", "carthage", "swift-package-manager",
            
            # Popular frameworks/libraries
            "react", "angular", "vue", "svelte", "next.js", "nuxt.js", "gatsby",
            "django", "flask", "fastapi", "express", "koa", "nestjs", "spring",
            "spring-boot", "laravel", "symfony", "rails", "sinatra", "asp.net",
            "xamarin", "blazor", "electron", "tauri", "qt", "gtk", "tkinter",
            "flutter", "react-native", "ionic", "cordova", "phonegap",
            
            # Game engines/graphics
            "unity", "unreal-engine", "godot", "defold", "construct", "gamemaker",
            "renpy", "rpg-maker", "blender", "maya", "3ds-max", "cinema4d",
            "opengl", "vulkan", "directx", "metal", "webgl", "three.js",
            
            # Hardware/Electronics
            "arduino", "raspberry-pi", "esp32", "stm32", "fpga", "pcb", "circuit",
            "electronics", "robotics", "automation", "sensor", "actuator", "motor",
            "microcontroller", "embedded-systems", "real-time-systems",
            
            # Creative/Design
            "design", "ui", "ux", "graphic-design", "typography", "color", "layout",
            "prototyping", "wireframe", "mockup", "figma", "sketch", "adobe",
            "photoshop", "illustrator", "after-effects", "premiere", "davinci-resolve"
        ]
        
        # Search strategies for maximum coverage
        self.search_strategies = [
            "language_based", "topic_based", "organization_based", "time_based",
            "size_based", "star_based", "fork_based", "issue_based", "combination_based",
            "network_discovery", "trending_based", "recently_updated", "license_based"
        ]
    
    def init_database(self):
        """Initialize SQLite database for persistence"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                owner TEXT,
                stars INTEGER,
                forks INTEGER,
                language TEXT,
                topics TEXT,
                created_at TEXT,
                updated_at TEXT,
                size INTEGER,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_url ON repositories(url);
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_language ON repositories(language);
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_stars ON repositories(stars);
        ''')
        
        conn.commit()
        conn.close()
    
    def save_repositories_batch(self, repos_data: List[Dict]):
        """Save a batch of repositories to database"""
        if not repos_data:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insert_data = []
        for repo in repos_data:
            insert_data.append((
                repo.get('html_url', ''),
                repo.get('name', ''),
                repo.get('owner', {}).get('login', ''),
                repo.get('stargazers_count', 0),
                repo.get('forks_count', 0),
                repo.get('language', ''),
                json.dumps(repo.get('topics', [])),
                repo.get('created_at', ''),
                repo.get('updated_at', ''),
                repo.get('size', 0)
            ))
        
        cursor.executemany('''
            INSERT OR IGNORE INTO repositories 
            (url, name, owner, stars, forks, language, topics, created_at, updated_at, size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', insert_data)
        
        conn.commit()
        conn.close()
        
        self.collected_count += cursor.rowcount
    
    def get_collected_count(self) -> int:
        """Get current count of collected repositories"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM repositories')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def search_with_single_query(self, query: str, max_pages: int = 10) -> List[Dict]:
        """Search repositories with a single query, handling pagination"""
        all_repos = []
        
        for page in range(1, max_pages + 1):
            token, token_idx = self.rate_limiter.wait_and_get_token()
            if not token:
                print("❌ No tokens available")
                break
            
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "UltraMassiveRepoCollector/2.0"
            }
            
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc", 
                "per_page": 100,
                "page": page
            }
            
            try:
                response = requests.get(
                    "https://api.github.com/search/repositories",
                    params=params,
                    headers=headers,
                    timeout=30
                )
                
                self.rate_limiter.update_token_state(token_idx, response)
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get("items", [])
                    
                    if not repos:  # No more results
                        break
                    
                    all_repos.extend(repos)
                    
                    # Check if we've hit the search limit (1000 results max)
                    if data.get("total_count", 0) > 1000 and page * 100 >= 1000:
                        break
                
                elif response.status_code == 403:
                    print(f"🚫 Rate limited on token {token_idx}")
                    self.rate_limiter.mark_token_failure(token_idx)
                    time.sleep(1)
                    continue
                
                elif response.status_code == 422:
                    print(f"❌ Invalid query: {query}")
                    break
                
                else:
                    print(f"❌ HTTP {response.status_code} for query: {query}")
                    self.error_count += 1
                    break
                    
            except Exception as e:
                print(f"❌ Error searching '{query}': {e}")
                self.error_count += 1
                break
        
        return all_repos
    
    def generate_ultra_comprehensive_queries(self) -> List[str]:
        """Generate thousands of search queries for maximum coverage"""
        queries = []
        
        # 1. Language-based searches (detailed)
        for lang in self.programming_languages:
            queries.extend([
                f"language:{lang} stars:>0",
                f"language:{lang} stars:>1",
                f"language:{lang} stars:>5",
                f"language:{lang} stars:>10",
                f"language:{lang} stars:>50",
                f"language:{lang} stars:>100",
                f"language:{lang} stars:>500",
                f"language:{lang} stars:>1000",
                f"language:{lang} forks:>0",
                f"language:{lang} forks:>5",
                f"language:{lang} forks:>20",
                f"language:{lang} forks:>100",
                f"language:{lang} pushed:>2020-01-01",
                f"language:{lang} pushed:>2021-01-01",
                f"language:{lang} pushed:>2022-01-01",
                f"language:{lang} pushed:>2023-01-01",
                f"language:{lang} pushed:>2024-01-01",
                f"language:{lang} created:>2015-01-01",
                f"language:{lang} created:>2018-01-01",
                f"language:{lang} created:>2020-01-01",
                f"language:{lang} created:>2022-01-01"
            ])
        
        # 2. Topic-based searches (comprehensive)
        for topic in self.comprehensive_topics:
            queries.extend([
                f"topic:{topic}",
                f"topic:{topic} stars:>0",
                f"topic:{topic} stars:>5",
                f"topic:{topic} stars:>20",
                f"topic:{topic} stars:>100",
                f"topic:{topic} language:Python",
                f"topic:{topic} language:JavaScript",
                f"topic:{topic} language:TypeScript",
                f"topic:{topic} language:Java",
                f"topic:{topic} language:Go",
                f"topic:{topic} language:Rust",
                f"topic:{topic} language:C++",
                f"topic:{topic} language:C#"
            ])
        
        # 3. Organization searches (massive)
        organizations = [
            # Tech giants
            "microsoft", "google", "facebook", "apple", "amazon", "netflix",
            "meta", "alphabet", "tesla", "nvidia", "intel", "amd", "ibm",
            
            # Popular orgs
            "github", "gitlab", "atlassian", "slack", "discord", "spotify",
            "uber", "airbnb", "twitter", "linkedin", "pinterest", "snapchat",
            "shopify", "stripe", "square", "paypal", "zoom", "salesforce",
            
            # Open source orgs
            "mozilla", "apache", "linux", "gnu", "debian", "ubuntu", "redhat",
            "canonical", "docker", "kubernetes", "prometheus", "grafana",
            
            # AI/ML orgs
            "openai", "anthropic", "huggingface", "pytorch", "tensorflow",
            "keras-team", "scikit-learn", "pandas-dev", "numpy", "scipy",
            
            # Gaming orgs
            "unity", "unrealengine", "valve", "epicgames", "riot-games",
            "blizzard", "ea", "ubisoft", "rockstar-games", "nintendo",
            
            # Crypto/Blockchain
            "ethereum", "bitcoin", "chainlink", "polygon", "solana", "cardano",
            "polkadot", "cosmos", "avalanche", "near", "harmony", "algorand"
        ]
        
        for org in organizations:
            queries.extend([
                f"user:{org}",
                f"user:{org} stars:>0",
                f"user:{org} stars:>10",
                f"user:{org} language:Python",
                f"user:{org} language:JavaScript",
                f"user:{org} language:TypeScript",
                f"user:{org} language:Java",
                f"user:{org} language:Go",
                f"user:{org} language:C++",
                f"org:{org}",
                f"org:{org} stars:>0"
            ])
        
        # 4. Time-based searches
        years = list(range(2008, 2025))  # GitHub was founded in 2008
        for year in years:
            queries.extend([
                f"created:{year}-01-01..{year}-12-31 stars:>10",
                f"created:{year}-01-01..{year}-12-31 language:Python",
                f"created:{year}-01-01..{year}-12-31 language:JavaScript",
                f"pushed:{year}-01-01..{year}-12-31 stars:>50"
            ])
        
        # 5. Size-based searches
        size_ranges = [
            "0..1000", "1000..5000", "5000..10000", "10000..50000", 
            "50000..100000", "100000..500000", "500000..1000000", ">1000000"
        ]
        for size in size_ranges:
            for lang in self.programming_languages[:20]:  # Top 20 languages
                queries.append(f"size:{size} language:{lang} stars:>1")
        
        # 6. License-based searches
        licenses = [
            "mit", "apache-2.0", "gpl-3.0", "bsd-3-clause", "unlicense",
            "lgpl-3.0", "mpl-2.0", "cc0-1.0", "epl-2.0", "artistic-2.0"
        ]
        for license in licenses:
            queries.extend([
                f"license:{license} stars:>10",
                f"license:{license} language:Python",
                f"license:{license} language:JavaScript"
            ])
        
        # 7. Trending and recently updated
        recent_dates = [
            "2024-01-01", "2023-06-01", "2023-01-01", "2022-01-01"
        ]
        for date in recent_dates:
            queries.extend([
                f"pushed:>{date} stars:>0",
                f"pushed:>{date} stars:>10",
                f"updated:>{date} stars:>5"
            ])
        
        # 8. Keyword searches in name/description
        keywords = [
            "framework", "library", "tool", "cli", "api", "app", "game",
            "website", "bot", "script", "utility", "plugin", "extension",
            "template", "boilerplate", "starter", "example", "demo", "tutorial"
        ]
        for keyword in keywords:
            queries.extend([
                f"in:name {keyword} stars:>5",
                f"in:description {keyword} stars:>10",
                f"{keyword} language:Python",
                f"{keyword} language:JavaScript"
            ])
        
        # 9. Archive and mirror searches
        queries.extend([
            "archived:false stars:>100",
            "archived:true stars:>500",  # Popular archived projects
            "mirror:false stars:>50",
            "fork:false stars:>20",
            "fork:true stars:>100"  # Popular forks
        ])
        
        # 10. Language combination searches
        lang_pairs = [
            ("Python", "JavaScript"), ("Java", "Kotlin"), ("C", "C++"),
            ("TypeScript", "JavaScript"), ("Go", "Rust"), ("Swift", "Objective-C")
        ]
        for lang1, lang2 in lang_pairs:
            queries.extend([
                f"language:{lang1} OR language:{lang2} stars:>50",
                f"language:{lang1} language:{lang2} stars:>10"  # Multi-language repos
            ])
        
        # Remove duplicates and shuffle for better distribution
        queries = list(set(queries))
        random.shuffle(queries)
        
        print(f"Generated {len(queries):,} comprehensive search queries")
        return queries
    
    def collect_ultra_massive_repos(self) -> int:
        """Main collection function for 1M+ repositories"""
        print(f"🚀 Starting ULTRA MASSIVE repository collection")
        print(f"🎯 Target: {self.target_repos:,} repositories")
        print(f"🔧 Max workers: {self.max_workers}")
        print(f"💾 Database: {self.db_path}")
        
        # Check existing progress
        existing_count = self.get_collected_count()
        print(f"📊 Already collected: {existing_count:,} repositories")
        
        if existing_count >= self.target_repos:
            print(f"✅ Target already reached!")
            return existing_count
        
        # Generate comprehensive search queries
        all_queries = self.generate_ultra_comprehensive_queries()
        total_queries = len(all_queries)
        
        print(f"📡 Generated {total_queries:,} search queries")
        print(f"🔍 Starting parallel search execution...")
        
        # Process queries in batches with multiple workers
        batch_size = self.batch_size
        completed_queries = 0
        
        for i in range(0, len(all_queries), batch_size):
            batch_queries = all_queries[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(all_queries) + batch_size - 1) // batch_size
            
            print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch_queries)} queries)")
            
            # Execute batch with thread pool
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_query = {
                    executor.submit(self.search_with_single_query, query, 10): query
                    for query in batch_queries
                }
                
                batch_repos = []
                for future in as_completed(future_to_query):
                    query = future_to_query[future]
                    try:
                        repos = future.result()
                        batch_repos.extend(repos)
                        completed_queries += 1
                        
                        if completed_queries % 50 == 0:
                            current_count = self.get_collected_count()
                            progress = (completed_queries / total_queries) * 100
                            print(f"📈 Progress: {progress:.1f}% ({completed_queries}/{total_queries} queries) | "
                                  f"Collected: {current_count:,} repos")
                        
                    except Exception as e:
                        print(f"❌ Query failed '{query}': {e}")
                        self.error_count += 1
                
                # Save batch to database
                if batch_repos:
                    print(f"💾 Saving {len(batch_repos)} repositories from batch {batch_num}")
                    self.save_repositories_batch(batch_repos)
                
                # Check if target reached
                current_count = self.get_collected_count()
                if current_count >= self.target_repos:
                    print(f"🎯 TARGET REACHED! Collected {current_count:,} repositories")
                    break
            
            # Brief pause between batches to be respectful
            time.sleep(2)
        
        final_count = self.get_collected_count()
        print(f"\n✅ ULTRA MASSIVE COLLECTION COMPLETE!")
        print(f"📊 Final count: {final_count:,} repositories")
        print(f"❌ Errors encountered: {self.error_count}")
        print(f"💾 Database: {self.db_path}")
        
        return final_count
    
    def export_repositories(self, output_file: str = "ultra_massive_repos.json"):
        """Export collected repositories to JSON"""
        print(f"📤 Exporting repositories to {output_file}...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT url, name, owner, stars, forks, language, topics, created_at, updated_at, size
            FROM repositories 
            ORDER BY stars DESC
        ''')
        
        repos = []
        for row in cursor.fetchall():
            repos.append({
                "url": row[0],
                "name": row[1],
                "owner": row[2],
                "stars": row[3],
                "forks": row[4],
                "language": row[5],
                "topics": json.loads(row[6]) if row[6] else [],
                "created_at": row[7],
                "updated_at": row[8],
                "size": row[9]
            })
        
        conn.close()
        
        with open(output_file, 'w') as f:
            json.dump(repos, f, indent=2)
        
        print(f"✅ Exported {len(repos):,} repositories to {output_file}")
        return len(repos)

def main():
    """Ultra massive repository collection"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ultra Massive Repository Collector (1M+ repos)")
    parser.add_argument("--tokens", nargs='+', help="GitHub API tokens (space separated)")
    parser.add_argument("--target", type=int, default=1_000_000, help="Target number of repos (default: 1M)")
    parser.add_argument("--workers", type=int, default=20, help="Max parallel workers")
    parser.add_argument("--export", type=str, help="Export to JSON file")
    parser.add_argument("--resume", action="store_true", help="Resume from existing database")
    
    args = parser.parse_args()
    
    if not args.tokens:
        print("⚠️  WARNING: No GitHub tokens provided!")
        print("💡 For 1M+ repos, you NEED multiple GitHub tokens:")
        print("   python ultra_massive_repo_collector.py --tokens TOKEN1 TOKEN2 TOKEN3")
        print("🔗 Get tokens at: https://github.com/settings/tokens")
        return
    
    print(f"🔑 Using {len(args.tokens)} GitHub tokens")
    
    collector = UltraMassiveRepoCollector(github_tokens=args.tokens)
    collector.target_repos = args.target
    collector.max_workers = args.workers
    
    if args.resume:
        existing = collector.get_collected_count()
        print(f"📂 Resuming from {existing:,} existing repositories")
    
    # Start collection
    final_count = collector.collect_ultra_massive_repos()
    
    # Export if requested
    if args.export:
        collector.export_repositories(args.export)
    
    print(f"\n🎉 MISSION ACCOMPLISHED!")
    print(f"📊 Collected: {final_count:,} repositories")
    print(f"🎯 Target: {args.target:,} repositories")
    print(f"📈 Success rate: {(final_count/args.target)*100:.1f}%")

if __name__ == "__main__":
    main()
