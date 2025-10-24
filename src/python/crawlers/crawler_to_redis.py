 #!/usr/bin/env python3
"""
Crawler Adapter: Elasticsearch → Redis Queue
Reads repos from Elasticsearch and enqueues them to Redis for processing
"""

import os
import json
import logging
import time
from typing import List, Dict
import redis
from elasticsearch import Elasticsearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlerAdapter:
    """Adapts Elasticsearch crawler output to Redis queue"""

    def __init__(self):
        # Redis connection
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True
        )

        # Elasticsearch connection
        es_url = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
        self.es = Elasticsearch([es_url])

        self.queue_name = "pipeline:repos"
        self.processed_set = "pipeline:processed:repos"

        logger.info(f"Crawler Adapter initialized")
        logger.info(f"Elasticsearch: {es_url}")
        logger.info(f"Redis: {os.getenv('REDIS_HOST', 'redis')}")

    def fetch_repos_from_elasticsearch(self, batch_size: int = 1000) -> List[Dict]:
        """Fetch repositories from Elasticsearch"""
        logger.info("Fetching repos from Elasticsearch...")

        query = {
            "query": {
                "match_all": {}
            },
            "sort": [
                {"stars": {"order": "desc"}},
                {"crawled_at": {"order": "desc"}}
            ],
            "size": batch_size
        }

        try:
            response = self.es.search(
                index="github-coding-repos",
                body=query,
                scroll='5m'
            )

            repos = []
            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']

            while hits:
                for hit in hits:
                    repos.append(hit['_source'])

                # Get next batch
                response = self.es.scroll(scroll_id=scroll_id, scroll='5m')
                hits = response['hits']['hits']

            logger.info(f"Fetched {len(repos)} repos from Elasticsearch")
            return repos

        except Exception as e:
            logger.error(f"Error fetching from Elasticsearch: {e}")
            return []

    def enqueue_repos(self, repos: List[Dict]) -> int:
        """Enqueue repos to Redis"""
        enqueued = 0

        for repo in repos:
            full_name = repo.get('full_name', '')

            # Skip if already processed
            if self.redis_client.sismember(self.processed_set, full_name):
                continue

            # Create job
            job = {
                'repo_url': repo.get('url', '').replace('https://github.com/', 'https://github.com/') + '.git',
                'full_name': full_name,
                'stars': repo.get('stars', 0),
                'forks': repo.get('forks', 0),
                'language': repo.get('language', 'Unknown'),
                'quality_score': self._calculate_quality_score(repo),
                'topics': repo.get('topics', [])
            }

            # Only enqueue if quality is good enough
            if job['quality_score'] >= 50:
                self.redis_client.rpush(self.queue_name, json.dumps(job))
                enqueued += 1

                if enqueued % 100 == 0:
                    logger.info(f"Enqueued {enqueued} repos...")

        logger.info(f"Total enqueued: {enqueued} repos")
        return enqueued

    def _calculate_quality_score(self, repo: Dict) -> int:
        """Calculate repository quality score"""
        score = 0

        # Stars
        stars = repo.get('stars', 0)
        if stars >= 100:
            score += 30
        elif stars >= 50:
            score += 20
        elif stars >= 10:
            score += 10

        # Forks
        forks = repo.get('forks', 0)
        if forks >= 20:
            score += 20
        elif forks >= 10:
            score += 15
        elif forks >= 3:
            score += 10

        # Language
        target_languages = ['Rust', 'Go', 'Python', 'TypeScript', 'JavaScript', 'Dart']
        if repo.get('language') in target_languages:
            score += 30

        # Topics (frameworks, etc.)
        topics = repo.get('topics', [])
        framework_keywords = [
            'fastapi', 'django', 'flask', 'angular', 'react', 'vue',
            'pytorch', 'tensorflow', 'tokio', 'actix', 'gin', 'fiber'
        ]
        if any(keyword in ' '.join(topics).lower() for keyword in framework_keywords):
            score += 20

        return score

    def run_continuous(self, interval_seconds: int = 3600):
        """Continuously sync repos from Elasticsearch to Redis"""
        logger.info(f"Starting continuous sync (interval: {interval_seconds}s)")

        while True:
            try:
                logger.info("Starting sync cycle...")

                # Fetch repos from Elasticsearch
                repos = self.fetch_repos_from_elasticsearch()

                # Enqueue to Redis
                if repos:
                    enqueued = self.enqueue_repos(repos)
                    logger.info(f"Sync complete: {enqueued} new repos enqueued")
                else:
                    logger.warning("No repos fetched from Elasticsearch")

                # Show queue status
                queue_len = self.redis_client.llen(self.queue_name)
                processed = self.redis_client.scard(self.processed_set)
                logger.info(f"Queue status: {queue_len} pending, {processed} processed")

                # Wait before next sync
                logger.info(f"Sleeping for {interval_seconds}s...")
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in sync cycle: {e}", exc_info=True)
                time.sleep(60)

def main():
    """Main entry point"""
    adapter = CrawlerAdapter()

    # Check environment variable for mode
    mode = os.getenv("CRAWLER_MODE", "once")

    if mode == "continuous":
        interval = int(os.getenv("SYNC_INTERVAL", "3600"))
        adapter.run_continuous(interval_seconds=interval)
    else:
        # Run once
        repos = adapter.fetch_repos_from_elasticsearch()
        if repos:
            enqueued = adapter.enqueue_repos(repos)
            logger.info(f"One-time sync complete: {enqueued} repos enqueued")
        else:
            logger.warning("No repos to enqueue")

if __name__ == "__main__":
    main()
