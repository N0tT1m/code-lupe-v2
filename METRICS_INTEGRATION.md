# Metrics Integration Guide

## Overview

The metrics package (`pkg/metrics/metrics.go`) has been created, but needs to be integrated into your services. This guide shows how to add metrics logging to each component.

## Integration Steps

### 1. Import the Metrics Package

Add to the top of your Go files:

```go
import "codelupe/pkg/metrics"
```

**Note:** You'll need to initialize a Go module first:
```bash
cd /Users/timmy/workspace/ai-apps/codelupe
go mod init codelupe
go mod tidy
```

### 2. Downloader Metrics

Add these metrics to `downloader.go`:

#### In `performDownload()` (after line 595):

```go
func (rd *RepoDownloader) performDownload(repo *RepoInfo, repoRecord *Repository) error {
	startTime := time.Now()

	// Track active downloads
	metrics.IncrCounter("downloader_active_downloads", 1)
	defer metrics.IncrCounter("downloader_active_downloads", -1)

	// ... existing download code ...

	// At the end, record metrics
	duration := time.Since(startTime).Seconds()
	metrics.ObserveHistogram("downloader_clone_duration_seconds", duration)

	if err != nil {
		metrics.IncrCounter("downloader_repos_failed_total", 1)
		return err
	}

	metrics.IncrCounter("downloader_repos_downloaded_total", 1)
	metrics.SetGauge("downloader_last_repo_size_kb", float64(repoRecord.SizeKB))
	metrics.ObserveHistogram("downloader_repo_lines_of_code", float64(repoRecord.CodeLines))

	return nil
}
```

#### In `evaluateRepo()` (after line 356):

```go
func (qf *QualityFilter) evaluateRepo(repo *RepoInfo) (bool, int, string) {
	// ... existing quality evaluation code ...

	metrics.ObserveHistogram("downloader_repo_quality_score", float64(score))

	if passed {
		metrics.IncrCounter("downloader_quality_passed_total", 1)
	} else {
		metrics.IncrCounter("downloader_quality_filtered_total", 1)
	}

	return passed, score, reason
}
```

#### In `main()` (after line 417):

```go
func main() {
	// ... existing setup code ...

	// Start metrics HTTP server
	go func() {
		http.Handle("/metrics", metrics.Handler())
		log.Printf("📊 Downloader metrics available at http://localhost:9091/metrics")
		if err := http.ListenAndServe(":9091", nil); err != nil {
			log.Printf("Metrics server error: %v", err)
		}
	}()

	// Set initial gauges
	metrics.SetGauge("downloader_max_concurrent", float64(maxConcurrent))

	// ... rest of main ...
}
```

### 3. Crawler Metrics

Add these metrics to `main.go` (crawler):

#### In `scrapeRepoDetails()` (after line 300):

```go
func (c *Crawler) scrapeRepoDetails(repo *Repository) error {
	startTime := time.Now()

	// ... existing scraping code ...

	duration := time.Since(startTime).Seconds()
	metrics.ObserveHistogram("crawler_scrape_duration_seconds", duration)

	if err != nil {
		metrics.IncrCounter("crawler_scrape_errors_total", 1)
		return err
	}

	metrics.IncrCounter("crawler_repos_scraped_total", 1)

	return nil
}
```

#### In `indexRepository()` (after line 390):

```go
func (c *Crawler) indexRepository(repo *Repository) error {
	// ... existing indexing code ...

	if err != nil {
		metrics.IncrCounter("crawler_index_errors_total", 1)
		return err
	}

	metrics.IncrCounter("crawler_repos_indexed_total", 1)
	metrics.SetGauge("crawler_last_repo_stars", float64(repo.Stars))

	return nil
}
```

#### In `main()` (add metrics server):

```go
func main() {
	log.Println("Starting GitHub Coding Repository Crawler")

	// Start metrics server
	go func() {
		http.Handle("/metrics", metrics.Handler())
		log.Printf("📊 Crawler metrics available at http://localhost:9092/metrics")
		if err := http.ListenAndServe(":9092", nil); err != nil {
			log.Printf("Metrics server error: %v", err)
		}
	}()

	// ... rest of main ...
}
```

### 4. Processor Metrics

Add these metrics to `resumable_processor.go`:

#### In `processFile()` (after line 590):

```go
func (p *ResumableProcessor) processFile(filePath, repoPath string, jobID int) *ProcessedFile {
	startTime := time.Now()

	// Track active file processing
	metrics.IncrCounter("processor_active_files", 1)
	defer metrics.IncrCounter("processor_active_files", -1)

	// ... existing processing code ...

	if processedFile == nil {
		metrics.IncrCounter("processor_files_skipped_total", 1)
		return nil
	}

	duration := time.Since(startTime).Seconds()
	metrics.ObserveHistogram("processor_file_duration_seconds", duration)
	metrics.IncrCounter("processor_files_processed_total", 1)
	metrics.ObserveHistogram("processor_file_quality_score", float64(processedFile.QualityScore))

	return processedFile
}
```

#### In `Run()` (add metrics server):

