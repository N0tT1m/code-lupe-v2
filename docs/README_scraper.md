# Ultimate GitHub Scraper

A high-performance, multi-token GitHub repository scraper built in Go designed to maximize hardware resources and create the world's largest quality coding dataset.

## Features

- **Multi-Token Support**: Plug-and-play token system - add 6 tokens, get 6 workers scraping 5000 repos/hour each
- **Intelligent Rate Limiting**: Per-token rate limiting with automatic token rotation and failure recovery  
- **Quality Filtering**: Advanced quality scoring system focusing on stars, activity, and code health
- **Storage Management**: Automatic failover from \\\\192.168.1.66\plex3\codelupe to network backup when storage fills up
- **Hardware Optimization**: Maximizes CPU/memory usage with configurable worker pools
- **Language Targeting**: Focuses on Python, Go, Dart/Flutter, TypeScript, Angular, SQL, AI/ML, and more

## Quick Start

### Prerequisites

- Go 1.21+
- Git installed and in PATH
- Access to \\\\192.168.1.66\plex3\codelupe and network storage
- GitHub Personal Access Tokens

### Installation

1. **Clone and setup**:
```bash
cd /path/to/codelupe
go mod tidy
```

2. **Configure your tokens**:
   - Edit `config.json` and replace the placeholder tokens with your actual GitHub Personal Access Tokens
   - Or set environment variable: `export GITHUB_TOKENS="token1,token2,token3,token4,token5,token6"`

3. **Verify storage access**:
   - Ensure \\\\192.168.1.66\plex3\codelupe\repos directory exists and is writable
   - Verify network path \\\\192.168.1.66\plex3\codebase\repos is accessible

### Running

```bash
# Using config file tokens
go run ultimate_github_scraper.go

# Or using environment variable
GITHUB_TOKENS="ghp_token1,ghp_token2,ghp_token3" go run ultimate_github_scraper.go
```

## Configuration

### Token Management
- **Plug-and-Play**: Add any number of tokens to scale workers automatically
- **Rate Limiting**: Each token respects GitHub's 5000 requests/hour limit
- **Failure Recovery**: Tokens are automatically disabled/re-enabled based on success rates

### Storage Strategy
1. **Primary**: \\\\192.168.1.66\plex3\codelupe\repos (14TB capacity)
2. **Backup**: \\\\192.168.1.66\plex3\codebase\repos (10TB capacity)  
3. **Auto-Failover**: Switches to backup when primary has <100GB free
4. **Organization**: Repos stored by language: `\\\\192.168.1.66\plex3\codelupe\repos\Python\owner\repo`

### Quality Scoring (0-100 points)
- **Stars** (0-40 pts): Higher stars = higher score
- **Fork Ratio** (0-20 pts): Good fork-to-star ratio indicates quality
- **Recent Activity** (0-20 pts): Recently updated repositories preferred
- **Size Optimization** (0-10 pts): Medium-sized repos (1KB-50MB) preferred
- **Topics/Tags** (0-10 pts): Well-tagged repositories score higher

### Performance Tuning

**For Maximum Throughput**:
```json
{
  "performance": {
    "workers_per_token": 6,
    "repos_per_hour_per_token": 5000,
    "max_requests_per_second": 2,
    "concurrent_clones": 12
  }
}
```

**For System Stability**:
```json
{
  "performance": {
    "workers_per_token": 2,
    "repos_per_hour_per_token": 3000,
    "max_requests_per_second": 1,
    "concurrent_clones": 4
  }
}
```

## Architecture

### Multi-Worker Design
- **Token Pool**: Smart token rotation with rate limit tracking
- **Worker Pool**: Configurable workers per token (default: 4 workers × 6 tokens = 24 total workers)
- **Search Strategy**: 100+ diverse queries targeting high-quality repositories
- **Clone Strategy**: Parallel shallow cloning of repositories scoring >70 quality points

### Database Schema
```sql
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY,
    github_id INTEGER UNIQUE,
    name TEXT,
    full_name TEXT,
    clone_url TEXT,
    language TEXT,
    stars INTEGER,
    forks INTEGER,
    size_kb INTEGER,
    pushed_at TEXT,
    description TEXT,
    topics TEXT,
    quality_score REAL,
    cloned BOOLEAN DEFAULT FALSE,
    clone_path TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Search Queries
The scraper uses sophisticated search strategies:
- **Language-specific**: `language:python stars:>100 pushed:>2023-01-01`
- **Technology-focused**: `topic:machine-learning stars:>50`
- **Quality-filtered**: `stars:>1000 forks:>100 pushed:>2023-01-01`
- **Size-optimized**: `size:<50000 stars:>50 pushed:>2023-06-01`

## Monitoring

### Real-time Stats (Every 5 minutes)
- Total repositories scraped
- Repositories per hour rate
- Total repositories cloned
- Error count and rates
- Active token count
- Storage space remaining

### Example Output
```
=== STATS ===
Runtime: 2h15m30s
Scraped: 67,500 repos (30,000.0/hour)
Cloned: 12,750 repos
Errors: 45
Active tokens: 6
Storage - Primary: 2,450.3GB, Backup: 8,921.7GB
```

## Scaling

### Adding More Tokens
Simply add tokens to `config.json` or the `GITHUB_TOKENS` environment variable:
```bash
export GITHUB_TOKENS="token1,token2,token3,token4,token5,token6,token7,token8"
```
The system automatically scales to use all available tokens.

### Hardware Recommendations
- **CPU**: High core count (16+ cores recommended)
- **RAM**: 32GB+ for optimal performance
- **Storage**: Fast SSD for database, high-capacity HDD for repositories
- **Network**: Stable high-speed connection for GitHub API and cloning

## Troubleshooting

### Common Issues

**Token Rate Limiting**:
- Tokens automatically rotate and respect rate limits
- Check token validity at https://github.com/settings/tokens

**Storage Issues**:
- Verify \\\\192.168.1.66\plex3\codelupe is mounted and writable
- Check network path accessibility
- Monitor disk space - scraper stops when both drives are full

**Performance Issues**:
- Reduce `workers_per_token` if system becomes unresponsive
- Lower `concurrent_clones` if network/disk I/O is saturated
- Increase `max_requests_per_second` carefully to avoid rate limiting

### Logs
Monitor the console output for:
- Worker startup/shutdown messages
- API rate limit warnings
- Clone failures
- Storage switching events

## Target Dataset Quality

This scraper is designed to create a premium dataset by:
- **Quality Focus**: Only repositories with 30+ quality score are saved
- **Language Diversity**: Balanced collection across target programming languages
- **Recency**: Prioritizes recently updated repositories
- **Size Optimization**: Avoids both toy projects and monolithic repositories
- **Technology Coverage**: Includes modern frameworks, databases, and AI/ML projects

Expected to compete with large model training datasets through superior quality over quantity.