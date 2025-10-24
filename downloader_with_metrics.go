// Example of how to integrate metrics into downloader.go
// Add this import at the top:
// import "codelupe/pkg/metrics"

// Then add metrics calls at key points:

// In performDownload() after successful clone (around line 595):
func (rd *RepoDownloader) performDownloadWithMetrics(repo *RepoInfo, repoRecord *Repository) error {
	startTime := time.Now()

	// ... existing download logic ...

	err := rd.performDownload(repo, repoRecord)

	// Record metrics
	duration := time.Since(startTime).Seconds()
	metrics.ObserveHistogram("download_duration_seconds", duration)

	if err != nil {
		metrics.IncrCounter("repos_download_failed_total", 1)
		return err
	}

	metrics.IncrCounter("repos_downloaded_total", 1)
	metrics.ObserveHistogram("repo_size_kb", float64(repoRecord.SizeKB))
	metrics.ObserveHistogram("repo_lines_of_code", float64(repoRecord.CodeLines))

	return nil
}

// In downloadWorker() to track active workers:
func (rd *RepoDownloader) downloadWorkerWithMetrics(repos <-chan *RepoInfo, wg *sync.WaitGroup) {
	defer wg.Done()
	metrics.IncrCounter("active_download_workers", 1)
	defer metrics.IncrCounter("active_download_workers", -1)

	// ... existing worker logic ...
}

// In evaluateRepo() to track quality filtering:
func (qf *QualityFilter) evaluateRepoWithMetrics(repo *RepoInfo) (bool, int, string) {
	passed, score, reason := qf.evaluateRepo(repo)

	metrics.ObserveHistogram("repo_quality_score", float64(score))

	if passed {
		metrics.IncrCounter("repos_quality_passed_total", 1)
	} else {
		metrics.IncrCounter("repos_quality_filtered_total", 1)
	}

	return passed, score, reason
}

// In main() to expose metrics endpoint:
func mainWithMetrics() {
	// ... existing main logic ...

	// Start metrics server
	go func() {
		http.Handle("/metrics", metrics.Handler())
		log.Printf("Metrics server listening on :9091")
		if err := http.ListenAndServe(":9091", nil); err != nil {
			log.Printf("Metrics server error: %v", err)
		}
	}()

	// ... rest of main ...
}