```go
func (p *ResumableProcessor) Run(ctx context.Context) error {
	fmt.Printf("🚀 Starting resumable processing pipeline\n")

	// Start metrics server
	go func() {
		http.Handle("/metrics", metrics.Handler())
		log.Printf("📊 Processor metrics available at http://localhost:9093/metrics")
		if err := http.ListenAndServe(":9093", nil); err != nil {
			log.Printf("Metrics server error: %v", err)
		}
	}()

	// Set worker count gauge
	metrics.SetGauge("processor_worker_count", float64(p.workerCount))

	// ... rest of Run ...
}
```

### 5. Trainer Metrics

The trainer already has comprehensive logging. To add Prometheus metrics:

#### In `continuous_trainer_qwen_5090.py`:

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
training_runs_total = Counter('trainer_training_runs_total', 'Total training runs')
training_duration = Histogram('trainer_training_duration_seconds', 'Training duration')
training_loss = Gauge('trainer_current_loss', 'Current training loss')
gpu_memory_usage = Gauge('trainer_gpu_memory_bytes', 'GPU memory usage')
files_trained = Counter('trainer_files_trained_total', 'Total files trained on')

# In main(), start metrics server:
def main():
    # Start Prometheus metrics server
    start_http_server(8091)  # Metrics on port 8091
    log_with_context('info', 'Metrics server started on :8091/metrics',
                     component='metrics', operation='startup')

    # ... rest of main ...

# In train() method, record metrics:
def train(self, train_dataset, eval_dataset):
    start_time = time.time()
    training_runs_total.inc()

    # ... training code ...

    duration = time.time() - start_time
    training_duration.observe(duration)
    training_loss.set(metrics.get('train_loss', 0))

    # Track GPU memory
    if torch.cuda.is_available():
        mem_bytes = torch.cuda.memory_allocated()
        gpu_memory_usage.set(mem_bytes)

    files_trained.inc(len(samples))
```

## Metrics Endpoints

Once integrated, metrics will be available at:

- **Downloader**: http://localhost:9091/metrics
- **Crawler**: http://localhost:9092/metrics
- **Processor**: http://localhost:9093/metrics
- **Trainer**: http://localhost:8091/metrics

## Prometheus Configuration

Add to `configs/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'downloader'
    static_configs:
      - targets: ['downloader:9091']
    scrape_interval: 15s

  - job_name: 'crawler'
    static_configs:
      - targets: ['crawler:9092']
    scrape_interval: 15s

  - job_name: 'processor'
    static_configs:
      - targets: ['processor:9093']
    scrape_interval: 15s

  - job_name: 'trainer'
    static_configs:
      - targets: ['trainer:8091']
    scrape_interval: 30s
```

## Grafana Dashboard Queries

### Downloader Metrics:

- Download rate: `rate(downloader_repos_downloaded_total[5m])`
- Average clone time: `rate(downloader_clone_duration_seconds_sum[5m]) / rate(downloader_clone_duration_seconds_count[5m])`
- Filter rate: `rate(downloader_quality_filtered_total[5m])`
- Active downloads: `downloader_active_downloads`

### Crawler Metrics:

- Index rate: `rate(crawler_repos_indexed_total[5m])`
- Scrape errors: `rate(crawler_scrape_errors_total[5m])`
- Average scrape time: `rate(crawler_scrape_duration_seconds_sum[5m]) / rate(crawler_scrape_duration_seconds_count[5m])`

### Processor Metrics:

- Processing rate: `rate(processor_files_processed_total[5m])`
- Active workers: `processor_active_files`
- Average quality score: `avg(processor_file_quality_score)`
- Files skipped: `rate(processor_files_skipped_total[5m])`

### Trainer Metrics:

- Training runs: `trainer_training_runs_total`
- GPU memory usage: `trainer_gpu_memory_bytes / 1024 / 1024 / 1024` (in GB)
- Training duration: `trainer_training_duration_seconds`
- Current loss: `trainer_current_loss`

## Quick Start

1. **Initialize Go module:**
   ```bash
   cd /Users/timmy/workspace/ai-apps/codelupe
   go mod init codelupe
   go mod tidy
   ```

2. **Add metrics to one service** (e.g., downloader):
   - Add import: `import "codelupe/pkg/metrics"`
   - Add metrics calls as shown above
   - Compile: `go build -o downloader downloader.go`

3. **Run and test:**
   ```bash
   ./downloader download ./repos 3 &
   curl http://localhost:9091/metrics
   ```

4. **Repeat for other services**

## Example Output

When you curl the metrics endpoint, you'll see:

```
# HELP Metrics
# Last updated: 2024-01-15T10:30:00Z

# Counters
downloader_repos_downloaded_total 42
downloader_repos_failed_total 3
downloader_quality_passed_total 45
downloader_quality_filtered_total 12

# Gauges
downloader_active_downloads 2.00
downloader_max_concurrent 3.00
downloader_last_repo_size_kb 1024.00

# Histograms (count)
downloader_clone_duration_seconds_count 42
downloader_repo_quality_score_count 57
```

## Next Steps

1. Add metrics to downloader first (highest impact)
2. Test with Prometheus locally
3. Add to other services
4. Create Grafana dashboards
5. Set up alerts for critical metrics

The infrastructure is ready - you just need to add the metrics calls at the key points shown above!
